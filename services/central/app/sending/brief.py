"""The referral summary sent to the specialist, built from the checked records only.

It is laid out like a referral letter: reason, planned procedure, current medicines,
history, recent visits, investigations (grouped by panel) and imaging, then what could
not be obtained. It is deterministic (no language model): every record-derived line cites
the record it came from, an unavailable or skipped source is stated as a limitation (never
as 'no history'), and medication flags are not restated here; they travel separately as
structured flags from the approved rules.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import INSTITUTIONS, procedure_label
from ..integration.retrieval import latest_by_source
from ..medications import service as med
from ..models import EvidenceItem, MedicationEntry, Referral

SECTION_TITLES = {
    "reason": "Reason for referral",
    "procedure": "Planned procedure",
    "medications": "Current medicines",
    "conditions": "Medical history",
    "surgeries": "Previous surgery",
    "visits": "Recent visits (last 6 months)",
    "results": "Investigations",
    "imaging": "Imaging",
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
        return "Paper brought by the patient"
    return "Told by the patient"


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


def _st(text: str, ids: list[int], kind: str = "template", source: str | None = None, date: str | None = None,
        group: str | None = None) -> dict:
    return {"id": uuid.uuid4().hex[:10], "text": text, "evidence_ids": ids, "author_kind": kind, "author_name": None,
            "edited_by": None, "verification": "verified" if ids else "none", "source": source, "date": date,
            "group": group}


def _line(ev: EvidenceItem) -> tuple[str, str | None]:
    """The text of one record without the source, and its grouping."""
    o = ev.original or {}
    if ev.category == "lab":
        return ev.display, o.get("panel") or o.get("test")
    if ev.category == "visit":
        return (": ".join(x for x in (o.get("setting"), o.get("reason")) if x) or ev.display) + \
            (f". {o['summary']}" if o.get("summary") else ""), None
    return ev.display, None


def build(db: Session, referral: Referral) -> dict:
    secs: dict[str, list[dict]] = {k: [] for k in SECTION_TITLES}
    if referral.reason:
        secs["reason"].append({**_st(referral.reason, [], "clinician"), "author_name": referral.requesting_doctor_name})
    if referral.kind == "referral":
        text = procedure_label(referral.procedure_status, referral.planned_procedure)
        if referral.procedure_status == "planned" and not referral.procedure_tags:
            text += " (what it involves was not recorded, so procedure-related medicine checks were not run)"
        secs["procedure"].append({**_st(text, [], "clinician"), "author_name": referral.requesting_doctor_name})
    for e in med.current_entries(db, referral.id):
        members = [e, *db.scalars(select(MedicationEntry).where(MedicationEntry.duplicate_of == e.id))]
        also = sorted({m.source_label for m in members})
        text = f"{e.original_name}" + (f" ({e.brand})" if e.brand and e.brand.lower() not in e.original_name.lower() else "")
        text += f" {e.dose or '(dose not recorded)'}"
        if e.over_the_counter:
            text += ", over the counter"
        if e.dose_differs:
            text += ". A different dose is recorded elsewhere"
        secs["medications"].append(_st(text, [m.evidence_id for m in members], source="; ".join(also)))
    for ev in permitted_evidence(db, referral):
        sec = CATEGORY_SECTION.get(ev.category)
        if not sec:
            continue
        text, group = _line(ev)
        date = ev.clinical_time.date().isoformat() if ev.clinical_time else None
        secs[sec].append(_st(text, [ev.id], source=_source(ev), date=date, group=group))
    # investigations: newest panel first, results of one panel together
    order: dict[str, int] = {}
    for i, st in enumerate(secs["results"]):
        order.setdefault(st["group"] or "", i)
    secs["results"].sort(key=lambda st: (order[st["group"] or ""], st["text"]))
    limitations = system_limitations(db, referral)
    for lim in limitations:
        secs["outstanding"].append(_st(lim, []))
    evidence_ids = sorted({i for s in secs.values() for st in s for i in st["evidence_ids"]})
    return {"sections": [{"key": k, "title": SECTION_TITLES[k], "statements": v} for k, v in secs.items() if v],
            "limitations": limitations, "evidence_ids": evidence_ids}
