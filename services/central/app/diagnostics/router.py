"""Test, scan and equipment requests sent alongside a referral.

Each request is its own order with its own status:
draft -> requested -> accepted | rejected -> scheduled -> done -> reported.
It can finish before the specialist has reviewed the referral. The laboratory or
imaging department must also confirm the patient (patient link) before it accepts.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from refcommon.auth import Principal
from refcommon.db import utcnow
from refcommon.exchange import DiagnosticOrder, ResultForward
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import institution_name
from ..db import get_db
from ..identity.links import verified_counterparts
from ..identity.router import create_request
from ..models import DiagnosticRequest, EvidenceItem, Outbox, Referral
from ..notifications import notify_doctor, notify_staff
from ..referrals.router import DiagnosticIn, add_diagnostic, validate_diagnostic
from ..referrals.state import TERMINAL, event
from ..security import DOCTOR, audit, error, get_principal, load_referral
from ..serializers import diagnostic_out
from ..tasks import enqueue

router = APIRouter(tags=["tests and scans"])


def _load(db: Session, dx_id: int, principal: Principal, action: str, roles=("clinic_staff", "clinician")):
    dx = db.get(DiagnosticRequest, dx_id)
    if dx is None:
        raise error(404, "not_found", "Request not found")
    r = load_referral(db, dx.referral_id, principal, action, roles=roles)
    return dx, r


def _history(dx: DiagnosticRequest, status: str, by: str, **extra) -> None:
    dx.history = list(dx.history or []) + [{"status": status, "by": by, "at": utcnow().isoformat(), **extra}]


@router.get("/referrals/{referral_id}/diagnostics")
def list_requests(referral_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    r = load_referral(db, referral_id, principal, "view")
    return [diagnostic_out(d) for d in db.scalars(select(DiagnosticRequest).where(DiagnosticRequest.referral_id == r.id)
                                                  .order_by(DiagnosticRequest.id))]


@router.post("/referrals/{referral_id}/diagnostics", status_code=201)
def add_request(referral_id: int, body: DiagnosticIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    r = load_referral(db, referral_id, principal, "add_diagnostic")
    if r.status in TERMINAL:
        raise error(409, "referral_closed", "This referral is closed")
    validate_diagnostic(body)
    dx = add_diagnostic(db, r, body, principal)
    audit(db, principal, "diagnostic.add", "diagnostic_request", dx.reference, "success", r.id, {"test": dx.test})
    db.commit()
    return diagnostic_out(dx)


def _patient_id_at(db: Session, r: Referral, institution: str) -> str | None:
    if institution == r.patient_institution:
        return r.patient_local_id
    linked = verified_counterparts(db, r.patient_institution, r.patient_local_id)
    return linked.get(institution, (None, None))[0]


@router.post("/diagnostics/{dx_id}/send")
def send_request(dx_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """Staff send the order. The destination must have confirmed the patient first; if not,
    a link request is sent to them and the order waits."""
    dx, r = _load(db, dx_id, principal, "send_diagnostic", roles=("clinic_staff",))
    if dx.status != "draft":
        raise error(409, "already_sent", f"This request is already {dx.status}")
    local_id = _patient_id_at(db, r, dx.destination_institution)
    if local_id is None:
        link = create_request(db, principal, local_id=r.patient_local_id, target=dx.destination_institution,
                              name=r.patient_name, birth_date=r.patient_birth_date, sex=r.patient_sex, cnic=r.patient_cnic,
                              referral=r, purpose=f"{dx.test} requested with referral {r.reference}")
        db.commit()
        raise error(409, "patient_not_linked",
                    f"{institution_name(dx.destination_institution)} has not confirmed the patient yet. A link request "
                    f"was sent (#{link.id}); send this order once they approve it.")
    now = utcnow()
    order = DiagnosticOrder(order_key=f"{r.source_institution}:{dx.reference}", order_ref=dx.reference,
                            referral_id=r.reference, sender_institution=r.source_institution,
                            destination_institution=dx.destination_institution,
                            destination_department=dx.destination_department, category=dx.category, test=dx.test,
                            body_area=dx.body_area, clinical_question=dx.clinical_question, urgency=dx.urgency,
                            patient={"name": r.patient_name, "birth_date": r.patient_birth_date, "sex": r.patient_sex,
                                     "local_patient_id": local_id,
                                     "sender_name": institution_name(r.source_institution)},
                            requested_by=dx.requested_by, requested_at=now)
    db.add(Outbox(referral_id=r.id, kind="deliver_order", target_institution=dx.destination_institution,
                  message_key=order.order_key, payload=order.model_dump(mode="json")))
    dx.status, dx.sent_by, dx.sent_at = "requested", principal.display_name, now
    _history(dx, "requested", principal.display_name)
    event(db, r, "diagnostic_sent", principal.display_name, principal.institution_id,
          {"reference": dx.reference, "test": dx.test, "to": dx.destination_institution})
    audit(db, principal, "diagnostic.send", "diagnostic_request", dx.reference, "success", r.id)
    db.commit()
    enqueue("deliver_outbox")
    return diagnostic_out(dx)


class CancelIn(BaseModel):
    reason: str = Field(min_length=3)


@router.post("/diagnostics/{dx_id}/cancel")
def cancel_request(dx_id: int, body: CancelIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    dx, r = _load(db, dx_id, principal, "cancel_diagnostic")
    if dx.status not in ("draft", "rejected"):
        raise error(409, "cannot_cancel", "Only a request that has not been sent (or was rejected) can be cancelled here")
    dx.status = "cancelled"
    _history(dx, "cancelled", principal.display_name, reason=body.reason)
    audit(db, principal, "diagnostic.cancel", "diagnostic_request", dx.reference, "success", r.id, {"reason": body.reason})
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
        db.commit()
    return diagnostic_out(dx)


# ------------------------------------------------------------------ applied from inbound events
def apply_order_event(db: Session, r: Referral, dx: DiagnosticRequest, etype: str, data: dict, actor: str,
                      institution: str) -> None:
    status = {"order_accepted": "accepted", "order_rejected": "rejected", "order_scheduled": "scheduled",
              "order_done": "done", "order_reported": "reported"}[etype]
    dx.status = status
    extra = {}
    if status == "rejected":
        dx.reject_reason = data.get("reason")
        extra["reason"] = dx.reject_reason
        notify_doctor(db, r, "diagnostic_rejected", f"{dx.test} was not accepted",
                      f"{institution_name(institution)}: {dx.reject_reason}", tab="tests")
        notify_staff(db, r, "diagnostic_rejected", f"{dx.test} was not accepted",
                     f"{institution_name(institution)}: {dx.reject_reason}", tab="tests")
    if status == "scheduled":
        dx.scheduled_for = datetime.fromisoformat(data["scheduled_for"]) if data.get("scheduled_for") else None
        extra["scheduled_for"] = data.get("scheduled_for")
    if status == "reported":
        dx.report = {"findings": data.get("findings"), "impression": data.get("impression"),
                     "report_text": data.get("report_text"), "values": data.get("values", []),
                     "reported_by": data.get("reported_by"), "reported_at": data.get("reported_at")}
        _add_result_evidence(db, r, dx, institution)
        notify_doctor(db, r, "diagnostic_reported", f"Result ready: {dx.test} ({r.patient_name})",
                      f"From {institution_name(institution)}.", tab="tests")
        if r.submitted_package_version:
            _forward(db, r, dx, institution)
    _history(dx, status, actor, **extra)
    event(db, r, f"diagnostic_{status}", actor, institution, {"reference": dx.reference, "test": dx.test, **extra})


def _add_result_evidence(db: Session, r: Referral, dx: DiagnosticRequest, institution: str) -> None:
    rep = dx.report or {}
    if dx.category == "laboratory" and rep.get("values"):
        for i, v in enumerate(rep["values"]):
            db.add(EvidenceItem(
                referral_id=r.id, patient_institution=institution, patient_local_id="", origin="source",
                source_institution=institution, source_record_type="DiagnosticResult", source_record_id=f"{dx.reference}-{i + 1}",
                source_record_version="1", category="lab",
                display=f"{v.get('test')}: {v.get('value')} {v.get('unit') or ''}".strip()
                + (f", reference {v['reference']}" if v.get("reference") else "") + (f", {v['flag']}" if v.get("flag") else ""),
                original={"test": v.get("test"), "value_text": v.get("value"), "unit": v.get("unit"),
                          "reference_range": v.get("reference"), "panel": dx.test, "order": dx.reference},
                current={}, clinical_time=utcnow(), review_state="imported", verification_status="source_record",
                selected=True))
    else:
        text = rep.get("impression") or rep.get("findings") or rep.get("report_text") or ""
        db.add(EvidenceItem(
            referral_id=r.id, patient_institution=institution, patient_local_id="", origin="source",
            source_institution=institution, source_record_type="DiagnosticResult", source_record_id=dx.reference,
            source_record_version="1", category="imaging", display=f"{dx.test}: {text}",
            original={"study": dx.test, "findings": rep.get("findings"), "impression": rep.get("impression"),
                      "reporter": rep.get("reported_by"), "order": dx.reference},
            current={}, clinical_time=utcnow(), review_state="imported", verification_status="source_record",
            selected=True))


def _forward(db: Session, r: Referral, dx: DiagnosticRequest, institution: str) -> None:
    rep = dx.report or {}
    fwd = ResultForward(forward_key=f"{dx.reference}:to:{r.destination_institution}", referral_id=r.reference,
                        order_ref=dx.reference, test=dx.test, performed_by_institution=institution,
                        report_text=rep.get("report_text") or "", values=rep.get("values", []),
                        reported_by=rep.get("reported_by") or "", reported_at=rep.get("reported_at") or utcnow())
    if not db.scalars(select(Outbox).where(Outbox.message_key == fwd.forward_key)).first():
        db.add(Outbox(referral_id=r.id, kind="forward_result", target_institution=r.destination_institution,
                      message_key=fwd.forward_key, payload=fwd.model_dump(mode="json")))


def forward_reported_results(db: Session, r: Referral) -> None:
    """Called when a referral is first delivered: results that arrived earlier go too."""
    for dx in db.scalars(select(DiagnosticRequest).where(DiagnosticRequest.referral_id == r.id,
                                                          DiagnosticRequest.status == "reported")):
        _forward(db, r, dx, dx.destination_institution)
