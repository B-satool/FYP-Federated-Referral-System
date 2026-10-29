"""A patient for the integration checks when the local Keycloak realm has no patient accounts.

The patient's device (keys, signatures) is real and runs here, as in e2e_client.Device. Only the sign-in is
simulated: the platform's patient handlers are called inside the central container with the identity a verified
patient token would give (patient role, CNIC, no institution). Every check after that is the real one: the
platform verifies the signed consent, and each adapter fetches it and verifies it again.

When the realm does have patient accounts, the tests use the real sign-in instead (PatientViaKeycloak).
"""
from __future__ import annotations

import json
import subprocess
import uuid

from e2e_client import ROOT
from helpers import central, ok, token
from refcommon import e2e

PRELUDE = """
import json, sys
from refcommon.auth import Principal
from app.db import SessionLocal
from app.keys import router as keys_router
from app.consent import router as consent_router
args = json.loads(sys.stdin.read())
p = Principal(subject=args["sub"], username=args["username"], display_name=args["name"], institution_id=None,
              roles=frozenset({"patient"}), client_id="referral-web", token="", cnic=args["cnic"])
db = SessionLocal()
"""


def _run(code: str, args: dict) -> object:
    run = subprocess.run(["docker", "compose", "exec", "-T", "central", "python", "-c", PRELUDE + code], cwd=ROOT,
                         input=json.dumps(args), capture_output=True, text=True, timeout=120)
    if run.returncode != 0:
        tail = run.stderr.strip().splitlines()[-1] if run.stderr.strip() else ""
        raise RuntimeError(tail or run.stderr[-500:])
    return json.loads(run.stdout.strip().splitlines()[-1])


class SimulatedPatient:
    simulated = True

    def __init__(self, name: str, cnic: str):
        self.name, self.cnic = name, "".join(ch for ch in cnic if ch.isdigit())
        self.sub = f"sim-{uuid.uuid4()}"
        self.subject_id = f"patient:{self.sub}"
        self.enc, self.sig = e2e.generate_key(), e2e.generate_key()

    @property
    def args(self) -> dict:
        return {"sub": self.sub, "username": "simulated.patient", "name": self.name, "cnic": self.cnic}

    def register(self) -> dict:
        reg = e2e.sign_object(self.sig, {"type": "refx.key.registration/v1", "subject_id": self.subject_id,
                                         "enc_public_key": e2e.public_spki(self.enc),
                                         "sig_public_key": e2e.public_spki(self.sig), "created_at": e2e.now_iso()})
        return _run("out = keys_router.register_patient_key(keys_router.PatientKeyIn(registration=args['reg']), db, p)\n"
                    "print(json.dumps(out, default=str))", {**self.args, "reg": reg})

    def consents(self) -> list:
        return _run("r = consent_router.my_consents(db, p)\nprint(r.body.decode())", self.args)

    def grant(self, reference: str, custodians: list[str], sensitive: list[str] = (), days: int = 7) -> dict:
        doc = self.prepare(reference, custodians, sensitive, days)
        return self.decide(reference, e2e.sign_object(self.sig, doc))

    def prepare(self, reference: str, custodians: list[str], sensitive=(), days: int = 7) -> dict:
        return _run("out = consent_router.prepare_consent(args['ref'], consent_router.PrepareIn(custodians=args['c'], "
                    "sensitive=args['s'], duration_days=args['d']), db, p)\nprint(json.dumps(out, default=str))",
                    {**self.args, "ref": reference, "c": custodians, "s": list(sensitive), "d": days})

    def decide(self, reference: str, document: dict) -> dict:
        return _run("from fastapi import HTTPException\ntry:\n"
                    "    out = consent_router.decide_consent(args['ref'], consent_router.DecisionIn(decision='grant', "
                    "document=args['doc']), db, p)\nexcept HTTPException as exc:\n"
                    "    out = {'error': exc.status_code, 'detail': exc.detail}\nprint(json.dumps(out, default=str))",
                    {**self.args, "ref": reference, "doc": document})

    def revoke(self, reference: str) -> dict:
        rev = e2e.sign_object(self.sig, {"type": "refx.consent.revocation/v1", "consent": reference,
                                         "revoked_at": e2e.now_iso()})
        return _run("out = consent_router.revoke_consent(args['ref'], consent_router.RevokeIn(revocation=args['rev']), "
                    "db, p)\nprint(json.dumps(out, default=str))", {**self.args, "ref": reference, "rev": rev})

    def copy(self, reference: str) -> tuple[int, dict]:
        return tuple(_run("from app import patient_access\nfrom fastapi import HTTPException\ntry:\n"
                          "    r = patient_access.my_copy(args['ref'], db, p)\n    out = [r.status_code, json.loads(r.body)]\n"
                          "except HTTPException as exc:\n    out = [exc.status_code, {'detail': exc.detail}]\n"
                          "print(json.dumps(out, default=str))", {**self.args, "ref": reference}))

    def add_paper(self, reference: str, body: dict) -> tuple[int, dict]:
        return tuple(_run("from app import patient_access\nfrom fastapi import HTTPException\ntry:\n"
                          "    out = [201, patient_access.add_papers(args['ref'], patient_access.PatientBatchIn(**args['b']), db, p)]\n"
                          "except HTTPException as exc:\n    out = [exc.status_code, {'detail': exc.detail}]\n"
                          "print(json.dumps(out, default=str))", {**self.args, "ref": reference, "b": body}))


