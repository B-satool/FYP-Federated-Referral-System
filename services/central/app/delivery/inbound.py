"""Inbound events from the institution services (deduplicated by event key)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from refcommon.auth import Principal
from refcommon.exchange import ProviderEvent
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import institution_name
from ..db import get_db
from ..diagnostics.router import apply_order_event
from ..models import Clarification, ConsultationResponse, DiagnosticRequest, InboundMessage, Referral
from ..notifications import notify_doctor, notify_staff
from ..referrals.state import event as add_event
from ..referrals.state import transition
from ..security import audit, error, get_principal, require_service

router = APIRouter(prefix="/inbound", tags=["inbound (institution services)"])


@router.post("/provider-events")
def provider_event(body: ProviderEvent, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    require_service(principal, "svc_provider")
    if principal.institution_id != body.institution_id:
        raise error(403, "wrong_institution", "Event institution does not match the sending service")
    if db.scalars(select(InboundMessage).where(InboundMessage.message_key == body.event_key)).first():
        return {"status": "duplicate", "event_key": body.event_key}
    referral = db.scalars(select(Referral).where(Referral.reference == body.referral_id)).first()
    if referral is None:
        raise error(404, "unknown_referral", "No such referral")
    db.add(InboundMessage(message_key=body.event_key, message_type=body.type, referral_id=referral.id,
                          payload=body.model_dump(mode="json")))
    inst_name = institution_name(body.institution_id)
    actor_label = f"{body.actor_name} ({inst_name})"
    actor = (body.actor_id, body.actor_name, body.institution_id)
    detail = {"package_version": body.package_version, **body.data}

    if body.type.startswith("order_"):
        dx = db.scalars(select(DiagnosticRequest).where(DiagnosticRequest.reference == body.order_ref,
                                                        DiagnosticRequest.referral_id == referral.id)).first()
        if dx is None or dx.destination_institution != body.institution_id:
            raise error(403, "wrong_destination", "Order is not addressed to this institution")
        apply_order_event(db, referral, dx, body.type, body.data, actor_label, body.institution_id)
    else:
        if referral.destination_institution != body.institution_id:
            raise error(403, "wrong_destination", "Event is not from this referral's receiving hospital")
        if body.type == "acknowledged":
            referral.acknowledged_at = body.occurred_at
            if referral.status == "submitted":
                transition(db, referral, "acknowledged", actor_label, None, detail, institution=body.institution_id)
            else:
                add_event(db, referral, "acknowledged", actor_label, body.institution_id, detail)
        elif body.type == "accepted":
            referral.accepted_at = body.occurred_at
            if referral.status == "submitted":
                transition(db, referral, "acknowledged", actor_label, None, detail, institution=body.institution_id)
            transition(db, referral, "accepted", actor_label, None, detail, institution=body.institution_id)
            notify_doctor(db, referral, "referral_accepted", f"{referral.reference} accepted by {inst_name}",
                          referral.patient_name)
        elif body.type == "declined":
            referral.decline_reason = body.data.get("reason")
            transition(db, referral, "declined", actor_label, None, detail, institution=body.institution_id)
            notify_doctor(db, referral, "referral_declined", f"{referral.reference} declined by {inst_name}",
                          f"Reason: {referral.decline_reason}")
            notify_staff(db, referral, "referral_declined", f"{referral.reference} declined by {inst_name}",
                         f"Reason: {referral.decline_reason}")
        elif body.type == "info_requested":
            pid = body.data.get("provider_clarification_id")
            if not db.scalars(select(Clarification).where(Clarification.referral_id == referral.id,
                                                          Clarification.provider_clarification_id == pid)).first():
                db.add(Clarification(referral_id=referral.id, provider_clarification_id=pid,
                                     package_version=body.package_version, question=body.data.get("question", ""),
                                     asked_by=actor_label))
            add_event(db, referral, "info_requested", actor_label, body.institution_id, detail)
            for notify in (notify_staff, notify_doctor):
                notify(db, referral, "info_requested", f"{inst_name} asks for more information",
                       body.data.get("question", ""), tab="response")
        elif body.type == "response_returned":
            if not db.scalars(select(ConsultationResponse).where(ConsultationResponse.remote_key == body.event_key)).first():
                db.add(ConsultationResponse(referral_id=referral.id, remote_key=body.event_key,
                                            package_version=body.data.get("package_version", body.package_version or 0),
                                            content=body.data.get("content", {}),
                                            specialist_name=body.data.get("returned_by", body.actor_name),
                                            returned_at=body.data.get("returned_at") or body.occurred_at,
                                            fhir_task=body.data.get("fhir_task")))
            if referral.status == "acknowledged":
                transition(db, referral, "accepted", actor_label, None, detail, institution=body.institution_id)
            transition(db, referral, "response_returned", actor_label, None, {"package_version": body.package_version},
                       institution=body.institution_id)
            notify_doctor(db, referral, "response_returned", f"Specialist response: {referral.reference}",
                          f"{referral.patient_name}, from {inst_name}.", tab="response")
    audit(db, None, f"inbound.{body.type}", "referral", referral.reference, "success", referral.id, detail, actor=actor)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return {"status": "duplicate", "event_key": body.event_key}
    return {"status": "applied", "event_key": body.event_key}
