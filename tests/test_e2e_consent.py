"""Spec v4 WP2: consent granted only by the patient (T-CONSENT-1), the institutions' own policy with structured
refusals (T-POLICY-1, T-REFUSAL-1), and the signed request checks at each adapter (T-TOKEN-1)."""
from __future__ import annotations

import json
import subprocess

import pytest

from conftest import new_referral
from e2e_client import CANARY, ROOT, Device
from helpers import central, institution, ok
from patient_sim import patient
from refcommon import e2e

PATIENT = "rubina.akhtar"  # synthetic patient P1 (has sensitive records at the clinic and the lab)


def _in_central(code: str) -> dict:
    run = subprocess.run(["docker", "compose", "exec", "-T", "central", "python", "-c", code], cwd=ROOT,
                         capture_output=True, text=True, timeout=120)
    assert run.returncode == 0, run.stderr[-2000:]
    return json.loads(run.stdout.strip().splitlines()[-1])


TOKEN_CHECKS = r"""
import json, time, httpx, jwt
from refcommon import e2e
from app.db import SessionLocal
from app.keys import platform
url = "http://chughtai:8000/e2e/record-requests"
body = {"request_key": "tok-test-%d" % int(time.time() * 1000), "local_patient_id": "MD-771203"}
good = {"refx": {"org": "drali", "practitioner": "someone", "purpose": "TREAT", "consent": "CNS-0000-00000",
                 "referral": "REF-0000-00000"}}
out = {}
with SessionLocal() as db:
    key = platform.signing_key(db)
    def post(tok, b=body):
        r = httpx.post(url, json=b, headers={"Authorization": "Bearer " + tok}, timeout=20)
        return r.status_code, r.text[:300]
    out["bad_signature"] = post(e2e.make_assertion(e2e.generate_key(), issuer="hub", audience="chughtai", claims=good))
    out["wrong_audience"] = post(e2e.make_assertion(key, issuer="hub", audience="akuh", claims=good))
    out["expired"] = post(e2e.make_assertion(key, issuer="hub", audience="chughtai", claims=good, ttl=-120))
    now = int(time.time())
    long = jwt.encode({"iss": "hub", "sub": "hub", "aud": "chughtai", "iat": now, "exp": now + 3600, "jti": str(now),
                       **good}, key, algorithm="ES256", headers={"kid": e2e.key_id(e2e.public_spki(key))})
    out["too_long"] = post(long)
    once = e2e.make_assertion(key, issuer="hub", audience="chughtai", claims=good)
    out["first"] = post(once, {**body, "request_key": body["request_key"] + "a"})
    out["replay"] = post(once, {**body, "request_key": body["request_key"] + "b"})
    out["non_participant"] = post(e2e.make_assertion(key, issuer="hub", audience="chughtai",
                                                     claims={"refx": {**good["refx"], "org": "evil-clinic"}}))
    out["purpose"] = post(e2e.make_assertion(key, issuer="hub", audience="chughtai",
                                             claims={"refx": {**good["refx"], "purpose": "MARKETING"}}))
    out["no_consent"] = post(e2e.make_assertion(key, issuer="hub", audience="chughtai",
                                                claims={"refx": {**good["refx"], "consent": None}}))
print(json.dumps(out))
"""


def test_adapter_rejects_bad_request_assertions():
    """T-TOKEN-1: bad signature, wrong audience, expired, over-long, replayed jti, non-participant organisation,
    a purpose the agreement does not allow, a missing consent link. A request with a well-formed assertion but a
    consent link that leads nowhere is refused with a reason code (never an empty answer)."""
    out = _in_central(TOKEN_CHECKS)
    for case in ("bad_signature", "wrong_audience", "expired", "too_long", "replay"):
        assert out[case][0] == 401, (case, out[case])
    assert "replay" in out["replay"][1]
    for case in ("non_participant", "purpose", "no_consent"):
        assert out[case][0] == 403 and "request_incomplete_or_invalid" in out[case][1], (case, out[case])
    status, text = out["first"]
    assert status == 200 and json.loads(text)["status"] == "refused"
    assert json.loads(text)["refusals"][0]["reason"] in ("request_incomplete_or_invalid", "consent_expired_or_out_of_range")


def test_staff_request_consent_but_cannot_grant_it():
    """T-CONSENT-1: staff create a request; only the patient can grant, decline or revoke, in the portal."""
    r = new_referral("Rubina Akhtar", "akuh", "dentistry", "Surgical removal of impacted lower wisdom tooth",
                     ["oral_surgery", "bleeding_risk"])
    assert central("dr.ali").post(f"/referrals/{r['id']}/consents", {}).status_code == 403  # staff ask, not doctors
    c = ok(central("staff.ali").post(f"/referrals/{r['id']}/consents", {}), 201)
    assert c["status"] == "requested" and not c["signed"]
    assert {x["institution_id"] for x in c["custodians_requested"]} >= {"drali"}
    for user in ("staff.ali", "dr.ali", "admin.ali"):
        api = central(user)
        assert api.post(f"/patient-access/consents/{c['reference']}/decision",
                        {"decision": "grant", "document": {}}).status_code == 403
        assert api.post(f"/patient-access/consents/{c['reference']}/prepare",
                        {"custodians": ["drali"], "duration_days": 7}).status_code == 403
    # records cannot be requested without a granted consent
    resp = central("staff.ali").post(f"/referrals/{r['id']}/record-requests")
    assert resp.status_code == 409 and resp.json()["detail"]["code"] == "no_consent"


