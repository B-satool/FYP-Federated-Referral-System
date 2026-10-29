"""Records requests from the platform (spec v4 WP2/WP3): answered under consent and this institution's policy, or
queued for this institution's staff. Staff here see the request (who asks, for which referral, under which
consent), never the records' content."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from refcommon.auth import Principal, forbid
from refcommon.sourcekit import record_audit
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import m2m, release
from .config import INSTITUTION, INSTITUTION_NAME
from .models import AuditEvent, RecordRequest

REVIEW_ROLES = ("clinic_staff", "institution_admin", "diagnostics_staff")
DECLINE_REASONS = ("prohibited_by_law", "sensitive_category_no_specific_consent", "request_incomplete_or_invalid",
                   "consent_expired_or_out_of_range")


class RecordRequestIn(BaseModel):
    request_key: str = Field(min_length=8, max_length=200)
    local_patient_id: str | None = None
    categories: list[str] | None = None
    sensitive: list[str] = []
    since: str | None = None
    reason: str | None = None
    practitioner_entry: dict | None = None
    patient_entry: dict | None = None


class DeclineIn(BaseModel):
    reason: str = Field(pattern="^(" + "|".join(DECLINE_REASONS) + ")$")
    note: str = ""


def _claims_of(req: RecordRequest) -> dict:
    return {"refx": {"org": req.requesting_org, "practitioner": req.practitioner_id, "purpose": req.purpose,
                     "consent": req.consent_ref, "referral": req.referral_ref}}


def _out(r: RecordRequest) -> dict:
    return {"id": r.id, "referral_ref": r.referral_ref, "requesting_org": r.requesting_org,
            "practitioner_name": r.practitioner_name, "purpose": r.purpose, "consent_ref": r.consent_ref,
            "local_patient_id": r.local_patient_id, "categories": r.categories, "sensitive": r.sensitive,
            "since": r.since, "reason": r.reason_text, "status": r.status, "refusals": r.refusals,
            "item_count": r.item_count, "policy_version": r.policy_version, "decided_by": r.decided_by,
            "decided_at": r.decided_at, "delivered": r.delivered_at is not None, "delivery_error": r.delivery_error,
            "created_at": r.created_at}


def deliver(db: Session, req: RecordRequest, result: dict) -> None:
    """Push a later answer (after staff review) to the platform."""
    try:
        resp = m2m.hub_call(db, "POST", "/e2e/adapter/record-responses", json=result, timeout=30)
        if resp.status_code < 300:
            req.delivered_at, req.delivery_error = datetime.now(timezone.utc), None
        else:
            req.delivery_error = f"platform returned {resp.status_code}: {resp.text[:200]}"
    except Exception as exc:  # noqa: BLE001 - kept for a retry by staff
        req.delivery_error = str(exc)[:300]


def build_router(get_db, get_principal) -> APIRouter:
    router = APIRouter(tags=["records requests"])

    @router.post("/e2e/record-requests")
    def receive_request(body: RecordRequestIn, request: Request, db: Session = Depends(get_db)):
        claims = m2m.verify_hub(request, db)
        problem = release.check_claims(claims)
        refx = claims.get("refx") or {}
        if problem:
            record_audit(db, AuditEvent, None, "records.request", "patient", body.local_patient_id or "?", "refused",
                         refx.get("referral"), {"reason": problem}, actor_override=release.actor(claims))
            db.commit()
            raise HTTPException(403, {"code": "refused", "message": problem,
                                      "refusal": {"reason": "request_incomplete_or_invalid", "message": problem}})
        req = db.scalars(select(RecordRequest).where(RecordRequest.request_key == body.request_key)).first()
        if req is None:
            req = RecordRequest(request_key=body.request_key, referral_ref=refx["referral"], requesting_org=refx["org"],
                                practitioner_id=refx["practitioner"],
                                practitioner_name=(body.practitioner_entry or {}).get("display_name"),
                                purpose=refx["purpose"], consent_ref=refx["consent"],
                                local_patient_id=body.local_patient_id, categories=body.categories or [],
                                sensitive=body.sensitive, since=body.since, reason_text=body.reason,
                                practitioner_entry=body.practitioner_entry, patient_entry=body.patient_entry,
                                status="received", policy_version="")
            db.add(req)
            db.flush()
        elif req.status == "pending_manual_review":
            db.commit()
            return {"request_key": req.request_key, "status": req.status, "refusals": req.refusals,
                    "policy_version": req.policy_version, "notes": [], "batch": None}
        result = release.answer(db, req, claims)
        req.delivered_at = datetime.now(timezone.utc) if req.status != "pending_manual_review" else None
        db.commit()
        return result

    def require_staff(principal: Principal) -> None:
        if principal.institution_id != INSTITUTION or not principal.has_any(*REVIEW_ROLES):
            raise forbid(f"Only {INSTITUTION_NAME} staff review records requests")

    @router.get("/e2e/record-requests")
    def list_requests(status: str | None = None, db: Session = Depends(get_db),
                      principal: Principal = Depends(get_principal)):
        require_staff(principal)
        stmt = select(RecordRequest).order_by(RecordRequest.created_at.desc()).limit(200)
        if status:
            stmt = stmt.where(RecordRequest.status == status)
        return [_out(r) for r in db.scalars(stmt)]

    def _pending(db: Session, request_id: int) -> RecordRequest:
        req = db.get(RecordRequest, request_id)
        if req is None:
            raise HTTPException(404, {"code": "not_found", "message": "No such request"})
        if req.status != "pending_manual_review":
            raise HTTPException(409, {"code": "not_pending", "message": f"This request is {req.status}"})
        return req

    @router.post("/e2e/record-requests/{request_id}/approve")
    def approve(request_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
        """Release under the same checks (consent is fetched and verified again now), then send to the platform."""
        require_staff(principal)
        req = _pending(db, request_id)
        result = release.answer(db, req, _claims_of(req), manual_approved=True)
        req.decided_by = principal.display_name
        record_audit(db, AuditEvent, principal, "records.request_review", "record_request", str(req.id), "approved",
                     req.referral_ref, {"result": req.status, "items": req.item_count})
        deliver(db, req, result)
        db.commit()
        return _out(req)

    @router.post("/e2e/record-requests/{request_id}/decline")
    def decline(request_id: int, body: DeclineIn, db: Session = Depends(get_db),
                principal: Principal = Depends(get_principal)):
        require_staff(principal)
        req = _pending(db, request_id)
        refusal = {"reason": body.reason, "categories": [],
                   "message": body.note.strip() or release.policy.REFUSAL_REASONS[body.reason]}
        req.status, req.refusals = "refused", [refusal]
        req.decided_by, req.decided_at = principal.display_name, datetime.now(timezone.utc)
        record_audit(db, AuditEvent, principal, "records.request_review", "record_request", str(req.id), "declined",
                     req.referral_ref, {"reason": body.reason})
        deliver(db, req, {"request_key": req.request_key, "status": "refused", "refusals": [refusal],
                          "policy_version": req.policy_version, "notes": [], "batch": None})
        db.commit()
        return _out(req)

    @router.post("/e2e/record-requests/{request_id}/redeliver")
    def redeliver(request_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
        """A reviewed answer that did not reach the platform: answered again (new data key) and sent."""
        require_staff(principal)
        req = db.get(RecordRequest, request_id)
        if req is None or req.delivered_at is not None or req.status in ("pending_manual_review", "received"):
            raise HTTPException(409, {"code": "nothing_to_send", "message": "Nothing waiting to be sent"})
        result = release.answer(db, req, _claims_of(req), manual_approved=True) if req.status != "refused" else \
            {"request_key": req.request_key, "status": "refused", "refusals": req.refusals,
             "policy_version": req.policy_version, "notes": [], "batch": None}
        deliver(db, req, result)
        db.commit()
        return _out(req)

    return router
