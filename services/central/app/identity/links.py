"""Verified patient links. A link is never inferred from matching IDs or names (FR-09)."""
from __future__ import annotations

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from ..models import PatientLink


def links_for(db: Session, institution: str, local_id: str, statuses: tuple[str, ...] | None = None) -> list[PatientLink]:
    stmt = select(PatientLink).where(or_(
        and_(PatientLink.a_institution == institution, PatientLink.a_local_id == local_id),
        and_(PatientLink.b_institution == institution, PatientLink.b_local_id == local_id),
    )).order_by(PatientLink.id)
    if statuses:
        stmt = stmt.where(PatientLink.status.in_(statuses))
    return list(db.scalars(stmt))


def counterpart(link: PatientLink, institution: str, local_id: str) -> tuple[str, str]:
    if link.a_institution == institution and link.a_local_id == local_id:
        return link.b_institution, link.b_local_id
    return link.a_institution, link.a_local_id


def verified_counterparts(db: Session, institution: str, local_id: str) -> dict[str, tuple[str, int]]:
    """institution -> (local id, link id) for every VERIFIED link of this patient record."""
    out: dict[str, tuple[str, int]] = {}
    for link in links_for(db, institution, local_id, ("verified",)):
        inst, other = counterpart(link, institution, local_id)
        out[inst] = (other, link.id)
    return out


def link_out(link: PatientLink) -> dict:
    return {
        "id": link.id, "a_institution": link.a_institution, "a_local_id": link.a_local_id,
        "b_institution": link.b_institution, "b_local_id": link.b_local_id, "status": link.status,
        "basis": link.basis, "match_check": link.match_check, "proposed_by": link.proposed_by,
        "proposed_at": link.proposed_at, "verified_by": link.verified_by, "verified_at": link.verified_at,
        "invalidated_by": link.invalidated_by, "invalidated_at": link.invalidated_at,
        "invalidation_reason": link.invalidation_reason,
    }
