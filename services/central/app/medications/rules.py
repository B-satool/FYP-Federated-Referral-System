"""Medication rules: manual rules edited in the app, and imported data (interactions, label rules).

Manual rules: each change creates a new version as a draft. A manual rule raises flags only once a
clinical reviewer approves that exact version; approving a newer version supersedes the older one.
Imported rules (DDInter interactions, drug-label rules) apply as loaded, labelled automatically
generated and not clinically reviewed, with their source shown on every flag.
"""
from __future__ import annotations

from refcommon.exchange import content_hash
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..models import DrugInteraction, Ingredient, LabelRule, MedicationRule, RulesetRelease
from .evaluator import Interaction, LabelRule as LabelRuleIn, Rule

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


def components(db: Session) -> dict[str, list[str]]:
    """Combination products -> their ingredients."""
    return {i.name: list(i.components) for i in db.scalars(select(Ingredient)) if i.components}


def interaction_coverage(db: Session) -> frozenset[str]:
    return frozenset(i.name for i in db.scalars(select(Ingredient).where(Ingredient.in_interaction_source.is_(True))))


def interactions_for(db: Session, ingredients: set[str]) -> list[Interaction]:
    if len(ingredients) < 2:
        return []
    rows = db.scalars(select(DrugInteraction).where(DrugInteraction.ingredient_a.in_(ingredients),
                                                    DrugInteraction.ingredient_b.in_(ingredients))
                      .order_by(DrugInteraction.ingredient_a, DrugInteraction.ingredient_b))
    return [Interaction(r.ingredient_a, r.ingredient_b, r.severity, r.source_ref, r.source_version) for r in rows]


def label_rules_for(db: Session, ingredients: set[str]) -> list[LabelRuleIn]:
    rows = db.scalars(select(LabelRule).where(LabelRule.status == "auto_extracted", LabelRule.ingredient.in_(ingredients))
                      .order_by(LabelRule.rule_key))
    return [LabelRuleIn(r.rule_key, r.kind, r.ingredient, r.target, r.target_label, r.severity_hint, r.summary, r.quote,
                        r.section, r.source_name, r.source_ref, r.source_version) for r in rows]


def ruleset_hash(db: Session, manual: list[Rule]) -> str:
    """Fingerprint of everything that can raise a flag: the latest release of imported data plus
    the approved manual rule versions."""
    release = db.scalars(select(RulesetRelease).order_by(RulesetRelease.id.desc())).first()
    return content_hash({"imported": release.hash if release else None,
                         "manual": sorted(f"{r.rule_id}v{r.version}" for r in manual)})


def search_interactions(db: Session, q: str, limit: int = 200) -> list[DrugInteraction]:
    stmt = select(DrugInteraction)
    if q.strip():
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(or_(DrugInteraction.ingredient_a.ilike(like), DrugInteraction.ingredient_b.ilike(like)))
    return list(db.scalars(stmt.order_by(DrugInteraction.ingredient_a, DrugInteraction.ingredient_b).limit(limit)))
