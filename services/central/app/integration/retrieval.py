"""Referral-specific retrieval: the most recent record of each kind of institution.

* The referring institution's own record is always included.
* For each other linked institution (verified links only) the platform asks when the
  patient was last seen there. It then retrieves from the most recently visited
  hospital, clinic and laboratory only. Older ones are listed as skipped, with the dates.
* A source that is unavailable or denies access is never skipped silently: it is
  recorded with that outcome, which the referral carries as a limitation.
* Each institution returns only what a referral needs (current medicines; visits,
  results and imaging since the window start).
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

from refcommon.auth import Principal
from refcommon.db import utcnow
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import INSTITUTIONS, SOURCES, settings
from ..identity.links import links_for, verified_counterparts
from ..models import EvidenceItem, Referral, SourceRetrieval
from ..security import audit
from . import importer, sources

KIND_WORD = {"hospital": "hospital", "clinic": "clinic", "laboratory": "laboratory"}


def window_start() -> date:
    return date.today() - timedelta(days=settings.referral_window_days)


def linked_sources(db: Session, referral: Referral) -> list[tuple[str, str, int | None]]:
    """Own record plus every verified records link: (institution, local id, link id). Intake links
    (made when a referral or order arrived somewhere) are not record sources: that record is the
    receiver's own, and a patient registered as new there holds no earlier history."""
    out: list[tuple[str, str, int | None]] = [(referral.patient_institution, referral.patient_local_id, None)]
    new_records = {x.id for x in links_for(db, referral.patient_institution, referral.patient_local_id, ("verified",))
                   if x.registered_new or x.kind == "intake"}
    for inst, (local_id, link_id) in verified_counterparts(db, referral.patient_institution, referral.patient_local_id).items():
        if inst in SOURCES and inst != referral.patient_institution and link_id not in new_records:
            out.append((inst, local_id, link_id))
    return out


def retrieval_targets(db: Session, referral: Referral) -> list[tuple[str, str, int | None]]:
    """The sources used by the latest retrieval (everything not skipped)."""
    latest = latest_by_source(db, referral)
    return [(inst, local, link) for inst, local, link in linked_sources(db, referral)
            if inst not in latest or latest[inst].status != "skipped"]


def latest_by_source(db: Session, referral: Referral) -> dict[str, SourceRetrieval]:
    out: dict[str, SourceRetrieval] = {}
    for sr in db.scalars(select(SourceRetrieval).where(SourceRetrieval.referral_id == referral.id)
                         .order_by(SourceRetrieval.id)):
        out[sr.source_institution] = sr
    return out


