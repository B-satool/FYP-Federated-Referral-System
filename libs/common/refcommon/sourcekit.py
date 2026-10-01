"""Building blocks shared by the clinic, laboratory and specialist services.

Every source makes its own access decision from its own database: membership
of the owning institution, the caller's role, and explicit access grants that
the source's administrator controls. The central platform cannot bypass this.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import JSON, DateTime, Integer, String, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from . import fhir
from .auth import Principal, forbid
from .db import utcnow

ALL_CATEGORIES = ("demographics", "encounters", "conditions", "medications", "labs", "documents", "consultations")

# What each role may read from its OWN institution's records.
OWN_ROLE_CATEGORIES: dict[str, set[str]] = {
    "clinician": set(ALL_CATEGORIES),
    "specialist": set(ALL_CATEGORIES),
    "clinic_staff": {"demographics", "encounters", "medications", "labs", "documents"},
    "lab_staff": {"demographics", "labs"},
}
# Roles from another institution that may use a grant at all.
GRANTEE_ROLES = {"clinician", "clinic_staff", "specialist"}


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


class Decision(BaseModel):
    allowed: set[str]
    denied: set[str]
    reason: str


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
    granted: set[str] = set()
    for g in grants:
        granted |= set(g.categories)
    allowed = requested & granted
    return Decision(
        allowed=allowed,
        denied=requested - allowed,
        reason="active access grant" if allowed else "no active access grant for this patient",
    )


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
        if not patient_exists(db, body.local_patient_id):
            raise HTTPException(404, {"code": "patient_not_found", "message": "No such local patient"})
        g = grant_model(grantee_institution=body.grantee_institution, local_patient_id=body.local_patient_id,
                        categories=sorted(set(body.categories)), basis=body.basis, granted_by=principal.display_name)
        db.add(g)
        db.flush()
        record_audit(db, audit_model, principal, "grant.create", "access_grant", str(g.id), "success",
                     detail={"grantee": g.grantee_institution, "patient": g.local_patient_id, "categories": g.categories})
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


class MatchIn(BaseModel):
    local_patient_id: str
    family: str
    given: str
    birth_date: str


def identity_match(patient, body: MatchIn) -> dict:
    """Field-by-field comparison used as verification evidence. Returns booleans only,
    never the source's demographics, so a failed match leaks nothing."""
    if patient is None:
        return {"record_exists": False, "family_match": False, "given_match": False, "birth_date_match": False}
    return {
        "record_exists": True,
        "family_match": patient.family.strip().lower() == body.family.strip().lower(),
        "given_match": patient.given.strip().lower() == body.given.strip().lower(),
        "birth_date_match": patient.birth_date.isoformat() == body.birth_date.strip(),
    }


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
