"""Building blocks shared by every institution service (clinic, laboratory, hospital).

Every institution makes its own access decision from its own database:
membership of the institution, the caller's role, and explicit access grants.
A grant is created when this institution's own staff approve a patient-link
request; the central platform cannot create or bypass one.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import JSON, DateTime, Integer, String, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from . import fhir
from .auth import Principal, forbid
from .db import utcnow

ALL_CATEGORIES = ("demographics", "conditions", "surgeries", "visits", "medications", "labs", "imaging", "documents")

# What each role may read from its OWN institution's records. Staff prepare referrals,
# so they read the same referral-relevant records as doctors.
OWN_ROLE_CATEGORIES: dict[str, set[str]] = {
    "clinician": set(ALL_CATEGORIES),
    "clinic_staff": set(ALL_CATEGORIES),
    "diagnostics_staff": {"demographics", "labs", "imaging"},
}
# Roles from another institution that may use a grant at all.
GRANTEE_ROLES = {"clinician", "clinic_staff"}

# Access grants are temporary. New grants always get an expiry; the duration is chosen up to this
# limit (days). Grants created before expiry existed have none and are reported as "legacy" so an
# administrator can renew or revoke them.
DEFAULT_GRANT_DAYS = int(os.environ.get("DEFAULT_GRANT_DAYS", "14"))
MAX_GRANT_DAYS = int(os.environ.get("MAX_GRANT_DAYS", "30"))


def normalize_cnic(value: str | None) -> str:
    """CNIC as 13 digits (dashes and spaces removed). Used only to look a patient up;
    a match is shown to a person who decides, it never links records by itself."""
    return re.sub(r"\D", "", value or "")


class AuditMixin:
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_id: Mapped[str] = mapped_column(String(100))
    actor_name: Mapped[str] = mapped_column(String(200))
    institution_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    action: Mapped[str] = mapped_column(String(100), index=True)
    target_type: Mapped[str] = mapped_column(String(60))
    target_id: Mapped[str] = mapped_column(String(100))
    outcome: Mapped[str] = mapped_column(String(20))
    referral_context: Mapped[str | None] = mapped_column(String(60), nullable=True)
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class AccessGrantMixin:
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    grantee_institution: Mapped[str] = mapped_column(String(50), index=True)
    local_patient_id: Mapped[str] = mapped_column(String(50), index=True)
    categories: Mapped[list[str]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="active")
    basis: Mapped[str] = mapped_column(Text, default="")
    granted_by: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    revoked_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Temporary access: the grant stops working at expires_at (NULL only for legacy grants).
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    # The referral this grant was opened for, so it can be closed with the referral.
    referral_ref: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)


def _aware(value: datetime) -> datetime:
    """Treat naive datetimes (SQLite) as UTC."""
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def grant_state(grant, now: datetime | None = None) -> str:
    """active | expired | revoked | legacy_no_expiry (still active, but has no end date)."""
    now = now or utcnow()
    if grant.status != "active":
        return "revoked"
    if grant.expires_at is None:
        return "legacy_no_expiry"
    return "expired" if _aware(grant.expires_at) <= _aware(now) else "active"


def grant_is_live(grant, now: datetime | None = None) -> bool:
    return grant_state(grant, now) in {"active", "legacy_no_expiry"}


def grant_expiry(days: int | None = None) -> datetime:
    days = DEFAULT_GRANT_DAYS if days is None else days
    if not 1 <= days <= MAX_GRANT_DAYS:
        raise HTTPException(422, {"code": "invalid_duration", "message": f"Access can be granted for 1 to {MAX_GRANT_DAYS} days"})
    return utcnow() + timedelta(days=days)


class Decision(BaseModel):
    allowed: set[str]
    denied: set[str]
    reason: str
    # True when a grant for this patient exists but has expired. Callers must show
    # "access expired", not "no records" (an unavailable source is never "none").
    expired: bool = False


def decide_access(
    db: Session,
    grant_model,
    principal: Principal,
    own_institution: str,
    local_patient_id: str,
    requested: set[str],
) -> Decision:
    """Return which requested data categories this caller may read."""
    if principal.institution_id == own_institution:
        role_cats: set[str] = set()
        for role, cats in OWN_ROLE_CATEGORIES.items():
            if role in principal.roles:
                role_cats |= cats
        allowed = requested & role_cats
        return Decision(
            allowed=allowed,
            denied=requested - allowed,
            reason="own institution" if allowed else "role has no record access at this institution",
        )
    if not principal.has_any(*GRANTEE_ROLES):
        return Decision(allowed=set(), denied=requested, reason="role may not access another institution's records")
    grants = db.scalars(
        select(grant_model).where(
            grant_model.grantee_institution == principal.institution_id,
            grant_model.local_patient_id == local_patient_id,
            grant_model.status == "active",
        )
    ).all()
    now = utcnow()
    granted: set[str] = set()
    expired_cats: set[str] = set()
    for g in grants:
        if grant_is_live(g, now):
            granted |= set(g.categories)
        else:
            expired_cats |= set(g.categories)
    allowed = requested & granted
    expired = bool(not allowed and (requested & expired_cats))
    if allowed:
        reason = "active access grant"
    elif expired:
        reason = "access grant expired"
    else:
        reason = "no active access grant for this patient"
    return Decision(allowed=allowed, denied=requested - allowed, reason=reason, expired=expired)


def record_audit(db: Session, audit_model, principal: Principal | None, action: str, target_type: str,
                 target_id: str, outcome: str, referral_context: str | None = None, detail: dict | None = None,
                 actor_override: tuple[str, str, str | None] | None = None) -> None:
    if actor_override:
        actor_id, actor_name, institution = actor_override
    elif principal:
        actor_id, actor_name, institution = principal.subject, principal.display_name, principal.institution_id
    else:
        actor_id, actor_name, institution = "anonymous", "anonymous", None
    db.add(audit_model(
        actor_id=actor_id,
        actor_name=actor_name,
        institution_id=institution,
        action=action,
        target_type=target_type,
        target_id=str(target_id),
        outcome=outcome,
        referral_context=referral_context,
        detail=detail or {},
    ))


class GrantIn(BaseModel):
    grantee_institution: str
    local_patient_id: str
    categories: list[str]
    basis: str = ""
    duration_days: int = DEFAULT_GRANT_DAYS
    referral_ref: str | None = None


class ExtendIn(BaseModel):
    days: int
    reason: str


class RevokeByReferralIn(BaseModel):
    referral_ref: str
    reason: str = "referral finished"


def build_admin_router(own_institution: str, grant_model, audit_model, patient_exists: Callable[[Session, str], bool],
                       get_db, get_principal) -> APIRouter:
    """Grant management and audit viewing for this source's institution administrators."""
    router = APIRouter(prefix="/admin", tags=["source administration"])

    def require_admin(principal: Principal) -> None:
        if principal.institution_id != own_institution or "institution_admin" not in principal.roles:
            raise forbid("Only this institution's administrators can manage source access")

    def grant_out(g) -> dict:
        return {
            "id": g.id, "grantee_institution": g.grantee_institution, "local_patient_id": g.local_patient_id,
            "categories": g.categories, "status": g.status, "basis": g.basis, "granted_by": g.granted_by,
            "created_at": g.created_at, "revoked_by": g.revoked_by, "revoked_at": g.revoked_at,
            "expires_at": g.expires_at, "referral_ref": g.referral_ref, "state": grant_state(g),
        }

    @router.get("/grants")
    def list_grants(db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
        require_admin(principal)
        return [grant_out(g) for g in db.scalars(select(grant_model).order_by(grant_model.id.desc())).all()]

    @router.post("/grants", status_code=201)
    def create_grant(body: GrantIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
        require_admin(principal)
        bad = set(body.categories) - set(ALL_CATEGORIES)
        if bad or not body.categories:
            raise HTTPException(422, {"code": "invalid_categories", "message": f"Unknown categories: {sorted(bad)}"})
        expires = grant_expiry(body.duration_days)
        if not patient_exists(db, body.local_patient_id):
            raise HTTPException(404, {"code": "patient_not_found", "message": "No such local patient"})
        g = grant_model(grantee_institution=body.grantee_institution, local_patient_id=body.local_patient_id,
                        categories=sorted(set(body.categories)), basis=body.basis, granted_by=principal.display_name,
                        expires_at=expires, referral_ref=body.referral_ref)
        db.add(g)
        db.flush()
        record_audit(db, audit_model, principal, "grant.create", "access_grant", str(g.id), "success",
                     referral_context=g.referral_ref,
                     detail={"grantee": g.grantee_institution, "patient": g.local_patient_id,
                             "categories": g.categories, "expires_at": g.expires_at.isoformat()})
        db.commit()
        return grant_out(g)

    @router.post("/grants/{grant_id}/extend")
    def extend_grant(grant_id: int, body: ExtendIn, db: Session = Depends(get_db),
                     principal: Principal = Depends(get_principal)):
        """Only this source's administrator can extend. Counted from now, capped at MAX_GRANT_DAYS."""
        require_admin(principal)
        if not 1 <= body.days <= MAX_GRANT_DAYS or not body.reason.strip():
            raise HTTPException(422, {"code": "invalid_extension", "message": f"Give a reason and 1 to {MAX_GRANT_DAYS} days"})
        g = db.get(grant_model, grant_id)
        if not g:
            raise HTTPException(404, {"code": "not_found", "message": "Grant not found"})
        if g.status != "active":
            raise HTTPException(409, {"code": "grant_revoked", "message": "A revoked grant cannot be extended"})
        g.expires_at = utcnow() + timedelta(days=body.days)
        record_audit(db, audit_model, principal, "grant.extend", "access_grant", str(g.id), "success",
                     referral_context=g.referral_ref,
                     detail={"reason": body.reason, "new_expires_at": g.expires_at.isoformat()})
        db.commit()
        return grant_out(g)

    @router.post("/grants/{grant_id}/revoke")
    def revoke_grant(grant_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
        require_admin(principal)
        g = db.get(grant_model, grant_id)
        if not g:
            raise HTTPException(404, {"code": "not_found", "message": "Grant not found"})
        g.status = "revoked"
        g.revoked_by = principal.display_name
        g.revoked_at = utcnow()
        record_audit(db, audit_model, principal, "grant.revoke", "access_grant", str(g.id), "success")
        db.commit()
        return grant_out(g)

    @router.get("/audit")
    def list_audit(limit: int = Query(200, le=1000), db: Session = Depends(get_db),
                   principal: Principal = Depends(get_principal)):
        require_admin(principal)
        rows = db.scalars(select(audit_model).order_by(audit_model.id.desc()).limit(limit)).all()
        return [{
            "id": r.id, "actor_name": r.actor_name, "institution_id": r.institution_id, "action": r.action,
            "target_type": r.target_type, "target_id": r.target_id, "outcome": r.outcome,
            "referral_context": r.referral_context, "detail": r.detail, "created_at": r.created_at,
        } for r in rows]

    return router


def build_grant_service_router(own_institution: str, grant_model, audit_model, get_db, get_principal) -> APIRouter:
    """Lets the central platform ask THIS source to close grants opened for a finished referral.

    Central never writes a source database. It calls this endpoint with its service token and the
    source revokes its own grants. If the call fails, each grant's expiry date is the backstop.
    """
    router = APIRouter(prefix="/grants", tags=["grant close-out"])

    @router.post("/revoke-by-referral")
    def revoke_by_referral(body: RevokeByReferralIn, db: Session = Depends(get_db),
                           principal: Principal = Depends(get_principal)):
        if "svc_central" not in principal.roles:
            raise forbid("Only the central platform service can close grants by referral")
        grants = db.scalars(select(grant_model).where(grant_model.referral_ref == body.referral_ref,
                                                      grant_model.status == "active")).all()
        for g in grants:
            g.status, g.revoked_by, g.revoked_at = "revoked", "central platform (referral finished)", utcnow()
            record_audit(db, audit_model, principal, "grant.revoke", "access_grant", str(g.id), "success",
                         referral_context=body.referral_ref, detail={"reason": body.reason, "institution": own_institution})
        db.commit()
        return {"revoked": len(grants), "referral_ref": body.referral_ref}

    return router


def records_bundle(resources: list[dict], withheld: set[str], institution_id: str, self_link: str | None = None) -> dict:
    """Searchset Bundle; withheld categories are reported as an OperationOutcome so the
    caller can show a *partial* result rather than silently missing data."""
    b = fhir.bundle(resources, "searchset", institution_id=institution_id, self_link=self_link)
    for entry in b["entry"]:
        entry["search"] = {"mode": "match"}
    if withheld:
        b["entry"].append({
            "resource": fhir.operation_outcome(
                "warning", "suppressed",
                f"Categories withheld by source authorization: {', '.join(sorted(withheld))}",
            ),
            "search": {"mode": "outcome"},
        })
    return b


def health_router(check_db: Callable[[], None]) -> APIRouter:
    router = APIRouter(tags=["health"])

    @router.get("/health")
    def health():
        return {"status": "ok"}

    @router.get("/ready")
    def ready():
        try:
            check_db()
        except Exception as exc:  # noqa: BLE001 - readiness reports any dependency failure
            raise HTTPException(503, {"code": "not_ready", "message": str(exc)}) from exc
        return {"status": "ready"}

    return router
