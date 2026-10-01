"""Specialty checklist and supported discrepancy detection (FR-35 to FR-38).

The checklist judges referral *completeness* against agreed requirements; it
never recommends investigations. A value that changed over time is not a
conflict: only the supported discrepancy types below are reported.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache

from refcommon.db import utcnow
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import SOURCES, settings
from ..integration.sources import source_name
from ..medications.service import current_entries, source_states
from ..models import EvidenceItem, Referral, ReviewItem


@dataclass
class Finding:
    item_key: str
    checklist_item_id: str
    kind: str  # missing | unresolved | discrepancy
    title: str
    detail: str
    blocking: bool
    override_allowed: bool
    clinical: bool
    evidence_ids: list[int] = field(default_factory=list)


@lru_cache
def checklist(specialty: str = "orthodontics") -> dict:
    path = settings.repo_root / "rules" / "checklists" / f"{specialty}.v1.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _evidence(db: Session, referral_id: int) -> list[EvidenceItem]:
    return list(db.scalars(select(EvidenceItem).where(
        EvidenceItem.referral_id == referral_id, EvidenceItem.superseded_by.is_(None),
        EvidenceItem.verification_status.notin_(["invalidated", "access_revoked"])).order_by(EvidenceItem.id)))


def _norm_dose(text: str | None) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def _when(ev: EvidenceItem) -> str:
    return ev.clinical_time.date().isoformat() if ev.clinical_time else "date not recorded"


def evaluate(db: Session, referral: Referral) -> list[Finding]:
    cfg = checklist(referral.specialty)
    items = {i["id"]: i for i in cfg["items"]}
    evidence = _evidence(db, referral.id)
    findings: list[Finding] = []

    def add(item_id: str, kind: str, title: str, detail: str, key_suffix: str = "", ev_ids: list[int] | None = None):
        meta = items[item_id]
        findings.append(Finding(item_key=item_id + (f":{key_suffix}" if key_suffix else ""), checklist_item_id=item_id,
                                kind=kind, title=title, detail=detail, blocking=meta["blocking"],
                                override_allowed=meta["override_allowed"], clinical=meta["clinical"],
                                evidence_ids=ev_ids or []))

    if len((referral.reason or "").strip()) < 10:
        add("CL-REASON", "missing", items["CL-REASON"]["title"], "Enter the reason for referral (at least a short sentence).")
    if not referral.priority:
        add("CL-PRIORITY", "missing", items["CL-PRIORITY"]["title"], "A clinician must select the priority; the system never assigns urgency.")
    if referral.procedure_status == "not_stated":
        add("CL-PROCEDURE", "missing", items["CL-PROCEDURE"]["title"],
            "Select the planned procedure or explicitly record that it is unknown.")
    if not referral.referring_clinician_id:
        add("CL-CLINICIAN", "missing", items["CL-CLINICIAN"]["title"], "Assign the referring clinician.")

    history = [e for e in evidence if e.category in ("condition", "consultation") and e.selected and e.review_state != "excluded"]
    if not history:
        add("CL-HISTORY", "missing", items["CL-HISTORY"]["title"],
            "No documented condition or prior consultation is selected for the brief. Select relevant history or mark not applicable.")

    entries = current_entries(db, referral.id)
    unverified = [e for e in entries if e.use_status == "unverified"]
    if unverified:
        add("CL-MEDS-VERIFIED", "unresolved", items["CL-MEDS-VERIFIED"]["title"],
            f"{len(unverified)} medication entr{'y' if len(unverified) == 1 else 'ies'} awaiting clinician current-use "
            f"verification: {', '.join(e.original_name for e in unverified)}",
            ev_ids=[e.evidence_id for e in unverified])

    for s in source_states(db, referral):
        if s.status == "successful":
            continue
        check = "CL-MED-SOURCES" if SOURCES.get(s.institution, {}).get("medication_source") else "CL-SOURCES"
        add(check, "unresolved", f"{s.name}: {s.status.replace('_', ' ')}",
            f"Records from {s.name} are {s.status.replace('_', ' ')}. Their absence is not an absence of history; "
            "retry retrieval or record this limitation.", key_suffix=s.institution)

    for e in evidence:
        if e.origin not in ("document", "manual") or not e.selected or e.review_state == "excluded":
            continue
        if e.review_state == "unresolved" or e.verification_status != "verified":
            state = "marked unresolved" if e.review_state == "unresolved" else "not yet clinician-verified"
            kind = "Document field" if e.origin == "document" else "Manually entered field"
            add("CL-DOC-FIELDS", "unresolved", f"{kind} {state}: {e.display}",
                "Verify, correct, exclude, or record the uncertainty for this extracted field.",
                key_suffix=str(e.id), ev_ids=[e.id])

    # D-MED-DOSE: same ingredient, current records, different dose instructions
    by_ingredient: dict[str, list] = {}
    for m in entries:
        if m.ingredient and m.use_status != "historical_stopped" and (m.source_status or "") not in ("stopped", "completed"):
            by_ingredient.setdefault(m.ingredient, []).append(m)
    ev_by_id = {e.id: e for e in evidence}
    for ingredient, meds in sorted(by_ingredient.items()):
        doses = {_norm_dose(m.dose) for m in meds if m.dose}
        if len(doses) > 1:
            parts = []
            for m in meds:
                ev = ev_by_id.get(m.evidence_id)
                parts.append(f"{m.source_label}: '{m.dose}' ({_when(ev) if ev else 'date not recorded'})")
            add("CL-DISCREPANCY", "discrepancy", f"Dose differs between records for {ingredient}",
                "Records disagree: " + " vs ".join(parts) + ". Review both sources and record a resolution or the remaining uncertainty.",
                key_suffix=f"D-MED-DOSE:{ingredient}", ev_ids=[m.evidence_id for m in meds])

    # D-LAB-SAME-TIME: same test on the same collection date with different values
    labs: dict[tuple[str, str], list[EvidenceItem]] = {}
    for e in evidence:
        if e.category != "lab":
            continue
        cur = e.current or e.original
        codes = [c.get("code") for c in cur.get("coding", []) if c.get("code")]
        test_key = codes[0] if codes else (cur.get("test") or "").lower()
        labs.setdefault((test_key, _when(e)), []).append(e)
    for (test_key, day), items_ in sorted(labs.items()):
        values = {str((i.current or i.original).get("value") or (i.current or i.original).get("value_text")) for i in items_}
        if len(items_) > 1 and len(values) > 1 and day != "date not recorded":
            desc = " vs ".join(f"{source_name(i.source_institution)} {i.display} ({_when(i)})" for i in items_)
            add("CL-DISCREPANCY", "discrepancy", f"Conflicting results for the same test on {day}",
                f"{desc}. Results from different dates are not treated as conflicts.",
                key_suffix=f"D-LAB-SAME-TIME:{test_key}:{day}", ev_ids=[i.id for i in items_])
    return findings


def refresh(db: Session, referral: Referral) -> list[ReviewItem]:
    findings = evaluate(db, referral)
    version = checklist(referral.specialty)["version"]
    existing = {ri.item_key: ri for ri in db.scalars(select(ReviewItem).where(ReviewItem.referral_id == referral.id))}
    seen = set()
    for f in findings:
        seen.add(f.item_key)
        ri = existing.get(f.item_key)
        if ri is None:
            db.add(ReviewItem(referral_id=referral.id, item_key=f.item_key, kind=f.kind, checklist_item_id=f.checklist_item_id,
                              checklist_version=version, title=f.title, detail=f.detail, evidence_ids=f.evidence_ids,
                              blocking=f.blocking, override_allowed=f.override_allowed, clinical=f.clinical))
            continue
        ri.title, ri.detail, ri.evidence_ids = f.title, f.detail, f.evidence_ids
        if ri.status in ("obsolete",) or (ri.status == "resolved" and ri.resolved_by == "system"):
            ri.status = "open"
            ri.resolution = None
            ri.resolved_by = None
            ri.resolved_at = None
    for key, ri in existing.items():
        if key in seen or ri.kind == "link_invalidated" or ri.checklist_item_id is None:
            continue
        if ri.status == "open":
            ri.status = "resolved"
            ri.resolution = "Automatically resolved: the required information is now present"
            ri.resolved_by = "system"
            ri.resolved_at = utcnow()
    db.flush()
    return list(db.scalars(select(ReviewItem).where(ReviewItem.referral_id == referral.id).order_by(ReviewItem.id)))


def checklist_summary(db: Session, referral: Referral) -> list[dict]:
    cfg = checklist(referral.specialty)
    items = list(db.scalars(select(ReviewItem).where(ReviewItem.referral_id == referral.id)))
    out = []
    for c in cfg["items"]:
        related = [i for i in items if i.checklist_item_id == c["id"] and i.status != "obsolete"]
        open_ = [i for i in related if i.status == "open"]
        if open_:
            state = "missing" if any(i.kind == "missing" for i in open_) else (
                "conflict" if any(i.kind == "discrepancy" for i in open_) else "unresolved")
        elif any(i.status == "not_applicable" for i in related):
            state = "not_applicable"
        elif any(i.status in ("overridden", "uncertainty_recorded") for i in related):
            state = "limitation_recorded"
        else:
            state = "present"
        out.append({"id": c["id"], "title": c["title"], "state": state, "blocking": c["blocking"],
                    "override_allowed": c["override_allowed"], "open_items": [i.id for i in open_]})
    return out
