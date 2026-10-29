"""Patient view: a patient sees the referrals and test requests made for them.

A patient account belongs to no institution. Its CNIC comes only from the verified token (an
administrator sets it in Keycloak; the patient cannot change it). The platform answers with referral
status and routing only. The patient's medical history is not served from here: the patient's device
asks each institution directly (GET /patient-access/records on the institution's own API), so the
platform never holds a copy of it (decision 2026-10-29, patient view).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from refcommon.auth import Principal
from refcommon.db import utcnow
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import INSTITUTIONS, SOURCES, URGENCIES, department_name, institution_name
from .db import get_db
from .models import DiagnosticRequest, Referral, ReferralEvent
from .security import audit, deny, error, get_principal

router = APIRouter(prefix="/patient-access", tags=["patient access"])
NO_STORE = {"Cache-Control": "no-store", "Pragma": "no-cache"}

# What each status means to the patient (staff labels describe work; these describe where things stand)
REFERRAL_STEPS = {
    "requested": "Your doctor asked for this referral. Their clinic is preparing it.",
    "submitted": "Sent to {to}.",
    "acknowledged": "{to} received it.",
    "accepted": "{to} accepted it.",
    "response_returned": "{to} replied to your doctor.",
    "followup_pending": "Your clinic is following up.",
    "closed": "Closed.",
    "declined": "{to} declined it.",
    "cancelled": "Withdrawn by your doctor.",
}
TEST_STEPS = {**REFERRAL_STEPS, "requested": "Your doctor asked for these tests. Their clinic is preparing the order.",
              "submitted": "Sent to the laboratory or scan department.",
              "response_returned": "Results are back with your doctor."}
PATIENT_STATUS = {"requested": "Being prepared", "submitted": "Sent", "acknowledged": "Received", "accepted": "Accepted",
                  "response_returned": "Replied", "followup_pending": "Follow-up", "closed": "Closed",
                  "declined": "Declined", "cancelled": "Withdrawn"}
TEST_STATUS = {**PATIENT_STATUS, "submitted": "Sent to the lab", "response_returned": "Results back"}
ORDER_STATUS = {"draft": "Being prepared", "requested": "Sent", "accepted": "Accepted", "scheduled": "Booked",
                "done": "Done, report pending", "reported": "Result reported", "rejected": "Not accepted"}


def require_patient(principal: Principal, action: str) -> str:
    """The signed-in patient's CNIC; anyone else is refused (and the refusal audited)."""
    if "patient" not in principal.roles or principal.institution_id is not None:
        raise deny(principal, action, "patient", "self", "Only a patient account can use the patient view")
    if not principal.cnic or len(principal.cnic) != 13:
        raise deny(principal, action, "patient", "self", "This patient account has no CNIC, so nothing can be matched to it")
    return principal.cnic


def _cnic(value: str | None) -> str:
    return "".join(ch for ch in (value or "") if ch.isdigit())


def _when(dt) -> str | None:
    return dt.isoformat() if dt else None


