"""Each seed patient's scenario (seed-data/patients/*.json -> scenario.should_flag):
the medication flags fire for the planned procedure, and only those."""
from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from conftest import ROOT, SURGERY, new_referral
from helpers import CENTRAL, central, ok, token, wait_for

STAFF = central("staff.ali")
DOCS = ROOT / "seed-data" / "documents"
ANGIO = ["iodinated_contrast", "arterial_access"]


def _flags(rid: int) -> set[tuple[str, str]]:
    meds = ok(STAFF.get(f"/referrals/{rid}/medications"))
    return {(f["rule_id"], f["medication"].split()[0].lower()) for f in meds["flags"] if f["kind"] == "confirmed"}


@pytest.mark.parametrize("patient,dest,dept,procedure,tags,expected", [
    ("Rubina", "akuh", "dentistry", "Surgical extraction of lower left molar", ["oral_surgery", "bleeding_risk"],
     {("RULE-010", "alendronate")}),
    ("Tariq", "ziauddin", "cardiology", "Coronary angiography", ANGIO, {("RULE-005", "metformin")}),
    ("Gondal", "akuh", "orthopaedics", "Total knee replacement (right)", SURGERY,
     {("RULE-002", "aspirin"), ("RULE-003", "diclofenac")}),
    ("Shazia", "ziauddin", "gastro_hepatology", "Upper GI endoscopy", ["gi_endoscopy", "sedation"],
     {("RULE-004", "ibuprofen")}),
])
def test_scenario_flags(patient, dest, dept, procedure, tags, expected):
    r = new_referral(patient, dest, dept, procedure, tags)
    ok(STAFF.post(f"/referrals/{r['id']}/retrieve"))
    assert _flags(r["id"]) == expected


def test_procedure_without_features_is_not_checked():
    """A procedure written without saying what it involves: procedure rules are not run, and say so."""
    r = new_referral("Imtiaz", "akuh", "general_surgery", "Gallbladder operation", [])
    ok(STAFF.post(f"/referrals/{r['id']}/retrieve"))
    meds = ok(STAFF.get(f"/referrals/{r['id']}/medications"))
    kinds = {f["kind"] for f in meds["flags"]}
    assert "confirmed" not in kinds and "procedure_not_checked" in kinds


def test_p2_last_visited_hospital_and_stopped_medicine():
    """P2 was seen at AKUH (Aug 2026) and at Ziauddin radiology (Oct 2026): only Ziauddin is used.
    Diclofenac was stopped and must not appear as a current medicine."""
    r = new_referral("Tariq", "ziauddin", "cardiology", "Coronary angiography", ANGIO)
    # Staff ask Ziauddin for his records there (a records request: match a record or say there is none).
    link = ok(STAFF.post(f"/referrals/{r['id']}/links", {"target_institution": "ziauddin"}), 201)
    zia = central("staff.zia")
    cands = ok(zia.post(f"/patient-links/{link['id']}/lookup"))["candidates"]
    assert len(cands) == 1 and cands[0]["compare"]["cnic"]
    assert zia.post(f"/patient-links/{link['id']}/approve",
                    {"register_new": True, "note": "not allowed for a records request"}).status_code == 422
    ok(zia.post(f"/patient-links/{link['id']}/approve",
                {"local_patient_id": cands[0]["local_patient_id"], "note": "CNIC, name and date of birth match"}))
    res = {x["source_institution"]: x for x in ok(STAFF.post(f"/referrals/{r['id']}/retrieve"))["results"]}
    assert res["ziauddin"]["status"] == "successful" and res["ziauddin"]["last_activity"] == "2026-10-10"
    assert res["akuh"]["status"] == "skipped" and "2026-08-30" in res["akuh"]["message"]
    meds = ok(STAFF.get(f"/referrals/{r['id']}/medications"))["entries"]
    assert "diclofenac" not in {m["ingredient"] for m in meds}
    # lipid profile from 2025 is outside the 6-month window
    ev = ok(STAFF.get(f"/referrals/{r['id']}/evidence", params={"category": "lab"}))
    assert all("2025" not in (e["clinical_time"] or "") for e in ev)


def test_uploaded_prescription_merges_with_recorded_medicines():
    """P5's cardiology prescription (photo) lists the same medicines as the clinic record:
    after staff check the read fields, each medicine is shown once."""
    r = new_referral("Imtiaz", "akuh", "general_surgery", "Laparoscopic cholecystectomy", SURGERY)
    rid = r["id"]
    ok(STAFF.post(f"/referrals/{rid}/retrieve"))
    path = DOCS / "P5_prescription_cardiology_2025-06-18.jpg"
    with path.open("rb") as fh:
        up = httpx.post(f"{CENTRAL}/referrals/{rid}/documents", headers={"Authorization": f"Bearer {token('staff.ali')}"},
                        files={"file": (path.name, fh, "image/jpeg")}, data={"doc_type": "prescription"}, timeout=60)
    doc_id = ok(up, 201)["document"]["id"]
    detail = wait_for(lambda: (d := ok(STAFF.get(f"/documents/{doc_id}")))["document"]["status"] in ("extracted", "unreadable", "failed") and d,
                      180, 2, "OCR")
    assert detail["document"]["status"] == "extracted", detail["document"]
    read = {f["current"].get("medication", "").split()[0].lower() for f in detail["fields"] if f["category"] == "medication"}
    assert {"disprin", "plavix", "lipitor", "concor"} <= read, read
    for f in detail["fields"]:
        ok(STAFF.post(f"/evidence/{f['id']}/verify", {"expected_row_version": f["row_version"], "note": "Checked against the paper"}))
    entries = ok(STAFF.get(f"/referrals/{rid}/medications"))["entries"]
    shown = [m for m in entries if not m["duplicate_of"] and m["ingredient"] in ("aspirin", "clopidogrel", "atorvastatin", "bisoprolol")]
    assert sorted(m["ingredient"] for m in shown) == ["aspirin", "atorvastatin", "bisoprolol", "clopidogrel"]
    assert all(any(d["duplicate_of"] == m["id"] for d in entries) for m in shown)
