"""Spec v4 WP1: hospital-signed key directory, department group keys, revocation and rotation (T-DIR-1,
T-GROUP-1), and the signed machine-to-machine requests between adapters and the platform."""
from __future__ import annotations

import json
import subprocess

import pytest

from e2e_client import Device, ROOT, issuer_key, verified
from helpers import central, institution, ok, token
from refcommon import e2e


def _in_adapter(inst: str, code: str) -> dict:
    """Run Python inside an institution's adapter container (it holds that hospital's signing key)."""
    run = subprocess.run(["docker", "compose", "exec", "-T", inst, "python", "-c", code], cwd=ROOT,
                         capture_output=True, text=True, timeout=120)
    assert run.returncode == 0, run.stderr[-2000:]
    return json.loads(run.stdout.strip().splitlines()[-1])


def test_doctor_key_is_signed_by_the_hospital_and_gets_the_department_key():
    dev = Device("dr.asma")
    out = dev.register("ziauddin")
    assert out["status"] == "active" and out["department"] == "cardiology"
    rows = ok(central("dr.asma").get("/e2e/directory", params={"subject_id": dev.subject_id}))
    entry = verified(next(r for r in rows if r["entry"]["enc_key_id"] == dev.enc_key_id))
    assert entry["hospital_id"] == "ziauddin" and entry["issued_by"] == "ziauddin"
    assert e2e.check_entry(entry, issuer_key("akuh")) is not None  # another hospital's key does not verify it
    key, version = dev.group_key("ziauddin", "cardiology")
    assert key is not None and version >= 1
    # anyone signed in can read public entries; a colleague elsewhere can verify the department key
    dept = ok(central("dr.ali").get("/e2e/directory/departments/ziauddin/cardiology"))
    assert verified(dept[0])["subject_type"] == "department"


def test_registration_needs_proof_of_possession_and_a_doctor():
    dev = Device("dr.irfan")
    reg = dev.registration()
    forged = {**reg, "enc_public_key": e2e.public_spki(e2e.generate_key())}  # signature no longer matches
    r = institution("ziauddin", "dr.irfan").post("/e2e/keys/doctor", {"registration": forged})
    assert r.status_code == 422 and "proof of possession" in r.text
    other = {**reg, "subject_id": "someone-else"}
    assert institution("ziauddin", "dr.irfan").post("/e2e/keys/doctor", {"registration": other}).status_code == 422
    assert institution("ziauddin", "staff.zia").post("/e2e/keys/doctor", {"registration": reg}).status_code == 403
    assert institution("akuh", "dr.irfan").post("/e2e/keys/doctor", {"registration": reg}).status_code == 403


FORGED_PUBLISH = """
import json
from refcommon import e2e
from app.main import SessionLocal
from app import m2m
from app.config import INSTITUTION
with SessionLocal() as db:
    impostor = e2e.generate_key()
    pinned_kid = e2e.key_id(m2m.keys.hospital_public(db))
    entry = e2e.directory_entry(subject_id="forged-doctor", subject_type="doctor", role="doctor",
        hospital_id=INSTITUTION, department="general_practice", display_name="Dr Forged",
        enc_public_key=e2e.public_spki(e2e.generate_key()), sig_public_key=e2e.public_spki(e2e.generate_key()),
        key_version=1, valid_days=30, issued_by=INSTITUTION, signer_key_id=pinned_kid)
    forged = e2e.sign_object(impostor, entry)                      # not signed by the pinned hospital key
    unsigned = {k: v for k, v in entry.items()}                    # no signature at all
    r = m2m.hub_call(db, "POST", "/e2e/adapter/directory", json={"entries": [forged, unsigned]})
    bad = e2e.make_assertion(impostor, issuer=INSTITUTION, audience="hub")
    import httpx
    r2 = httpx.post(m2m.HUB_URL + "/e2e/adapter/directory", json={"entries": []},
                    headers={"Authorization": "Bearer " + bad}, timeout=15)
    token = e2e.make_assertion(m2m.keys.hospital_key(db), issuer=INSTITUTION, audience="hub")
    h = {"Authorization": "Bearer " + token}
    r3 = httpx.post(m2m.HUB_URL + "/e2e/adapter/directory", json={}, headers=h, timeout=15)
    r4 = httpx.post(m2m.HUB_URL + "/e2e/adapter/directory", json={}, headers=h, timeout=15)
    wrong_aud = e2e.make_assertion(m2m.keys.hospital_key(db), issuer=INSTITUTION, audience="akuh")
    r5 = httpx.post(m2m.HUB_URL + "/e2e/adapter/directory", json={},
                    headers={"Authorization": "Bearer " + wrong_aud}, timeout=15)
    print(json.dumps({"forged": r.json(), "bad_key": r2.status_code, "first": r3.status_code,
                      "replay": r4.status_code, "replay_text": r4.text, "wrong_aud": r5.status_code}))
"""


