"""Specialist C source service.

Owns incoming referrals, specialist decisions, flag acknowledgments,
clarification requests and consultation responses. Approval of a response is
enforced here, where the response is owned, not only in the screen.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Literal

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from refcommon.auth import (
    KeycloakConfig,
    Principal,
    ServiceTokenProvider,
    TokenVerifier,
    forbid,
    make_principal_dependency,
)
from refcommon.db import make_session_factory, session_dependency, utcnow
from refcommon.exchange import ClarificationAnswer, SpecialistEvent
from refcommon.sourcekit import (
    MatchIn,
    build_admin_router,
    decide_access,
    health_router,
    identity_match,
    record_audit,
    records_bundle,
)
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import adapter
from .models import (
    AccessGrant,
    AuditEvent,
    Case,
    Clarification,
    ConsultationResponse,
    FlagReview,
    IncomingPackage,
    Outbox,
    Patient,
    PriorConsultation,
)

log = logging.getLogger("specialist")
INSTITUTION = "spec-c"
CENTRAL_URL = os.environ.get("CENTRAL_URL", "http://central:8000").rstrip("/")
OUTBOX_MAX_ATTEMPTS = 12

engine, SessionLocal = make_session_factory(os.environ["DATABASE_URL"])
get_db = session_dependency(SessionLocal)
kc = KeycloakConfig()
verifier = TokenVerifier(kc, audience="specialist-api")
get_principal = make_principal_dependency(verifier)
service_tokens = ServiceTokenProvider(kc)
_stop = threading.Event()


# --------------------------------------------------------------------------- outbox delivery
def _deliver_once() -> int:
    sent = 0
    with SessionLocal() as db:
        due = db.scalars(
            select(Outbox).where(Outbox.status == "pending", Outbox.next_attempt_at <= utcnow())
            .order_by(Outbox.id).limit(20)
        ).all()
        for item in due:
            item.attempts += 1
            try:
                token = service_tokens.get()
                resp = httpx.post(f"{CENTRAL_URL}/inbound/specialist-events", json=item.payload,
                                  headers={"Authorization": f"Bearer {token}"}, timeout=10.0)
                if resp.status_code < 300:
                    item.status = "sent"
                    item.sent_at = utcnow()
                    item.last_error = None
                    sent += 1
                elif 400 <= resp.status_code < 500 and resp.status_code not in (401, 408, 409, 429):
                    item.status = "failed"
                    item.last_error = f"rejected by central ({resp.status_code}): {resp.text[:300]}"
                else:
                    raise httpx.HTTPStatusError(f"central returned {resp.status_code}", request=resp.request, response=resp)
            except httpx.HTTPError as exc:
                item.last_error = str(exc)[:500]
                if item.attempts >= OUTBOX_MAX_ATTEMPTS:
                    item.status = "failed"
                else:
                    item.next_attempt_at = utcnow() + timedelta(seconds=min(60, 2 ** item.attempts))
            db.commit()
    return sent


def _outbox_loop() -> None:
    while not _stop.is_set():
        try:
            _deliver_once()
        except Exception:  # noqa: BLE001 - keep the loop alive; errors are stored per item
            log.exception("outbox loop error")
        _stop.wait(3)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    thread = threading.Thread(target=_outbox_loop, name="outbox", daemon=True)
    thread.start()
    yield
    _stop.set()


app = FastAPI(
    title="Specialist C source service",
    version="1.0.0",
    description="Example specialist system: receives approved referral packages, records decisions and returns responses.",
    lifespan=lifespan,
)


def _check_db() -> None:
    with engine.connect() as conn:
        conn.execute(text("select 1"))


app.include_router(health_router(_check_db))
app.include_router(build_admin_router(
    INSTITUTION, AccessGrant, AuditEvent,
    lambda db, pid: db.get(Patient, pid) is not None,
    get_db, get_principal,
))


# --------------------------------------------------------------------------- helpers
def _require_specialist(principal: Principal) -> None:
    if principal.institution_id != INSTITUTION or "specialist" not in principal.roles:
        raise forbid("Only Specialist C clinicians can act on incoming referrals")


def _require_central(principal: Principal) -> None:
    if "svc_central" not in principal.roles:
        raise forbid("Only the central referral platform may deliver to this endpoint")


def _get_case(db: Session, case_id: int) -> Case:
    case = db.get(Case, case_id)
    if not case:
        raise HTTPException(404, {"code": "not_found", "message": "Referral not found"})
    return case


def _latest_package(db: Session, case: Case) -> IncomingPackage:
    return db.scalars(select(IncomingPackage).where(IncomingPackage.case_id == case.id,
                                                    IncomingPackage.version == case.latest_version)).one()


def _emit(db: Session, case: Case, event_type: str, key: str, principal: Principal, data: dict | None = None,
          package_version: int | None = None) -> None:
    existing = db.scalars(select(Outbox).where(Outbox.event_key == key)).first()
    if existing:
        return
    event = SpecialistEvent(
        event_key=key, referral_id=case.central_referral_id,
        package_version=package_version or case.latest_version, type=event_type,
        actor_id=principal.subject, actor_name=principal.display_name, institution_id=INSTITUTION,
        occurred_at=utcnow(), data=data or {},
    )
    db.add(Outbox(event_key=key, event_type=event_type, case_id=case.id, payload=event.model_dump(mode="json")))


def _case_summary(case: Case) -> dict:
    return {
        "id": case.id, "central_referral_id": case.central_referral_id, "sender_institution": case.sender_institution,
        "patient_name": case.patient_name, "patient_birth_date": case.patient_birth_date,
        "specialist_patient_id": case.specialist_patient_id, "priority": case.priority, "status": case.status,
        "latest_version": case.latest_version, "acknowledged_by": case.acknowledged_by,
        "acknowledged_at": case.acknowledged_at, "decision": case.decision, "decision_by": case.decision_by,
        "decision_at": case.decision_at, "decline_reason": case.decline_reason, "received_at": case.received_at,
        "updated_at": case.updated_at,
    }


# --------------------------------------------------------------------------- inbound from central
@app.post("/inbound/referrals", tags=["inbound (central platform)"])
def receive_package(raw: dict, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """Idempotent receipt of an approved package version (keyed by delivery key)."""
    _require_central(principal)
    delivery_key = raw.get("delivery_key")
    existing = db.scalars(select(IncomingPackage).where(IncomingPackage.delivery_key == delivery_key)).first()
    if existing:
        return {"status": "already_received", "case_id": existing.case_id, "version": existing.version,
                "received_at": existing.received_at}
    try:
        env, fields = adapter.translate_package(raw)
    except adapter.PackageRejected as exc:
        record_audit(db, AuditEvent, principal, "package.receive", "referral", str(raw.get("referral_id")), "rejected",
                     detail={"reason": str(exc)})
        db.commit()
        raise HTTPException(422, {"code": "package_rejected", "message": str(exc)}) from exc
    except Exception as exc:  # pydantic validation errors
        raise HTTPException(422, {"code": "invalid_envelope", "message": str(exc)[:500]}) from exc

    case = db.scalars(select(Case).where(Case.central_referral_id == env.referral_id)).first()
    if case and env.package_version <= case.latest_version:
        same = db.scalars(select(IncomingPackage).where(IncomingPackage.case_id == case.id,
                                                        IncomingPackage.version == env.package_version)).first()
        if same:
            return {"status": "already_received", "case_id": case.id, "version": same.version, "received_at": same.received_at}
    if case is None:
        case = Case(latest_version=env.package_version, **fields)
        db.add(case)
        db.flush()
    else:
        case.latest_version = max(case.latest_version, env.package_version)
        case.priority = fields["priority"]
        case.specialist_patient_id = fields["specialist_patient_id"] or case.specialist_patient_id
    pkg = IncomingPackage(case_id=case.id, version=env.package_version, delivery_key=env.delivery_key,
                          envelope=env.model_dump(mode="json"), content_hash=env.content_hash)
    db.add(pkg)
    record_audit(db, AuditEvent, principal, "package.receive", "referral", env.referral_id, "success",
                 detail={"version": env.package_version, "hash": env.content_hash})
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalars(select(IncomingPackage).where(IncomingPackage.delivery_key == delivery_key)).one()
        return {"status": "already_received", "case_id": existing.case_id, "version": existing.version,
                "received_at": existing.received_at}
    return {"status": "received", "case_id": case.id, "version": pkg.version, "received_at": pkg.received_at}


@app.post("/inbound/clarification-answers", tags=["inbound (central platform)"])
def receive_answer(body: ClarificationAnswer, db: Session = Depends(get_db),
                   principal: Principal = Depends(get_principal)):
    _require_central(principal)
    clar = db.get(Clarification, body.specialist_clarification_id)
    if not clar:
        raise HTTPException(404, {"code": "not_found", "message": "Clarification not found"})
    if clar.answer_key == body.answer_key:
        return {"status": "already_received", "clarification_id": clar.id}
    clar.answer = body.answer
    clar.answered_by = body.answered_by
    clar.answered_at = body.answered_at
    clar.answer_key = body.answer_key
    clar.status = "answered"
    record_audit(db, AuditEvent, principal, "clarification.answer_received", "clarification", str(clar.id), "success",
                 referral_context=body.referral_id)
    db.commit()
    return {"status": "received", "clarification_id": clar.id}


# --------------------------------------------------------------------------- specialist workspace
@app.get("/specialist/cases", tags=["specialist workspace"])
def list_cases(status: str | None = None, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    _require_specialist(principal)
    stmt = select(Case).order_by(Case.updated_at.desc())
    if status:
        stmt = stmt.where(Case.status == status)
    cases = db.scalars(stmt).all()
    out = []
    for c in cases:
        item = _case_summary(c)
        item["open_clarifications"] = len(db.scalars(select(Clarification.id).where(
            Clarification.case_id == c.id, Clarification.status == "open")).all())
        out.append(item)
    return out


@app.get("/specialist/cases/{case_id}", tags=["specialist workspace"])
def get_case(case_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    _require_specialist(principal)
    case = _get_case(db, case_id)
    packages = db.scalars(select(IncomingPackage).where(IncomingPackage.case_id == case.id)
                          .order_by(IncomingPackage.version.desc())).all()
    reviews = db.scalars(select(FlagReview).where(FlagReview.case_id == case.id).order_by(FlagReview.id)).all()
    clars = db.scalars(select(Clarification).where(Clarification.case_id == case.id).order_by(Clarification.id)).all()
    responses = db.scalars(select(ConsultationResponse).where(ConsultationResponse.case_id == case.id)
                           .order_by(ConsultationResponse.id)).all()
    outbox = db.scalars(select(Outbox).where(Outbox.case_id == case.id).order_by(Outbox.id)).all()
    history = []
    if case.specialist_patient_id:
        history = [{"id": c.id, "seen_at": c.seen_at, "clinician": c.clinician, "summary": c.summary,
                    "diagnosis": c.diagnosis}
                   for c in db.scalars(select(PriorConsultation).where(
                       PriorConsultation.patient_id == case.specialist_patient_id))]
    record_audit(db, AuditEvent, principal, "case.view", "referral", case.central_referral_id, "success")
    db.commit()
    return {
        "case": _case_summary(case),
        "packages": [{"version": p.version, "received_at": p.received_at, "content_hash": p.content_hash,
                      "envelope": p.envelope} for p in packages],
        "flag_reviews": [{"id": r.id, "package_version": r.package_version, "flag_id": r.flag_id,
                          "flag_version": r.flag_version, "action": r.action, "reviewer": r.reviewer,
                          "clarification_id": r.clarification_id, "created_at": r.created_at} for r in reviews],
        "clarifications": [{"id": c.id, "package_version": c.package_version, "flag_id": c.flag_id,
                            "question": c.question, "status": c.status, "created_by": c.created_by,
                            "created_at": c.created_at, "answer": c.answer, "answered_by": c.answered_by,
                            "answered_at": c.answered_at} for c in clars],
        "responses": [{"id": r.id, "package_version": r.package_version, "content": r.content, "status": r.status,
                       "drafted_by": r.drafted_by, "drafted_at": r.drafted_at, "row_version": r.row_version,
                       "approved_by": r.approved_by, "approved_at": r.approved_at, "returned_at": r.returned_at}
                      for r in responses],
        "local_history": history,
        "outbox": [{"id": o.id, "event_type": o.event_type, "status": o.status, "attempts": o.attempts,
                    "last_error": o.last_error, "created_at": o.created_at, "sent_at": o.sent_at} for o in outbox],
    }


@app.post("/specialist/cases/{case_id}/acknowledge", tags=["specialist workspace"])
def acknowledge(case_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    _require_specialist(principal)
    case = _get_case(db, case_id)
    if case.acknowledged_at is None:
        case.acknowledged_by = principal.display_name
        case.acknowledged_at = utcnow()
        if case.status == "received":
            case.status = "acknowledged"
        _emit(db, case, "acknowledged", f"{INSTITUTION}:{case.central_referral_id}:acknowledged", principal)
        record_audit(db, AuditEvent, principal, "case.acknowledge", "referral", case.central_referral_id, "success")
        db.commit()
    return _case_summary(case)


class DecisionIn(BaseModel):
    decision: Literal["accept", "decline"]
    reason: str | None = None


@app.post("/specialist/cases/{case_id}/decision", tags=["specialist workspace"])
def decide(case_id: int, body: DecisionIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    _require_specialist(principal)
    case = _get_case(db, case_id)
    if case.acknowledged_at is None:
        raise HTTPException(409, {"code": "not_acknowledged", "message": "Acknowledge receipt before deciding"})
    if case.decision:
        if case.decision == ("accepted" if body.decision == "accept" else "declined"):
            return _case_summary(case)
        raise HTTPException(409, {"code": "already_decided", "message": f"Referral already {case.decision}"})
    if body.decision == "decline" and not (body.reason or "").strip():
        raise HTTPException(422, {"code": "reason_required", "message": "A reason is required to decline"})
    case.decision = "accepted" if body.decision == "accept" else "declined"
    case.decision_by = principal.display_name
    case.decision_at = utcnow()
    case.decline_reason = body.reason if body.decision == "decline" else None
    case.status = case.decision
    _emit(db, case, case.decision, f"{INSTITUTION}:{case.central_referral_id}:{case.decision}", principal,
          {"reason": case.decline_reason} if case.decline_reason else {})
    record_audit(db, AuditEvent, principal, f"case.{case.decision}", "referral", case.central_referral_id, "success")
    db.commit()
    return _case_summary(case)


class ClarificationIn(BaseModel):
    question: str = Field(min_length=3)
    flag_id: int | None = None


def _create_clarification(db: Session, case: Case, principal: Principal, question: str, flag_id: int | None) -> Clarification:
    clar = Clarification(case_id=case.id, package_version=case.latest_version, flag_id=flag_id,
                         question=question, created_by=principal.display_name)
    db.add(clar)
    db.flush()
    _emit(db, case, "clarification_requested", f"{INSTITUTION}:{case.central_referral_id}:clarification:{clar.id}",
          principal, {"specialist_clarification_id": clar.id, "question": question, "flag_id": flag_id})
    return clar


@app.post("/specialist/cases/{case_id}/clarifications", tags=["specialist workspace"])
def request_clarification(case_id: int, body: ClarificationIn, db: Session = Depends(get_db),
                          principal: Principal = Depends(get_principal)):
    _require_specialist(principal)
    case = _get_case(db, case_id)
    if case.acknowledged_at is None:
        raise HTTPException(409, {"code": "not_acknowledged", "message": "Acknowledge receipt first"})
    clar = _create_clarification(db, case, principal, body.question, body.flag_id)
    record_audit(db, AuditEvent, principal, "clarification.request", "referral", case.central_referral_id, "success",
                 detail={"clarification_id": clar.id})
    db.commit()
    return {"id": clar.id, "status": clar.status}


class FlagReviewIn(BaseModel):
    flag_version: int
    action: Literal["reviewed", "request_clarification"]
    question: str | None = None


@app.post("/specialist/cases/{case_id}/flags/{flag_id}/review", tags=["specialist workspace"])
def review_flag(case_id: int, flag_id: int, body: FlagReviewIn, db: Session = Depends(get_db),
                principal: Principal = Depends(get_principal)):
    """Reviewed = acknowledgment only; it does not clear treatment or close the referral (FR-69)."""
    _require_specialist(principal)
    case = _get_case(db, case_id)
    if case.acknowledged_at is None:
        raise HTTPException(409, {"code": "not_acknowledged", "message": "Acknowledge receipt before reviewing flags"})
    pkg = _latest_package(db, case)
    flags = {f["flag_id"]: f for f in pkg.envelope.get("medication_flags", [])}
    flag = flags.get(flag_id)
    if not flag or flag["version"] != body.flag_version:
        raise HTTPException(409, {"code": "flag_version_mismatch",
                                  "message": "This flag version is not in the latest approved package"})
    clar = None
    if body.action == "request_clarification":
        if not (body.question or "").strip():
            raise HTTPException(422, {"code": "question_required", "message": "Enter the clarification question"})
        clar = _create_clarification(db, case, principal, body.question.strip(), flag_id)
    review = FlagReview(case_id=case.id, package_version=pkg.version, flag_id=flag_id, flag_version=body.flag_version,
                        action=body.action, reviewer=principal.display_name, reviewer_id=principal.subject,
                        clarification_id=clar.id if clar else None)
    db.add(review)
    db.flush()
    _emit(db, case, "flag_reviewed", f"{INSTITUTION}:{case.central_referral_id}:flag-review:{review.id}", principal,
          {"flag_id": flag_id, "flag_version": body.flag_version, "action": body.action,
           "specialist_clarification_id": clar.id if clar else None}, package_version=pkg.version)
    record_audit(db, AuditEvent, principal, "flag.review", "medication_flag", f"{flag_id}v{body.flag_version}", "success",
                 referral_context=case.central_referral_id, detail={"action": body.action})
    db.commit()
    return {"id": review.id, "action": review.action, "clarification_id": review.clarification_id}


class ResponseIn(BaseModel):
    findings: str = ""
    assessment: str = ""
    recommendations: str = ""
    follow_up_advice: str = ""
    expected_row_version: int | None = None


def _response_out(r: ConsultationResponse) -> dict:
    return {"id": r.id, "package_version": r.package_version, "content": r.content, "status": r.status,
            "drafted_by": r.drafted_by, "row_version": r.row_version, "approved_by": r.approved_by,
            "approved_at": r.approved_at, "returned_at": r.returned_at}


def _current_response(db: Session, case: Case) -> ConsultationResponse | None:
    return db.scalars(select(ConsultationResponse).where(ConsultationResponse.case_id == case.id)
                      .order_by(ConsultationResponse.id.desc())).first()


@app.put("/specialist/cases/{case_id}/response", tags=["specialist workspace"])
def save_response(case_id: int, body: ResponseIn, db: Session = Depends(get_db),
                  principal: Principal = Depends(get_principal)):
    _require_specialist(principal)
    case = _get_case(db, case_id)
    if case.decision != "accepted":
        raise HTTPException(409, {"code": "not_accepted", "message": "Accept the referral before drafting a response"})
    content = body.model_dump(exclude={"expected_row_version"})
    resp = _current_response(db, case)
    if resp and resp.status == "draft":
        if body.expected_row_version is not None and body.expected_row_version != resp.row_version:
            raise HTTPException(409, {"code": "stale_version", "message": "Response changed since you opened it; reload"})
        resp.content = content
        resp.row_version += 1
        resp.drafted_by = principal.display_name
        resp.drafted_at = utcnow()
    elif resp and resp.status in ("approved", "returned"):
        raise HTTPException(409, {"code": "response_locked", "message": "An approved response cannot be edited"})
    else:
        resp = ConsultationResponse(case_id=case.id, package_version=case.latest_version, content=content,
                                    drafted_by=principal.display_name)
        db.add(resp)
    record_audit(db, AuditEvent, principal, "response.save_draft", "referral", case.central_referral_id, "success")
    db.commit()
    return _response_out(resp)


class ApproveIn(BaseModel):
    expected_row_version: int


@app.post("/specialist/cases/{case_id}/response/approve", tags=["specialist workspace"])
def approve_response(case_id: int, body: ApproveIn, db: Session = Depends(get_db),
                     principal: Principal = Depends(get_principal)):
    _require_specialist(principal)
    case = _get_case(db, case_id)
    resp = _current_response(db, case)
    if not resp or resp.status != "draft":
        raise HTTPException(409, {"code": "no_draft", "message": "There is no draft response to approve"})
    if resp.row_version != body.expected_row_version:
        raise HTTPException(409, {"code": "stale_version", "message": "Response changed since you opened it; reload"})
    if not any(str(v).strip() for v in resp.content.values()):
        raise HTTPException(422, {"code": "empty_response", "message": "Response is empty"})
    resp.status = "approved"
    resp.approved_by = principal.display_name
    resp.approved_by_id = principal.subject
    resp.approved_at = utcnow()
    record_audit(db, AuditEvent, principal, "response.approve", "referral", case.central_referral_id, "success")
    db.commit()
    return _response_out(resp)


@app.post("/specialist/cases/{case_id}/response/return", tags=["specialist workspace"])
def return_response(case_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    _require_specialist(principal)
    case = _get_case(db, case_id)
    resp = _current_response(db, case)
    if not resp or resp.status not in ("approved", "returned"):
        raise HTTPException(409, {"code": "not_approved", "message": "Only an approved response can be returned (FR-51)"})
    if resp.status == "returned":
        return _response_out(resp)
    resp.return_key = f"{INSTITUTION}:{case.central_referral_id}:response:{resp.id}"
    resp.status = "returned"
    resp.returned_at = utcnow()
    case.status = "responded"
    approved_at = resp.approved_at.isoformat()
    _emit(db, case, "response_returned", resp.return_key, principal, {
        "response_id": resp.id, "content": resp.content, "approved_by": resp.approved_by,
        "approved_at": approved_at, "package_version": resp.package_version,
        "fhir_task": adapter.response_task(case.central_referral_id, resp.id, resp.content, resp.approved_by, approved_at),
    })
    record_audit(db, AuditEvent, principal, "response.return", "referral", case.central_referral_id, "success")
    db.commit()
    return _response_out(resp)


@app.post("/specialist/outbox/{item_id}/retry", tags=["specialist workspace"])
def retry_outbox(item_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    _require_specialist(principal)
    item = db.get(Outbox, item_id)
    if not item:
        raise HTTPException(404, {"code": "not_found", "message": "Outbox item not found"})
    if item.status == "failed":
        item.status = "pending"
        item.attempts = 0
        item.next_attempt_at = utcnow()
        db.commit()
    return {"id": item.id, "status": item.status}


# --------------------------------------------------------------------------- source records
@app.post("/identity/match", tags=["identity"])
def match_identity(body: MatchIn, request: Request, db: Session = Depends(get_db),
                   principal: Principal = Depends(get_principal)):
    if not principal.has_any("clinic_staff", "clinician", "institution_admin", "specialist"):
        raise forbid("Role may not request identity verification checks")
    result = identity_match(db.get(Patient, body.local_patient_id), body)
    record_audit(db, AuditEvent, principal, "identity.match", "patient", body.local_patient_id, "success",
                 referral_context=request.headers.get("x-referral-id"), detail=result)
    db.commit()
    return result


@app.get("/fhir/patients/{local_id}/records", tags=["fhir"])
def patient_records(local_id: str, request: Request, categories: str | None = None,
                    db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    referral_ctx = request.headers.get("x-referral-id")
    supported = {"demographics", "consultations", "conditions"}
    requested = set(categories.split(",")) & supported if categories else supported
    patient = db.get(Patient, local_id)
    if patient is None:
        record_audit(db, AuditEvent, principal, "records.read", "patient", local_id, "not_found", referral_ctx)
        db.commit()
        raise HTTPException(404, {"code": "patient_not_found", "message": "No such patient at Specialist C"})
    decision = decide_access(db, AccessGrant, principal, INSTITUTION, local_id, requested)
    if not decision.allowed:
        record_audit(db, AuditEvent, principal, "records.read", "patient", local_id, "denied", referral_ctx,
                     {"reason": decision.reason})
        db.commit()
        raise forbid(f"Specialist C denied access: {decision.reason}", code="access_denied")
    resources: list[dict] = []
    if "demographics" in decision.allowed:
        resources.append(adapter.patient(patient))
    consults = db.scalars(select(PriorConsultation).where(PriorConsultation.patient_id == local_id)).all()
    if "consultations" in decision.allowed:
        resources += [adapter.consultation_encounter(c) for c in consults]
    if "conditions" in decision.allowed:
        resources += [r for r in (adapter.consultation_condition(c) for c in consults) if r]
    record_audit(db, AuditEvent, principal, "records.read", "patient", local_id,
                 "partial" if decision.denied else "success", referral_ctx,
                 {"categories": sorted(decision.allowed), "withheld": sorted(decision.denied), "count": len(resources)})
    db.commit()
    return records_bundle(resources, decision.denied)
