"""A test stand-in for a doctor's or patient's browser: it holds private keys locally and does what the web
client does with WebCrypto, using the same suite (refcommon.e2e; interop checked in libs/common/tests)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jwt

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "libs" / "common"))

from refcommon import e2e  # noqa: E402

from helpers import central, institution, ok, token  # noqa: E402

PINNED = ROOT / "infra" / "participants" / "participants.json"
CANARY = "CANARY-9F3A-NOT-A-REAL-PATIENT"


def pinned() -> dict:
    return json.loads(PINNED.read_text(encoding="utf-8"))


def issuer_key(issuer: str) -> str:
    reg = pinned()
    return reg["platform"]["signing_key"] if issuer == "hub" else reg["institutions"][issuer]["signing_key"]


def subject_of(username: str) -> str:
    return jwt.decode(token(username), options={"verify_signature": False})["sub"]


def verified(row: dict) -> dict:
    """The entry if its issuer's pinned key signed it and it is not revoked (as the browser checks)."""
    entry = row["entry"]
    problem = e2e.check_entry(entry, issuer_key(entry["issued_by"]))
    assert problem is None, problem
    assert not row["revoked"]
    return entry


class Device:
    def __init__(self, username: str, kind: str = "doctor"):
        self.username, self.kind = username, kind
        self.enc, self.sig = e2e.generate_key(), e2e.generate_key()
        sub = subject_of(username)
        self.subject_id = f"patient:{sub}" if kind == "patient" else sub

    @property
    def enc_public(self) -> str:
        return e2e.public_spki(self.enc)

    @property
    def enc_key_id(self) -> str:
        return e2e.key_id(self.enc_public)

    def registration(self) -> dict:
        return e2e.sign_object(self.sig, {"type": "refx.key.registration/v1", "subject_id": self.subject_id,
                                          "enc_public_key": self.enc_public,
                                          "sig_public_key": e2e.public_spki(self.sig), "created_at": e2e.now_iso()})

    def register(self, institution_id: str | None = None, recovery: bool = False) -> dict:
        if self.kind == "patient":
            return ok(central(self.username).post("/e2e/patient-keys", {"registration": self.registration()}), 201)
        return ok(institution(institution_id, self.username).post(
            "/e2e/keys/doctor", {"registration": self.registration(), "recovery": recovery}), (200, 201))

    def directory(self) -> dict:
        return ok(central(self.username).get("/e2e/directory/me"))

    def group_key(self, hospital: str, department: str, version: int | None = None):
        """Unwrap the department group key addressed to this device and check it belongs to the signed entry."""
        mine = self.directory()
        wraps = [w for w in mine["group_wraps"] if w["hospital_id"] == hospital and w["department"] == department
                 and w["member_key_id"] == self.enc_key_id and (version is None or w["group_version"] == version)]
        if not wraps:
            return None
        w = max(wraps, key=lambda x: x["group_version"])
        pkcs8 = e2e.unwrap(self.enc, w["wrapped"], e2e.group_context(hospital, department, w["group_version"],
                                                                     self.enc_key_id))
        rows = ok(central(self.username).get(f"/e2e/directory/departments/{hospital}/{department}"))
        entry = next(r["entry"] for r in rows if r["entry"]["key_version"] == w["group_version"])
        assert e2e.check_entry(entry, issuer_key(hospital)) is None
        key = e2e.load_private(pkcs8)
        assert e2e.public_spki(key) == entry["enc_public_key"], "group key does not match the signed entry"
        return key, w["group_version"]


def decrypt_all(resp: dict, deks: dict[str, bytes]) -> dict[str, bytes]:
    """{item_id: plaintext bytes} for every item whose data key is known."""
    ref = resp["reference"]
    out: dict[str, bytes] = {}
    for it in resp["items"]:
        dek = deks.get(it["batch_id"])
        if dek is None:
            continue
        if "chunks" in it["sealed"]:
            out[it["item_id"]] = e2e.decrypt_chunks(dek, it["sealed"]["chunks"], ref, it["item_id"], it["batch_id"])
        else:
            out[it["item_id"]] = e2e.decrypt(dek, it["sealed"], e2e.item_aad(ref, it["item_id"], it["batch_id"]))
    return out


def upload_note(dev: "Device", referral_id: int, text: str, label: str = "Consultation notes",
                category: str = "note", record: dict | None = None) -> str:
    """The doctor's own item (notes, the medicine list), encrypted on the device to the doctor's own key."""
    import uuid

    ref = ok(central(dev.username).get(f"/referrals/{referral_id}"))["reference"]
    batch = f"doc-{uuid.uuid4().hex[:12]}"
    dek = e2e.new_dek()
    item_id = f"{batch}:{category}"
    content = {"type": "refx.item/v1", "item_id": item_id, "category": category, "label": label,
               "date": e2e.now_iso()[:10], "record": record or {"text": text}}
    sealed = e2e.encrypt(dek, json.dumps(content).encode(), e2e.item_aad(ref, item_id, batch))
    ok(central(dev.username).post(f"/referrals/{referral_id}/encrypted-batches", {
        "batch_id": batch, "items": [{"title": {"item_id": item_id, "kind": "note", "category": category,
                                                "label": label, "date": e2e.now_iso()[:10]}, "sealed": sealed}],
        "wraps": [{"recipient_key_id": dev.enc_key_id,
                   "wrapped": e2e.wrap(dev.enc_public, dek, e2e.wrap_context(ref, batch, dev.enc_key_id))}]}), 201)
    return item_id


