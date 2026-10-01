"""Approval, submission, delivery status, packages, response review, follow-up and closure."""
from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from refcommon.auth import Principal
from refcommon.db import utcnow
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import ConsultationResponse, FollowupTask, Outbox, ReferralPackage
from ..referrals.state import event, transition
from ..security import audit, check_version, error, get_principal, load_referral
from ..serializers import referral_out, response_out, task_out
from ..tasks import enqueue
from . import packages

router = APIRouter(tags=["approval, submission and follow-up"])


class ApproveIn(BaseModel):
    expected_version: int
    acknowledge_evaluation_failure: bool = False
    manual_review_note: str | None = None


@router.get("/referrals/{referral_id}/approval-check")
def approval_check(referral_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    r = load_referral(db, referral_id, principal, "view")
    return {"blockers": packages.approval_blockers(db, r), "status": r.status, "amendment_open": r.amendment_open}


@router.post("/referrals/{referral_id}/approve")
def approve(referral_id: int, body: ApproveIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """Only an authorized clinician approves the exact version to be sent (FR-47)."""
    r = load_referral(db, referral_id, principal, "approve", roles=("clinician",))
    check_version(r, body.expected_version)
    pkg = packages.approve(db, r, principal, body.acknowledge_evaluation_failure, body.manual_review_note)
    db.commit()
    return {"referral": referral_out(r), "package_version": pkg.version, "content_hash": pkg.content_hash}


class SubmitIn(BaseModel):
    expected_version: int


@router.post("/referrals/{referral_id}/submit")
def submit(referral_id: int, body: SubmitIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    r = load_referral(db, referral_id, principal, "submit")
    check_version(r, body.expected_version)
    box = packages.schedule_send(db, r, principal)
    db.commit()
    enqueue("deliver_outbox")
    return {"referral": referral_out(r), "outbox": {"id": box.id, "status": box.status, "message_key": box.message_key}}


@router.post("/referrals/{referral_id}/retry-delivery")
def retry_delivery(referral_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """Retry reuses the same delivery key, so the specialist never receives a duplicate (FR-57)."""
    r = load_referral(db, referral_id, principal, "submit")
    boxes = db.scalars(select(Outbox).where(Outbox.referral_id == r.id, Outbox.status == "failed")).all()
    for b in boxes:
        b.status, b.attempts, b.next_attempt_at = "pending", 0, utcnow()
    if boxes:
        r.delivery_status = "pending"
        event(db, r, "delivery_retry", principal.display_name, principal.institution_id, {"items": [b.id for b in boxes]})
        audit(db, principal, "delivery.retry", "referral", r.reference, "success", r.id)
    db.commit()
    enqueue("deliver_outbox")
    return {"retried": len(boxes)}


@router.get("/referrals/{referral_id}/delivery")
def delivery(referral_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    r = load_referral(db, referral_id, principal, "view")
    rows = db.scalars(select(Outbox).where(Outbox.referral_id == r.id).order_by(Outbox.id)).all()
    return [{"id": b.id, "kind": b.kind, "message_key": b.message_key, "status": b.status, "attempts": b.attempts,
             "last_error": b.last_error, "next_attempt_at": b.next_attempt_at, "created_at": b.created_at,
             "sent_at": b.sent_at, "remote_result": b.remote_result} for b in rows]


@router.get("/referrals/{referral_id}/packages/{version}")
def get_package(referral_id: int, version: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    r = load_referral(db, referral_id, principal, "view")
    pkg = db.scalars(select(ReferralPackage).where(ReferralPackage.referral_id == r.id, ReferralPackage.version == version)).first()
    if pkg is None:
        raise error(404, "not_found", "Package version not found")
    reviews = packages.flag_reviews(db, r.id)
    return {"version": pkg.version, "approved_by": pkg.approved_by, "approved_at": pkg.approved_at,
            "content_hash": pkg.content_hash, "superseded": pkg.superseded, "overrides": pkg.overrides,
            "envelope": pkg.envelope,
            "flag_reviews": [{"flag_id": x.flag_id, "flag_version": x.flag_version, "side": x.side, "action": x.action,
                              "reviewer": x.reviewer, "package_version": x.package_version, "created_at": x.created_at}
                             for x in reviews]}


# ------------------------------------------------------------------ response and follow-up
@router.get("/referrals/{referral_id}/responses")
def responses(referral_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    r = load_referral(db, referral_id, principal, "view")
    return [response_out(x) for x in db.scalars(select(ConsultationResponse).where(ConsultationResponse.referral_id == r.id)
                                                .order_by(ConsultationResponse.id))]


@router.post("/responses/{response_id}/record-receipt")
def record_receipt(response_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    resp = db.get(ConsultationResponse, response_id)
    if resp is None:
        raise error(404, "not_found", "Response not found")
    r = load_referral(db, resp.referral_id, principal, "record_receipt")
    if resp.receipt_recorded_at is None:
        resp.receipt_recorded_by, resp.receipt_recorded_at = principal.display_name, utcnow()
        audit(db, principal, "response.receipt", "consultation_response", resp.id, "success", r.id)
        db.commit()
    return response_out(resp)


class ReviewIn(BaseModel):
    note: str = ""


@router.post("/responses/{response_id}/review")
def review_response(response_id: int, body: ReviewIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """Clinician review is recorded separately from receipt (FR-52)."""
    resp = db.get(ConsultationResponse, response_id)
    if resp is None:
        raise error(404, "not_found", "Response not found")
    r = load_referral(db, resp.referral_id, principal, "review_response", roles=("clinician",))
    if resp.receipt_recorded_at is None:
        resp.receipt_recorded_by, resp.receipt_recorded_at = principal.display_name, utcnow()
    resp.reviewed_by, resp.reviewed_by_id, resp.reviewed_at, resp.review_note = (
        principal.display_name, principal.subject, utcnow(), body.note)
    open_tasks = db.scalars(select(FollowupTask).where(FollowupTask.referral_id == r.id, FollowupTask.status == "open")).first()
    if r.status == "response_returned" and open_tasks is not None:
        transition(db, r, "followup_pending", principal.display_name, principal)
    audit(db, principal, "response.review", "consultation_response", resp.id, "success", r.id)
    db.commit()
    return {"response": response_out(resp), "referral": referral_out(r)}


class TaskIn(BaseModel):
    description: str = Field(min_length=3)
    specified_by: str | None = None
    assignee_name: str | None = None
    assignee_role: str | None = None
    due_date: date | None = None


@router.get("/referrals/{referral_id}/tasks")
def tasks(referral_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    r = load_referral(db, referral_id, principal, "view")
    return [task_out(t) for t in db.scalars(select(FollowupTask).where(FollowupTask.referral_id == r.id).order_by(FollowupTask.id))]


@router.post("/referrals/{referral_id}/tasks", status_code=201)
def add_task(referral_id: int, body: TaskIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    r = load_referral(db, referral_id, principal, "followup")
    if r.status not in ("response_returned", "followup_pending"):
        raise error(409, "no_response", "Follow-up tasks are recorded after the specialist response is received")
    specified_by = body.specified_by or (principal.display_name if "clinician" in principal.roles else None)
    if not specified_by:
        raise error(422, "clinician_required", "Record which clinician specified this task")
    t = FollowupTask(referral_id=r.id, description=body.description.strip(), specified_by=specified_by,
                     assignee_name=body.assignee_name, assignee_role=body.assignee_role, due_date=body.due_date,
                     created_by=principal.display_name)
    db.add(t)
    resp_reviewed = db.scalars(select(ConsultationResponse).where(ConsultationResponse.referral_id == r.id,
                                                                  ConsultationResponse.reviewed_at.is_not(None))).first()
    if r.status == "response_returned" and resp_reviewed:
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
        raise error(409, "already_disposed", "Task already has an outcome")
    t.status, t.outcome, t.completed_by, t.completed_at = body.status, body.outcome.strip(), principal.display_name, utcnow()
    audit(db, principal, "task.outcome", "followup_task", t.id, "success", r.id, {"status": body.status})
    db.commit()
    return task_out(t)


class CloseIn(BaseModel):
    expected_version: int


@router.post("/referrals/{referral_id}/close")
def close(referral_id: int, body: CloseIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """Closure = workflow completion, not a statement about the patient's condition."""
    r = load_referral(db, referral_id, principal, "close")
    check_version(r, body.expected_version)
    reviewed = db.scalars(select(ConsultationResponse).where(ConsultationResponse.referral_id == r.id,
                                                             ConsultationResponse.reviewed_at.is_not(None))).first()
    if reviewed is None:
        raise error(409, "response_not_reviewed", "A clinician must review the specialist response before closure")
    open_tasks = db.scalars(select(FollowupTask).where(FollowupTask.referral_id == r.id, FollowupTask.status == "open")).all()
    if open_tasks:
        raise error(409, "tasks_open", f"{len(open_tasks)} follow-up task(s) still need an outcome")
    r.closed_at, r.closed_by = utcnow(), principal.display_name
    transition(db, r, "closed", principal.display_name, principal)
    db.commit()
    return referral_out(r)
