"""Specialist response, information requests, informing the patient, tasks and closure."""
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

from ..db import get_db
from ..models import Clarification, ConsultationResponse, FollowupTask, Outbox
from ..referrals.state import TERMINAL, event, transition
from ..security import DOCTOR, STAFF, audit, check_version, error, get_principal, load_referral
from ..serializers import referral_out, response_out, task_out
from ..tasks import enqueue

router = APIRouter(tags=["response and follow-through"])


@router.get("/referrals/{referral_id}/responses")
def responses(referral_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    r = load_referral(db, referral_id, principal, "view")
    return [response_out(x) for x in db.scalars(select(ConsultationResponse).where(ConsultationResponse.referral_id == r.id)
                                                .order_by(ConsultationResponse.id))]


class ReviewIn(BaseModel):
    note: str = ""


@router.post("/responses/{response_id}/review")
def review_response(response_id: int, body: ReviewIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """The referring doctor records that the outcome has been seen."""
    resp = db.get(ConsultationResponse, response_id)
    if resp is None:
        raise error(404, "not_found", "Response not found")
    r = load_referral(db, resp.referral_id, principal, "review_response", roles=(DOCTOR,))
    resp.reviewed_by, resp.reviewed_by_id, resp.reviewed_at, resp.review_note = (
        principal.display_name, principal.subject, utcnow(), body.note)
    if r.status == "response_returned":
        transition(db, r, "followup_pending", principal.display_name, principal)
    audit(db, principal, "response.review", "consultation_response", resp.id, "success", r.id)
    db.commit()
    return {"response": response_out(resp), "referral": referral_out(r)}


class AnswerIn(BaseModel):
    answer: str = Field(min_length=2)


@router.post("/clarifications/{clarification_id}/answer")
def answer(clarification_id: int, body: AnswerIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """Answer the receiving doctor's request for more information; the answer is sent back."""
    c = db.get(Clarification, clarification_id)
    if c is None:
        raise error(404, "not_found", "Request not found")
    r = load_referral(db, c.referral_id, principal, "answer_info_request")
    if c.status != "open":
        raise error(409, "already_answered", "This request has already been answered")
    c.answer, c.answered_by, c.answered_at, c.status = body.answer.strip(), principal.display_name, utcnow(), "answered"
    msg = ClarificationAnswer(answer_key=f"{r.reference}:answer:{c.id}", referral_id=r.reference,
                              provider_clarification_id=c.provider_clarification_id or 0, answer=c.answer,
                              answered_by=principal.display_name, answered_at=c.answered_at)
    db.add(Outbox(referral_id=r.id, kind="clarification_answer", target_institution=r.destination_institution,
                  message_key=msg.answer_key, payload=msg.model_dump(mode="json")))
    event(db, r, "info_answered", principal.display_name, principal.institution_id, {"clarification_id": c.id})
    audit(db, principal, "info_request.answer", "clarification", c.id, "success", r.id)
    db.commit()
    enqueue("deliver_outbox")
    return {"id": c.id, "status": c.status, "answer": c.answer, "answered_by": c.answered_by, "answered_at": c.answered_at}


class InformedIn(BaseModel):
    note: str = Field(min_length=3)


@router.post("/referrals/{referral_id}/patient-informed")
def patient_informed(referral_id: int, body: InformedIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """Staff record that the patient was told the outcome and what happens next."""
    r = load_referral(db, referral_id, principal, "inform_patient", roles=(STAFF, DOCTOR))
    if r.status not in ("response_returned", "followup_pending", "declined"):
        raise error(409, "no_outcome", "There is no outcome to tell the patient yet")
    r.patient_informed_by, r.patient_informed_at, r.patient_informed_note = principal.display_name, utcnow(), body.note.strip()
    event(db, r, "patient_informed", principal.display_name, principal.institution_id, {"note": body.note})
    audit(db, principal, "referral.patient_informed", "referral", r.reference, "success", r.id)
    db.commit()
    return referral_out(r)


class TaskIn(BaseModel):
    description: str = Field(min_length=3)
    assignee_name: str | None = None
    due_date: date | None = None


@router.get("/referrals/{referral_id}/tasks")
def tasks(referral_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    r = load_referral(db, referral_id, principal, "view")
    return [task_out(t) for t in db.scalars(select(FollowupTask).where(FollowupTask.referral_id == r.id).order_by(FollowupTask.id))]


@router.post("/referrals/{referral_id}/tasks", status_code=201)
def add_task(referral_id: int, body: TaskIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """Tasks such as a repeat test or making sure the patient attends."""
    r = load_referral(db, referral_id, principal, "followup")
    if r.status not in ("response_returned", "followup_pending"):
        raise error(409, "no_response", "Follow-up tasks are added after the specialist's response arrives")
    t = FollowupTask(referral_id=r.id, description=body.description.strip(), specified_by=principal.display_name,
                     assignee_name=body.assignee_name, due_date=body.due_date, created_by=principal.display_name)
    db.add(t)
    if r.status == "response_returned":
        transition(db, r, "followup_pending", principal.display_name, principal)
    audit(db, principal, "task.create", "followup_task", "new", "success", r.id, {"description": t.description})
    db.commit()
    return task_out(t)


class TaskOutcomeIn(BaseModel):
    status: Literal["completed", "not_completed"]
    outcome: str = Field(min_length=2)


@router.post("/tasks/{task_id}/outcome")
def task_outcome(task_id: int, body: TaskOutcomeIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    t = db.get(FollowupTask, task_id)
    if t is None:
        raise error(404, "not_found", "Task not found")
    r = load_referral(db, t.referral_id, principal, "followup")
    if t.status != "open":
        raise error(409, "already_done", "Task already has an outcome")
    t.status, t.outcome, t.completed_by, t.completed_at = body.status, body.outcome.strip(), principal.display_name, utcnow()
    audit(db, principal, "task.outcome", "followup_task", t.id, "success", r.id, {"status": body.status})
    db.commit()
    return task_out(t)


class CloseIn(BaseModel):
    expected_version: int


@router.post("/referrals/{referral_id}/close")
def close(referral_id: int, body: CloseIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """Closure means the workflow is complete, not a statement about the patient's condition."""
    r = load_referral(db, referral_id, principal, "close")
    check_version(r, body.expected_version)
    if r.status in TERMINAL:
        raise error(409, "already_closed", "This referral is already closed")
    reviewed = db.scalars(select(ConsultationResponse).where(ConsultationResponse.referral_id == r.id,
                                                             ConsultationResponse.reviewed_at.is_not(None))).first()
    if reviewed is None:
        raise error(409, "outcome_not_seen", "The referring doctor must review the specialist's response before closing")
    if r.patient_informed_at is None:
        raise error(409, "patient_not_informed", "Record that the patient has been told the outcome before closing")
    open_tasks = db.scalars(select(FollowupTask).where(FollowupTask.referral_id == r.id, FollowupTask.status == "open")).all()
    if open_tasks:
        raise error(409, "tasks_open", f"{len(open_tasks)} follow-up task(s) still need an outcome")
    r.closed_at, r.closed_by = utcnow(), principal.display_name
    transition(db, r, "closed", principal.display_name, principal)
    db.commit()
    return referral_out(r)
