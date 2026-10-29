"""Reusable end-to-end steps for the spec v4 checks: a referral with the patient's consent and its records
requested, as the doctor's and patient's devices (tests/e2e_client.py, tests/patient_sim.py) would do it."""
from __future__ import annotations

from conftest import new_referral
from e2e_client import Device
from helpers import central, ok
from patient_sim import patient

RUBINA = ("rubina.akhtar", "Rubina Akhtar", "35202-0000011-4")


def rubina():
    p = patient(*RUBINA)
    p.register()
    return p


def consented_referral(pat, custodians: list[str] | None = None, *, doctor: Device | None = None,
                       sensitive: tuple = (), dest: str = "akuh", dept: str = "dentistry",
                       procedure: str = "Surgical removal of impacted lower wisdom tooth",
                       tags: tuple = ("oral_surgery", "bleeding_risk")) -> tuple[dict, Device, dict]:
    """(referral, the referring doctor's device, the records-request result)."""
    doc = doctor or Device("dr.ali")
    if doctor is None:
        doc.register("drali")
    r = new_referral("Rubina Akhtar", dest, dept, procedure, list(tags))
    body = {"custodians": custodians} if custodians else {}
    c = ok(central("staff.ali").post(f"/referrals/{r['id']}/consents", body), 201)
    granted = pat.grant(c["reference"], custodians or [x["institution_id"] for x in c["custodians_requested"]],
                        sensitive=list(sensitive))
    assert granted.get("status") == "granted", granted
    out = ok(central("staff.ali").post(f"/referrals/{r['id']}/record-requests"))
    return r, doc, out
