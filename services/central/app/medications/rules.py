"""Medication rules stored in the database and edited in the app.

Each change creates a new version as a draft. A rule raises flags only once a
clinical reviewer approves that exact version; approving a newer version
supersedes the older one.
"""
from __future__ import annotations

from refcommon.exchange import content_hash
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import MedicationRule
from .evaluator import Rule

HASHED = ("rule_id", "version", "title", "drug_class", "procedure_tags", "message", "rationale", "reference")


def rule_hash(r: MedicationRule | dict) -> str:
    get = (lambda k: r[k]) if isinstance(r, dict) else (lambda k: getattr(r, k))
    return content_hash({k: get(k) for k in HASHED})


def active_rules(db: Session) -> list[Rule]:
    rows = db.scalars(select(MedicationRule).where(MedicationRule.status == "approved")
                      .order_by(MedicationRule.rule_id, MedicationRule.version.desc())).all()
    latest: dict[str, MedicationRule] = {}
    for r in rows:
        if r.content_hash != rule_hash(r):
            continue  # content changed outside the app: the approval no longer applies
        latest.setdefault(r.rule_id, r)
    return [Rule(rule_id=r.rule_id, version=r.version, drug_class=r.drug_class, procedure_tags=tuple(r.procedure_tags),
                 title=r.title, message=r.message, rationale=r.rationale, reference=r.reference)
            for r in latest.values()]
