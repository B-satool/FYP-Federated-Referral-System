"""Patient view (decision 2026-10-29): a patient sees only their own referrals from the platform, and
reads their own records from each institution directly. Nobody else can use these endpoints, and a
patient cannot use any staff endpoint."""
from __future__ import annotations

from conftest import find_patient, new_referral
from helpers import central, institution, ok

RUBINA = "rubina.akhtar"


def test_patient_sees_own_referrals_only():
    mine = new_referral("Rubina", "akuh", "dentistry", "Surgical extraction of lower left molar",
                        ["oral_surgery", "bleeding_risk"])
    other = new_referral("Tariq", "ziauddin", "cardiology", "Coronary angiography", ["iodinated_contrast"])
    draft = new_referral("Rubina", "akuh", "orthopaedics", None, submit=False)

    resp = central(RUBINA).get("/patient-access/referrals")
    assert resp.status_code == 200 and resp.headers["cache-control"] == "no-store"
    refs = {r["reference"]: r for r in resp.json()}
    assert mine["reference"] in refs and other["reference"] not in refs
    assert draft["reference"] not in refs  # the doctor has not submitted it yet
    r = refs[mine["reference"]]
    assert r["status_label"] == "Being prepared" and r["to"]["institution"] == "Aga Khan University Hospital"
    assert r["timeline"][0]["text"].startswith("Your doctor asked for this referral")
    assert other["reference"] in {x["reference"] for x in ok(central("muhammad.tariq.mahmood").get("/patient-access/referrals"))}

    # a patient cannot open a referral, or any list, through the staff API
    assert central(RUBINA).get(f"/referrals/{mine['id']}").status_code == 403
    assert central(RUBINA).get("/referrals").status_code == 403
    assert central(RUBINA).get("/work-queue").status_code == 403


def test_patient_reads_own_records_from_each_institution():
    summaries = {inst: institution(inst, RUBINA).get("/patient-access/summary") for inst in ("drali", "chughtai", "akuh")}
    assert all(s.status_code == 200 and s.headers["cache-control"] == "no-store" for s in summaries.values())
    assert summaries["drali"].json()["held"] and summaries["chughtai"].json()["held"]
    assert summaries["akuh"].json()["held"] is False  # never seen there

    history = institution("drali", RUBINA).get("/patient-access/records")
    assert history.status_code == 200 and history.headers["cache-control"] == "no-store"
    body = history.json()
    assert body["patient"]["name"] == "Rubina Akhtar"
    assert {m["status"] for m in body["medicines"]} >= {"active", "completed"}  # whole history, not current only
    assert institution("akuh", RUBINA).get("/patient-access/records").status_code == 404

    # the institution's own audit records the patient reading their records
    audit = ok(institution("drali", "admin.ali").get("/admin/audit"))
    assert any(a["action"] == "patient.records" and a["outcome"] == "success" for a in audit)


def test_patient_endpoints_refuse_everyone_else_and_staff_endpoints_refuse_patients():
    rubina_here = find_patient("Rubina")["local_patient_id"]
    for user in ("dr.ali", "staff.ali", "admin.ali"):
        assert central(user).get("/patient-access/referrals").status_code == 403
        assert institution("drali", user).get("/patient-access/records").status_code == 403
    assert institution("drali", RUBINA).get("/patients").status_code == 403
    assert institution("drali", RUBINA).get(f"/patients/{rubina_here}").status_code == 403
    # the referral records endpoint needs an access grant to another institution; a patient has none
    assert institution("drali", RUBINA).get(f"/fhir/patients/{rubina_here}/records").status_code == 403
