"""Test and scan requests (a request of kind "test").

The doctor lists the tests; staff check and send each one as its own order:
draft -> requested -> accepted | rejected -> scheduled -> done -> reported.
The order carries the patient's identity details. If the laboratory or radiology department
has not confirmed this patient before, they match their record or register the patient as
new when the order arrives. Reports come back with findings and, for scans, the images.
"""
from __future__ import annotations

import base64
import re
from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from refcommon.auth import Principal
from refcommon.db import utcnow
from refcommon.exchange import DiagnosticOrder
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import department_name, institution_name, settings
from ..db import get_db
from ..models import DiagnosticRequest, EvidenceItem, Outbox, Referral
from ..notifications import notify_doctor, notify_staff
from ..referrals.router import DiagnosticIn, add_diagnostic, validate_diagnostic
from ..referrals.state import event, transition
from ..security import DOCTOR, STAFF, audit, error, get_principal, load_referral
from ..sending.packages import intake_details
from ..serializers import diagnostic_out
from ..tasks import enqueue

router = APIRouter(tags=["tests and scans"])
OPEN_ORDER = ("requested", "accepted", "scheduled", "done")


def _load(db: Session, dx_id: int, principal: Principal, action: str, roles=(STAFF, DOCTOR)):
    dx = db.get(DiagnosticRequest, dx_id)
    if dx is None:
        raise error(404, "not_found", "Request not found")
    r = load_referral(db, dx.referral_id, principal, action, roles=roles)
    return dx, r


def _history(dx: DiagnosticRequest, status: str, by: str, **extra) -> None:
    dx.history = list(dx.history or []) + [{"status": status, "by": by, "at": utcnow().isoformat(), **extra}]


def _orders(db: Session, r: Referral) -> list[DiagnosticRequest]:
    return list(db.scalars(select(DiagnosticRequest).where(DiagnosticRequest.referral_id == r.id,
                                                            DiagnosticRequest.status != "cancelled")))


