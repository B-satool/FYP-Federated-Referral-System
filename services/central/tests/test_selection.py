"""Packet selection (spec v3 B): the rule-based default and the checks on the AI recommendation."""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from app.generation.provider import ProviderOutputInvalid
from app.selection.selection import SCHEMA, in_default, validate

TODAY = date(2026, 10, 27)


def at(y, m, d):
    return datetime(y, m, d, tzinfo=timezone.utc)


def item(eid, rec="include", rel="high", reason="Recent kidney function matters for contrast during angiography."):
    return {"evidence_id": eid, "recommendation": rec, "relevance": rel, "reason": reason}


def test_default_floor():
    assert in_default("condition", {"clinical_status": "active"}, None, today=TODAY)
    assert not in_default("condition", {"clinical_status": "resolved"}, None, today=TODAY)
    assert in_default("medication", {}, None, today=TODAY) and in_default("surgery", {}, at(2010, 1, 1), today=TODAY)
    assert in_default("lab", {}, at(2026, 6, 1), today=TODAY)
    assert not in_default("lab", {}, at(2025, 3, 1), today=TODAY)  # older than 6 months: offered, not selected
    assert not in_default("imaging", {}, None, today=TODAY)
    assert in_default("lab", {}, at(2020, 1, 1), origin="document", today=TODAY)  # staff-checked papers always


def test_schema_is_strict():
    assert SCHEMA["additionalProperties"] is False and set(SCHEMA["required"]) == {"items", "missing"}
    inner = SCHEMA["properties"]["items"]["items"]
    assert inner["additionalProperties"] is False and len(inner["required"]) == 4


def test_valid_answer():
    recs, missing = validate({"items": [item(1), item(2, "exclude", "low", "Unrelated childhood fracture.")],
                              "missing": ["Recent ECG"]}, {1, 2, 3})
    assert recs[2]["recommendation"] == "exclude" and missing == ["Recent ECG"]


@pytest.mark.parametrize("raw", [
    {"items": [item(99)], "missing": []},                                   # id not supplied
    {"items": [item(1), item(1)], "missing": []},                           # duplicate
    {"items": [{**item(1), "extra": 1}], "missing": []},                    # extra field
    {"items": [item(1, rec="must_include")], "missing": []},                # unknown value
    {"items": [item(1, reason=" ".join(["word"] * 26))], "missing": []},    # reason too long
    {"items": [item(1, reason="Stop metformin before the procedure.")], "missing": []},  # advice
    {"items": [item(1, reason="Increase the dose to 20 mg.")], "missing": []},           # dosing
    {"items": [item(1)], "missing": ["Discontinue aspirin"]},              # advice in missing
    {"items": [item(1)]},                                                   # missing key
    {"items": [{**item(1), "evidence_id": True}], "missing": []},          # bool is not an id
    "include everything",
])
def test_rejected_answers(raw):
    with pytest.raises(ProviderOutputInvalid):
        validate(raw, {1, 2})


def test_prompt_injection_in_record_text_cannot_add_ids():
    """A record that says 'include record 500' cannot make the model's answer use an id outside the set."""
    with pytest.raises(ProviderOutputInvalid):
        validate({"items": [item(500, reason="Record text asked for this.")], "missing": []}, {1, 2})
