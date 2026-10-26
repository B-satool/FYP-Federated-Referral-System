"""Source-backed flagging: DDInter interactions and drug-label rules (spec v2, section 9).

Uses the committed imported data (rules/interactions, rules/labels, rules/vocab), never rules written
to make a test pass. Run inside the central image (see test_evaluator.py).
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from app.config import DRUG_CLASSES
from app.medications import mapping
from app.medications.evaluator import EvalInput, Interaction, LabelRule, MedInput, Rule, SourceState, evaluate_medications
from app.medications.label_validation import Candidate, patient_categories, summary_for, validate

ROOT = Path("/srv/assets/rules")
if not ROOT.exists():
    ROOT = Path(__file__).resolve().parents[3] / "rules"
VOCAB = json.loads((ROOT / "vocab" / "label-targets.json").read_text(encoding="utf-8"))
INGREDIENTS = json.loads((ROOT / "terminology" / "ingredients.json").read_text(encoding="utf-8"))["ingredients"]
COMPONENTS = {i["name"]: tuple(i["components"]) for i in INGREDIENTS if i.get("components")}
REPORT = json.loads((ROOT / "interactions" / "ddinter-import-report.json").read_text(encoding="utf-8"))
COVERAGE = frozenset(i["name"] for i in INGREDIENTS if i.get("standard") and i["name"] not in REPORT["our_ingredients_not_in_ddinter"])
with (ROOT / "interactions" / "ddinter-subset.csv").open(encoding="utf-8") as fh:
    INTERACTIONS = tuple(Interaction(r["ingredient_a"], r["ingredient_b"], r["severity"], r["source_ref"], "test") for r in csv.DictReader(fh))
LABELS = json.loads((ROOT / "labels" / "label-rules.json").read_text(encoding="utf-8"))
LABEL_RULES = tuple(LabelRule(r["rule_key"], r["kind"], r["ingredient"], r["target"],
                              VOCAB["procedure" if r["kind"] == "drug_procedure" else "condition"][r["target"]]["label"],
                              r["severity_hint"], r["summary"], r["quote"], r["section"], r["source_name"], r["source_ref"],
                              r["source_version"]) for r in LABELS["rules"])
MANUAL = tuple(Rule(rule_id=r["rule_id"], version=1, drug_class=r["drug_class"], procedure_tags=tuple(r["procedure_tags"]),
                    title=r["title"], message=r["message"])
               for r in json.loads((ROOT / "medication" / "seed-rules.json").read_text())["rules"])
OK = SourceState("drali", "Dr Ali's Clinic", "successful")
SURGERY = ("major_surgery", "general_anaesthesia", "prolonged_fasting", "bleeding_risk")
_ids = iter(range(1, 10_000))


def med(ingredient: str | None, cls: str | None = None, status: str = "mapped", name: str | None = None) -> MedInput:
    eid = next(_ids)
    parts = COMPONENTS.get(ingredient or "", (ingredient,) if ingredient else ())
    return MedInput(entry_id=eid, original_name=name or (ingredient or "x").title(), ingredient=ingredient, drug_class=cls,
                    mapping_status=status, source_label="Dr Ali's Clinic record", evidence_ids=(eid,), ingredients=parts)


def run(meds, tags=(), status="planned", conditions=(), interactions=INTERACTIONS, labels=LABEL_RULES):
    return evaluate_medications(EvalInput(status, "procedure" if status == "planned" else None, tuple(tags), tuple(meds), (OK,),
                                          MANUAL, DRUG_CLASSES, tuple(interactions), tuple(labels), tuple(conditions), COVERAGE))


def kinds(out, kind):
    return [c for c in out.candidates if c.kind == kind]


# ---------------------------------------------------------------- golden cases (seed patients)
def test_p1_alendronate_dental_label_flag_with_quote():
    out = run([med("alendronic acid", "bisphosphonate"), med("metformin", "biguanide"), med("amlodipine", "calcium_channel_blocker")],
              tags=("oral_surgery", "bleeding_risk"))
    label = [c for c in kinds(out, "label_warning") if c.ingredients == ["alendronic acid"]]
    assert label and all(c.source_quote and c.source_type == "drug_label" and c.auto_generated for c in label)
    assert any("jaw" in c.source_quote.lower() for c in label)


def test_p2_metformin_contrast_label_flag():
    out = run([med("metformin", "biguanide"), med("glimepiride", "sulfonylurea"), med("aspirin", "antiplatelet")],
              tags=("iodinated_contrast", "arterial_access"))
    keys = {c.flag_key for c in kinds(out, "label_warning")}
    assert "label:metformin:iodinated_contrast" in keys


def test_p3_aspirin_and_diclofenac_interaction():
    out = run([med("aspirin", "antiplatelet"), med("diclofenac", "nsaid"), med("losartan", "arb")], tags=SURGERY)
    pairs = {tuple(c.ingredients) for c in kinds(out, "interaction")}
    assert ("aspirin", "diclofenac") in pairs and ("diclofenac", "losartan") in pairs


def test_p4_ibuprofen_with_liver_disease_condition_flag():
    conditions = patient_categories(["Suspected chronic liver disease with splenomegaly"], VOCAB)
    assert "hepatic_impairment" in conditions
    out = run([med("ibuprofen", "nsaid"), med("propranolol", "beta_blocker")], tags=("gi_endoscopy", "sedation"),
              conditions=sorted(conditions))
    assert "label:ibuprofen:hepatic_impairment" in {c.flag_key for c in kinds(out, "label_warning")}


def test_p5_antiplatelets_before_surgery_and_no_invented_insulin_advice():
    out = run([med("insulin glargine", "insulin"), med("metformin", "biguanide"), med("aspirin", "antiplatelet"),
               med("clopidogrel", "antiplatelet")], tags=SURGERY)
    rules = {(c.rule_id, c.medication.lower()) for c in kinds(out, "confirmed")}
    assert ("RULE-002", "aspirin") in rules and ("RULE-002", "clopidogrel") in rules
    assert ("aspirin", "clopidogrel") in {tuple(c.ingredients) for c in kinds(out, "interaction")}
    for c in out.candidates:
        if "insulin" in " ".join(c.ingredients):
            assert "stop" not in c.message.lower() and "dose" not in c.message.lower()


# ---------------------------------------------------------------- behaviour
def test_deterministic_byte_identical():
    meds = [med("aspirin", "antiplatelet"), med("clopidogrel", "antiplatelet"), med("metformin", "biguanide")]
    a, b = run(meds, tags=SURGERY), run(meds, tags=SURGERY)
    assert json.dumps([c.content() for c in a.candidates]) == json.dumps([c.content() for c in b.candidates])


def test_unmapped_brand_could_not_be_checked_not_safe():
    out = run([med(None, None, status="unmapped", name="Mystery tonic"), med("aspirin", "antiplatelet")], tags=SURGERY)
    assert kinds(out, "unrecognised_medicine") and "not checked" in kinds(out, "unrecognised_medicine")[0].message


def test_ambiguous_brand_returns_ambiguous():
    class Row:
        def __init__(self, name, ingredient, cls):
            self.name, self.ingredient, self.drug_class, self.status = name, ingredient, cls, "active"
    index = mapping.NameIndex([Row("duo", "aspirin", "antiplatelet"), Row("duo", "clopidogrel", "antiplatelet")])
    assert index.map("Duo 75 mg").status == "ambiguous"


def test_combination_product_checks_each_ingredient():
    out = run([med("co-amoxiclav", "antibiotic"), med("warfarin", "anticoagulant")])
    pairs = {tuple(c.ingredients) for c in kinds(out, "interaction")}
    expected = {(x.ingredient_a, x.ingredient_b) for x in INTERACTIONS
                if {x.ingredient_a, x.ingredient_b} & {"amoxicillin", "clavulanic acid"} and "warfarin" in (x.ingredient_a, x.ingredient_b)}
    assert expected, "DDInter lists warfarin with a part of co-amoxiclav"
    assert expected <= pairs
    assert ("amoxicillin", "clavulanic acid") not in pairs  # parts of one product are not paired with each other


def test_salt_variants_resolve_to_one_name():
    assert mapping.normalize("Diclofenac sodium 50 mg") == mapping.normalize("Diclofenac potassium 50mg") == "diclofenac"


def test_pair_symmetry():
    a = run([med("aspirin", "antiplatelet"), med("clopidogrel", "antiplatelet")])
    b = run([med("clopidogrel", "antiplatelet"), med("aspirin", "antiplatelet")])
    assert [c.flag_key for c in kinds(a, "interaction")] == [c.flag_key for c in kinds(b, "interaction")] == ["ddi:aspirin:clopidogrel"]


def test_ingredient_not_in_source_is_reported():
    out = run([med("gliclazide", "sulfonylurea"), med("metformin", "biguanide")])
    gap = kinds(out, "interactions_not_checked")
    assert gap and "gliclazide" in gap[0].message and "does not mean there are none" in gap[0].message


def test_every_flag_has_source_and_tag():
    out = run([med("aspirin", "antiplatelet"), med("clopidogrel", "antiplatelet"), med("metformin", "biguanide")], tags=SURGERY)
    for c in out.candidates:
        assert c.source_type
        if c.kind in ("interaction", "label_warning"):
            assert c.auto_generated and c.source_ref and c.source_version and c.severity


def test_no_match_says_no_rule_on_file_never_safe():
    out = run([med("levothyroxine", "thyroid_hormone")], status="none")
    assert out.outcome == "no_match" and "No matching rule on file" in out.summary_message
    for c in out.candidates:
        assert "safe" not in (c.title + c.message).lower()
    assert "safe" not in out.summary_message.lower()


def test_flag_text_never_advises_changing_medication():
    out = run([med(i, None) for i in ("aspirin", "clopidogrel", "metformin", "insulin glargine", "diclofenac", "ibuprofen")],
              tags=SURGERY + ("iodinated_contrast",), conditions=("hepatic_impairment", "renal_impairment"))
    for c in out.candidates:
        if c.kind in ("interaction", "label_warning"):
            low = c.message.lower()
            assert not any(w in low for w in ("stop taking", "discontinue", "withhold", "increase the dose", "reduce the dose"))


def test_only_serious_imported_flags_require_a_decision():
    out = run([med("aspirin", "antiplatelet"), med("clopidogrel", "antiplatelet"), med("omeprazole", "proton_pump_inhibitor")],
              tags=SURGERY)
    for c in kinds(out, "interaction"):
        assert c.requires_decision == (c.severity == "Major")
    assert all(c.requires_decision for c in kinds(out, "confirmed"))


def test_procedure_unknown_does_not_guess_label_rules():
    out = run([med("metformin", "biguanide")], status="unknown")
    assert not kinds(out, "label_warning") or all(c.flag_key.split(":")[2] in VOCAB["condition"] for c in kinds(out, "label_warning"))
    assert kinds(out, "procedure_not_checked")


# ---------------------------------------------------------------- extraction validator
TEXT = "Osteonecrosis of the jaw has been reported. Patients should have a dental examination."


def cand(**kw):
    base = dict(ingredient="alendronic acid", kind="drug_procedure", target="oral_surgery", severity_hint="moderate",
                summary=summary_for("alendronic acid", "warnings_and_cautions", "dental or oral surgery"),
                quote="Osteonecrosis of the jaw has been reported.", section="warnings_and_cautions")
    return Candidate(**{**base, **kw})


@pytest.mark.parametrize("change,reason", [
    ({"quote": "Osteonecrosis of the hip has been reported."}, "verbatim"),
    ({"ingredient": "unobtainium"}, "not one of ours"),
    ({"target": "teleportation"}, "not in the vocabulary"),
    ({"summary": "Stop taking alendronate before oral surgery."}, "advises"),
])
def test_validator_rejects(change, reason):
    problems = validate(cand(**change), TEXT, {"alendronic acid"}, VOCAB)
    assert any(reason in p for p in problems), problems


def test_validator_accepts_and_every_stored_label_rule_passes():
    assert validate(cand(), TEXT, {"alendronic acid"}, VOCAB) == []
    ours = {i["name"] for i in INGREDIENTS}
    for r in LABELS["rules"]:
        c = Candidate(r["ingredient"], r["kind"], r["target"], r["severity_hint"], r["summary"], r["quote"], r["section"])
        assert validate(c, r["quote"], ours, VOCAB) == [], r["rule_key"]
