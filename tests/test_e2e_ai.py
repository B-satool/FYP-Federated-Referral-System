"""Spec v4 WP6 and WP7 Layer 2: the AI relay (T-AI-1, T-AI-2, T-FLAG-2).

* A payload that still holds the patient's identifiers is refused; the audit trail keeps the payload's hash, never
  its text; only the referring doctor (with the ai:use scope) may ask; nothing runs without a request.
* With a model configured (LLM_PROVIDER and its key in .env), the answer comes back checked: ids that are not in the
  request are dropped. Without one, "AI check not available" (503), never an empty answer.
"""
from __future__ import annotations

import json

import pytest

from conftest import new_referral
from flows import central_python
from helpers import central, ok

NOTE = "Rubina Akhtar reports pain on chewing for three weeks, worse at night."


def payload(text: str) -> dict:
    return {"patient": {"age_years": 41, "sex": "female", "name": "should be dropped"},
            "referral": {"kind": "referral", "reason": "Pain in a lower molar", "department": "Dentistry",
                         "planned_procedure": "Surgical extraction of a lower molar", "procedure_status": "planned"},
            "records": [{"id": 1, "category": "note", "when": "2 days before the referral", "default": True, "text": text},
                        {"id": 2, "category": "medication", "when": "30 days before the referral", "default": True,
                         "text": "Clopidogrel 75 mg once daily"},
                        {"id": 3, "category": "lab", "when": "400 days before the referral", "default": False,
                         "text": "Haemoglobin: 12.1 g/dL"}]}


@pytest.fixture(scope="module")
def referral():
    return new_referral("Rubina Akhtar", "akuh", "dentistry", "Surgical extraction of lower left molar", ["oral_surgery"])


def model_configured() -> bool:
    return central_python("from app.config import settings; print(settings.llm_configured)").splitlines()[-1] == "True"


def test_identifiers_are_refused_and_never_logged(referral):
    resp = central("dr.ali").post("/ai/relay/selection", {"referral_id": referral["id"], "payload": payload(NOTE)})
    assert resp.status_code == 422 and "patient name" in resp.text and "Rubina" not in resp.text
    trail = ok(central("dr.ali").get(f"/referrals/{referral['id']}/audit"))
    relay = [a for a in trail if a["action"] == "ai.relay.selection"]
    assert relay and relay[0]["outcome"] == "refused" and relay[0]["detail"]["payload_sha256"]
    assert "chewing" not in json.dumps(trail) and "Rubina Akhtar reports" not in json.dumps(trail)


def test_only_the_referring_doctor_may_ask(referral):
    body = {"referral_id": referral["id"], "payload": payload("[patient] reports pain on chewing.")}
    assert central("staff.ali").post("/ai/relay/selection", body).status_code == 403
    assert central("dr.asma").post("/ai/relay/selection", body).status_code == 403


def test_answer_is_checked_or_unavailable_is_said(referral):
    body = {"referral_id": referral["id"], "payload": payload("[patient] reports pain on chewing for three weeks.")}
    resp = central("dr.ali").post("/ai/relay/selection", body)
    if not model_configured():
        assert resp.status_code == 503 and "not available" in resp.text
        return
    if resp.status_code in (502, 503):  # the free model's rate limit, or an answer that failed the checks
        pytest.skip(f"model did not answer usably: {resp.text[:200]}")
    out = ok(resp)
    assert {x["id"] for x in out["recommendations"]} <= {1, 2, 3}
    assert out["label"] == "AI suggestion, unverified"
    trail = ok(central("dr.ali").get(f"/referrals/{referral['id']}/audit"))
    assert "chewing" not in json.dumps(trail)
