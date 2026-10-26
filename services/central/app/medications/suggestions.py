"""AI suggestions: possible drug-drug clashes for pairs with no entry in the interaction source.

Scored offline by scripts/train_ai_suggestions.py; the app only looks the stored suggestions up.
This module is separate from the evaluator on purpose: a suggestion can never add, remove,
downgrade or hide a flag, never blocks sending and is never sent as part of the referral.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

LABEL = "AI suggestion, unverified"


@dataclass(frozen=True)
class Suggestion:
    pair_key: str
    ingredient_a: str
    ingredient_b: str
    score: float
    reason: str
    model_version: str
    data_version: str


def suggestions_for(ingredients: set[str], stored: dict[str, Suggestion], interaction_pairs: set[tuple[str, str]]) -> list[Suggestion]:
    """Stored suggestions for pairs among the current medicines, skipping any pair the interaction
    source covers (that pair is handled by the verified table, whatever the model scored)."""
    out = []
    for a, b in combinations(sorted(ingredients), 2):
        if (a, b) in interaction_pairs:
            continue
        s = stored.get(f"{a}|{b}")
        if s is not None:
            out.append(s)
    return sorted(out, key=lambda s: (-s.score, s.pair_key))
