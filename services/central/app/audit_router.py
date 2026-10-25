"""Audit trail views, the signed-in user, and reference data for the forms."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from refcommon.auth import Principal
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .config import (
    DEPARTMENTS,
    DIAGNOSTIC_CATEGORIES,
    DRUG_CLASSES,
    INSTITUTIONS,
    PRACTITIONERS,
    PROCEDURE_TAGS,
    PROCEDURES,
    TEST_SUGGESTIONS,
    URGENCIES,
    URGENCY_NOTE,
    department_name,
    settings,
)
from .db import get_db
from .models import AuditEvent, Referral, User
from .referrals.state import STATUS_LABELS
from .security import get_principal, load_referral, require_roles

router = APIRouter(tags=["audit and reference data"])


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
    inst = INSTITUTIONS.get(principal.institution_id or "", {})
    return {"id": principal.subject, "username": principal.username, "name": principal.display_name,
            "institution_id": principal.institution_id, "institution_name": inst.get("name"),
            "institution_kind": inst.get("kind"), "department": principal.department,
            "department_name": department_name(principal.department),
            "department_kind": DEPARTMENTS.get(principal.department or "", {}).get("kind"),
            "roles": sorted(principal.roles), "account_status": u.account_status if u else "active"}


@router.get("/reference-data")
def reference_data(principal: Principal = Depends(get_principal)):
    institutions = {k: {x: y for x, y in v.items() if x != "url_env"} for k, v in INSTITUTIONS.items()
                    if k != "central-platform"}
    return {
        "institutions": institutions, "departments": DEPARTMENTS, "procedures": PROCEDURES,
        "procedure_tags": PROCEDURE_TAGS, "urgencies": URGENCIES, "urgency_note": URGENCY_NOTE,
        "statuses": STATUS_LABELS, "practitioners": PRACTITIONERS, "test_suggestions": TEST_SUGGESTIONS,
        "diagnostic_categories": DIAGNOSTIC_CATEGORIES, "drug_classes": DRUG_CLASSES,
        "referral_window_days": settings.referral_window_days,
        "llm_configured": settings.llm_configured,
        "limits": {"max_upload_mb": settings.max_upload_bytes // (1024 * 1024), "max_pages": settings.max_pages,
                   "formats": ["PDF", "PNG", "JPEG"], "language": "English"},
    }
