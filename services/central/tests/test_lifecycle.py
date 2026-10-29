"""Referral lifecycle (spec v4 7, 11): close reminders, extension limits, purge timing; and role templates (spec v4
4.1). Purge itself (crypto-shredding with a receipt) is checked against the running stack in tests/test_e2e_lifecycle.py."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.config import INSTITUTIONS, settings
from app.identity import role_templates
from app.lifecycle import working_set

NOW = datetime(2026, 10, 27, 12, tzinfo=timezone.utc)
HOLD = timedelta(days=settings.accepted_hold_days)
GRACE = timedelta(hours=settings.working_set_grace_hours)
CLOSE = timedelta(days=settings.close_grace_days)
DECLINE = timedelta(days=settings.decline_grace_days)
MAX = timedelta(days=settings.max_referral_days)


def referral(kind="referral", **kw):
    base = dict(kind=kind, status="submitted", working_set_expires_at=None, working_set_purged_at=None,
                receiver_completed_at=None, accepted_at=None, close_reminder_due_at=None, reminders_sent=0,
                last_reminder_at=None, escalated_at=None)
    return SimpleNamespace(**{**base, **kw})


def test_no_limit_until_accepted_then_a_reminder_not_a_purge():
    r = referral()
    for status in ("acknowledged", "response_returned", "closed"):
        working_set.on_status(r, status, NOW)
        assert r.working_set_expires_at is None and r.close_reminder_due_at is None
    working_set.on_status(r, "accepted", NOW)
    assert r.close_reminder_due_at == NOW + HOLD
    assert r.working_set_expires_at is None  # never purged just because time passed (O4)


def test_extension_moves_the_reminder_and_stops_at_the_maximum():
    r = referral(status="accepted", accepted_at=NOW, close_reminder_due_at=NOW + HOLD, reminders_sent=2,
                 escalated_at=NOW + HOLD)
    day31 = NOW + timedelta(days=31)
    assert working_set.extend(r, day31) == day31 + HOLD  # from the later of now and the due date
    assert r.reminders_sent == 0 and r.escalated_at is None
    for _ in range(10):
        working_set.extend(r, NOW + timedelta(days=40))
    assert r.close_reminder_due_at == NOW + MAX  # never past the maximum lifetime


def test_close_purges_after_the_grace_period():
    r = referral(status="accepted", accepted_at=NOW, close_reminder_due_at=NOW + HOLD)
    later = NOW + timedelta(days=12)
    assert working_set.close(r, later) == later + CLOSE
    assert r.close_reminder_due_at is None
    r.receiver_completed_at = later
    assert working_set.extend(r, later) is None  # nothing to extend once closed


def test_decline_and_cancel_purge_after_a_short_grace():
    r = referral(status="acknowledged")
    working_set.on_status(r, "declined", NOW)
    assert r.working_set_expires_at == NOW + DECLINE
    r = referral(status="accepted", accepted_at=NOW, close_reminder_due_at=NOW + HOLD)
    working_set.on_status(r, "cancelled", NOW)
    assert r.working_set_expires_at == NOW + DECLINE and r.close_reminder_due_at is None


def test_test_requests_end_after_results():
    r = referral(kind="test")
    working_set.on_status(r, "response_returned", NOW)
    assert r.working_set_expires_at == NOW + GRACE
    working_set.on_status(r, "closed", NOW + timedelta(hours=10))  # never later than before
    assert r.working_set_expires_at == NOW + GRACE

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
