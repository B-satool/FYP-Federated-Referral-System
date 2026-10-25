"""Patient links. A link is verified only by staff at the other institution; it is never
inferred from matching IDs or names."""
from __future__ import annotations

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from ..config import institution_name
from ..models import PatientLink


def links_for(db: Session, institution: str, local_id: str, statuses: tuple[str, ...] | None = None) -> list[PatientLink]:
    stmt = select(PatientLink).where(or_(
        and_(PatientLink.requester_institution == institution, PatientLink.requester_local_id == local_id),
        and_(PatientLink.target_institution == institution, PatientLink.target_local_id == local_id),
    )).order_by(PatientLink.id)
    if statuses:
        stmt = stmt.where(PatientLink.status.in_(statuses))
    return list(db.scalars(stmt))


def counterpart(link: PatientLink, institution: str, local_id: str) -> tuple[str, str | None]:
    if link.requester_institution == institution and link.requester_local_id == local_id:
        return link.target_institution, link.target_local_id
    return link.requester_institution, link.requester_local_id


def verified_counterparts(db: Session, institution: str, local_id: str) -> dict[str, tuple[str, int]]:
    """institution -> (local id, link id) for every VERIFIED link of this patient record."""
    out: dict[str, tuple[str, int]] = {}
    for link in links_for(db, institution, local_id, ("verified",)):
        inst, other = counterpart(link, institution, local_id)
        if other:
            out[inst] = (other, link.id)
    return out


def open_request(db: Session, institution: str, local_id: str, target: str) -> PatientLink | None:
    return db.scalars(select(PatientLink).where(
        PatientLink.requester_institution == institution, PatientLink.requester_local_id == local_id,
        PatientLink.target_institution == target, PatientLink.status.in_(("requested", "verified")))).first()


def link_out(link: PatientLink) -> dict:
    return {
        "id": link.id, "requester_institution": link.requester_institution,
        "requester_name": institution_name(link.requester_institution), "requester_local_id": link.requester_local_id,
        "target_institution": link.target_institution, "target_name": institution_name(link.target_institution),
        "target_local_id": link.target_local_id, "patient_name": link.patient_name,
        "patient_birth_date": link.patient_birth_date, "patient_sex": link.patient_sex, "patient_cnic": link.patient_cnic,
        "referral_id": link.referral_id, "purpose": link.purpose, "status": link.status,
        "requested_by": link.requested_by, "requested_at": link.requested_at, "decided_by": link.decided_by,
        "decided_at": link.decided_at, "decision_note": link.decision_note, "match_check": link.match_check,
        "registered_new": link.registered_new, "invalidated_by": link.invalidated_by,
        "invalidated_at": link.invalidated_at, "invalidation_reason": link.invalidation_reason,
    }
