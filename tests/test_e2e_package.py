"""Spec v4 WP5: the doctor approves on their device (a signed manifest, data keys re-wrapped to the receiving
department and the patient), staff send a titles-only notice, and the receiving department's doctor opens the
package with the department group key and checks it against the signature (T-APPROVE-1, T-STAFF-1, T-DOC-1)."""
from __future__ import annotations

import json

import pytest

from e2e_client import CANARY, Device, build_approval, open_received, upload_note
from flows import consented_referral, rubina
from helpers import central, institution, ok, wait_for
from refcommon import e2e


@pytest.fixture(scope="module")
def pat():
    return rubina()


@pytest.fixture(scope="module")
def faisal():
    """A doctor of the receiving department (Aga Khan, dentistry): registering gives him the group key."""
    dev = Device("dr.faisal")
    dev.register("akuh")
    return dev


def _case(reference: str, user: str) -> dict:
    cases = ok(institution("akuh", user).get("/cases"))
    return next(c for c in cases if c["central_referral_id"] == reference)


def test_approve_send_and_the_receiving_doctor_opens_it(pat, faisal):
    r, doctor, _ = consented_referral(pat, ["drali", "chughtai"])
    notes = upload_note(doctor, r["id"], f"{CANARY} pain on chewing for three weeks")
    staff = central("staff.ali")
    assert staff.post(f"/referrals/{r['id']}/send", {"expected_version": r["row_version"]}).status_code == 409

    approval = build_approval(doctor, r["id"])
    pm = ok(central("dr.ali").post(f"/referrals/{r['id']}/packages", approval), 201)
    assert pm["version"] == 1 and pm["item_count"] == len(approval["manifest"]["items"])
    assert notes in {x["item_id"] for x in approval["manifest"]["items"]}

    detail = ok(staff.get(f"/referrals/{r['id']}"))
    sent = ok(staff.post(f"/referrals/{r['id']}/send", {"expected_version": detail["row_version"]}))
    assert sent["package_version"] == 1
    reference = detail["reference"]
    wait_for(lambda: ok(staff.get(f"/referrals/{r['id']}"))["status"] == "submitted", 60, what="delivery")

    # the receiving hospital's system holds a notice: titles and the manifest hash, no content
    case = _case(reference, "staff.aku")
    full = ok(institution("akuh", "staff.aku").get(f"/cases/{case['id']}"))
    assert CANARY not in json.dumps(full) and full["packages"][0]["content_hash"] == pm["manifest_sha256"]
    assert {t["title"] for t in full["packages"][0]["record_titles"]} >= {"Consultation notes"}

    # the department's doctor opens and verifies it; staff and other departments cannot fetch it
    pkg, plain = open_received(faisal, reference, "akuh", "dentistry")
    assert CANARY in plain[notes].decode()
    assert any(CANARY in v.decode(errors="ignore") for k, v in plain.items() if k != notes)
    assert central("staff.aku").get(f"/e2e/received/{reference}/package").status_code == 403
    assert central("dr.naveed").get(f"/e2e/received/{reference}/package").status_code == 403
    assert central("dr.ali").get(f"/e2e/received/{reference}/package").status_code == 403