class PatientViaKeycloak(SimulatedPatient):
    simulated = False

    def __init__(self, username: str):
        self.username = username
        import jwt
        self.sub = jwt.decode(token(username), options={"verify_signature": False})["sub"]
        self.subject_id = f"patient:{self.sub}"
        self.enc, self.sig = e2e.generate_key(), e2e.generate_key()

    def register(self) -> dict:
        reg = e2e.sign_object(self.sig, {"type": "refx.key.registration/v1", "subject_id": self.subject_id,
                                         "enc_public_key": e2e.public_spki(self.enc),
                                         "sig_public_key": e2e.public_spki(self.sig), "created_at": e2e.now_iso()})
        return ok(central(self.username).post("/e2e/patient-keys", {"registration": reg}), 201)

    def consents(self) -> list:
        return ok(central(self.username).get("/patient-access/consents"))

    def prepare(self, reference, custodians, sensitive=(), days=7) -> dict:
        return ok(central(self.username).post(f"/patient-access/consents/{reference}/prepare",
                                              {"custodians": custodians, "sensitive": list(sensitive), "duration_days": days}))

    def decide(self, reference, document) -> dict:
        resp = central(self.username).post(f"/patient-access/consents/{reference}/decision",
                                           {"decision": "grant", "document": document})
        return resp.json() if resp.status_code == 200 else {"error": resp.status_code, "detail": resp.json().get("detail")}

    def revoke(self, reference) -> dict:
        rev = e2e.sign_object(self.sig, {"type": "refx.consent.revocation/v1", "consent": reference,
                                         "revoked_at": e2e.now_iso()})
        return ok(central(self.username).post(f"/patient-access/consents/{reference}/revoke", {"revocation": rev}))

    def copy(self, reference) -> tuple[int, dict]:
        resp = central(self.username).get(f"/patient-access/referrals/{reference}/copy")
        return resp.status_code, resp.json()

    def add_paper(self, reference, body) -> tuple[int, dict]:
        resp = central(self.username).post(f"/patient-access/referrals/{reference}/papers", body)
        return resp.status_code, resp.json()


def patient(username: str, name: str, cnic: str) -> SimulatedPatient:
    """The real patient account if the realm has it, otherwise the simulated sign-in."""
    try:
        token(username)
        return PatientViaKeycloak(username)
    except Exception:  # noqa: BLE001
        return SimulatedPatient(name, cnic)
