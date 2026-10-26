"""Data lifecycle (spec v3 A, C): grant expiry, working-set timing, package manifest and role menus."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from refcommon.exchange import package_hash
from refcommon.sourcekit import MAX_GRANT_DAYS, grant_expiry, grant_is_live, grant_state

from app.config import INSTITUTIONS, settings
from app.identity import role_templates
from app.lifecycle import working_set
from app.lifecycle.manifest import build_manifest, is_purged, purged_envelope, verify_copy

NOW = datetime(2026, 10, 27, 12, tzinfo=timezone.utc)


# ---------------------------------------------------------------- access grants
def grant(status="active", expires_at=None):
    return SimpleNamespace(status=status, expires_at=expires_at)


def test_grant_states():
    assert grant_state(grant(expires_at=NOW + timedelta(days=1)), NOW) == "active"
    assert grant_state(grant(expires_at=NOW), NOW) == "expired"  # the end time itself is already expired
    assert grant_state(grant(expires_at=(NOW - timedelta(seconds=1)).replace(tzinfo=None)), NOW) == "expired"  # naive = UTC
    assert grant_state(grant(status="revoked", expires_at=NOW + timedelta(days=1)), NOW) == "revoked"
    assert grant_state(grant(), NOW) == "legacy_no_expiry"
    assert grant_is_live(grant(), NOW) and not grant_is_live(grant(expires_at=NOW), NOW)


@pytest.mark.parametrize("days", [0, -1, MAX_GRANT_DAYS + 1])
def test_grant_duration_bounds(days):
    with pytest.raises(HTTPException) as exc:
        grant_expiry(days)
    assert exc.value.status_code == 422


def test_grant_expiry_default_and_max():
    assert grant_expiry() > datetime.now(timezone.utc)
    assert grant_expiry(MAX_GRANT_DAYS) - datetime.now(timezone.utc) <= timedelta(days=MAX_GRANT_DAYS)


# ---------------------------------------------------------------- working set timing
def test_working_set_starts_and_shortens_on_ending_status():
    r = SimpleNamespace(working_set_expires_at=None, working_set_purged_at=None)
    working_set.start(r, NOW)
    assert r.working_set_expires_at == NOW + timedelta(days=settings.working_set_max_days)
    working_set.on_status(r, "accepted", NOW)  # not an ending status
    assert r.working_set_expires_at == NOW + timedelta(days=settings.working_set_max_days)
    working_set.on_status(r, "response_returned", NOW)
    assert r.working_set_expires_at == NOW + timedelta(hours=settings.working_set_grace_hours)
    later = NOW + timedelta(hours=10)
    working_set.on_status(r, "closed", later)  # never extends past the earlier grace end
    assert r.working_set_expires_at == NOW + timedelta(hours=settings.working_set_grace_hours)


def test_working_set_restarts_after_purge():
    r = SimpleNamespace(working_set_expires_at=NOW, working_set_purged_at=NOW)
    working_set.start(r, NOW + timedelta(days=1))
    assert r.working_set_purged_at is None and r.working_set_expires_at > NOW + timedelta(days=1)


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
        assert set(t.roles) <= role_templates.ASSIGNABLE_ROLES and t.home in t.menu


def test_menu_only_offers_screens_the_roles_allow():
    screens = role_templates.screens()
    for t in role_templates.templates().values():
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