def test_tampered_or_foreign_signatures_are_refused_and_versions_stay_verifiable(pat, faisal):
    """T-APPROVE-1: a ciphertext hash that does not match, or a manifest signed with another key, is refused; a
    second version needs its own signature, and the first still verifies for its own version."""
    r, doctor, _ = consented_referral(pat, ["drali"])
    bad = build_approval(doctor, r["id"], tamper="ciphertext_hash")
    resp = central("dr.ali").post(f"/referrals/{r['id']}/packages", bad)
    assert resp.status_code == 422 and "does not match the stored ciphertext" in resp.text

    forged = build_approval(doctor, r["id"])
    forged["manifest"] = e2e.sign_object(e2e.generate_key(), e2e.unsigned(forged["manifest"]))
    assert central("dr.ali").post(f"/referrals/{r['id']}/packages", forged).status_code == 422

    v1 = build_approval(doctor, r["id"])
    ok(central("dr.ali").post(f"/referrals/{r['id']}/packages", v1), 201)
    first = v1["manifest"]["items"][0]["item_id"]
    v2 = build_approval(doctor, r["id"], only={x["item_id"] for x in v1["manifest"]["items"]} - {first}, version=2)
    pm2 = ok(central("dr.ali").post(f"/referrals/{r['id']}/packages", v2), 201)
    assert pm2["version"] == 2

    reference = ok(central("dr.ali").get(f"/referrals/{r['id']}"))["reference"]
    check = ok(central("dr.ali").post("/e2e/verify-manifest", {"reference": reference, "manifest": v1["manifest"]}))
    assert check["result"] == "match" and check["signature_valid"]
    changed = json.loads(json.dumps(v1["manifest"]))
    changed["items"][0]["content_hash"] = "f" * 64  # any change after signing breaks the signature
    check = ok(central("dr.ali").post("/e2e/verify-manifest", {"reference": reference, "manifest": changed}))
    assert check["result"] == "mismatch" and not check["signature_valid"]
    rows = ok(central("staff.ali").get(f"/referrals/{r['id']}/packages"))
    assert [x["superseded"] for x in rows] == [False, True] and "manifest" not in rows[0]


def test_receiving_hospital_adds_its_own_records_for_its_doctors():
    """Spec v4 step 8: receiving staff add their hospital's records; they are encrypted to the department's key, so
    the department's doctors open them and nobody on the referring side gets a key (or even the titles)."""
    from conftest import new_referral
    from flows import send_and_take_in

    salman = Device("dr.salman")
    salman.register("akuh")
    doctor = Device("dr.ali")
    doctor.register("drali")
    # Tariq is already an Aga Khan patient with records there (seed P2), so intake matches and nothing new is registered
    r = new_referral("Tariq", "akuh", "orthopaedics", "Total knee replacement (right)", ["major_surgery"])
    upload_note(doctor, r["id"], "Knee pain for two years; referred for a surgical opinion.")
    reference, case = send_and_take_in(r, doctor, assign_to="dr.salman")
    added = ok(institution("akuh", "staff.aku").post(f"/cases/{case['id']}/own-records"))
    assert added["items"] > 0
    assert institution("akuh", "dr.salman").post(f"/cases/{case['id']}/own-records").status_code == 403  # staff only
    pkg, plain = open_received_with_own(salman, reference, "akuh", "orthopaedics")
    own = [it for it in pkg["items"] if it["item_id"].startswith("akuh:")]
    assert len(own) == added["items"] and all(it["item_id"] in plain for it in own)
    mine = ok(central("dr.ali").get(f"/referrals/{r['id']}/encrypted"))
    assert not [it for it in mine["items"] if it["item_id"].startswith("akuh:")]
    titles = ok(central("staff.ali").get(f"/referrals/{r['id']}/titles"))
    assert not [t for t in titles if t["item_id"].startswith("akuh:")]


def open_received_with_own(dev: Device, reference: str, hospital: str, department: str):
    """Like open_received, plus the receiving hospital's own batches (not in the signed manifest)."""
    from e2e_client import decrypt_all

    pkg = ok(central(dev.username).get(f"/e2e/received/{reference}/package"))
    group = {}
    for w in pkg["wraps"]:
        if w["key_version"] not in group:
            group[w["key_version"]] = dev.group_key(hospital, department, w["key_version"])[0]
    deks = {w["batch_id"]: e2e.unwrap(group[w["key_version"]], w["wrapped"],
                                      e2e.wrap_context(reference, w["batch_id"], w["recipient_key_id"]))
            for w in pkg["wraps"]}
    return pkg, decrypt_all(pkg, deks)


def test_only_the_referring_doctor_approves(pat, faisal):
    r, doctor, _ = consented_referral(pat, ["drali"])
    approval = build_approval(doctor, r["id"])
    assert central("staff.ali").post(f"/referrals/{r['id']}/packages", approval).status_code == 403
