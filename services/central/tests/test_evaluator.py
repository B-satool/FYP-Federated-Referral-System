"""The deterministic server evaluator's general behaviour (kept for tests and the pre-v4 flow; spec v4 9.3).

Spec v4 9.1 removed every hand-written drug-class rule (they paired drug classes with procedures, which the spec
forbids), so these checks run with no rules: what must hold whatever the rules are. The browser's Layer 1 library is
checked in libs/common/tests/test_browser_flags.py.
Run: docker compose run --rm --no-deps -v ${PWD}/services/central/tests:/srv/tests central python -m pytest tests -q
"""
from __future__ import annotations

from app.config import DRUG_CLASSES, PROCEDURE_HINTS
from app.medications.evaluator import EvalInput, MedInput, SourceState, evaluate_medications

SURGERY = ("major_surgery", "general_anaesthesia", "prolonged_fasting", "bleeding_risk")
OK = SourceState("drali", "Dr Ali's Clinic", "successful")
_ids = iter(range(1, 10_000))


def med(ingredient: str, cls: str | None, mapping: str = "mapped", name: str | None = None) -> MedInput:
    eid = next(_ids)
    return MedInput(entry_id=eid, original_name=name or ingredient.title(), ingredient=ingredient if mapping in ("mapped", "staff_mapped") else None,
                    drug_class=cls if mapping in ("mapped", "staff_mapped") else None, mapping_status=mapping,
                    source_label="Dr Ali's Clinic record", evidence_ids=(eid,))


def run(meds, procedure="laparoscopic cholecystectomy", status="planned", sources=(OK,), tags=SURGERY):
    return evaluate_medications(EvalInput(status, procedure if status == "planned" else None,
                                          tuple(tags) if status == "planned" else (), tuple(meds), tuple(sources), (),
                                          DRUG_CLASSES))


def kinds(out) -> list[str]:
    return sorted(c.kind for c in out.candidates)


def test_name_hints_cover_the_seed_procedures():
    """Words in the procedure name pre-tick the features the doctor confirms (features, not medicines)."""
    def hinted(text):
        return {t for word, tags in PROCEDURE_HINTS.items() if word in text.lower() for t in tags}
    assert hinted("Laparoscopic cholecystectomy") >= set(SURGERY)
    assert hinted("Surgical extraction of lower molar") >= {"oral_surgery", "bleeding_risk"}
    assert hinted("Coronary angiography") >= {"iodinated_contrast"}


def test_unrecognised_medicine_is_reported_not_ignored():
    out = run([med("x", None, mapping="unmapped", name="Mystery tonic")])
    assert "unrecognised_medicine" in kinds(out)


def test_unavailable_source_is_a_limitation_not_none():
    out = run([med("aspirin", "antiplatelet")], sources=(OK, SourceState("ziauddin", "Ziauddin Hospital", "unavailable")))
    gap = [c for c in out.candidates if c.kind == "records_incomplete"]
    assert gap and "does not mean the absence" in gap[0].message


def test_no_rules_is_not_a_negative_result():
    out = run([med("aspirin", "antiplatelet")])
    assert out.outcome != "flags" and "safe" not in out.summary_message.lower()
    assert "not a negative result" in out.summary_message or "No matching rule on file" in out.summary_message


def test_deterministic():
    meds = [med("insulin glargine", "insulin"), med("metformin", "biguanide"), med("aspirin", "antiplatelet")]
    a, b = run(meds), run(meds)
    assert [c.content() for c in a.candidates] == [c.content() for c in b.candidates]
