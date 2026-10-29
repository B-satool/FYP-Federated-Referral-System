"""Spec v4 WP3: records arrive encrypted; only the doctor's device opens them (T-DOC-1); staff get titles only
(T-STAFF-1); the platform database holds no record plaintext, data key or private key (T-DB-1); a lost key is
replaced and records are fetched again, while items that existed only on the platform are unrecoverable (T-REC-1)."""
from __future__ import annotations

import json
import subprocess
import uuid

import pytest

from e2e_client import CANARY, ROOT, Device, open_referral
from flows import consented_referral, rubina
from helpers import central, institution, ok
from refcommon import e2e


@pytest.fixture(scope="module")
def pat():
    return rubina()


def _central_dump() -> str:
    run = subprocess.run(["docker", "compose", "exec", "-T", "postgres", "pg_dump", "-U", "postgres", "--data-only",
                          "central_db"], cwd=ROOT, capture_output=True, text=True, timeout=300, encoding="utf-8")
    assert run.returncode == 0, run.stderr[-500:]
    return run.stdout


def test_doctor_opens_records_staff_see_titles_and_the_database_holds_no_plaintext(pat):
    r, doctor, out = consented_referral(pat, ["drali", "chughtai"])
    assert {x["custodian"]: x["status"] for x in out["requests"]} == {"drali": "answered", "chughtai": "answered"}
    resp, opened, deks = open_referral(doctor, r["id"])
    texts = json.dumps([v for v in opened.values() if isinstance(v, dict)])
    assert CANARY in texts  # the canary records were released and decrypt on the doctor's device
    assert len(opened) == len(resp["items"]) > 5
    # staff: titles only, in every response they get (T-STAFF-1)
    staff = central("staff.ali")
    bodies = [staff.get(f"/referrals/{r['id']}").text, staff.get(f"/referrals/{r['id']}/titles").text,
              staff.get(f"/referrals/{r['id']}/record-requests").text, staff.get(f"/referrals/{r['id']}/events").text,
              staff.get(f"/referrals/{r['id']}/audit").text]
    for body in bodies:
        assert CANARY not in body and "Mild depressive" not in body and "7.6" not in body
    assert staff.get(f"/referrals/{r['id']}/encrypted").status_code == 403
    assert staff.post(f"/referrals/{r['id']}/encrypted-batches", {"batch_id": "doc-x", "items": [], "wraps": []}).status_code == 403
    # T-DB-1: the platform database has no canary plaintext, no data key, no doctor private key
    dump = _central_dump()
    assert CANARY not in dump
    for dek in deks.values():
        assert e2e.b64e(dek) not in dump and dek.hex() not in dump
    assert e2e.b64e(e2e.private_pkcs8(doctor.enc)) not in dump


def test_other_doctors_cannot_open_the_referral(pat):
    """T-DOC-1: a doctor at another hospital is refused; ciphertext is only ever wrapped to the referring doctor."""
    r, doctor, _ = consented_referral(pat, ["drali"])
    assert central("dr.asma").get(f"/referrals/{r['id']}/encrypted").status_code == 403
    resp = ok(central("dr.ali").get(f"/referrals/{r['id']}/encrypted"))
    assert {w["recipient_key_id"] for w in resp["wraps"]} == {doctor.enc_key_id}


def test_doctor_uploads_own_items_wrapped_only_to_allowed_keys(pat):
    r, doctor, _ = consented_referral(pat, ["drali"])
    ref = ok(central("dr.ali").get(f"/referrals/{r['id']}"))["reference"]
    batch = f"doc-{uuid.uuid4().hex[:12]}"
    dek = e2e.new_dek()
    item_id = f"{batch}:notes"
    content = {"type": "refx.item/v1", "item_id": item_id, "category": "note", "label": "Consultation notes",
               "record": {"text": f"{CANARY} pain on chewing for 3 weeks"}}
    sealed = e2e.encrypt(dek, json.dumps(content).encode(), e2e.item_aad(ref, item_id, batch))
    title = {"item_id": item_id, "kind": "note", "label": "Consultation notes", "date": e2e.now_iso()[:10]}
    stranger = e2e.public_spki(e2e.generate_key())
    bad = {"batch_id": batch, "items": [{"title": title, "sealed": sealed}],
           "wraps": [{"recipient_key_id": e2e.key_id(stranger), "wrapped": e2e.wrap(stranger, dek, "x")}]}
    assert central("dr.ali").post(f"/referrals/{r['id']}/encrypted-batches", bad).status_code == 422
    good = {"batch_id": batch, "items": [{"title": title, "sealed": sealed}],
            "wraps": [{"recipient_key_id": doctor.enc_key_id,
                       "wrapped": e2e.wrap(doctor.enc_public, dek, e2e.wrap_context(ref, batch, doctor.enc_key_id))}]}
    ok(central("dr.ali").post(f"/referrals/{r['id']}/encrypted-batches", good), 201)
    _, opened, _ = open_referral(doctor, r["id"])
    assert CANARY in opened[item_id]["record"]["text"]
    titles = ok(central("staff.ali").get(f"/referrals/{r['id']}/titles"))
    assert any(t["label"] == "Consultation notes" for t in titles) and CANARY not in json.dumps(titles)


def test_lost_key_records_are_fetched_again_but_platform_only_items_are_lost(pat):
    """T-REC-1: a replacement key is signed, the old one revoked and the administrators told; records from the
    institutions come again for the new key; the doctor's own platform-only item has no wrap for the new key."""
    r, old, _ = consented_referral(pat, ["drali"])
    ref = ok(central("dr.ali").get(f"/referrals/{r['id']}"))["reference"]
    batch = f"doc-{uuid.uuid4().hex[:12]}"
    dek = e2e.new_dek()
    item_id = f"{batch}:notes"
    sealed = e2e.encrypt(dek, b'{"record": {"text": "only on the platform"}}', e2e.item_aad(ref, item_id, batch))
    ok(central("dr.ali").post(f"/referrals/{r['id']}/encrypted-batches", {
        "batch_id": batch, "items": [{"title": {"item_id": item_id, "kind": "note", "label": "Consultation notes"},
                                      "sealed": sealed}],
        "wraps": [{"recipient_key_id": old.enc_key_id,
                   "wrapped": e2e.wrap(old.enc_public, dek, e2e.wrap_context(ref, batch, old.enc_key_id))}]}), 201)
    new = Device("dr.ali")
    assert new.register("drali", recovery=True)["status"] == "active"
    notices = ok(central("admin.ali").get("/notifications"))
    assert any(n["kind"] == "key_recovery" for n in notices)
    ok(central("staff.ali").post(f"/referrals/{r['id']}/record-requests"))  # fetched again under the same consent
    resp, opened, _ = open_referral(new, r["id"])
    assert any(CANARY in json.dumps(v) for v in opened.values() if isinstance(v, dict))
    assert item_id not in opened  # the doctor's own item is unrecoverable without the patient's copy
    revoked = ok(central("dr.ali").get("/e2e/directory", params={"subject_id": old.subject_id, "include_revoked": True}))
    assert any(x["revoked"] and x["entry"]["enc_key_id"] == old.enc_key_id for x in revoked)


def test_records_requests_from_others_are_listed_for_the_source_staff_without_content(pat):
    consented_referral(pat, ["chughtai"])
    rows = ok(institution("chughtai", "staff.chughtai").get("/e2e/record-requests"))
    assert rows and CANARY not in json.dumps(rows)
    assert institution("chughtai", "dr.ali").get("/e2e/record-requests").status_code == 403