def _referral(r: Referral, events: list[ReferralEvent], orders: list[DiagnosticRequest]) -> dict:
    to = institution_name(r.destination_institution) or "the receiving hospital"
    steps = TEST_STEPS if r.kind == "test" else REFERRAL_STEPS
    timeline = [{"at": _when(r.requested_at or r.created_at), "text": steps["requested"].format(to=to)}]
    for e in events:
        if e.event_type == "status_change" and e.to_status in steps and e.to_status != "requested":
            text = steps[e.to_status].format(to=to)
            if e.to_status == "declined" and r.decline_reason:
                text += f" Reason given: {r.decline_reason}"
            timeline.append({"at": _when(e.created_at), "text": text})
        elif e.event_type == "patient_informed":
            timeline.append({"at": _when(e.created_at), "text": "Your clinic told you about this referral."})
        elif e.event_type in ("completed_by_receiver", "closed_by_specialist"):
            timeline.append({"at": _when(e.created_at), "text": f"{to} closed the referral."})
        elif e.event_type == "patient_notice":
            d = e.detail or {}
            timeline.append({"at": _when(e.created_at), "text": f"{d.get('title', '')}. {d.get('body', '')}".strip(),
                             "notice": d.get("kind")})
    statuses = TEST_STATUS if r.kind == "test" else PATIENT_STATUS
    return {
        "reference": r.reference, "kind": r.kind,
        "status": r.status, "status_label": statuses.get(r.status, r.status),
        "open": r.status not in ("closed", "declined", "cancelled"),
        "from": {"institution": institution_name(r.source_institution), "department": department_name(r.source_department),
                 "doctor": r.requesting_doctor_name,
                 # the app looks up this doctor's hospital-signed key to encrypt papers the patient adds
                 "doctor_id": r.requesting_doctor_id},
        "to": None if r.kind == "test" else {"institution": to, "department": department_name(r.destination_department),
                                             "doctor": r.destination_doctor},
        "urgency": URGENCIES.get(r.urgency, {}).get("label", r.urgency),
        "urgency_detail": URGENCIES.get(r.urgency, {}).get("detail"),
        # the patient's own referral: why they are being referred and for what procedure
        "reason": r.reason, "planned_procedure": r.planned_procedure if r.procedure_status == "planned" else None,
        "tests": [{"test": d.test, "where": f"{institution_name(d.destination_institution)}, "
                                            f"{department_name(d.destination_department)}",
                   "status": d.status, "status_label": ORDER_STATUS.get(d.status, d.status),
                   "scheduled_for": _when(d.scheduled_for)} for d in orders if d.status != "draft"],
        "created_at": _when(r.requested_at or r.created_at), "closed_at": _when(r.closed_at),
        # the patient's own copy (spec v4 11.3): a signed version exists to save; purged means only the phone has it
        "copy_available": r.kind == "referral" and r.packet_reviewed_at is not None and r.working_set_purged_at is None,
        "purged_at": _when(r.working_set_purged_at),
        "timeline": timeline,
    }