def build_approval(dev: "Device", referral_id: int, only: set[str] | None = None, version: int | None = None,
                   tamper: str | None = None, not_for_patient: set[str] = frozenset()) -> dict:
    """What the doctor's browser does on 'Approve and sign': decrypt the chosen items, hash each plaintext, build and
    sign the manifest, and re-wrap each included batch's data key to the receiving department and the patient (both
    entries verified against pinned keys first)."""
    detail = ok(central(dev.username).get(f"/referrals/{referral_id}"))
    resp, _, deks = open_referral(dev, referral_id)
    plain = decrypt_all(resp, deks)
    dept = verified({"entry": detail["recipient_keys"]["department"]["entry"], "revoked": False})
    patient_row = detail["recipient_keys"]["patient"]
    patient = verified({"entry": patient_row["entry"], "revoked": False}) if patient_row else None
    items = []
    for it in resp["items"]:
        if it["item_id"] not in plain or (only is not None and it["item_id"] not in only):
            continue
        items.append({"batch_id": it["batch_id"], "item_id": it["item_id"], "kind": it["kind"], "title": it["label"],
                      "content_hash": e2e.sha256_hex(plain[it["item_id"]]),
                      "ciphertext_hash": it["ciphertext_sha256"]})
    if tamper:  # a hash that does not match what is stored, or a changed item after signing
        items[0][tamper] = "0" * 64
    me = dev.directory()["entries"][0]["entry"]
    manifest = e2e.package_manifest(
        referral=resp["reference"], version=version or len(detail["packages"]) + 1, signer_subject=dev.subject_id,
        signer_sig_public=me["sig_public_key"], signer_hospital=me["hospital_id"],
        recipient_hospital=dept["hospital_id"], recipient_department=dept["department"],
        group_enc_public=dept["enc_public_key"], group_key_version=dept["key_version"], items=items,
        patient_enc_public=patient["enc_public_key"] if patient else None)
    signed = e2e.sign_object(dev.sig, manifest)
    wraps = []
    for batch in sorted({it["batch_id"] for it in items}):
        for target in filter(None, [dept, None if batch in not_for_patient else patient]):
            wraps.append({"batch_id": batch, "recipient_key_id": target["enc_key_id"],
                          "wrapped": e2e.wrap(target["enc_public_key"], deks[batch],
                                              e2e.wrap_context(resp["reference"], batch, target["enc_key_id"]))})
    return {"manifest": signed, "wraps": wraps}


def open_received(dev: "Device", reference: str, hospital: str, department: str) -> tuple[dict, dict[str, bytes]]:
    """The receiving doctor's browser: fetch the sent package, open the department group key wrapped to this
    device, unwrap each batch's data key, decrypt, and check the copy against the signed manifest."""
    pkg = ok(central(dev.username).get(f"/e2e/received/{reference}/package"))
    signer = verified(pkg["signer"])
    group = {}
    for w in pkg["wraps"]:
        if w["key_version"] not in group:
            got = dev.group_key(hospital, department, w["key_version"])
            assert got, f"no group key version {w['key_version']} for this device"
            group[w["key_version"]] = got[0]
    deks = {w["batch_id"]: e2e.unwrap(group[w["key_version"]], w["wrapped"],
                                      e2e.wrap_context(reference, w["batch_id"], w["recipient_key_id"]))
            for w in pkg["wraps"]}
    plain = decrypt_all(pkg, deks)
    problems = e2e.check_copy(pkg["manifest"], signer["sig_public_key"], plain)
    assert not problems, problems
    return pkg, plain


def open_referral(dev: "Device", referral_id: int, group: tuple | None = None) -> tuple[dict, dict, dict]:
    """What the browser does on the Records step: fetch ciphertext and wraps, unwrap each batch's data key with this
    device's key (or a department group key: (private key, key id)), decrypt. Returns (response, {item_id: content
    or bytes}, {batch_id: data key})."""
    resp = ok(central(dev.username).get(f"/referrals/{referral_id}/encrypted"))
    ref = resp["reference"]
    deks: dict[str, bytes] = {}
    for w in resp["wraps"]:
        if w["batch_id"] in deks:
            continue
        if w["recipient_key_id"] == dev.enc_key_id:
            deks[w["batch_id"]] = e2e.unwrap(dev.enc, w["wrapped"], e2e.wrap_context(ref, w["batch_id"], dev.enc_key_id))
        elif group and w["recipient_key_id"] == group[1]:
            deks[w["batch_id"]] = e2e.unwrap(group[0], w["wrapped"], e2e.wrap_context(ref, w["batch_id"], group[1]))
    opened: dict[str, object] = {}
    for it in resp["items"]:
        dek = deks.get(it["batch_id"])
        if dek is None:
            continue
        if "chunks" in it["sealed"]:
            opened[it["item_id"]] = e2e.decrypt_chunks(dek, it["sealed"]["chunks"], ref, it["item_id"], it["batch_id"])
        else:
            opened[it["item_id"]] = json.loads(e2e.decrypt(dek, it["sealed"], e2e.item_aad(ref, it["item_id"], it["batch_id"])))
    return resp, opened, deks
