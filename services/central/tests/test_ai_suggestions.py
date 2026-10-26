"""AI suggestion layer (spec v2, section 8): suggestions never touch flags.

Run inside the central image (see test_evaluator.py).
"""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from app.medications.suggestions import LABEL, Suggestion, suggestions_for

from test_flagging import INTERACTIONS, SURGERY, med, run

ROOT = Path("/srv/assets/rules")
if not ROOT.exists():
    ROOT = Path(__file__).resolve().parents[3] / "rules"
FILE = ROOT / "ai" / "suggestions.json"
DATA = json.loads(FILE.read_text(encoding="utf-8")) if FILE.exists() else None
COVERED = {(x.ingredient_a, x.ingredient_b) for x in INTERACTIONS}


def stored(score: float | None = None) -> dict[str, Suggestion]:
    """The committed suggestions, plus one made-up suggestion for a pair DDInter does cover."""
    out = {}
    for s in (DATA or {}).get("suggestions", []):
        out[s["pair_key"]] = Suggestion(s["pair_key"], s["ingredient_a"], s["ingredient_b"], s["score"], s["reason"],
                                        DATA["model_version"], DATA["data_version"])
    a, b = sorted(next(iter(COVERED)))
    out[f"{a}|{b}"] = Suggestion(f"{a}|{b}", a, b, 0.99, "forced", "test", "test")
    if score is not None:
        out = {k: replace(v, score=score) for k, v in out.items()}
    return out


def test_pair_in_interaction_table_is_never_a_suggestion():
    a, b = sorted(next(iter(COVERED)))
    for score in (0.0, 1.0):
        assert all(s.pair_key != f"{a}|{b}" for s in suggestions_for({a, b}, stored(score), COVERED))


@pytest.mark.parametrize("score", [0.0, 1.0])
def test_forcing_scores_never_changes_flags(score):
    meds = [med("aspirin", "antiplatelet"), med("clopidogrel", "antiplatelet"), med("gliclazide", "sulfonylurea"),
            med("metformin", "biguanide")]
    before = [c.content() for c in run(meds, tags=SURGERY).candidates]
    suggestions_for({"aspirin", "clopidogrel", "gliclazide", "metformin"}, stored(score), COVERED)
    after = [c.content() for c in run(meds, tags=SURGERY).candidates]
    assert before == after  # the evaluator has no input from the model at all


def test_suggestions_only_for_current_medicines_and_carry_versions():
    if not DATA or not DATA["suggestions"]:
        pytest.skip("no suggestions trained")
    s = DATA["suggestions"][0]
    got = suggestions_for({s["ingredient_a"], s["ingredient_b"]}, stored(), COVERED)
    assert [x.pair_key for x in got] == [s["pair_key"]]
    assert got[0].model_version and got[0].data_version and got[0].ingredient_a and got[0].ingredient_b
    assert suggestions_for({s["ingredient_a"]}, stored(), COVERED) == []


def test_committed_suggestions_exclude_ddinter_pairs_and_are_labelled():
    if not DATA:
        pytest.skip("no suggestions trained")
    assert LABEL == "AI suggestion, not verified"
    for s in DATA["suggestions"]:
        assert (s["ingredient_a"], s["ingredient_b"]) not in COVERED
        assert s["ingredient_a"] < s["ingredient_b"] and s["score"] >= DATA["threshold"] and s["reason"]
