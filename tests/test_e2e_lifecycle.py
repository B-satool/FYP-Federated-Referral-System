"""Spec v4 WP9: close reminder 30 days after acceptance, weekly repeats and escalation (never a silent auto-close);
extend with a reason, capped at 180 days; the specialist closes and the referral is crypto-shredded after the grace
period, with a receipt, idempotently; a decline purges after a short grace (T-LIFE-1, T-NOCOPY-1)."""
from __future__ import annotations

import json

import pytest

from e2e_client import CANARY, Device
from flows import central_python, consented_referral, rubina, send_and_take_in
from helpers import central, institution, ok, wait_for


@pytest.fixture(scope="module")
def pat():
    return rubina()


@pytest.fixture(scope="module")
def asma():
    """The receiving doctor: Ziauddin cardiology (Rubina is already a Ziauddin patient, so intake matches her record
    and no test leaves a new registration behind)."""
    dev = Device("dr.asma")
    dev.register("ziauddin")
    return dev


def shift(reference: str, days: int, *fields: str) -> None:
    """Move the given referral timestamps back by `days` (the clock moves forward for this referral)."""
    sets = "; ".join(f"r.{f} = r.{f} - timedelta(days={days}) if r.{f} else None" for f in fields)
    central_python(f"""
from datetime import timedelta
from sqlalchemy import select
from app.db import SessionLocal
from app.models import Referral
with SessionLocal() as db:
    r = db.scalars(select(Referral).where(Referral.reference == {reference!r})).one()
    {sets}
    db.commit()
""")


def job(name: str) -> dict:
    out = central_python(f"""
import json
from app.db import SessionLocal
from app.lifecycle.working_set import {name}
with SessionLocal() as db:
    print(json.dumps({name}(db), default=str))
""")
    return json.loads(out.splitlines()[-1])


def accepted_referral(pat, asma):
    r, doctor, _ = consented_referral(pat, ["drali", "chughtai"], dest="ziauddin", dept="cardiology", procedure="Coronary angiography", tags=("iodinated_contrast",))
    ref, case = send_and_take_in(r, doctor, assign_to="dr.asma", hospital="ziauddin")
    ok(institution("ziauddin", "dr.asma").post(f"/cases/{case['id']}/decision", {"decision": "accept"}))
    wait_for(lambda: ok(central("staff.ali").get(f"/referrals/{r['id']}"))["status"] == "accepted", 60, what="acceptance")
    return r, ref, case


def notes(user: str, ref: str, kind: str) -> list:
    return [n for n in ok(central(user).get("/notifications")) if n["kind"] == kind and ref in n["title"]]


def test_reminders_escalate_extension_moves_them_and_close_purges(pat, asma):
    r, ref, case = accepted_referral(pat, asma)
    assert job("reminders_due")["reminded"] == 0 or not notes("dr.asma", ref, "close_reminder")  # not due yet

    shift(ref, 31, "accepted_at", "close_reminder_due_at")
    job("reminders_due")
    assert notes("dr.asma", ref, "close_reminder")  # day 30: the department's doctors
    for _ in range(2):  # weekly repeats, then escalation to the receiving staff
        shift(ref, 8, "last_reminder_at")
        job("reminders_due")
    assert notes("staff.zia", ref, "close_reminder_escalated")
    assert ok(central("staff.ali").get(f"/referrals/{r['id']}"))["status"] == "accepted"  # never auto-closed

    surgeon = institution("ziauddin", "dr.asma")
    assert surgeon.post(f"/cases/{case['id']}/extend-hold", {"reason": ""}).status_code == 422  # a reason is required
    ok(surgeon.post(f"/cases/{case['id']}/extend-hold", {"reason": "Waiting for the operation date"}))
    events = wait_for(lambda: [e for e in ok(central("staff.ali").get(f"/referrals/{r['id']}/events"))
                               if e["event_type"] == "extended_by_specialist"], 30, what="extension at the platform")
    assert events

    ok(surgeon.post(f"/cases/{case['id']}/complete"))  # the specialist closes
    detail = wait_for(lambda: (d := ok(central("staff.ali").get(f"/referrals/{r['id']}"))) and d["status"] == "closed" and d,
                      60, what="closed at the platform")
    assert detail["working_set_purged_at"] is None  # the grace period comes first
    assert job("purge_due") == 0
    shift(ref, 8, "working_set_expires_at")
    assert job("purge_due") == 1
    # crypto-shredded: no ciphertext or wrapped keys left; the receipt keeps the manifest hash; idempotent
    left = central_python(f"""
from sqlalchemy import func, select
from app.db import SessionLocal
from app.models import EncryptedItem, PurgeReceipt, Referral, WrappedKey
with SessionLocal() as db:
    r = db.scalars(select(Referral).where(Referral.reference == {ref!r})).one()
    items = db.scalar(select(func.count()).select_from(EncryptedItem).where(EncryptedItem.referral_id == r.id))
    wraps = db.scalar(select(func.count()).select_from(WrappedKey).where(WrappedKey.referral_id == r.id))
    rec = db.scalars(select(PurgeReceipt).where(PurgeReceipt.referral_id == r.id)).one()
    print(items, wraps, rec.trigger, bool(rec.manifest_hash), rec.items_count > 0)
""")
    assert left.split()[-5:] == ["0", "0", "closed_by_specialist", "True", "True"], left
    assert job("purge_due") == 0
    assert central("dr.asma").get(f"/e2e/received/{ref}/package").status_code == 410
    assert central("dr.ali").get(f"/referrals/{r['id']}/encrypted").status_code == 410
    titles = ok(central("staff.ali").get(f"/referrals/{r['id']}/titles"))
    assert titles == []  # titles go with the ciphertext (O6)
    # the receiving hospital drops its notice too, and nothing there ever held content (T-NOCOPY-1)
    removed = wait_for(lambda: ok(institution("ziauddin", "staff.zia").get(f"/cases/{case['id']}"))["case"]["shared_removed_at"],
                       60, what="removal at the receiving hospital")
    assert removed and CANARY not in json.dumps(ok(institution("ziauddin", "staff.zia").get(f"/cases/{case['id']}")))


def test_extension_stops_at_the_maximum(pat, asma):
    r, ref, case = accepted_referral(pat, asma)
    surgeon = institution("ziauddin", "dr.asma")
    for _ in range(5):
        ok(surgeon.post(f"/cases/{case['id']}/extend-hold", {"reason": "Still under treatment"}))
    resp = surgeon.post(f"/cases/{case['id']}/extend-hold", {"reason": "Still under treatment"})
    assert resp.status_code == 409 and "180" in resp.text


def test_decline_purges_after_a_short_grace(pat, asma):
    r, doctor, _ = consented_referral(pat, ["drali"], dest="ziauddin", dept="cardiology", procedure="Coronary angiography", tags=("iodinated_contrast",))
    ref, case = send_and_take_in(r, doctor, assign_to="dr.asma", hospital="ziauddin")
    ok(institution("ziauddin", "dr.asma").post(f"/cases/{case['id']}/decision",
                                             {"decision": "decline", "reason": "Not a dental problem"}))
    d = wait_for(lambda: (x := ok(central("staff.ali").get(f"/referrals/{r['id']}"))) and x["status"] == "declined" and x,
                 60, what="decline at the platform")
    assert d["working_set_purged_at"] is None
    shift(ref, 2, "working_set_expires_at")
    assert job("purge_due") == 1
    assert ok(central("staff.ali").get(f"/referrals/{r['id']}"))["working_set_purged_at"]
