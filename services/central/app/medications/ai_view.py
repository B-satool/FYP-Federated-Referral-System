"""AI suggestions for one referral's current medicines, with the doctor's decision on each."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AiSuggestion, Referral, SuggestionReview
from . import rules, service, suggestions


def for_referral(db: Session, r: Referral) -> list[dict]:
    """Suggestions for pairs among the current medicines that the interaction source does not cover."""
    ings = {i for e in service.current_entries(db, r.id) if e.mapping_status in ("mapped", "staff_mapped")
            for i in (e.ingredients or ([e.ingredient] if e.ingredient else []))}
    covered = {(x.ingredient_a, x.ingredient_b) for x in rules.interactions_for(db, ings)}
    stored = {s.pair_key: suggestions.Suggestion(s.pair_key, s.ingredient_a, s.ingredient_b, s.score, s.reason, s.model_version,
                                                 s.data_version)
              for s in db.scalars(select(AiSuggestion).where(AiSuggestion.ingredient_a.in_(ings), AiSuggestion.ingredient_b.in_(ings)))}
    reviews = {v.pair_key: v for v in db.scalars(select(SuggestionReview).where(SuggestionReview.referral_id == r.id)
                                                 .order_by(SuggestionReview.id))}
    out = []
    for s in suggestions.suggestions_for(ings, stored, covered):
        v = reviews.get(s.pair_key)
        out.append({"pair_key": s.pair_key, "ingredients": [s.ingredient_a, s.ingredient_b], "score": s.score, "reason": s.reason,
                    "model_version": s.model_version, "data_version": s.data_version, "label": suggestions.LABEL,
                    "review": {"decision": v.decision, "note": v.note, "by": v.reviewer, "at": v.created_at.isoformat()}
                    if v else None})
    return out