@router.get("/referrals/{referral_id}/diagnostics")
def list_requests(referral_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    r = load_referral(db, referral_id, principal, "view")
    return [diagnostic_out(d) for d in db.scalars(select(DiagnosticRequest).where(DiagnosticRequest.referral_id == r.id)
                                                  .order_by(DiagnosticRequest.id))]


@router.post("/referrals/{referral_id}/diagnostics", status_code=201)
def add_request(referral_id: int, body: DiagnosticIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """The doctor adds a test to their test request (before it is sent)."""
    r = load_referral(db, referral_id, principal, "add_diagnostic", roles=(DOCTOR,))
    if r.kind != "test":
        raise error(409, "not_a_test_request", "Request tests and scans separately (New request, then Test or scan)")
    if r.status not in ("draft", "requested"):
        raise error(409, "already_sent", "These tests were already sent; make a new test request")
    validate_diagnostic(body, principal)
    dx = add_diagnostic(db, r, body, principal)
    audit(db, principal, "diagnostic.add", "diagnostic_request", dx.reference, "success", r.id, {"test": dx.test})
    db.commit()
    return diagnostic_out(dx)


@router.post("/diagnostics/{dx_id}/send")
def send_request(dx_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """Staff check the request and send the order, with the patient's identity details."""
    dx, r = _load(db, dx_id, principal, "send_diagnostic", roles=(STAFF,))
    if r.status != "requested" and r.status != "submitted":
        raise error(409, "not_submitted", "The doctor has not submitted this request yet")
    if dx.status != "draft":
        raise error(409, "already_sent", f"This request is already {dx.status}")
    patient = intake_details(db, r, dx.destination_institution, principal,
                             f"{dx.test} ({r.reference}) at {department_name(dx.destination_department)}")
    dx.local_patient_id = patient["local_patient_id"]
    now = utcnow()
    order = DiagnosticOrder(order_key=f"{r.source_institution}:{dx.reference}", order_ref=dx.reference,
                            referral_id=r.reference, sender_institution=r.source_institution,
                            destination_institution=dx.destination_institution,
                            destination_department=dx.destination_department, category=dx.category, test=dx.test,
                            body_area=dx.body_area, clinical_question=dx.clinical_question, urgency=dx.urgency,
                            patient={"name": r.patient_name, "birth_date": r.patient_birth_date, "sex": r.patient_sex,
                                     **patient},
                            requested_by=dx.requested_by, requested_at=now)
    db.add(Outbox(referral_id=r.id, kind="deliver_order", target_institution=dx.destination_institution,
                  message_key=order.order_key, payload=order.model_dump(mode="json")))
    dx.status, dx.sent_by, dx.sent_at = "requested", principal.display_name, now
    _history(dx, "requested", principal.display_name)
    event(db, r, "diagnostic_sent", principal.display_name, principal.institution_id,
          {"reference": dx.reference, "test": dx.test, "to": dx.destination_institution})
    audit(db, principal, "diagnostic.send", "diagnostic_request", dx.reference, "success", r.id)
    if r.status == "requested" and all(d.status != "draft" for d in _orders(db, r)):
        transition(db, r, "submitted", principal.display_name, principal)
        notify_doctor(db, r, "tests_sent", f"{r.reference}: tests sent", r.patient_name, tab="tests")
    db.commit()
    enqueue("deliver_outbox")
    return diagnostic_out(dx)


class CancelIn(BaseModel):
    reason: str = Field(min_length=3)


@router.post("/diagnostics/{dx_id}/cancel")
def cancel_request(dx_id: int, body: CancelIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """The doctor withdraws a test that has not been sent (or was rejected)."""
    dx, r = _load(db, dx_id, principal, "cancel_diagnostic", roles=(DOCTOR,))
    if dx.status not in ("draft", "rejected"):
        raise error(409, "cannot_cancel", "Only a request that has not been sent (or was rejected) can be cancelled here")
    dx.status = "cancelled"
    _history(dx, "cancelled", principal.display_name, reason=body.reason)
    audit(db, principal, "diagnostic.cancel", "diagnostic_request", dx.reference, "success", r.id, {"reason": body.reason})
    _check_complete(db, r, principal.display_name, principal.institution_id)
    db.commit()
    return diagnostic_out(dx)


@router.post("/diagnostics/{dx_id}/seen")
def mark_seen(dx_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """The requesting doctor records that they have seen the result."""
    dx, r = _load(db, dx_id, principal, "see_result", roles=(DOCTOR,))
    if dx.status != "reported":
        raise error(409, "no_result", "There is no result yet")
    if dx.seen_at is None:
        dx.seen_by, dx.seen_at = principal.display_name, utcnow()
        audit(db, principal, "diagnostic.result_seen", "diagnostic_request", dx.reference, "success", r.id)
        if all(d.seen_at or d.status in ("rejected",) for d in _orders(db, r)):
            notify_staff(db, r, "results_seen", f"{r.reference}: doctor has seen the results",
                         "Tell the patient and close the request.", tab="tests")
        db.commit()
    return diagnostic_out(dx)


@router.get("/diagnostics/{dx_id}/attachments/{n}")
def attachment(dx_id: int, n: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """An image or file returned with the report."""
    dx, r = _load(db, dx_id, principal, "view_result")
    item = next((a for a in dx.attachments or [] if a.get("n") == n), None)
    if item is None:
        raise error(404, "not_found", "Attachment not found")
    audit(db, principal, "diagnostic.attachment_view", "diagnostic_request", f"{dx.reference}#{n}", "success", r.id)
    db.commit()
    return FileResponse(settings.storage_root / item["storage_key"], media_type=item["content_type"],
                        filename=item["filename"])


# ------------------------------------------------------------------ applied from inbound events
def _store_attachments(dx: DiagnosticRequest, items: list[dict]) -> list[dict]:
    """Attachments arrive base64-encoded inside the report event; they are written once."""
    out = []
    folder = settings.storage_root / "results" / dx.reference
    folder.mkdir(parents=True, exist_ok=True)
    for i, a in enumerate(items, start=1):
        name = re.sub(r"[^A-Za-z0-9._-]", "_", a.get("filename") or f"attachment-{i}")[:80]
        path = folder / f"{i}-{name}"
        path.write_bytes(base64.b64decode(a["data"]))
        out.append({"n": i, "filename": name, "content_type": a.get("content_type") or "application/octet-stream",
                    "size": path.stat().st_size, "storage_key": str(path.relative_to(settings.storage_root))})
    return out


def _check_complete(db: Session, r: Referral, actor: str, institution: str | None) -> None:
    """A test request has its results once no order is still waiting to be sent or done."""
    orders = _orders(db, r)
    if r.status == "submitted" and orders and all(d.status in ("reported", "rejected") for d in orders):
        transition(db, r, "response_returned", actor, None, {"results": len([d for d in orders if d.status == "reported"])},
                   institution=institution)
        notify_doctor(db, r, "results_ready", f"All results received: {r.reference}", r.patient_name, tab="tests")


def apply_order_event(db: Session, r: Referral, dx: DiagnosticRequest, etype: str, data: dict, actor: str,
                      institution: str) -> None:
    status = {"order_accepted": "accepted", "order_rejected": "rejected", "order_scheduled": "scheduled",
              "order_done": "done", "order_reported": "reported"}[etype]
    dx.status = status
    extra = {}
    if data.get("local_patient_id"):
        dx.local_patient_id = data["local_patient_id"]
    if status == "rejected":
        dx.reject_reason = data.get("reason")
        extra["reason"] = dx.reject_reason
        for fn in (notify_doctor, notify_staff):
            fn(db, r, "diagnostic_rejected", f"{dx.test} was not accepted",
               f"{institution_name(institution)}: {dx.reject_reason}", tab="tests")
    if status == "scheduled":
        dx.scheduled_for = datetime.fromisoformat(data["scheduled_for"]) if data.get("scheduled_for") else None
        extra["scheduled_for"] = data.get("scheduled_for")
    if status == "reported":
        dx.report = {"findings": data.get("findings"), "impression": data.get("impression"),
                     "report_text": data.get("report_text"), "values": data.get("values", []),
                     "reported_by": data.get("reported_by"), "reported_at": data.get("reported_at")}
        if data.get("attachments") and not dx.attachments:
            dx.attachments = _store_attachments(dx, data["attachments"])
        extra["attachments"] = len(dx.attachments or [])
        _add_result_evidence(db, r, dx, institution)
        notify_doctor(db, r, "diagnostic_reported", f"Result ready: {dx.test} ({r.patient_name})",
                      f"From {institution_name(institution)}.", tab="tests")
    _history(dx, status, actor, **extra)
    event(db, r, f"diagnostic_{status}", actor, institution, {"reference": dx.reference, "test": dx.test, **extra})
    if status in ("reported", "rejected"):
        db.flush()
        _check_complete(db, r, actor, institution)


def _add_result_evidence(db: Session, r: Referral, dx: DiagnosticRequest, institution: str) -> None:
    rep = dx.report or {}
    if dx.category == "laboratory" and rep.get("values"):
        for i, v in enumerate(rep["values"]):
            db.add(EvidenceItem(
                referral_id=r.id, patient_institution=institution, patient_local_id=dx.local_patient_id or "",
                origin="source", source_institution=institution, source_record_type="DiagnosticResult",
                source_record_id=f"{dx.reference}-{i + 1}", source_record_version="1", category="lab",
                display=f"{v.get('test')}: {v.get('value')} {v.get('unit') or ''}".strip()
                + (f", reference {v['reference']}" if v.get("reference") else "") + (f", {v['flag']}" if v.get("flag") else ""),
                original={"test": v.get("test"), "value_text": v.get("value"), "unit": v.get("unit"),
                          "reference_range": v.get("reference"), "panel": dx.test, "order": dx.reference},
                current={}, clinical_time=utcnow(), review_state="imported", verification_status="source_record",
                selected=True))
    else:
        text = rep.get("impression") or rep.get("findings") or rep.get("report_text") or ""
        db.add(EvidenceItem(
            referral_id=r.id, patient_institution=institution, patient_local_id=dx.local_patient_id or "",
            origin="source", source_institution=institution, source_record_type="DiagnosticResult",
            source_record_id=dx.reference, source_record_version="1", category="imaging",
            display=f"{dx.test}: {text}",
            original={"study": dx.test, "findings": rep.get("findings"), "impression": rep.get("impression"),
                      "reporter": rep.get("reported_by"), "order": dx.reference,
                      "attachments": len(dx.attachments or [])},
            current={}, clinical_time=utcnow(), review_state="imported", verification_status="source_record",
            selected=True))
