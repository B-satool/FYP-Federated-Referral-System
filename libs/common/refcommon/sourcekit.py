"""Building blocks shared by every institution service (clinic, laboratory, hospital).

Every institution makes its own access decisions. Its own staff read its own records by role. Another
institution's request for a referral's records arrives as a signed request from the platform and is decided by
this institution's adapter under the patient's signed consent and its own policy (spec v4 section 6; see
services/provider/app/release.py). The per-patient sharing grants of earlier versions are gone (approval A3).
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import JSON, DateTime, Integer, String, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from . import fhir
from .auth import Principal, forbid
from .db import utcnow

ALL_CATEGORIES = ("demographics", "conditions", "surgeries", "visits", "medications", "labs", "imaging", "documents")

# What each role may read from its OWN institution's records through these endpoints. Staff handle the process
# and never read record content (spec v4 D14): they find the patient, nothing more.
OWN_ROLE_CATEGORIES: dict[str, set[str]] = {
    "clinician": set(ALL_CATEGORIES),
    "clinic_staff": {"demographics"},
    "diagnostics_staff": {"demographics", "labs", "imaging"},
}


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


class Decision(BaseModel):
    allowed: set[str]
    denied: set[str]
    reason: str


def decide_access(principal: Principal, own_institution: str, requested: set[str]) -> Decision:
    """Which requested categories this institution's own staff may read, by role. Nobody from another
    institution reads records through these endpoints: referral records travel encrypted under consent."""
    if principal.institution_id != own_institution:
        return Decision(allowed=set(), denied=requested,
                        reason="records for another institution are requested under the patient's consent")
    role_cats: set[str] = set()
    for role, cats in OWN_ROLE_CATEGORIES.items():
        if role in principal.roles:
            role_cats |= cats
    allowed = requested & role_cats
    return Decision(allowed=allowed, denied=requested - allowed,
                    reason="own institution" if allowed else "role has no record access at this institution")


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


def build_admin_router(own_institution: str, audit_model, get_db, get_principal) -> APIRouter:
    """Audit viewing for this institution's administrators."""
    router = APIRouter(prefix="/admin", tags=["source administration"])

    @router.get("/audit")
    def list_audit(limit: int = Query(200, le=1000), db: Session = Depends(get_db),
                   principal: Principal = Depends(get_principal)):
        if principal.institution_id != own_institution or "institution_admin" not in principal.roles:
            raise forbid("Only this institution's administrators can read its audit trail")
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
