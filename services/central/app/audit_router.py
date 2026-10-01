"""Audit trail views (FR-59, FR-60) and session/reference metadata."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from refcommon.auth import Principal
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .config import INSTITUTIONS, PRIORITIES, PROCEDURES, SPECIALTIES, settings
from .db import get_db
from .models import AuditEvent, Referral, User
from .referrals.state import STATUS_LABELS
from .security import get_principal, load_referral, require_roles

router = APIRouter(tags=["audit and metadata"])


def _out(a: AuditEvent) -> dict:
    return {"id": a.id, "actor_id": a.actor_id, "actor_name": a.actor_name, "institution_id": a.institution_id,
            "action": a.action, "target_type": a.target_type, "target_id": a.target_id, "referral_id": a.referral_id,
            "outcome": a.outcome, "detail": a.detail, "created_at": a.created_at}


@router.get("/referrals/{referral_id}/audit")
def referral_audit(referral_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    r = load_referral(db, referral_id, principal, "view_audit")
    return [_out(a) for a in db.scalars(select(AuditEvent).where(AuditEvent.referral_id == r.id).order_by(AuditEvent.id))]


@router.get("/admin/audit")
def institution_audit(action: str | None = None, outcome: str | None = None, limit: int = Query(300, le=2000),
                      db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """Administrators see audit metadata for their institution (no clinical record content)."""
    require_roles(principal, "institution_admin", action="admin.audit")
    own_refs = select(Referral.id).where(Referral.source_institution == principal.institution_id)
    stmt = select(AuditEvent).where(or_(AuditEvent.institution_id == principal.institution_id,
                                        AuditEvent.referral_id.in_(own_refs)))
    if action:
        stmt = stmt.where(AuditEvent.action.ilike(f"%{action}%"))
    if outcome:
        stmt = stmt.where(AuditEvent.outcome == outcome)
    rows = db.scalars(stmt.order_by(AuditEvent.id.desc()).limit(limit)).all()
    out = []
    for a in rows:
        item = _out(a)
        item["detail"] = {k: v for k, v in (a.detail or {}).items() if k in
                          ("reason", "message", "from", "to", "outcome", "trigger", "changes", "action", "status")}
        out.append(item)
    return out


@router.get("/me")
def me(db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    u = db.get(User, principal.subject)
    return {"id": principal.subject, "username": principal.username, "name": principal.display_name,
            "institution_id": principal.institution_id,
            "institution_name": INSTITUTIONS.get(principal.institution_id or "", {}).get("name"),
            "institution_kind": INSTITUTIONS.get(principal.institution_id or "", {}).get("kind"),
            "roles": sorted(principal.roles), "account_status": u.account_status if u else "active"}


@router.get("/reference-data")
def reference_data(principal: Principal = Depends(get_principal)):
    return {"institutions": INSTITUTIONS, "specialties": SPECIALTIES, "procedures": PROCEDURES, "priorities": PRIORITIES,
            "statuses": STATUS_LABELS, "llm_configured": settings.llm_configured,
            "llm_model": settings.llm_model if settings.llm_configured else None,
            "limits": {"max_upload_mb": settings.max_upload_bytes // (1024 * 1024), "max_pages": settings.max_pages,
                       "formats": ["PDF", "PNG", "JPEG"], "language": "English"}}
