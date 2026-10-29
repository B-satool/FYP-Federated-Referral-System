"""Spec v4 WP8 and WP10: papers and the patient's copy (T-LIFE-2, T-OCR-1, T-NOCOPY-1).

* The patient adds a paper in the app, encrypted on the phone to the referring doctor's key and their own; the doctor
  opens it; staff see "Patient-provided document" and a date; the platform's plaintext upload path refuses referrals.
* The patient saves their copy: ciphertext, the data keys wrapped to their key and the signed manifest. Notes the
  doctor did not share have no wrap for the patient. After the purge the platform answers "purged", and the copy kept
  on the device still opens and verifies against the doctor's signature.
"""
from __future__ import annotations

import json

import pytest

from e2e_client import CANARY, Device, decrypt_all, open_referral, upload_note, build_approval
from flows import central_python, consented_referral, rubina
from helpers import central, institution, ok, wait_for
from refcommon import e2e


@pytest.fixture(scope="module")
def pat():
    return rubina()


@pytest.fixture(scope="module")
def faisal():
    dev = Device("dr.faisal")
    dev.register("akuh")
    return dev


def patient_batch(pat, doctor: Device, reference: str, data: bytes) -> dict:
    batch = "pat-" + e2e.b64e(e2e.new_dek())[:12].replace("+", "a").replace("/", "b").lower()
    dek = e2e.new_dek()
    item_id = f"{batch}:scan"
    chunks = e2e.encrypt_chunks(dek, data, reference, item_id, batch)
    me = e2e.public_spki(pat.enc)
    return {"batch_id": batch,
            "items": [{"title": {"item_id": item_id, "kind": "scan", "label": f"{CANARY} prescription"},
                       "sealed": {"chunks": chunks, "mime": "image/png"}}],
            "wraps": [{"recipient_key_id": doctor.enc_key_id,
                       "wrapped": e2e.wrap(doctor.enc_public, dek, e2e.wrap_context(reference, batch, doctor.enc_key_id))},
                      {"recipient_key_id": e2e.key_id(me),
                       "wrapped": e2e.wrap(me, dek, e2e.wrap_context(reference, batch, e2e.key_id(me)))}]}


def test_patient_adds_a_paper_only_the_doctor_and_patient_can_read(pat, faisal):
    r, doctor, _ = consented_referral(pat, ["drali"])
    reference = ok(central("dr.ali").get(f"/referrals/{r['id']}"))["reference"]
    # the server's plaintext upload path refuses referrals: papers are read and encrypted on the device (D15)
    resp = central("dr.ali").post(f"/referrals/{r['id']}/documents", files={"file": ("p.png", b"\x89PNG", "image/png")})
    assert resp.status_code == 409
    stranger = e2e.public_spki(e2e.generate_key())
    bad = patient_batch(pat, doctor, reference, b"x")
    bad["wraps"][0] = {"recipient_key_id": e2e.key_id(stranger), "wrapped": bad["wraps"][0]["wrapped"]}
    assert pat.add_paper(reference, bad)[0] == 422
    status, out = pat.add_paper(reference, patient_batch(pat, doctor, reference, f"{CANARY} image bytes".encode()))
    assert status == 201, out
    _, opened, _ = open_referral(doctor, r["id"])
    assert any(isinstance(v, bytes) and CANARY.encode() in v for v in opened.values())
    titles = ok(central("staff.ali").get(f"/referrals/{r['id']}/titles"))
    paper = [t for t in titles if t["label"] == "Patient-provided document"]
    assert paper and CANARY not in json.dumps(titles)  # the patient's own label never reaches staff


def test_patient_copy_survives_the_purge_and_verifies(pat, faisal):
    r, doctor, _ = consented_referral(pat, ["drali", "chughtai"])
    notes = upload_note(doctor, r["id"], "Private notes for the specialist only")
    ok(central("dr.ali").post(f"/referrals/{r['id']}/packages",
                              build_approval(doctor, r["id"], not_for_patient={notes.split(":")[0]})), 201)
    detail = ok(central("staff.ali").get(f"/referrals/{r['id']}"))
    reference = detail["reference"]
    ok(central("staff.ali").post(f"/referrals/{r['id']}/send", {"expected_version": detail["row_version"]}))
    status, copy = pat.copy(reference)
    assert status == 200, copy
    # the patient's device: unwrap with the patient's key, decrypt, check against the doctor's signature
    me = e2e.key_id(e2e.public_spki(pat.enc))
    deks = {w["batch_id"]: e2e.unwrap(pat.enc, w["wrapped"], e2e.wrap_context(reference, w["batch_id"], me))
            for w in copy["wraps"]}
    plain = decrypt_all(copy, deks)
    assert notes not in plain and any(CANARY in v.decode(errors="ignore") for v in plain.values())
    signer = copy["signer"]["entry"]["sig_public_key"]
    shared = {**copy["manifest"], "items": [x for x in copy["manifest"]["items"] if x["item_id"] in plain]}
    assert e2e.verify_object(signer, copy["manifest"])
    assert not [p for p in e2e.check_copy(shared, signer, plain) if "signature" not in p]

    wait_for(lambda: ok(central("staff.ali").get(f"/referrals/{r['id']}"))["status"] == "submitted", 60, what="delivery")
    version = ok(central("dr.ali").get(f"/referrals/{r['id']}"))["row_version"]
    ok(central("dr.ali").post(f"/referrals/{r['id']}/cancel", {"reason": "Synthetic test: purge", "expected_version": version}))
    central_python(f"""
from datetime import timedelta
from sqlalchemy import select
from app.db import SessionLocal
from app.lifecycle.working_set import purge_due
from app.models import Referral
with SessionLocal() as db:
    r = db.scalars(select(Referral).where(Referral.reference == {reference!r})).one()
    r.working_set_expires_at = r.working_set_expires_at - timedelta(days=2)
    db.commit()
    print(purge_due(db))
""")
    status, gone = pat.copy(reference)
    assert status == 410 and gone.get("purged")
    check = ok(central("dr.ali").post("/e2e/verify-manifest", {"reference": reference, "manifest": copy["manifest"]}))
    assert check["result"] == "purged" and check["signature_valid"]
    # the copy kept on the device still opens and verifies, with nothing from the platform
    again = decrypt_all(copy, {w["batch_id"]: e2e.unwrap(pat.enc, w["wrapped"], e2e.wrap_context(reference, w["batch_id"], me))
                               for w in copy["wraps"]})
    assert again == plain
