"""The institution's own release policy (spec v4 6.2): structured refusals in the agreed order (T-POLICY-1 logic)."""
from __future__ import annotations

import json
from pathlib import Path

from app import policy

POLICIES = Path(__file__).resolve().parent.parent / "policies"
REASONS = set(policy.REFUSAL_REASONS)


def _pol(**over) -> dict:
    return {**policy.DEFAULTS, "hash": "test", **over}


def _consent(classes=policy.RECORD_CATEGORIES, sensitive=(), data_start="2023-01-01") -> dict:
    return {"provision": {"class": [{"code": c} for c in classes], "dataPeriod": {"start": data_start}},
            "refx": {"sensitive_categories_specific": list(sensitive)}}


REQ = {"referral": "REF-1", "local_patient_id": "MD-1", "purpose": "TREAT"}


def test_every_policy_file_is_valid_and_versioned():
    for path in sorted(POLICIES.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["version"].startswith(path.stem), path
        assert set(data) >= {"auto_approve_with_valid_consent", "excluded_categories", "manual_review",
                             "respond_within_consent_window_only", "allowed_record_types_from_consent",
                             "sensitive_title_masking"}, path
        assert {"psychiatric", "hiv_sexual_health"} <= set(data["excluded_categories"]), path


def test_valid_consent_is_answered_within_the_consent_window():
    d = policy.evaluate(_pol(), {**REQ, "since": "2020-01-01"}, _consent(), None)
    assert d.status == "answer" and d.categories == set(policy.RECORD_CATEGORIES) and not d.refusals
    assert d.since == "2023-01-01"  # the consent's data period wins over an earlier request


def test_missing_or_bad_consent_is_a_structured_refusal_never_an_empty_answer():
    expired = policy.evaluate(_pol(), REQ, None, "consent expired")
    assert expired.status == "refused" and expired.refusals[0]["reason"] == "consent_expired_or_out_of_range"
    forged = policy.evaluate(_pol(), REQ, None, "the consent is not signed by the patient")
    assert forged.refusals[0]["reason"] == "request_incomplete_or_invalid"
    incomplete = policy.evaluate(_pol(), {"referral": "REF-1"}, _consent(), None)
    assert incomplete.status == "refused" and incomplete.refusals[0]["reason"] == "request_incomplete_or_invalid"
    for d in (expired, forged, incomplete):
        assert all(r["reason"] in REASONS and r["message"] for r in d.refusals)


def test_sensitive_category_needs_specific_consent():
    without = policy.evaluate(_pol(), {**REQ, "sensitive": ["psychiatric"]}, _consent(), None)
    assert without.status == "answer" and "psychiatric" not in without.sensitive
    assert [r["reason"] for r in without.refusals] == ["sensitive_category_no_specific_consent"]
    assert without.refusals[0]["categories"] == ["psychiatric"]
    with_it = policy.evaluate(_pol(), {**REQ, "sensitive": ["psychiatric"]}, _consent(sensitive=["psychiatric"]), None)
    assert with_it.sensitive == {"psychiatric"} and not with_it.refusals


def test_manual_review_rule_queues_the_request():
    pol = _pol(manual_review={"categories": ["hiv_sexual_health"], "request_types": [], "always": False})
    d = policy.evaluate(pol, REQ, _consent(sensitive=["hiv_sexual_health"]), None)
    assert d.status == "pending" and d.refusals[-1]["reason"] == "pending_manual_review"
    approved = policy.evaluate(pol, REQ, _consent(sensitive=["hiv_sexual_health"]), None, manual_approved=True)
    assert approved.status == "answer" and approved.sensitive == {"hiv_sexual_health"}
    emergency = policy.evaluate(_pol(manual_review={"request_types": ["ETREAT"]}), {**REQ, "purpose": "ETREAT"},
                                _consent(), None)
    assert emergency.status == "pending"
    assert policy.evaluate(_pol(auto_approve_with_valid_consent=False), REQ, _consent(), None).status == "pending"


def test_only_consented_record_types_and_what_the_law_allows():
    d = policy.evaluate(_pol(prohibited_by_law=["imaging"]), REQ, _consent(classes=["labs", "imaging"]), None)
    assert d.categories == {"labs"}
    reasons = {r["reason"]: r["categories"] for r in d.refusals}
    assert reasons["prohibited_by_law"] == ["imaging"]
    assert set(reasons["consent_expired_or_out_of_range"]) == {"conditions", "surgeries", "visits", "medications"}
    nothing = policy.evaluate(_pol(prohibited_by_law=list(policy.RECORD_CATEGORIES)), REQ, _consent(), None)
    assert nothing.status == "refused"
