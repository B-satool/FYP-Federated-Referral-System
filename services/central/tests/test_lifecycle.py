"""Data lifecycle (spec v3 A, C): working-set timing, package manifest and role menus. (Sharing grants were
replaced by consent and each institution's policy in spec v4: see services/provider/tests/test_policy.py.)"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from refcommon.exchange import package_hash

from app.config import INSTITUTIONS, settings
from app.identity import role_templates
from app.lifecycle import working_set
from app.lifecycle.manifest import build_manifest, is_purged, purged_envelope, verify_copy

NOW = datetime(2026, 10, 27, 12, tzinfo=timezone.utc)


# ---------------------------------------------------------------- working set timing
def referral(kind="referral", **kw):
    base = dict(kind=kind, status="submitted", working_set_expires_at=None, working_set_purged_at=None,
                receiver_completed_at=None, accepted_at=None)
    return SimpleNamespace(**{**base, **kw})


HOLD = timedelta(days=settings.accepted_hold_days)
GRACE = timedelta(hours=settings.working_set_grace_hours)


def test_no_limit_until_accepted_then_safety_limit():
    r = referral()
    working_set.start(r, NOW)
    assert r.working_set_expires_at is None  # sent but not accepted: no time limit
    for status in ("acknowledged", "response_returned", "closed"):
        working_set.on_status(r, status, NOW)
        assert r.working_set_expires_at is None  # answering or closing alone does not start the clock
    working_set.on_status(r, "accepted", NOW)
    assert r.working_set_expires_at == NOW + HOLD


def test_receiver_extends_and_completes():
    r = referral(status="accepted", working_set_expires_at=NOW + HOLD)
    later = NOW + timedelta(days=20)
    assert working_set.extend(r, later) == later + HOLD  # 30 days from when they extend
    assert working_set.extend(r, NOW) == later + HOLD  # never shortens
    working_set.complete(r, later)
    r.receiver_completed_at = later
    assert r.working_set_expires_at == later + GRACE
    assert working_set.extend(r, later) is None  # nothing to extend once complete


def test_decline_removes_now_and_cancel_after_grace():
    r = referral(status="acknowledged")
    working_set.on_status(r, "declined", NOW)
    assert r.working_set_expires_at == NOW
    r = referral(status="accepted", working_set_expires_at=NOW + HOLD)
    working_set.on_status(r, "cancelled", NOW)
    assert r.working_set_expires_at == NOW + GRACE


def test_test_requests_end_after_results():
    r = referral(kind="test")
    working_set.on_status(r, "response_returned", NOW)
    assert r.working_set_expires_at == NOW + GRACE
    working_set.on_status(r, "closed", NOW + timedelta(hours=10))  # never later than before
    assert r.working_set_expires_at == NOW + GRACE


def test_working_set_restarts_after_purge():
    r = referral(status="accepted", accepted_at=NOW, working_set_expires_at=NOW, working_set_purged_at=NOW)
    working_set.start(r, NOW + timedelta(days=1))
    assert r.working_set_purged_at is None and r.working_set_expires_at == NOW + timedelta(days=1) + HOLD
    r = referral(working_set_expires_at=NOW, working_set_purged_at=NOW)  # not accepted yet
    working_set.start(r, NOW + timedelta(days=1))
    assert r.working_set_purged_at is None and r.working_set_expires_at is None

# ---------------------------------------------------------------- manifest and copy check
ENVELOPE = {
    "referral_id": "REF-1", "package_version": 1, "sender_institution": "drali", "destination_institution": "akuh",
    "sent_by_id": "u1", "sent_at": "2026-10-27T10:00:00Z", "content_hash": "abc", "delivery_key": "k1",
    "evidence": [{"evidence_id": 5, "category": "lab", "origin": "source", "source_institution": "chughtai",
                  "source_record_type": "Observation", "source_record_id": "L1", "source_record_version": "2",
                  "display": "Creatinine 1.4 mg/dL"}],
    "medication_flags": [{"flag_id": 9, "version": 1, "kind": "interaction", "rule_id": "r1", "rule_version": 3,
                          "message": "secret clinical text", "acknowledged": {"decision": "research"}}],
    "medication_evaluation": {"ruleset_hash": "rs1"},
    "ai_suggestions": [{"pair_key": "a|b", "text": "x"}],
    "selection": {"counts": {"selected": 1}},
}


def test_manifest_holds_references_not_values():
    m = build_manifest(ENVELOPE)
    assert m["evidence"][0]["source_record_version"] == "2" and m["ruleset_hash"] == "rs1"
    assert m["medication_flags"][0]["decision"] == "research" and m["ai_suggestions"] == ["a|b"]
    text = str(m)
    assert "Creatinine" not in text and "secret clinical text" not in text


def test_purged_envelope_keeps_identity_only():
    p = purged_envelope(ENVELOPE)
    assert is_purged(p) and p["content_hash"] == "abc" and "evidence" not in p and "medication_flags" not in p


def test_verify_copy():
    stored = package_hash(ENVELOPE)
    assert verify_copy(stored, dict(ENVELOPE))["result"] == "match"
    assert verify_copy(stored, {**ENVELOPE, "delivery_key": "other"})["result"] == "match"  # not a hashed field
    assert verify_copy(stored, {**ENVELOPE, "package_version": 2})["result"] == "mismatch"
    assert verify_copy(stored, None)["result"] == "unusable_copy"


# ---------------------------------------------------------------- role templates
def test_every_template_is_valid():
    assert role_templates.templates()  # loading validates the file
    for t in role_templates.templates().values():
        if t.assignable:
            assert set(t.roles) <= role_templates.ASSIGNABLE_ROLES and t.home in t.menu
        assert t.record_visibility in role_templates.VISIBILITY and set(t.api_scopes) <= set(role_templates.scopes())


def test_templates_give_visibility_keys_and_scopes():
    """Spec v4 4.1: staff see titles only and hold no keys; doctors open content on their device and hold keys."""
    staff = role_templates.profile({"clinic_staff"}, "drali")
    assert staff["record_visibility"] == "titles_only" and not staff["holds_keys"]
    assert "records:content" not in staff["scopes"] and "consent:request" in staff["scopes"]
    doctor = role_templates.profile({"clinician"}, "drali")
    assert doctor["record_visibility"] == "content" and doctor["holds_keys"]
    assert {"records:content", "package:approve"} <= set(doctor["scopes"]) and "consent:request" not in doctor["scopes"]
    patient = role_templates.profile({"patient"}, None)
    assert patient["holds_keys"] and patient["scopes"] == ["patient:self"]
    assert role_templates.profile({"rule_reviewer"}, "drali")["record_visibility"] == "none"
    assert all(t.assignable for t in role_templates.templates_for_institution("drali"))


def test_menu_only_offers_screens_the_roles_allow():
    screens = role_templates.screens()
    for t in [t for t in role_templates.templates().values() if t.assignable]:
        inst = next(i for i, v in INSTITUTIONS.items() if v["kind"] in t.institution_kinds)
        nav = role_templates.navigation(set(t.roles), inst)
        assert t.template_id in nav["templates"] and nav["home"]
        for item in nav["menu"]:
            assert set(screens[item["key"]]["roles"]) & set(t.roles)


def test_front_desk_does_not_get_reviewer_screens():
    nav = role_templates.navigation({"clinic_staff"}, "drali")
    keys = {m["key"] for m in nav["menu"]}
    assert "rules" not in keys and "medicine_names" not in keys and "accounts" not in keys


def test_plan_change_only_removes_managed_roles():
    t = role_templates.templates()["doctor"]
    add, remove = role_templates.plan_change({"clinic_staff", "offline_access"}, t)
    assert add == ["clinician"] and remove == ["clinic_staff"]
