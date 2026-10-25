"""Each seed patient's scenario (seed-data/patients/*.json -> scenario.should_flag):
the medication flags fire for the planned procedure, and only those."""
from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from conftest import ROOT, new_referral
from helpers import CENTRAL, central, ok, token, wait_for

STAFF = central("staff.ali")
DOCS = ROOT / "seed-data" / "documents"


def _approve_destination(rid: int, staff_user: str, match_existing: bool) -> dict | None:
    staff = central(staff_user)
    link = next((x for x in ok(staff.get("/patient-links/incoming")) if x["referral_id"] == rid), None)
    if link is None:  # confirmed earlier (e.g. by another test): no new request is needed
        dest = ok(STAFF.get(f"/referrals/{rid}"))["destination_institution"]
        assert any(s["institution_id"] == dest and s["linked"] for s in ok(STAFF.get(f"/referrals/{rid}"))["sources"])
        return None
    cands = ok(staff.post(f"/patient-links/{link['id']}/lookup"))["candidates"]
    if match_existing:
        assert len(cands) == 1 and cands[0]["compare"]["cnic"] and cands[0]["compare"]["birth_date"]
        body = {"local_patient_id": cands[0]["local_patient_id"], "note": "CNIC, name and date of birth match"}
    else:
        assert cands == []
        body = {"register_new": True, "note": "New patient; identity checked"}
    return ok(staff.post(f"/patient-links/{link['id']}/approve", body))


def _flags(rid: int) -> set[tuple[str, str]]:
    meds = ok(STAFF.get(f"/referrals/{rid}/medications"))
    return {(f["rule_id"], f["medication"].split()[0].lower()) for f in meds["flags"] if f["kind"] == "confirmed"}


@pytest.mark.parametrize("patient,dest,dept,procedure,dest_staff,existing,expected", [
    ("Rubina", "akuh", "dentistry", "surgical_tooth_extraction", "staff.aku", False, {("RULE-010", "alendronate")}),
    ("Tariq", "ziauddin", "cardiology", "coronary_angiography", "staff.zia", True, {("RULE-005", "metformin")}),
    ("Gondal", "akuh", "orthopaedics", "total_knee_replacement", "staff.aku", False,
     {("RULE-002", "aspirin"), ("RULE-003", "diclofenac")}),
    ("Shazia", "ziauddin", "gastro_hepatology", "upper_gi_endoscopy", "staff.zia", False, {("RULE-004", "ibuprofen")}),
])
def test_scenario_flags(patient, dest, dept, procedure, dest_staff, existing, expected):
    r = new_referral(patient, dest, dept, procedure)
    _approve_destination(r["id"], dest_staff, existing)
    ok(STAFF.post(f"/referrals/{r['id']}/retrieve"))
    assert _flags(r["id"]) == expected


def test_p2_last_visited_hospital_and_stopped_medicine():
    """P2 was seen at AKUH (Aug 2026) and at Ziauddin radiology (Oct 2026): only Ziauddin is used.
    Diclofenac was stopped and must not appear as a current medicine."""
    r = new_referral("Tariq", "ziauddin", "cardiology", "coronary_angiography")
    _approve_destination(r["id"], "staff.zia", True)
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
    r = new_referral("Imtiaz", "akuh", "general_surgery", "laparoscopic_cholecystectomy")
    rid = r["id"]
    _approve_destination(rid, "staff.aku", False)
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
