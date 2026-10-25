"""The referral summary sent to the specialist, built from the checked records only.

It is deterministic (no language model): every record-derived line cites the
record it came from, an unavailable or skipped source is stated as a limitation
(never as 'no history'), and medication flags are not restated here; they travel
separately as structured flags from the approved rules.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import DIAGNOSTIC_CATEGORIES, INSTITUTIONS, department_name
from ..integration.retrieval import latest_by_source
from ..medications import service as med
from ..models import DiagnosticRequest, EvidenceItem, MedicationEntry, Referral

SECTION_TITLES = {
    "reason": "Reason for referral",
    "medications": "Current medicines",
    "conditions": "Conditions",
    "surgeries": "Previous surgery",
    "visits": "Visits in the last 6 months",
    "results": "Recent test results",
    "imaging": "Recent imaging",
    "requests": "Tests and scans requested with this referral",
    "outstanding": "Not available or outstanding",
}
CATEGORY_SECTION = {"condition": "conditions", "surgery": "surgeries", "visit": "visits", "lab": "results",
                    "lab_report": "results", "imaging": "imaging"}
USABLE = ("source_record", "verified")


def permitted_evidence(db: Session, referral: Referral) -> list[EvidenceItem]:
    return list(db.scalars(select(EvidenceItem).where(
        EvidenceItem.referral_id == referral.id, EvidenceItem.selected.is_(True),
        EvidenceItem.superseded_by.is_(None), EvidenceItem.review_state != "excluded",
        EvidenceItem.verification_status.in_(USABLE)).order_by(EvidenceItem.clinical_time.desc().nulls_last(),
                                                              EvidenceItem.id)))


def _source(ev: EvidenceItem) -> str:
    if ev.origin == "source":
        return INSTITUTIONS.get(ev.source_institution, {}).get("name", ev.source_institution)
    if ev.origin == "document":
        return "paper brought by the patient"
    return "told by the patient"


def system_limitations(db: Session, referral: Referral) -> list[str]:
    out = []
    for sr in latest_by_source(db, referral).values():
        name = INSTITUTIONS.get(sr.source_institution, {}).get("name", sr.source_institution)
        if sr.status == "skipped":
            out.append(f"{name}: {sr.message}")
        elif sr.status not in ("successful", "empty"):
            out.append(f"{name}: records {sr.status.replace('_', ' ')}. Information from this source is not available.")
    for e in med.current_entries(db, referral.id):
        if e.mapping_status in ("unmapped", "ambiguous"):
            out.append(f"Medicine not recognised and not checked against the rules: {e.original_name}")
    return out


def _st(text: str, ids: list[int], kind: str = "template") -> dict:
    return {"id": uuid.uuid4().hex[:10], "text": text, "evidence_ids": ids, "author_kind": kind, "author_name": None,
            "edited_by": None, "verification": "verified" if ids else "none"}


def build(db: Session, referral: Referral) -> dict:
    secs: dict[str, list[dict]] = {k: [] for k in SECTION_TITLES}
    if referral.reason:
        secs["reason"].append({**_st(referral.reason, [], "clinician"), "author_name": referral.requesting_doctor_name})
    for e in med.current_entries(db, referral.id):
        members = [e, *db.scalars(select(MedicationEntry).where(MedicationEntry.duplicate_of == e.id))]
        also = sorted({m.source_label for m in members})
        text = f"{e.original_name}" + (f" ({e.brand})" if e.brand and e.brand.lower() not in e.original_name.lower() else "")
        text += f" - {e.dose or 'dose not recorded'}"
        if e.over_the_counter:
            text += ", over the counter"
        text += f". Source: {'; '.join(also)}"
        if e.dose_differs:
            text += ". Note: a different dose is recorded elsewhere"
        secs["medications"].append(_st(text, [m.evidence_id for m in members]))
    by_id: dict[int, EvidenceItem] = {}
    for ev in permitted_evidence(db, referral):
        sec = CATEGORY_SECTION.get(ev.category)
        if not sec:
            continue
        by_id[ev.id] = ev
        date = f" [{ev.clinical_time.date().isoformat()}]" if ev.clinical_time and ev.category in ("lab", "visit", "imaging") else ""
        secs[sec].append(_st(f"{ev.display}{date} - {_source(ev)}", [ev.id]))
    for dx in db.scalars(select(DiagnosticRequest).where(DiagnosticRequest.referral_id == referral.id,
                                                          DiagnosticRequest.status != "cancelled")):
        where = f"{INSTITUTIONS[dx.destination_institution]['name']}, {department_name(dx.destination_department)}"
        status = dx.status.replace("_", " ")
        secs["requests"].append(_st(f"{DIAGNOSTIC_CATEGORIES.get(dx.category, dx.category)}: {dx.test}"
                                    + (f" ({dx.body_area})" if dx.body_area else "")
                                    + f" at {where}. Question: {dx.clinical_question}. Status: {status}.", []))
    limitations = system_limitations(db, referral)
    for lim in limitations:
        secs["outstanding"].append(_st(lim, []))
    evidence_ids = sorted({i for s in secs.values() for st in s for i in st["evidence_ids"]})
    return {"sections": [{"key": k, "title": SECTION_TITLES[k], "statements": v} for k, v in secs.items() if v],
            "limitations": limitations, "evidence_ids": evidence_ids}
