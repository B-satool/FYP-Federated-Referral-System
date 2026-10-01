"""Inbound events from the specialist service (deduplicated by event key - FR-57)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from refcommon.auth import Principal
from refcommon.exchange import SpecialistEvent
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Clarification, ConsultationResponse, FlagReview, InboundMessage, MedicationFlag, Referral
from ..referrals.state import event as add_event
from ..referrals.state import transition
from ..security import audit, error, get_principal, require_service

router = APIRouter(prefix="/inbound", tags=["inbound (specialist service)"])


@router.post("/specialist-events")
def specialist_event(body: SpecialistEvent, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    require_service(principal, "svc_specialist")
    if db.scalars(select(InboundMessage).where(InboundMessage.message_key == body.event_key)).first():
        return {"status": "duplicate", "event_key": body.event_key}
    referral = db.scalars(select(Referral).where(Referral.reference == body.referral_id)).first()
    if referral is None:
        raise error(404, "unknown_referral", "No such referral")
    if referral.destination_institution != body.institution_id or principal.institution_id != body.institution_id:
        raise error(403, "wrong_destination", "Event is not from this referral's destination")
    db.add(InboundMessage(message_key=body.event_key, message_type=body.type, referral_id=referral.id,
                          payload=body.model_dump(mode="json")))
    actor_label = f"{body.actor_name} (Specialist C)"
    actor = (body.actor_id, body.actor_name, body.institution_id)
    detail = {"package_version": body.package_version, **body.data}

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
    elif body.type == "declined":
        referral.decline_reason = body.data.get("reason")
        transition(db, referral, "declined", actor_label, None, detail, institution=body.institution_id)
    elif body.type == "clarification_requested":
        sid = body.data.get("specialist_clarification_id")
        if not db.scalars(select(Clarification).where(Clarification.referral_id == referral.id,
                                                      Clarification.specialist_clarification_id == sid)).first():
            db.add(Clarification(referral_id=referral.id, origin="specialist", question=body.data.get("question", ""),
                                 flag_id=body.data.get("flag_id"), assignee_institution=referral.source_institution,
                                 assignee_role="clinician", created_by=actor_label, specialist_clarification_id=sid,
                                 package_version=body.package_version))
        add_event(db, referral, "specialist_clarification_requested", actor_label, body.institution_id, detail)
    elif body.type == "flag_reviewed":
        flag = db.get(MedicationFlag, body.data.get("flag_id"))
        if flag is None or flag.referral_id != referral.id:
            raise error(422, "unknown_flag", "Flag not part of this referral")
        clar = None
        if body.data.get("specialist_clarification_id"):
            clar = db.scalars(select(Clarification).where(
                Clarification.referral_id == referral.id,
                Clarification.specialist_clarification_id == body.data["specialist_clarification_id"])).first()
        db.add(FlagReview(referral_id=referral.id, flag_id=flag.id, flag_version=body.data.get("flag_version"),
                          side="specialist", action=body.data.get("action"), reviewer=body.actor_name,
                          reviewer_id=body.actor_id, institution_id=body.institution_id,
                          package_version=body.package_version, clarification_id=clar.id if clar else None))
        add_event(db, referral, "specialist_flag_review", actor_label, body.institution_id, detail)
    elif body.type == "response_returned":
        if not db.scalars(select(ConsultationResponse).where(ConsultationResponse.remote_key == body.event_key)).first():
            db.add(ConsultationResponse(referral_id=referral.id, remote_key=body.event_key,
                                        package_version=body.data.get("package_version", body.package_version),
                                        content=body.data.get("content", {}), specialist_name=body.data.get("approved_by", body.actor_name),
                                        approved_at=body.data.get("approved_at") or body.occurred_at,
                                        fhir_task=body.data.get("fhir_task")))
        transition(db, referral, "response_returned", actor_label, None, {"package_version": body.package_version},
                   institution=body.institution_id)
    audit(db, None, f"inbound.{body.type}", "referral", referral.reference, "success", referral.id, detail, actor=actor)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return {"status": "duplicate", "event_key": body.event_key}
    return {"status": "applied", "event_key": body.event_key}