def retrieve(db: Session, referral: Referral, principal: Principal) -> list[SourceRetrieval]:
    targets = linked_sources(db, referral)
    own, others = targets[0], targets[1:]
    since = window_start().isoformat()
    with ThreadPoolExecutor(max_workers=max(1, len(others))) as pool:
        activity = list(pool.map(lambda t: sources.last_activity(t[0], t[1], principal, referral.reference), others))

    # choose the most recently visited institution of each kind
    chosen: list[tuple[str, str, int | None]] = [own]
    chosen_dates: dict[str, str | None] = {}
    results: list[SourceRetrieval] = []
    by_kind: dict[str, list[tuple[tuple[str, str, int | None], str | None]]] = {}
    for t, (status, last, message) in zip(others, activity):
        kind = INSTITUTIONS[t[0]]["kind"]
        if status != "successful":
            results.append(_row(referral, t, principal, status, message, kind, None, since,
                                retryable=status == "unavailable"))
            if status == "denied":
                _revoke_retained(db, referral, t[0], principal)
            continue
        by_kind.setdefault(kind, []).append((t, last))
    for kind, items in by_kind.items():
        items.sort(key=lambda x: x[1] or "", reverse=True)
        (best, best_date), rest = items[0], items[1:]
        chosen.append(best)
        for t, last in rest:
            note = (f"Not retrieved: last seen here on {last}" if last else "Not retrieved: no visits, tests or scans recorded here")
            note += (f". {sources.source_name(best[0])} is the most recently visited {KIND_WORD.get(kind, kind)}"
                     f" ({best_date or 'date not recorded'}), so its records are used instead.")
            results.append(_row(referral, t, principal, "skipped", note, kind, last, since))
            _deselect(db, referral, t[0])
        chosen_dates[best[0]] = best_date

    with ThreadPoolExecutor(max_workers=len(chosen)) as pool:
        calls = list(pool.map(lambda t: sources.fetch_records(t[0], t[1], principal, referral.reference, since), chosen))
    for t, call in zip(chosen, calls):
        inst, local_id, link_id = t
        sr = _row(referral, t, principal, call.status, call.message, INSTITUTIONS[inst]["kind"],
                  chosen_dates.get(inst), since, retryable=call.retryable, attempts=call.attempts,
                  duration_ms=call.duration_ms, withheld=call.withheld)
        if call.status == "denied":
            _revoke_retained(db, referral, inst, principal)
        if call.bundle is not None:
            mapped, invalid = importer.parse_bundle(call.bundle)
            sr.record_count, sr.invalid_count = len(mapped), len(invalid)
            sr.new_count, sr.duplicate_count = _import(db, referral, inst, local_id, link_id, mapped)
            if invalid and not mapped:
                sr.status, sr.message = "invalid", f"All {len(invalid)} returned records failed validation"
            elif invalid or call.withheld:
                sr.status = "partial"
                parts = [f"{len(invalid)} record(s) failed validation and were excluded"] if invalid else []
                sr.message = ". ".join(parts + list(call.withheld))
            elif not mapped:
                sr.status, sr.message = "empty", "Responded, but holds no referral-relevant records for this patient"
            else:
                sr.message = f"{len(mapped)} record(s): {sr.new_count} new, {sr.duplicate_count} already retrieved"
            if invalid:
                sr.withheld = list(sr.withheld) + [f"invalid {i['resourceType']}/{i['id']}: {'; '.join(i['problems'])}"
                                                   for i in invalid]
        results.append(sr)
    for sr in results:
        db.add(sr)
        audit(db, principal, "records.retrieve", "source", sr.source_institution, sr.status, referral.id,
              {"local_patient_id": sr.local_patient_id, "link_id": sr.link_id, "records": sr.record_count,
               "new": sr.new_count, "last_activity": sr.last_activity, "since": since, "message": sr.message})
    db.flush()
    return results


def _row(referral: Referral, t: tuple[str, str, int | None], principal: Principal, status: str, message: str,
         kind: str, last: str | None, since: str, **extra) -> SourceRetrieval:
    inst, local_id, link_id = t
    return SourceRetrieval(referral_id=referral.id, source_institution=inst, local_patient_id=local_id, link_id=link_id,
                           institution_kind=kind, last_activity=last, window_start=since, status=status,
                           message=message, requested_by=principal.display_name,
                           retryable=extra.get("retryable", False), attempts=extra.get("attempts", 1),
                           duration_ms=extra.get("duration_ms", 0), withheld=extra.get("withheld", []))


def _import(db: Session, referral: Referral, inst: str, local_id: str, link_id: int | None,
            mapped: list[importer.Mapped]) -> tuple[int, int]:
    new = dup = 0
    for m in mapped:
        if m.category == "demographics":
            continue
        exists = db.scalars(select(EvidenceItem).where(
            EvidenceItem.referral_id == referral.id, EvidenceItem.source_institution == inst,
            EvidenceItem.source_record_type == m.record_type, EvidenceItem.source_record_id == m.record_id,
            EvidenceItem.source_record_version == m.version)).first()
        if exists:
            if exists.verification_status == "access_revoked":
                exists.verification_status = "source_record"
            if not exists.selected and m.category in importer.DEFAULT_SELECTED and exists.review_state != "excluded":
                exists.selected = True
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


def _deselect(db: Session, referral: Referral, inst: str) -> None:
    """Records from a source that is no longer the most recent of its kind stop being used."""
    for ev in db.scalars(select(EvidenceItem).where(EvidenceItem.referral_id == referral.id,
                                                    EvidenceItem.source_institution == inst,
                                                    EvidenceItem.origin == "source", EvidenceItem.selected.is_(True))):
        ev.selected = False


def _revoke_retained(db: Session, referral: Referral, inst: str, principal: Principal) -> None:
    """If a source now denies access, centrally retained copies from it stop being usable."""
    items = db.scalars(select(EvidenceItem).where(
        EvidenceItem.referral_id == referral.id, EvidenceItem.source_institution == inst,
        EvidenceItem.origin == "source", EvidenceItem.verification_status != "access_revoked")).all()
    for item in items:
        item.verification_status = "access_revoked"
        item.selected = False
    if items:
        audit(db, principal, "evidence.access_revoked", "source", inst, "success", referral.id,
              {"items": [i.id for i in items]})
