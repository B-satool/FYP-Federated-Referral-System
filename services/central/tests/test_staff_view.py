"""Staff never see clinical content (decision 2026-10-29), consultation notes travel in the package without
changing older packages' hashes, and interaction flags carry the drug label's own sentence when one exists."""
from __future__ import annotations

from datetime import datetime, timezone

from refcommon.exchange import package_hash, record_title

from app.config import DRUG_CLASSES
from app.medications.evaluator import EvalInput, Interaction, MedInput, SourceState, evaluate_medications
from app.models import DiagnosticRequest, EvidenceItem, Referral
from app.serializers import HIDDEN, diagnostic_out, evidence_out, referral_out

NOW = datetime(2026, 10, 29, tzinfo=timezone.utc)


def _lab() -> EvidenceItem:
    return EvidenceItem(id=7, referral_id=1, origin="source", source_institution="chughtai", category="lab",
                        display="HbA1c: 8.4 % (high)", original={"test": "HbA1c", "value": 8.4, "unit": "%"},
                        current={"test": "HbA1c", "value": 8.4}, source_text="HbA1c 8.4", review_state="imported",
                        verification_status="source_record", selected=True, in_default=True, row_version=1,
                        ai_recommendation="include", ai_relevance="high", ai_reason="Raised HbA1c relevant to surgery",
                        clinical_time=NOW, retrieved_at=NOW)


def test_record_titles_name_the_chart_never_the_content():
    assert record_title("lab", {"test": "HbA1c", "value": 8.4}) == "Lab result: HbA1c"
    assert record_title("imaging", {"study": "MRI knee", "findings": "Tear"}) == "Imaging report: MRI knee"
    assert record_title("visit", {"setting": "Clinic visit", "reason": "Chest pain"}) == "Visit: Clinic visit"
    # a diagnosis, surgery or medicine name is itself clinical: only the kind of record is shown
    assert record_title("condition", {"condition": "Type 2 diabetes"}) == "Diagnosis"
    assert record_title("surgery", {"procedure": "Caesarean section"}) == "Previous surgery"
    assert record_title("medication", {"medication": "Warfarin 5 mg"}) == "Medicine"


def test_staff_evidence_view_has_no_values_or_ai_reasoning():
    staff = evidence_out(_lab(), clinical=False)
    assert staff["redacted"] is True and staff["display"] == "Lab result: HbA1c"
    text = repr(staff)
    for secret in ("8.4", "high", "Raised HbA1c"):
        assert secret not in text, secret
    assert staff["original"] == {} and staff["current"] == {} and staff["source_text"] is None
    doctor = evidence_out(_lab(), clinical=True)
    assert doctor["redacted"] is False and "8.4" in doctor["display"]


def _referral() -> Referral:
    return Referral(id=1, reference="REF-2026-00099", kind="referral", patient_institution="drali", patient_local_id="DA-1",
                    patient_name="Test Patient", source_institution="drali", requesting_doctor_name="Dr Ali",
                    created_by_id="u", created_by_name="Dr Ali", destination_institution="akuh",
                    destination_department="cardiology", reason="Exertional chest pain",
                    consultation_notes="Pain on stairs for 6 weeks. BP 150/90.", urgency="urgent", status="requested",
                    procedure_status="planned", planned_procedure="Coronary angiography",
                    procedure_tags=["iodinated_contrast"], row_version=1, delivery_status="none", amendment_open=False)


def test_staff_referral_view_hides_reason_notes_and_procedure():
    staff = referral_out(_referral(), clinical=False)
    text = repr(staff)
    for secret in ("chest pain", "stairs", "150/90", "angiography", "iodinated"):
        assert secret.lower() not in text.lower(), secret
    assert staff["procedure_label"] == HIDDEN and staff["redacted"] is True
    # what staff need to do their job stays
    assert staff["urgency"] == "urgent" and staff["destination_institution"] == "akuh" and staff["patient"]["name"]
    assert referral_out(_referral())["consultation_notes"].startswith("Pain on stairs")


def test_staff_test_view_hides_question_and_result():
    d = DiagnosticRequest(id=1, reference="DX-2026-00001", referral_id=1, category="laboratory", test="Lipid profile",
                          clinical_question="Raised cholesterol on statin?", urgency="routine",
                          destination_institution="chughtai", destination_department="laboratory", status="reported",
                          requested_by="Dr Ali", requested_by_id="u", report={"text": "LDL 4.9 mmol/L"},
                          attachments=[{"n": 1, "filename": "report.pdf", "storage_key": "k"}], history=[])
    staff = diagnostic_out(d, clinical=False)
    assert staff["test"] == "Lipid profile" and staff["status"] == "reported"
    assert staff["clinical_question"] is None and staff["report"] is None and staff["attachments"] == []


def test_consultation_notes_are_hashed_without_changing_older_packages():
    base = {"referral_id": "REF-1", "package_version": 1, "reason": "x", "sent_at": "2026-10-29T00:00:00+00:00"}
    old = package_hash(base)
    assert package_hash({**base, "consultation_notes": None}) == old  # a package without notes keeps its hash
    with_notes = package_hash({**base, "consultation_notes": "Pain on stairs"})
    assert with_notes != old and with_notes != package_hash({**base, "consultation_notes": "Pain at rest"})


def test_interaction_flag_quotes_the_label_when_a_sentence_exists():
    meds = (MedInput(1, "Fosamax", "alendronic acid", "bisphosphonate", "mapped", "clinic", (1,)),
            MedInput(2, "Calcium with D3", "calcium carbonate", "calcium_vitamin_d", "mapped", "clinic", (2,)))
    quote = "Calcium supplements, antacids, or oral medications containing multivalent cations interfere with absorption of alendronate."
    x = Interaction("alendronic acid", "calcium carbonate", "Moderate", "DDInter1-DDInter2", "test",
                    quote, "US label (FOSAMAX)", "Drug interactions")
    out = evaluate_medications(EvalInput("none", None, (), meds, (SourceState("drali", "Dr Ali's Clinic", "successful"),),
                                         (), DRUG_CLASSES, interactions=(x,),
                                         interaction_coverage=frozenset({"alendronic acid", "calcium carbonate"})))
    flag = next(c for c in out.candidates if c.kind == "interaction")
    assert flag.source_quote == quote and "US label (FOSAMAX)" in flag.source_name
    assert "advice" in flag.message  # the platform's own wording stays the fixed, non-advice sentence
    # without a label sentence nothing is invented
    plain = Interaction("alendronic acid", "calcium carbonate", "Moderate", "DDInter1-DDInter2", "test")
    out2 = evaluate_medications(EvalInput("none", None, (), meds, (SourceState("drali", "Dr Ali's Clinic", "successful"),),
                                          (), DRUG_CLASSES, interactions=(plain,),
                                          interaction_coverage=frozenset({"alendronic acid", "calcium carbonate"})))
    flag2 = next(c for c in out2.candidates if c.kind == "interaction")
    assert flag2.source_quote is None and flag2.source_name == "DDInter 2.0"
