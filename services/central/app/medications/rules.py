"""Versioned medication rule files + in-app clinical approval (FR-61)."""
from __future__ import annotations

import json
from functools import lru_cache

from refcommon.exchange import content_hash
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import RuleApproval
from .evaluator import Rule


@lru_cache
def ruleset(specialty: str = "orthodontics") -> dict:
    path = settings.repo_root / "rules" / "medication" / f"{specialty}.v1.json"
    return json.loads(path.read_text(encoding="utf-8"))


def rule_hash(rule: dict) -> str:
    return content_hash(rule)


def all_rules(db: Session, specialty: str = "orthodontics") -> list[dict]:
    """Every rule in the file with its approval state from the database."""
    approvals = {(a.rule_id, a.rule_version): a for a in db.scalars(select(RuleApproval))}
    out = []
    for rule in ruleset(specialty)["rules"]:
        a = approvals.get((rule["rule_id"], rule["version"]))
        h = rule_hash(rule)
        state = "draft"
        if a is not None:
            if a.content_hash != h:
                state = "approval_invalid_content_changed"
            else:
                state = a.status
        out.append({
            **rule,
            "content_hash": h,
            "approval_state": state,
            "active": state == "approved",
            "reviewer": a.reviewer if a else None,
            "reference_checked": a.reference_checked if a else None,
            "decided_at": a.decided_at if a else None,
            "approval_note": a.note if a else None,
        })
    return out


def active_rules(db: Session, specialty: str) -> list[Rule]:
    try:
        rules = all_rules(db, specialty)
    except FileNotFoundError:
        return []
    return [Rule.from_dict(r) for r in rules if r["active"]]


def active_rule_versions(db: Session, specialty: str) -> dict[str, int]:
    return {r.rule_id: r.version for r in active_rules(db, specialty)}
