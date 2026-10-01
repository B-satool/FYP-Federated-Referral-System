"""Review items, clarification requests and the work queue (FR-36, FR-39, FR-40, FR-54)."""
from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from refcommon.auth import Principal
from refcommon.db import utcnow
from refcommon.exchange import ClarificationAnswer
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import INSTITUTIONS
from ..db import get_db
from ..identity.links import verified_counterparts
from ..models import Clarification, ConsultationResponse, Document, FollowupTask, Outbox, Referral, ReviewItem
from ..referrals.state import PRE_SUBMISSION, event, transition
from ..security import audit, error, get_principal, load_referral, require_roles
from ..serializers import clarification_out, referral_out, review_item_out, task_out
from .checklist import refresh

router = APIRouter(tags=["review and clarification"])
ANSWER_ROLES = ("clinic_staff", "clinician", "lab_staff", "specialist")


@router.get("/referrals/{referral_id}/review-items")
def review_items(referral_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    r = load_referral(db, referral_id, principal, "view")
    items = refresh(db, r)
    db.commit()
    return [review_item_out(i) for i in items if i.status != "obsolete"]


class ResolveIn(BaseModel):
    action: Literal["resolved", "not_applicable", "uncertainty_recorded", "overridden", "reopen"]
    rationale: str = ""


@router.post("/review-items/{item_id}/resolve")
def resolve_item(item_id: int, body: ResolveIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    item = db.get(ReviewItem, item_id)
    if item is None:
        raise error(404, "not_found", "Review item not found")
    roles = ("clinician",) if item.clinical else ("clinic_staff", "clinician")
    r = load_referral(db, item.referral_id, principal, "resolve_review_item", roles=roles)
    if body.action != "reopen" and len(body.rationale.strip()) < 3:
        raise error(422, "rationale_required", "Record the rationale for this resolution (FR-40)")
    if body.action in ("not_applicable", "overridden", "uncertainty_recorded") and not item.override_allowed:
        raise error(409, "override_not_allowed",
                    "This required item cannot be overridden; provide the missing information instead")
    if body.action == "resolved" and item.kind == "missing":
        raise error(409, "still_missing", "Add the missing information; the item resolves automatically when present")
    prior = item.status
    if body.action == "reopen":
        item.status, item.resolution, item.resolved_by, item.resolved_at = "open", None, None, None
    else:
        item.status = body.action
        item.resolution = body.rationale.strip()
        item.resolved_by, item.resolved_at = principal.display_name, utcnow()
    audit(db, principal, "review_item.resolve", "review_item", item.id, "success", r.id,
          {"from": prior, "to": item.status, "rationale": body.rationale, "title": item.title})
    db.commit()
    return review_item_out(item)


class ClarificationIn(BaseModel):
    question: str = Field(min_length=5)
    assignee_institution: str
    assignee_role: str | None = None
    review_item_id: int | None = None
    due_date: date | None = None


@router.post("/referrals/{referral_id}/clarifications", status_code=201)
def create_clarification(referral_id: int, body: ClarificationIn, db: Session = Depends(get_db),
                         principal: Principal = Depends(get_principal)):
    r = load_referral(db, referral_id, principal, "clarify")
    if body.assignee_institution not in INSTITUTIONS:
        raise error(422, "unknown_institution", "Unknown assignee institution")
    if body.assignee_institution not in (r.source_institution, *verified_counterparts(db, r.patient_institution, r.patient_local_id)):
        raise error(422, "assignee_not_participant",
                    "Clarifications can be assigned to your institution or a source with a verified link for this patient")
    c = Clarification(referral_id=r.id, review_item_id=body.review_item_id, origin="clinic", question=body.question.strip(),
                      assignee_institution=body.assignee_institution, assignee_role=body.assignee_role,
                      due_date=body.due_date, created_by=principal.display_name)
    db.add(c)
    db.flush()
    if r.status in ("draft", "awaiting_approval"):
        transition(db, r, "awaiting_information", principal.display_name, principal, {"clarification_id": c.id})
    audit(db, principal, "clarification.create", "clarification", c.id, "success", r.id,
          {"assignee": body.assignee_institution})
    db.commit()
    return clarification_out(c, r)


@router.get("/referrals/{referral_id}/clarifications")
def list_clarifications(referral_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    r = load_referral(db, referral_id, principal, "view")
    return [clarification_out(c, r) for c in db.scalars(select(Clarification).where(Clarification.referral_id == r.id)
                                                        .order_by(Clarification.id))]


class AnswerIn(BaseModel):
    response_text: str = Field(min_length=2)
    document_ids: list[int] = Field(default_factory=list)


@router.post("/clarifications/{clarification_id}/answer")
def answer(clarification_id: int, body: AnswerIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    c = db.get(Clarification, clarification_id)
    if c is None:
        raise error(404, "not_found", "Clarification not found")
    require_roles(principal, *ANSWER_ROLES, action="clarification.answer")
    if principal.institution_id != c.assignee_institution:
        raise error(403, "forbidden", "This request is assigned to another institution")
    if c.status not in ("open", "answered"):
        raise error(409, "closed", "This clarification is already resolved")
    r = db.get(Referral, c.referral_id)
    for doc_id in body.document_ids:
        doc = db.get(Document, doc_id)
        if doc is None or doc.referral_id != r.id:
            raise error(422, "invalid_document", "Attached documents must belong to this referral")
    c.response_text, c.response_document_ids = body.response_text.strip(), body.document_ids
    c.answered_by, c.answered_at, c.status = principal.display_name, utcnow(), "answered"
    if c.origin == "specialist" and c.specialist_clarification_id:
        msg = ClarificationAnswer(answer_key=f"answer:{c.id}:{int(c.answered_at.timestamp())}", referral_id=r.reference,
                                  specialist_clarification_id=c.specialist_clarification_id, answer=c.response_text,
                                  answered_by=principal.display_name, answered_at=c.answered_at)
        db.add(Outbox(referral_id=r.id, kind="clarification_answer", message_key=msg.answer_key,
                      payload=msg.model_dump(mode="json")))
        c.status = "resolved"
        c.resolved_by, c.resolved_at = principal.display_name, utcnow()
        event(db, r, "specialist_clarification_answered", principal.display_name, principal.institution_id, {"clarification_id": c.id})
    audit(db, principal, "clarification.answer", "clarification", c.id, "success", r.id)
    db.commit()
    return clarification_out(c, r)


class ResolveClarIn(BaseModel):
    note: str = ""


@router.post("/clarifications/{clarification_id}/resolve")
def resolve_clarification(clarification_id: int, body: ResolveClarIn, db: Session = Depends(get_db),
                          principal: Principal = Depends(get_principal)):
    c = db.get(Clarification, clarification_id)
    if c is None:
        raise error(404, "not_found", "Clarification not found")
    r = load_referral(db, c.referral_id, principal, "clarify")
    if c.status == "resolved":
        return clarification_out(c, r)
    c.status, c.resolved_by, c.resolved_at, c.resolution_note = "resolved", principal.display_name, utcnow(), body.note
    audit(db, principal, "clarification.resolve", "clarification", c.id, "success", r.id)
    db.flush()
    open_left = db.scalars(select(Clarification).where(Clarification.referral_id == r.id, Clarification.origin == "clinic",
                                                       Clarification.status.in_(["open", "answered"]))).first()
    if open_left is None and r.status == "awaiting_information":
        transition(db, r, "draft", principal.display_name, principal, {"reason": "all clarification requests resolved"})
    db.commit()
    return clarification_out(c, r)


@router.post("/clarifications/{clarification_id}/cancel")
def cancel_clarification(clarification_id: int, body: ResolveClarIn, db: Session = Depends(get_db),
                         principal: Principal = Depends(get_principal)):
    c = db.get(Clarification, clarification_id)
    if c is None:
        raise error(404, "not_found", "Clarification not found")
    r = load_referral(db, c.referral_id, principal, "clarify")
    if c.origin != "clinic":
        raise error(409, "cannot_cancel", "Specialist requests must be answered")
    c.status, c.resolution_note, c.resolved_by, c.resolved_at = "cancelled", body.note, principal.display_name, utcnow()
    audit(db, principal, "clarification.cancel", "clarification", c.id, "success", r.id)
    db.commit()
    return clarification_out(c, r)


@router.get("/work-queue")
def work_queue(db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """Open requests, overdue tasks and items awaiting this user's institution (FR-54)."""
    require_roles(principal, *ANSWER_ROLES, action="work_queue")
    today = date.today()
    clar_rows = db.scalars(select(Clarification).where(Clarification.assignee_institution == principal.institution_id,
                                                       Clarification.status.in_(["open", "answered"]))
                           .order_by(Clarification.created_at)).all()
    clarifications = []
    for c in clar_rows:
        r = db.get(Referral, c.referral_id)
        item = clarification_out(c, r)
        if principal.institution_id != r.source_institution:
            # Assignee sees its own local identifier for the patient, never the referring clinic's record.
            link = verified_counterparts(db, r.patient_institution, r.patient_local_id).get(principal.institution_id)
            item["patient_ref_at_assignee"] = link[0] if link else None
        item["overdue"] = bool(c.due_date and c.due_date < today)
        clarifications.append(item)
    out = {"clarifications": clarifications}
    if principal.has_any("clinic_staff", "clinician"):
        mine = select(Referral).where(Referral.source_institution == principal.institution_id)
        tasks = db.scalars(select(FollowupTask).join(Referral, Referral.id == FollowupTask.referral_id)
                           .where(Referral.source_institution == principal.institution_id, FollowupTask.status == "open")
                           .order_by(FollowupTask.due_date.nulls_last())).all()
        out["tasks"] = [{**task_out(t), "overdue": bool(t.due_date and t.due_date < today),
                         "referral_reference": db.get(Referral, t.referral_id).reference} for t in tasks]
        out["awaiting_approval"] = [referral_out(r) for r in db.scalars(mine.where(
            (Referral.status == "awaiting_approval") | Referral.amendment_open.is_(True)))]
        out["awaiting_information"] = [referral_out(r) for r in db.scalars(mine.where(Referral.status == "awaiting_information"))]
        pending_review = db.scalars(select(ConsultationResponse).join(Referral, Referral.id == ConsultationResponse.referral_id)
                                    .where(Referral.source_institution == principal.institution_id,
                                           ConsultationResponse.reviewed_at.is_(None))).all()
        out["responses_to_review"] = [{"referral_id": cr.referral_id, "referral_reference": db.get(Referral, cr.referral_id).reference,
                                       "specialist_name": cr.specialist_name, "received_at": cr.received_at} for cr in pending_review]
        out["delivery_problems"] = [referral_out(r) for r in db.scalars(mine.where(Referral.delivery_status.in_(["failed", "retrying"])))]
        out["drafts"] = [referral_out(r) for r in db.scalars(mine.where(Referral.status.in_(list(PRE_SUBMISSION - {'awaiting_approval', 'awaiting_information'}))))]
    return out