@pytest.fixture(scope="module")
def pat():
    """Rubina Akhtar's own device (keys here); real sign-in when the realm has patient accounts (patient_sim.py)."""
    p = patient(PATIENT, "Rubina Akhtar", "35202-0000011-4")
    p.register()
    return p


def test_patient_grants_consent_and_records_arrive_encrypted(pat):
    doctor = Device("dr.ali")
    doctor.register("drali")
    r = new_referral("Rubina Akhtar", "akuh", "dentistry", "Surgical removal of impacted lower wisdom tooth",
                     ["oral_surgery", "bleeding_risk"])
    c = ok(central("staff.ali").post(f"/referrals/{r['id']}/consents", {}), 201)
    assert any(x["reference"] == c["reference"] and x["status"] == "requested" for x in pat.consents())
    # a document the patient did not sign (or changed after signing) is refused
    doc = pat.prepare(c["reference"], ["drali"])
    assert pat.decide(c["reference"], e2e.sign_object(e2e.generate_key(), doc))["error"] == 422
    widened = e2e.sign_object(pat.sig, {**doc, "provision": {**doc["provision"], "period": {
        "start": doc["provision"]["period"]["start"], "end": "2099-01-01T00:00:00Z"}}})
    assert pat.decide(c["reference"], widened)["error"] == 422
    custodians = [x["institution_id"] for x in c["custodians_requested"]]
    granted = pat.grant(c["reference"], custodians)
    assert granted["status"] == "granted" and granted["signed"]
    out = ok(central("staff.ali").post(f"/referrals/{r['id']}/record-requests"))
    by = {x["custodian"]: x for x in out["requests"]}
    assert by["drali"]["status"] in ("answered", "partial") and by["drali"]["item_count"] > 0
    titles = out["titles"]
    assert titles and all(set(t) >= {"item_id", "kind", "label", "date", "source_institution"} for t in titles)
    # titles never carry values; the masked sensitive record shows only "Restricted record"
    blob = json.dumps(titles)
    for secret in ("7.6", "Mild depressive", "Metformin", "Low mood"):
        assert secret not in blob, secret


def test_sensitive_lab_result_needs_specific_consent_and_staff_review(pat):
    """T-POLICY-1 at the laboratory: without specific consent the HIV result is refused with a reason code; with
    it, the request waits for the lab's staff (pending_manual_review) and is released after their approval."""
    doctor = Device("dr.ali")
    doctor.register("drali")
    r = new_referral("Rubina Akhtar", "akuh", "dentistry", "Surgical removal of impacted lower wisdom tooth",
                     ["oral_surgery", "bleeding_risk"])
    c = ok(central("staff.ali").post(f"/referrals/{r['id']}/consents", {"custodians": ["chughtai"]}), 201)
    pat.grant(c["reference"], ["chughtai"])
    first = {x["custodian"]: x for x in ok(central("staff.ali").post(f"/referrals/{r['id']}/record-requests"))["requests"]}
    assert first["chughtai"]["status"] in ("answered", "partial")
    c2 = ok(central("staff.ali").post(f"/referrals/{r['id']}/consents", {"custodians": ["chughtai"]}), 201)
    pat.grant(c2["reference"], ["chughtai"], sensitive=["hiv_sexual_health"])
    second = {x["custodian"]: x for x in ok(central("staff.ali").post(f"/referrals/{r['id']}/record-requests"))["requests"]}
    assert second["chughtai"]["status"] == "pending_manual_review"
    assert "pending_manual_review" in [x["reason"] for x in second["chughtai"]["refusals"]]
    queue = ok(institution("chughtai", "staff.chughtai").get("/e2e/record-requests", params={"status": "pending_manual_review"}))
    mine = next(q for q in queue if q["referral_ref"] == r["reference"])
    assert CANARY not in json.dumps(queue)
    ok(institution("chughtai", "staff.chughtai").post(f"/e2e/record-requests/{mine['id']}/approve"))
    after = {x["custodian"]: x for x in ok(central("staff.ali").get(f"/referrals/{r['id']}/record-requests"))["requests"]}
    assert after["chughtai"]["status"] in ("answered", "partial") and after["chughtai"]["item_count"] > first["chughtai"]["item_count"]
    titles = ok(central("staff.ali").get(f"/referrals/{r['id']}/titles"))
    assert any(t["sensitive"] and t["label"] == "Restricted record" for t in titles)
    assert not any("HIV" in t["label"] for t in titles)


def test_revoked_consent_blocks_further_requests(pat):
    r = new_referral("Rubina Akhtar", "akuh", "dentistry", "Surgical removal of impacted lower wisdom tooth",
                     ["oral_surgery", "bleeding_risk"])
    c = ok(central("staff.ali").post(f"/referrals/{r['id']}/consents", {"custodians": ["drali"]}), 201)
    pat.grant(c["reference"], ["drali"])
    assert pat.revoke(c["reference"])["status"] == "revoked"
    resp = central("staff.ali").post(f"/referrals/{r['id']}/record-requests")
    assert resp.status_code == 409 and resp.json()["detail"]["code"] == "no_consent"
