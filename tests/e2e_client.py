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
