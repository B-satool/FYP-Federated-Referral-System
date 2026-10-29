"""Patient view: a patient sees the referrals and test requests made for them.

A patient account belongs to no institution. Its CNIC comes only from the verified token (an
administrator sets it in Keycloak; the patient cannot change it). The platform answers with referral
status and routing only. The patient's medical history is not served from here: the patient's device
asks each institution directly (GET /patient-access/records on the institution's own API), so the
platform never holds a copy of it (decision 2026-10-29, patient view).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from refcommon.auth import Principal
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import INSTITUTIONS, SOURCES, URGENCIES, department_name, institution_name
from .db import get_db
from .models import DiagnosticRequest, Referral, ReferralEvent
from .security import audit, deny, get_principal

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
        elif e.event_type == "completed_by_receiver":
            timeline.append({"at": _when(e.created_at), "text": f"{to} marked its part as complete."})
    statuses = TEST_STATUS if r.kind == "test" else PATIENT_STATUS
    return {
        "reference": r.reference, "kind": r.kind,
        "status": r.status, "status_label": statuses.get(r.status, r.status),
        "open": r.status not in ("closed", "declined", "cancelled"),
        "from": {"institution": institution_name(r.source_institution), "department": department_name(r.source_department),
                 "doctor": r.requesting_doctor_name},
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


@router.get("/places")
def places(principal: Principal = Depends(get_principal)):
    """The institutions on the network. The patient's device asks each one directly whether it holds
    records for them; the platform does not keep that list."""
    require_patient(principal, "patient.places")
    return [{"institution_id": k, "name": INSTITUTIONS[k]["name"], "kind": INSTITUTIONS[k]["kind"]}
            for k in sorted(SOURCES, key=lambda k: INSTITUTIONS[k]["name"])]
