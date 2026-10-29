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
from ..lifecycle import working_set
from ..models import Clarification, ConsultationResponse, DiagnosticRequest, InboundMessage, Outbox, Referral
from ..notifications import notify_doctor, notify_staff
from ..referrals.state import event as add_event
from ..referrals.state import transition
from ..security import audit, error, get_principal, require_service
from ..tasks import enqueue

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
    purge_now = False
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
                          f"{referral.patient_name}. Accepted by {body.actor_name}.", tab="response")
            notify_staff(db, referral, "referral_accepted", f"{referral.reference} accepted by {inst_name}",
                         f"{referral.patient_name}. Tell the patient, then close the referral.", tab="response")
        elif body.type == "declined":
            referral.decline_reason = body.data.get("reason")
            transition(db, referral, "declined", actor_label, None, detail, institution=body.institution_id)
            purge_now = True  # a declined referral's shared records are removed straight away
            notify_doctor(db, referral, "referral_declined", f"{referral.reference} declined by {inst_name}",
                          f"Reason: {referral.decline_reason}", tab="response")
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
            notify_doctor(db, referral, "info_requested", f"{inst_name} asks for more information",
                          body.data.get("question", ""), tab="response")
            notify_staff(db, referral, "info_requested", f"{inst_name} asks for more information",
                         "The doctor has been asked to answer.", tab="response")  # staff never see the question
        elif body.type == "response_returned":
            if not db.scalars(select(ConsultationResponse).where(ConsultationResponse.remote_key == body.event_key)).first():
                db.add(ConsultationResponse(referral_id=referral.id, remote_key=body.event_key,
                                            package_version=body.data.get("package_version", body.package_version or 0),
                                            content=body.data.get("content", {}),
                                            specialist_name=body.data.get("returned_by", body.actor_name),
                                            returned_at=body.data.get("returned_at") or body.occurred_at,
                                            fhir_task=body.data.get("fhir_task")))
            # the sending clinic keeps its own copy of the response too
            copy_key = f"copy:{body.event_key}"
            if not db.scalars(select(Outbox).where(Outbox.message_key == copy_key)).first():
                db.add(Outbox(referral_id=referral.id, kind="sender_copy", target_institution=referral.source_institution,
                              message_key=copy_key,
                              payload={"copy_key": copy_key, "referral_id": referral.reference, "kind": "response",
                                       "version": body.package_version or 0, "content": body.data}))
            if referral.status == "acknowledged":
                transition(db, referral, "accepted", actor_label, None, detail, institution=body.institution_id)
            transition(db, referral, "response_returned", actor_label, None, {"package_version": body.package_version},
                       institution=body.institution_id)
            notify_doctor(db, referral, "response_returned", f"Specialist response: {referral.reference}",
                          f"{referral.patient_name}, from {inst_name}.", tab="response")
        elif body.type == "completed":
            if referral.status not in ("accepted", "response_returned", "followup_pending", "closed"):
                raise error(409, "not_accepted", "Only an accepted referral can be marked complete")
            if referral.receiver_completed_at is None:
                referral.receiver_completed_at, referral.receiver_completed_by = body.occurred_at, actor_label
                working_set.complete(referral, body.occurred_at)
                add_event(db, referral, "completed_by_receiver", actor_label, body.institution_id,
                          {**detail, "records_removed_at": referral.working_set_expires_at.isoformat()})
                when = referral.working_set_expires_at.strftime("%d %b %Y, %H:%M")
                for notify in (notify_doctor, notify_staff):
                    notify(db, referral, "referral_completed", f"{referral.reference} marked complete by {inst_name}",
                           f"{body.actor_name} has finished with this referral. The shared records are removed on {when} (UTC).",
                           tab="response")
        elif body.type == "hold_extended":
            until = working_set.extend(referral, body.occurred_at)
            add_event(db, referral, "hold_extended_by_receiver", actor_label, body.institution_id,
                      {**detail, "records_kept_until": until.isoformat() if until else None})
    audit(db, None, f"inbound.{body.type}", "referral", referral.reference, "success", referral.id, detail, actor=actor)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return {"status": "duplicate", "event_key": body.event_key}
    if purge_now:
        enqueue("purge_working_sets")
    return {"status": "applied", "event_key": body.event_key}
