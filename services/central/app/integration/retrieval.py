"""Referral-specific retrieval across the three source services."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from refcommon.auth import Principal
from refcommon.db import utcnow
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import SOURCES
from ..identity.links import verified_counterparts
from ..models import EvidenceItem, Referral, SourceRetrieval
from ..security import audit
from . import importer, sources


def retrieval_targets(db: Session, referral: Referral) -> list[tuple[str, str, int | None]]:
    targets: list[tuple[str, str, int | None]] = [(referral.patient_institution, referral.patient_local_id, None)]
    for inst, (local_id, link_id) in verified_counterparts(db, referral.patient_institution, referral.patient_local_id).items():
        if inst in SOURCES and inst != referral.patient_institution:
            targets.append((inst, local_id, link_id))
    return targets


def retrieve(db: Session, referral: Referral, principal: Principal, only: str | None = None) -> list[SourceRetrieval]:
    targets = [t for t in retrieval_targets(db, referral) if only in (None, t[0])]
    with ThreadPoolExecutor(max_workers=len(targets) or 1) as pool:
        calls = list(pool.map(lambda t: sources.fetch_records(t[0], t[1], principal, referral.reference), targets))

    results: list[SourceRetrieval] = []
    for (inst, local_id, link_id), call in zip(targets, calls):
        sr = SourceRetrieval(
            referral_id=referral.id, source_institution=inst, local_patient_id=local_id, link_id=link_id,
            status=call.status, message=call.message, retryable=call.retryable, attempts=call.attempts,
            duration_ms=call.duration_ms, requested_by=principal.display_name, withheld=call.withheld,
        )
        if call.status == "denied":
            _revoke_retained(db, referral, inst, principal)
        if call.bundle is not None:
            mapped, invalid = importer.parse_bundle(call.bundle)
            sr.record_count = len(mapped)
            sr.invalid_count = len(invalid)
            new, dup = _import(db, referral, inst, local_id, link_id, mapped)
            sr.new_count, sr.duplicate_count = new, dup
            if invalid and not mapped:
                sr.status = "invalid"
                sr.message = f"All {len(invalid)} returned records failed validation"
            elif invalid or call.withheld:
                sr.status = "partial"
                parts = []
                if invalid:
                    parts.append(f"{len(invalid)} record(s) failed validation and were excluded")
                if call.withheld:
                    parts.append("; ".join(call.withheld))
                sr.message = ". ".join(parts)
            elif not mapped:
                sr.status = "empty"
                sr.message = "Source responded but holds no records for this patient in the requested categories"
            else:
                sr.message = f"{len(mapped)} record(s): {new} new, {dup} already imported"
            if invalid:
                sr.withheld = list(sr.withheld) + [f"invalid {i['resourceType']}/{i['id']}: {'; '.join(i['problems'])}" for i in invalid]
        db.add(sr)
        audit(db, principal, "records.retrieve", "source", inst, sr.status, referral.id,
              {"local_patient_id": local_id, "link_id": link_id, "records": sr.record_count, "new": sr.new_count,
               "duplicates": sr.duplicate_count, "invalid": sr.invalid_count, "message": sr.message})
        results.append(sr)
    db.flush()
    return results


def _import(db: Session, referral: Referral, inst: str, local_id: str, link_id: int | None,
            mapped: list[importer.Mapped]) -> tuple[int, int]:
    new = dup = 0
    for m in mapped:
        exists = db.scalars(select(EvidenceItem).where(
            EvidenceItem.referral_id == referral.id, EvidenceItem.source_institution == inst,
            EvidenceItem.source_record_type == m.record_type, EvidenceItem.source_record_id == m.record_id,
            EvidenceItem.source_record_version == m.version)).first()
        if exists:
            if exists.verification_status == "access_revoked":
                exists.verification_status = "source_record"  # source authorized it again
            dup += 1
            continue
        prior = db.scalars(select(EvidenceItem).where(
            EvidenceItem.referral_id == referral.id, EvidenceItem.source_institution == inst,
            EvidenceItem.source_record_type == m.record_type, EvidenceItem.source_record_id == m.record_id,
            EvidenceItem.superseded_by.is_(None))).first()
        item = EvidenceItem(
            referral_id=referral.id, patient_institution=inst, patient_local_id=local_id, origin="source",
            source_institution=inst, source_record_type=m.record_type, source_record_id=m.record_id,
            source_record_version=m.version, link_id=link_id, category=m.category, display=m.display,
            original=m.original, current=m.original, fhir=m.resource, clinical_time=m.clinical_time,
            retrieved_at=utcnow(), review_state="imported", verification_status="source_record",
            selected=(m.category in importer.DEFAULT_SELECTED) if prior is None else prior.selected,
        )
        db.add(item)
        db.flush()
        if prior is not None:
            prior.superseded_by = item.id
            prior.selected = False
        new += 1
    return new, dup


def _revoke_retained(db: Session, referral: Referral, inst: str, principal: Principal) -> None:
    """If a source now denies access, centrally retained copies from it stop being usable (FR-05)."""
    items = db.scalars(select(EvidenceItem).where(
        EvidenceItem.referral_id == referral.id, EvidenceItem.source_institution == inst,
        EvidenceItem.origin == "source", EvidenceItem.verification_status != "access_revoked")).all()
    for item in items:
        item.verification_status = "access_revoked"
        item.selected = False
    if items:
        audit(db, principal, "evidence.access_revoked", "source", inst, "success", referral.id,
              {"items": [i.id for i in items]})
