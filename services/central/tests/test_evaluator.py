"""Table-driven checks for the deterministic medication-against-procedure evaluator.

Uses the real seed rules (rules/medication/seed-rules.json) and procedure tags (app.config).
Run: docker compose run --rm --no-deps -v ${PWD}/services/central/tests:/srv/tests central python -m pytest tests -q
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.config import DRUG_CLASSES, PROCEDURES
from app.medications.evaluator import EvalInput, MedInput, Rule, SourceState, evaluate_medications

RULES_FILE = Path("/srv/assets/rules/medication/seed-rules.json")
if not RULES_FILE.exists():  # running from the repository instead of the image
    RULES_FILE = Path(__file__).resolve().parents[3] / "rules" / "medication" / "seed-rules.json"
RULES = tuple(Rule(rule_id=r["rule_id"], version=1, drug_class=r["drug_class"], procedure_tags=tuple(r["procedure_tags"]),
                   title=r["title"], message=r["message"]) for r in json.loads(RULES_FILE.read_text())["rules"])
OK = SourceState("drali", "Dr Ali's Clinic", "successful")
_ids = iter(range(1, 10_000))


def med(ingredient: str, cls: str | None, mapping: str = "mapped", name: str | None = None) -> MedInput:
    eid = next(_ids)
    return MedInput(entry_id=eid, original_name=name or ingredient.title(), ingredient=ingredient if mapping in ("mapped", "staff_mapped") else None,
                    drug_class=cls if mapping in ("mapped", "staff_mapped") else None, mapping_status=mapping,
                    source_label="Dr Ali's Clinic record", evidence_ids=(eid,))


def run(meds, procedure=None, status="known", sources=(OK,), rules=RULES):
    tags = tuple(PROCEDURES[procedure]["tags"]) if status == "known" and procedure else ()
    return evaluate_medications(EvalInput(status, procedure, tags, tuple(meds), tuple(sources), tuple(rules), DRUG_CLASSES))


def confirmed(out) -> set[tuple[str, str]]:
    return {(c.rule_id, c.medication.lower()) for c in out.candidates if c.kind == "confirmed"}


# The five seed patients (seed-data/patients/*.json, scenario.should_flag)
SCENARIOS = [
    ("P1 alendronate before oral surgery",
     [med("alendronic acid", "bisphosphonate"), med("metformin", "biguanide"), med("amlodipine", "calcium_channel_blocker")],
     "surgical_tooth_extraction", {("RULE-010", "alendronic acid")}),
    ("P2 metformin with contrast; aspirin and glimepiride not flagged for angiography",
     [med("metformin", "biguanide"), med("glimepiride", "sulfonylurea"), med("aspirin", "antiplatelet"),
      med("atorvastatin", "statin"), med("enalapril", "ace_inhibitor")],
     "coronary_angiography", {("RULE-005", "metformin")}),
    ("P3 aspirin and diclofenac before knee replacement",
     [med("diclofenac", "nsaid"), med("aspirin", "antiplatelet"), med("losartan", "arb"), med("esomeprazole", "proton_pump_inhibitor")],
     "total_knee_replacement", {("RULE-002", "aspirin"), ("RULE-003", "diclofenac")}),
    ("P4 ibuprofen before GI endoscopy",
     [med("propranolol", "beta_blocker"), med("omeprazole", "proton_pump_inhibitor"), med("paracetamol", "analgesic"),
      med("ibuprofen", "nsaid")],
     "upper_gi_endoscopy", {("RULE-004", "ibuprofen")}),
    ("P5 antiplatelets, insulin and metformin before cholecystectomy",
     [med("insulin glargine", "insulin"), med("metformin", "biguanide"), med("aspirin", "antiplatelet"),
      med("clopidogrel", "antiplatelet"), med("atorvastatin", "statin"), med("bisoprolol", "beta_blocker")],
     "laparoscopic_cholecystectomy",
     {("RULE-002", "aspirin"), ("RULE-002", "clopidogrel"), ("RULE-006", "metformin"), ("RULE-007", "insulin glargine")}),
]


@pytest.mark.parametrize("label,meds,procedure,expected", SCENARIOS, ids=[s[0] for s in SCENARIOS])
def test_seed_scenarios(label, meds, procedure, expected):
    out = run(meds, procedure)
    assert confirmed(out) == expected
    assert out.outcome == "flags"


def test_procedure_not_known_is_never_guessed():
    out = run([med("aspirin", "antiplatelet")], status="unknown")
    assert [c.kind for c in out.candidates] == ["procedure_not_checked"]
    assert out.outcome == "no_match"


def test_consultation_only_has_no_procedure_flags():
    out = run([med("warfarin", "anticoagulant")], status="none")
    assert out.candidates == [] and "consultation only" in out.summary_message


def test_unrecognised_medicine_is_reported_not_ignored():
    out = run([med("x", None, mapping="unmapped", name="Mystery tonic")], "laparoscopic_cholecystectomy")
    assert [c.kind for c in out.candidates] == ["unrecognised_medicine"]


def test_unavailable_source_is_a_limitation_not_none():
    out = run([med("aspirin", "antiplatelet")], "laparoscopic_cholecystectomy",
              sources=(OK, SourceState("ziauddin", "Ziauddin Hospital", "unavailable")))
    kinds = sorted(c.kind for c in out.candidates)
    assert kinds == ["confirmed", "records_incomplete"]
    assert "does not mean the absence" in next(c for c in out.candidates if c.kind == "records_incomplete").message


def test_no_rules_is_not_a_negative_result():
    out = run([med("aspirin", "antiplatelet")], "laparoscopic_cholecystectomy", rules=())
    assert out.outcome == "no_rules" and "not a negative result" in out.summary_message


def test_one_flag_per_medicine_and_rule_however_many_sources():
    out = run([med("aspirin", "antiplatelet"), med("aspirin", "antiplatelet", name="Disprin Cardio 75 mg")],
              "laparoscopic_cholecystectomy")
    flags = [c for c in out.candidates if c.kind == "confirmed"]
    assert len(flags) == 1 and len(flags[0].evidence_ids) == 2


def test_deterministic():
    meds = SCENARIOS[4][1]
    a, b = run(meds, "laparoscopic_cholecystectomy"), run(meds, "laparoscopic_cholecystectomy")
    assert [c.content() for c in a.candidates] == [c.content() for c in b.candidates]


def test_messages_never_advise_changing_a_medicine():
    for r in RULES:
        low = r.message.lower()
        assert not any(w in low for w in ("stop", "discontinue", "withhold", "do not take", "increase", "reduce the dose")), r.rule_id
