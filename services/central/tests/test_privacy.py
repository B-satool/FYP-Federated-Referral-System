"""What a language model may be sent, and where (app/generation/privacy.py)."""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import settings
from app.db import Base
from app.generation import privacy
from app.generation.provider import LLMProvider, OllamaProvider, OpenAICompatibleProvider, ProviderUnavailable
from app.models import EvidenceItem, Referral
from app.selection import selection

NAME, CNIC, LOCAL = "Imtiaz Ali Soomro", "41304-0000055-9", "DA-6120"


def test_scrubber_removes_identifiers_and_keeps_the_clinical_content():
    s = privacy.Scrubber(NAME, [CNIC, LOCAL], date(2026, 10, 28))
    text = (f"Imtiaz Soomro (CNIC {CNIC}, {LOCAL}) seen by Dr Naveed Baig at Aga Khan University Hospital "
            "on 2026-10-15, phone 0300-1234567: metformin 500 mg twice daily, HbA1c 8.9 %")
    out = s.text(text)
    for leaked in ("Imtiaz", "Soomro", CNIC, LOCAL, "Naveed", "Aga Khan", "2026-10-15", "1234567"):
        assert leaked not in out, leaked
    assert "metformin 500 mg twice daily" in out and "HbA1c 8.9 %" in out and "a hospital" in out
    assert s.when(datetime(2026, 10, 15, tzinfo=timezone.utc)) == "13 days before the referral"
    assert "2026-10-15" in privacy.Scrubber(NAME, [], None, keep_dates=True).text("started 2026-10-15")


def test_cloud_and_remote_models_need_explicit_permission_and_https(monkeypatch):
    monkeypatch.setattr(settings, "llm_external_allowed", False)
    cloud_via_local = OllamaProvider("http://host.docker.internal:11434", "gemma4:cloud")
    assert privacy.destination(cloud_via_local) == (True, "ollama.com")  # a :cloud model leaves the computer
    with pytest.raises(ProviderUnavailable, match="switched off"):
        privacy.check_destination(cloud_via_local)
    assert privacy.check_destination(OllamaProvider("http://host.docker.internal:11434", "medgemma:4b"))["external"] is False

    monkeypatch.setattr(settings, "llm_external_allowed", True)
    assert privacy.check_destination(cloud_via_local) == {"external": True, "destination": "ollama.com", "deidentified": True}
    assert privacy.check_destination(OllamaProvider("https://ollama.com", "gemma4:31b", "key"))["destination"] == "ollama.com"
    with pytest.raises(ProviderUnavailable, match="https"):
        privacy.check_destination(OpenAICompatibleProvider("http://models.example.org/v1", "m"))


class Capture(LLMProvider):
    name, model = "fake", "fake-1"

    def structured(self, system, user_payload, schema, max_tokens=16000):
        self.payload = user_payload
        return {"items": [], "missing": []}


def test_packet_selection_sends_no_identifiers():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        r = Referral(reference="REF-2026-00042", kind="referral", status="requested", patient_institution="drali",
                     patient_local_id=LOCAL, patient_name=NAME, patient_cnic=CNIC, patient_birth_date="1981-01-05",
                     patient_sex="male", source_institution="drali", requesting_doctor_name="Dr Ali Raza",
                     reason="Imtiaz Ali has gallstones; please assess.", urgency="routine", procedure_status="planned",
                     planned_procedure="Laparoscopic cholecystectomy", procedure_tags=[], created_by_name="t", created_by_id="t",
                     requested_at=datetime(2026, 10, 28, tzinfo=timezone.utc))
        db.add(r)
        db.flush()
        db.add(EvidenceItem(referral_id=r.id, patient_institution="drali", patient_local_id=LOCAL, origin="source",
                            source_institution="drali", source_record_type="Encounter", source_record_id="v1",
                            source_record_version="1", category="visit", original={}, current={},
                            display="Clinic visit with Dr Ali Raza (Dr Ali's Clinic, Clifton) on 2026-10-20: Mr Soomro has RUQ pain",
                            clinical_time=datetime(2026, 10, 20, tzinfo=timezone.utc), review_state="imported",
                            verification_status="source_record", selected=True))
        db.flush()
        fake = Capture()
        selection.recommend(db, r, "staff", provider_factory=lambda: fake)
        sent = str(fake.payload)
        for leaked in ("Imtiaz", "Soomro", CNIC, LOCAL, "REF-2026-00042", "1981", "Ali Raza", "Clifton", "2026-10-20"):
            assert leaked not in sent, leaked
        assert fake.payload["patient"] == {"age_years": 45, "sex": "male"}
        assert fake.payload["records"][0]["when"] == "8 days before the referral"
        assert "RUQ pain" in fake.payload["records"][0]["text"]
