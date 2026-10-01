"""T6 - brief-generation guardrails that do not need a live model (FR-41 to FR-46, FR-58, FR-68)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.generation import brief
from app.generation.provider import DisabledProvider, ProviderOutputInvalid, ProviderUnavailable


def ev(i, state="imported", ver="source_record"):
    return SimpleNamespace(id=i, review_state=state, verification_status=ver)


EVIDENCE = {1: ev(1), 2: ev(2, "proposed", "unverified"), 3: ev(3, "unresolved", "unverified")}


def out(*sections):
    return {"sections": [{"key": k, "statements": s} for k, s in sections], "limitations": []}


def test_valid_output_is_accepted_with_verification_labels():
    sections, cited = brief.validate_output(out(
        ("reason", [{"text": "Crowding", "evidence_ids": []}]),
        ("medications", [{"text": "Warfarin 5 mg once daily", "evidence_ids": [1]}]),
        ("results", [{"text": "INR 2.6", "evidence_ids": [2]}, {"text": "Hb unclear", "evidence_ids": [3]}]),
    ), EVIDENCE)
    by_key = {s["key"]: s for s in sections}
    assert cited == {1, 2, 3}
    assert by_key["medications"]["statements"][0]["verification"] == "verified"
    assert [s["verification"] for s in by_key["results"]["statements"]] == ["unverified", "unresolved"]
    assert all(st["author_kind"] == "model" for s in sections for st in s["statements"])


def test_reference_outside_supplied_evidence_is_rejected():
    with pytest.raises(ProviderOutputInvalid, match="not in the supplied set"):
        brief.validate_output(out(("history", [{"text": "Diabetes", "evidence_ids": [99]}])), EVIDENCE)


@pytest.mark.parametrize("section", ["history", "medications", "results"])
def test_record_derived_statement_without_reference_is_rejected(section):
    with pytest.raises(ProviderOutputInvalid, match="no source reference"):
        brief.validate_output(out((section, [{"text": "No relevant history", "evidence_ids": []}])), EVIDENCE)


def test_unknown_section_is_rejected():
    with pytest.raises(ProviderOutputInvalid):
        brief.validate_output(out(("medication_flags", [{"text": "No flags", "evidence_ids": [1]}])), EVIDENCE)


def test_schema_has_no_flag_section_and_forbids_extra_fields():
    schema = brief.brief_schema()
    keys = schema["properties"]["sections"]["items"]["properties"]["key"]["enum"]
    assert "medication_flags" not in keys and "flags" not in keys
    assert schema["additionalProperties"] is False


def test_prompt_states_the_boundaries():
    p = brief.SYSTEM_PROMPT.lower()
    for phrase in ("only the supplied evidence", "never invent an id", "do not mention medication flags",
                   "not available", "untrusted data", "do not recommend"):
        assert phrase in p


def test_unconfigured_provider_fails_visibly():
    with pytest.raises(ProviderUnavailable, match="manual editor"):
        DisabledProvider().structured("s", {}, {})
