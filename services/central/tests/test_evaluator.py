"""T5 - table-driven checks for the deterministic medication evaluator (FR-61 to FR-72).

Run: docker compose run --rm --no-deps central python -m pytest tests -q
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.medications.evaluator import EvalInput, MedInput, Rule, SourceState, evaluate_medications

RULES_FILE = Path(__file__).resolve().parents[1] / "assets" / "rules" / "medication" / "orthodontics.v1.json"
if not RULES_FILE.exists():  # running from the repository instead of the image
    RULES_FILE = Path(__file__).resolve().parents[3] / "rules" / "medication" / "orthodontics.v1.json"
RULES = tuple(Rule.from_dict(r) for r in json.loads(RULES_FILE.read_text())["rules"])
CLINIC_OK = SourceState("clinic-a", "Clinic A", True, "successful")


def med(name="Warfarin 5 mg", ingredient="warfarin", cls="anticoagulant", mapping="mapped", use="confirmed_current", eid=1):
    return MedInput(entry_id=eid, original_name=name, ingredient=ingredient, drug_class=cls, mapping_status=mapping,
                    use_status=use, source_label="Clinic A prescription RX-1 v1", evidence_ids=(eid,))


def run(meds, procedure="tooth_extraction", status="known", sources=(CLINIC_OK,), rules=RULES):
    return evaluate_medications(EvalInput("orthodontics", status, procedure if status == "known" else None,
                                          tuple(meds), tuple(sources), tuple(rules)))


def kinds(out):
    return sorted(c.kind for c in out.candidates)


CASES = [
    # id, meds, procedure, procedure_status, sources, expected kinds, expected outcome
    ("confirmed matching use", [med()], "tooth_extraction", "known", (CLINIC_OK,), ["confirmed"], "flags"),
    ("stopped use", [med(use="historical_stopped")], "tooth_extraction", "known", (CLINIC_OK,), [], "no_match"),
    ("uncertain use", [med(use="uncertain")], "tooth_extraction", "known", (CLINIC_OK,), ["possible_use"], "no_match"),
    ("unverified use", [med(use="unverified")], "tooth_extraction", "known", (CLINIC_OK,), ["possible_use"], "no_match"),
    ("ambiguous mapping", [med(name="Calcium D", ingredient=None, cls=None, mapping="ambiguous")], "tooth_extraction",
     "known", (CLINIC_OK,), ["ambiguous_mapping"], "no_match"),
    ("missing procedure", [med()], None, "unknown", (CLINIC_OK,), ["procedure_context_required"], "no_match"),
    ("denied source", [med()], "tooth_extraction", "known",
     (SourceState("clinic-a", "Clinic A", True, "denied"),), ["confirmed", "history_incomplete"], "flags"),
    ("unavailable source alone", [], "tooth_extraction", "known",
     (SourceState("clinic-a", "Clinic A", True, "unavailable"),), ["history_incomplete"], "no_match"),
    ("no match", [med(name="Metformin", ingredient="metformin", cls="biguanide")], "tooth_extraction", "known",
     (CLINIC_OK,), [], "no_match"),
    ("procedure outside rule", [med()], "fixed_appliance", "known", (CLINIC_OK,), [], "no_match"),
    ("specialty-only rule without procedure", [med("Alendronate", "alendronate", "bisphosphonate")], None, "unknown",
     (CLINIC_OK,), ["confirmed", "procedure_context_required"], "flags"),
    ("lab not a medication source", [med()], "tooth_extraction", "known",
     (CLINIC_OK, SourceState("lab-b", "Lab B", False, "unavailable")), ["confirmed"], "flags"),
]


@pytest.mark.parametrize("name,meds,proc,status,sources,expected,outcome", CASES, ids=[c[0] for c in CASES])
def test_rule_table(name, meds, proc, status, sources, expected, outcome):
    out = run(meds, proc, status, sources)
    assert kinds(out) == sorted(expected)
    assert out.outcome == outcome


def test_flag_content_is_traceable():
    c = run([med()]).candidates[0]
    assert (c.rule_id, c.rule_version) == ("ORTHO-ANTICOAG-SURG", 1)
    assert c.source_label and c.evidence_ids == [1] and c.current_use_status == "confirmed_current"
    assert c.medication == "Warfarin 5 mg" and c.drug_class == "anticoagulant"


def test_same_medication_from_two_records_gives_one_flag():
    out = run([med(eid=1), med(name="Coumadin 5 mg", eid=2)])
    confirmed = [c for c in out.candidates if c.kind == "confirmed"]
    assert len(confirmed) == 1 and confirmed[0].evidence_ids == [1, 2]


def test_deterministic_repeat_evaluation():
    a, b = run([med(), med(use="uncertain", eid=3)]), run([med(), med(use="uncertain", eid=3)])
    assert [c.content() for c in a.candidates] == [c.content() for c in b.candidates]


def test_changed_procedure_context_changes_result():
    assert kinds(run([med()], "tooth_extraction")) == ["confirmed"]
    assert kinds(run([med()], "orthodontic_assessment")) == []


def test_changed_rule_version_changes_flag_identity():
    v2 = tuple(Rule(**{**r.__dict__, "version": 2}) if r.rule_id == "ORTHO-ANTICOAG-SURG" else r for r in RULES)
    a, b = run([med()]).candidates[0], run([med()], rules=v2).candidates[0]
    assert a.flag_key == b.flag_key and a.content() != b.content()


def test_no_approved_rules_is_unsupported_coverage_not_negative():
    out = run([med()], rules=())
    assert out.outcome == "unsupported_coverage" and "not a negative result" in out.summary_message


def test_no_match_message_states_coverage_limits():
    out = run([med("Metformin", "metformin", "biguanide")])
    assert "not treatment clearance" in out.summary_message and "available verified records" in out.summary_message


def test_evaluation_failure_raises_distinctly():
    broken = (Rule("BROKEN", 1, "anticoagulant", "orthodontics", True, (), "t", "m"),)
    with pytest.raises(ValueError):
        run([med()], rules=broken)


@pytest.mark.parametrize("word", ["stop", "discontinue", "withhold", "start taking", "switch", "urgent"])
def test_flags_never_advise_medication_change_or_urgency(word):
    out = run([med(), med("Alendronate", "alendronate", "bisphosphonate", eid=2), med(use="uncertain", eid=3)], None, "unknown")
    texts = " ".join(f"{c.title} {c.message}" for c in out.candidates).lower()
    assert word not in texts
    for r in RULES:
        assert word not in f"{r.title} {r.message}".lower()