@router.get("/referrals")
def my_referrals(db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """Every referral and test request for this patient, at any institution, newest first. Drafts the
    doctor has not submitted are left out."""
    cnic = require_patient(principal, "patient.referrals")
    rows = [r for r in db.scalars(select(Referral).where(Referral.patient_cnic.is_not(None), Referral.status != "draft")
                                  .order_by(Referral.created_at.desc()))
            if _cnic(r.patient_cnic) == cnic]
    ids = [r.id for r in rows]
    events: dict[int, list[ReferralEvent]] = {i: [] for i in ids}
    orders: dict[int, list[DiagnosticRequest]] = {i: [] for i in ids}
    if ids:
        for e in db.scalars(select(ReferralEvent).where(ReferralEvent.referral_id.in_(ids)).order_by(ReferralEvent.id)):
            events[e.referral_id].append(e)
        for d in db.scalars(select(DiagnosticRequest).where(DiagnosticRequest.referral_id.in_(ids))
                            .order_by(DiagnosticRequest.id)):
            orders[d.referral_id].append(d)
    audit(db, principal, "patient.referrals", "patient", "self", detail={"count": len(rows)})
    db.commit()
    return JSONResponse([_referral(r, events[r.id], orders[r.id]) for r in rows], headers=NO_STORE)


def _own_referral(db: Session, principal: Principal, reference: str, action: str) -> Referral:
    cnic = require_patient(principal, action)
    r = db.scalars(select(Referral).where(Referral.reference == reference)).first()
    if r is None or _cnic(r.patient_cnic) != cnic or r.status == "draft":
        raise deny(principal, action, "referral", reference, "Not your referral")
    return r


@router.get("/referrals/{reference}/copy")
def my_copy(reference: str, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """The patient's own copy (spec v4 11.3): the signed manifest, the items, and the data keys wrapped to the patient's
    key. The app decrypts it on the phone, checks it against the signature and keeps it there, even after the
    referral is purged here. Items the doctor did not share with the patient have no wrap for them."""
    from .records.router import package_bundle

    r = _own_referral(db, principal, reference, "patient.copy")
    if r.working_set_purged_at is not None:
        return JSONResponse({"purged": True, "purged_at": _when(r.working_set_purged_at),
                             "note": "Purged from the platform. Your saved copy on this phone is the only one."}, status_code=410,
                            headers=NO_STORE)
    out = package_bundle(db, r, "patient", {f"patient:{principal.subject}"})
    audit(db, principal, "patient.copy", "referral", r.reference, detail={"version": out["version"], "items": len(out["items"]),
                                                                         "wraps": len(out["wraps"])})
    db.commit()
    return JSONResponse(jsonable_encoder(out), headers=NO_STORE)


class PatientBatchIn(BaseModel):
    batch_id: str
    items: list[dict]
    wraps: list[dict]


@router.post("/referrals/{reference}/papers", status_code=201)
def add_papers(reference: str, body: PatientBatchIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """Papers the patient adds in the app (spec v4 step 2, 10): encrypted on the phone to the referring doctor's key and
    the patient's own key. The platform checks only the shape; staff see "Patient-provided document" and a date."""
    from .keys.router import current_entry, patient_entry_for_cnic
    from .records.requests import store_batch
    from .referrals.state import TERMINAL

    r = _own_referral(db, principal, reference, "patient.papers")
    if r.status in TERMINAL or r.working_set_purged_at is not None:
        raise error(409, "not_open", "This referral no longer accepts papers")
    if not body.batch_id.startswith("pat-") or len(body.batch_id) > 60 or not 1 <= len(body.items) <= 10:
        raise error(422, "invalid_batch", "A batch from the patient's app has an id starting 'pat-' and 1 to 10 items")
    doctor = current_entry(db, r.requesting_doctor_id or "")
    me = patient_entry_for_cnic(db, r.patient_cnic or "")
    allowed = {}
    if doctor:
        allowed[doctor.enc_key_id] = ("doctor", doctor.subject_id)
    if me and me.subject_id == f"patient:{principal.subject}":
        allowed[me.enc_key_id] = ("patient", me.subject_id)
    for w in body.wraps:
        who = allowed.get(w.get("recipient_key_id", ""))
        if who is None:
            raise error(422, "invalid_recipient", "Papers are encrypted only to the referring doctor's key and your own")
        w["recipient_type"], w["recipient_subject"] = who
    if not any(w["recipient_type"] == "doctor" for w in body.wraps):
        raise error(422, "no_doctor_wrap", "Encrypt the paper to the referring doctor's key so they can read it")
    if sum(len(str(it.get("sealed", ""))) for it in body.items) > 25 * 1024 * 1024:
        raise error(413, "too_large", "At most 25 MB")
    for it in body.items:
        t = it.get("title") or {}
        if not str(t.get("item_id", "")).startswith(f"{body.batch_id}:") or "sealed" not in it:
            raise error(422, "invalid_item", "Each item needs an id inside its batch, a title and ciphertext")
        # the title is fixed here: the patient's own label could say what the paper is about
        it["title"] = {"item_id": t["item_id"], "kind": "scan" if t.get("kind") == "scan" else "note",
                       "category": "scan" if t.get("kind") == "scan" else "scan_reading",
                       "label": "Patient-provided document", "date": _when(utcnow())[:10],
                       "source_institution": None}
    b = store_batch(db, r, {"batch_id": body.batch_id, "items": body.items, "wraps": body.wraps}, origin="patient",
                    source=None, created_by="patient")
    from .notifications import notify_doctor
    from .referrals.state import event

    event(db, r, "patient_added_papers", "patient", None, {"batch": b.batch_id, "items": len(body.items)})
    notify_doctor(db, r, "patient_papers", f"{r.reference}: the patient added papers",
                  "Open the Papers step to read them on your device.", tab="papers")
    audit(db, principal, "patient.papers", "referral", r.reference, detail={"batch": b.batch_id, "items": len(body.items)})
    db.commit()
    return {"batch_id": b.batch_id, "items": len(body.items)}


@router.get("/places")
def places(principal: Principal = Depends(get_principal)):
    """The institutions on the network. The patient's device asks each one directly whether it holds
    records for them; the platform does not keep that list."""
    require_patient(principal, "patient.places")
    return [{"institution_id": k, "name": INSTITUTIONS[k]["name"], "kind": INSTITUTIONS[k]["kind"]}
            for k in sorted(SOURCES, key=lambda k: INSTITUTIONS[k]["name"])]
