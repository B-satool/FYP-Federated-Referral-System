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


def display_name(username: str) -> str:
    import jwt

    from helpers import token
    return jwt.decode(token(username), options={"verify_signature": False})["name"]


def central_python(code: str) -> str:
    """Run Python inside the central container (to move the clock in the database, or run a scheduled job now)."""
    import subprocess

    from e2e_client import ROOT
    run = subprocess.run(["docker", "compose", "exec", "-T", "central", "python", "-c", code], cwd=ROOT,
                         capture_output=True, text=True, timeout=180)
    assert run.returncode == 0, run.stderr[-800:]
    return run.stdout.strip()


def send_and_take_in(r: dict, doctor, *, assign_to: str = "dr.faisal", hospital: str = "akuh") -> tuple[str, dict]:
    """Approve (signed on the doctor's device), send, and at the receiving hospital acknowledge, confirm the patient
    and assign the doctor. Returns (reference, case)."""
    from e2e_client import build_approval
    from helpers import institution, wait_for

    ok(central(doctor.username).post(f"/referrals/{r['id']}/packages", build_approval(doctor, r["id"])), 201)
    detail = ok(central("staff.ali").get(f"/referrals/{r['id']}"))
    ok(central("staff.ali").post(f"/referrals/{r['id']}/send", {"expected_version": detail["row_version"]}))
    ref = detail["reference"]
    staff = institution(hospital, "staff.aku")
    case = wait_for(lambda: next((c for c in ok(staff.get("/cases")) if c["central_referral_id"] == ref), None), 60,
                    what="the referral at the receiving hospital")
    ok(staff.post(f"/cases/{case['id']}/acknowledge"))
    if not case["local_patient_id"]:
        link = case["link_request_id"]
        cands = ok(central("staff.aku").post(f"/patient-links/{link}/lookup"))["candidates"]
        body = {"local_patient_id": cands[0]["local_patient_id"], "note": "CNIC and date of birth checked"} if cands \
            else {"register_new": True, "note": "New patient; CNIC and date of birth checked"}
        ok(central("staff.aku").post(f"/patient-links/{link}/approve", body))
        wait_for(lambda: ok(staff.get(f"/cases/{case['id']}"))["case"]["local_patient_id"], 30,
                 what="the confirmed patient at the receiving hospital")
    case = ok(staff.post(f"/cases/{case['id']}/assign", {"doctor": display_name(assign_to)}))
    return ref, case


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