def test_platform_refuses_entries_not_signed_by_the_hospital_and_bad_assertions():
    """T-DIR-1 (platform side) and the platform's half of T-TOKEN-1."""
    out = _in_adapter("drali", FORGED_PUBLISH)
    assert out["forged"]["stored"] == 0 and len(out["forged"]["rejected"]) == 2
    assert out["bad_key"] == 401  # assertion signed by a key that is not drali's pinned key
    assert out["first"] == 200 and out["replay"] == 401 and "replay" in out["replay_text"]
    assert out["wrong_aud"] == 401
    rows = ok(central("dr.ali").get("/e2e/directory", params={"subject_id": "forged-doctor"}))
    assert rows == []
    audit = ok(central("admin.ali").get("/admin/audit", params={"action": "directory.signature_failure"}))
    assert any(a["target_id"] == "forged-doctor" and a["outcome"] == "denied" for a in audit)


def test_revoking_a_doctor_rotates_the_department_key():
    """T-GROUP-1: the leaver keeps only the old version; the department key moves on; a re-joined key gets
    the new version."""
    dev = Device("dr.salman")
    ok_entry = dev.register("akuh")
    _, v1 = dev.group_key("akuh", "orthopaedics")
    rows = ok(institution("akuh", "admin.aku").get("/e2e/keys/doctors"))
    mine = next(r for r in rows if r["enc_key_id"] == dev.enc_key_id)
    assert mine["id"] == ok_entry["id"]
    ok(institution("akuh", "admin.aku").post(f"/e2e/keys/doctors/{mine['id']}/revoke", {"reason": "left the department"}))
    revoked = ok(central("dr.salman").get("/e2e/directory", params={"subject_id": dev.subject_id,
                                                                    "include_revoked": True}))
    row = next(r for r in revoked if r["entry"]["enc_key_id"] == dev.enc_key_id)
    assert row["revoked"] and e2e.check_revocation(row["revocation"], issuer_key("akuh"))
    assert dev.directory()["group_wraps"] == []  # the leaver is served no group key any more
    dept = ok(central("dr.ali").get("/e2e/directory/departments/akuh/orthopaedics"))
    current = max(verified(r)["key_version"] for r in dept if not r["revoked"])
    assert current == v1 + 1
    rejoined = Device("dr.salman")
    rejoined.register("akuh")
    key, version = rejoined.group_key("akuh", "orthopaedics")
    assert version == current
    # the old device key cannot open the new version's wrap (it was never wrapped to it)
    assert dev.group_key("akuh", "orthopaedics", version) is None


def test_staff_and_patients_cannot_manage_doctor_keys():
    assert institution("akuh", "staff.aku").get("/e2e/keys/doctors").status_code == 403
    assert institution("akuh", "dr.faisal").post("/e2e/keys/departments/dentistry/rotate",
                                                 {"reason": "not allowed"}).status_code == 403


def _patient_user() -> str | None:
    try:
        token("rubina.akhtar")
        return "rubina.akhtar"
    except Exception:  # noqa: BLE001 - the local realm may predate the patient accounts
        return None


def test_patient_key_is_signed_by_the_platform():
    user = _patient_user()
    if user is None:
        pytest.skip("no patient account in the local Keycloak realm (run scripts/refresh-keycloak-realm.ps1 -Force)")
    dev = Device(user, kind="patient")
    out = dev.register()
    entry = verified(out)
    assert entry["issued_by"] == "hub" and entry["subject_type"] == "patient" and len(entry["patient_cnic"]) == 13
    assert central("dr.ali").post("/e2e/patient-keys", {"registration": dev.registration()}).status_code == 403
