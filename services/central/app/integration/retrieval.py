"""Where a referral's records can come from: the patient's own record at the referring institution, and every
institution that confirmed the patient (verified records links).

The records themselves are no longer imported here in plain text. They are requested under the patient's consent
and released encrypted by each institution's adapter (spec v4 5.6; records/requests.py). Visits, results and
imaging are asked for from history_start(), set by the destination specialty.
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import SOURCES, history_years_for, settings
from ..identity.links import links_for, verified_counterparts
from ..models import Referral, SourceRetrieval


def window_start() -> date:
    """Start of the 6-month window used by the default record selection."""
    return date.today() - timedelta(days=settings.referral_window_days)


def history_start(referral: Referral | None = None) -> date:
    """How far back visits, results and imaging are asked for, for this referral's specialty."""
    years = history_years_for(referral.destination_department if referral else None)
    return date.today() - timedelta(days=365 * years)


def linked_sources(db: Session, referral: Referral) -> list[tuple[str, str, int | None]]:
    """Own record plus every verified records link: (institution, local id, link id). Intake links (made when a
    referral or order arrived somewhere) are not record sources: that record is the receiver's own, and a patient
    registered as new there holds no earlier history."""
    out: list[tuple[str, str, int | None]] = [(referral.patient_institution, referral.patient_local_id, None)]
    new_records = {x.id for x in links_for(db, referral.patient_institution, referral.patient_local_id, ("verified",))
                   if x.registered_new or x.kind == "intake"}
    for inst, (local_id, link_id) in verified_counterparts(db, referral.patient_institution, referral.patient_local_id).items():
        if inst in SOURCES and inst != referral.patient_institution and link_id not in new_records:
            out.append((inst, local_id, link_id))
    return out


def latest_by_source(db: Session, referral: Referral) -> dict[str, SourceRetrieval]:
    """Plain-text retrievals made before spec v4 (kept only for referrals that already had them)."""
    out: dict[str, SourceRetrieval] = {}
    for sr in db.scalars(select(SourceRetrieval).where(SourceRetrieval.referral_id == referral.id)
                         .order_by(SourceRetrieval.id)):
        out[sr.source_institution] = sr
    return out


def retrieval_targets(db: Session, referral: Referral) -> list[tuple[str, str, int | None]]:
    latest = latest_by_source(db, referral)
    return [(inst, local, link) for inst, local, link in linked_sources(db, referral)
            if inst not in latest or latest[inst].status != "skipped"]
