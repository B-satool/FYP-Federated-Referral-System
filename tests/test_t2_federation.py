"""T2 - source records, verified identity links and federation (FR-06 to FR-10, FR-16 to FR-21, FR-55, FR-56)."""
from __future__ import annotations

import pytest
from conftest import compose, new_referral, start_service
from helpers import central, ok, wait_for

DR = "dr.malik"


def _evidence(ref_id: int, **params) -> list[dict]:
    return ok(central(DR).get(f"/referrals/{ref_id}/evidence", params=params))


def _by_source(results: list[dict]) -> dict[str, dict]:
    return {r["source_institution"]: r for r in results}


def test_only_verified_links_import_evidence_and_same_local_id_stays_separate():
    ref = new_referral("MR-102")
    res = _by_source(ok(central(DR).post(f"/referrals/{ref['id']}/retrieve"))["results"])
    assert res["clinic-a"]["status"] == "successful"
    assert res["lab-b"]["status"] == "successful" and res["lab-b"]["local_patient_id"] == "LB-5531"
    assert "spec-c" not in res  # no verified link -> not requested
    items = _evidence(ref["id"])
    labs = [e for e in items if e["source_institution"] == "lab-b"]
    assert any("INR" in e["display"] and "2.6" in e["display"] for e in labs)
    # Lab B / MR-102 (Bilal Ahmed, Hb 15.1) must never appear in Ayesha's referral (FR-09)
    assert not any(e["patient_ref"]["local_patient_id"] == "MR-102" and e["source_institution"] == "lab-b" for e in items)
    assert not any("15.1" in e["display"] for e in labs)
    # Original values, units and clinical dates preserved (FR-18, FR-19)
    inr = next(e for e in labs if e["display"].startswith("INR: 2.6"))
    assert inr["original"]["unit"] == "{INR}" and inr["original"]["collected"].startswith("2026-09-05")
    assert inr["clinical_time"].startswith("2026-09-05") and inr["retrieved_at"] != inr["clinical_time"]
    # Missing value stays explicitly missing (FR-32)
    glucose = next(e for e in labs if e["display"].startswith("Glucose"))
    assert glucose["original"]["value"] is None and "not recorded" in glucose["display"]


def test_repeated_retrieval_creates_no_duplicates():
    ref = new_referral("MR-102")
    ok(central(DR).post(f"/referrals/{ref['id']}/retrieve"))
    first = len(_evidence(ref["id"]))
    second = _by_source(ok(central(DR).post(f"/referrals/{ref['id']}/retrieve"))["results"])
    assert second["clinic-a"]["new_count"] == 0 and second["clinic-a"]["duplicate_count"] > 0
    assert second["lab-b"]["new_count"] == 0
    assert len(_evidence(ref["id"])) == first


def test_invalidated_link_is_not_used():
    ref = new_referral("MR-215")
    res = _by_source(ok(central(DR).post(f"/referrals/{ref['id']}/retrieve"))["results"])
    assert "lab-b" not in res
    detail = ok(central(DR).get(f"/referrals/{ref['id']}"))
    lab = next(s for s in detail["sources"] if s["source_institution"] == "lab-b")
    assert lab["linked"] is False and "invalidated" in lab["link_states"]


def test_denied_and_unavailable_are_distinct_and_keep_other_evidence():
    # Lab B has no grant for Clinic A on LB-7100 -> denied at the source (FR-03, FR-21)
    ref = new_referral("MR-330")
    res = _by_source(ok(central(DR).post(f"/referrals/{ref['id']}/retrieve"))["results"])
    assert res["lab-b"]["status"] == "denied" and res["lab-b"]["retryable"] is False
    assert res["clinic-a"]["status"] == "successful"

    ref2 = new_referral("MR-102")
    compose("stop", "lab")
    try:
        res2 = _by_source(ok(central(DR).post(f"/referrals/{ref2['id']}/retrieve"))["results"])
    finally:
        start_service("lab")
    assert res2["lab-b"]["status"] == "unavailable" and res2["lab-b"]["retryable"] is True
    assert res2["lab-b"]["attempts"] >= 2  # bounded retry happened
    assert res2["clinic-a"]["status"] == "successful"  # FR-55
    assert any(e["source_institution"] == "clinic-a" for e in _evidence(ref2["id"]))
    items = ok(central(DR).get(f"/referrals/{ref2['id']}/review-items"))
    assert any(i["item_key"] == "CL-SOURCES:lab-b" and i["status"] == "open" for i in items)
    # recovery: once Lab B is back, retrieval succeeds
    wait_for(lambda: central(DR).post(f"/referrals/{ref2['id']}/retrieve", params={"source": "lab-b"}).json()
             ["results"][0]["status"] == "successful", timeout=60, interval=3, what="lab recovery")


def test_link_proposal_identity_check_verification_and_invalidation():
    staff, dr = central("staff.a"), central(DR)
    # identity check returns booleans only; a wrong DOB is reported as mismatch
    wrong = ok(staff.post("/patient-links", {
        "a_local_id": "MR-418", "b_institution": "spec-c", "b_local_id": "SP-8020",
        "basis": "Specialist card presented at reception",
        "check_demographics": {"family": "Siddiqui", "given": "Hamza", "birth_date": "1995-08-10"}}), 201)
    assert wrong["status"] == "pending" and wrong["match_check"]["birth_date_match"] is False
    ok(dr.post(f"/patient-links/{wrong['id']}/reject", {"note": "Date of birth mismatch - recheck"}))

    link = ok(staff.post("/patient-links", {
        "a_local_id": "MR-418", "b_institution": "spec-c", "b_local_id": "SP-8020",
        "basis": "Specialist appointment card + national ID",
        "check_demographics": {"family": "Siddiqui", "given": "Hamza", "birth_date": "1995-08-09"}}), 201)
    assert all(link["match_check"][k] for k in ("record_exists", "family_match", "given_match", "birth_date_match"))
    # clinic staff may propose but not verify
    assert staff.post(f"/patient-links/{link['id']}/verify", {"note": "Looks like the same person"}).status_code == 403
    verified = ok(dr.post(f"/patient-links/{link['id']}/verify", {"note": "National ID and DOB confirmed"}))
    assert verified["status"] == "verified" and verified["verified_by"] == "Sana Malik" and verified["verified_at"]

    ref = new_referral("MR-418")
    res = _by_source(ok(dr.post(f"/referrals/{ref['id']}/retrieve"))["results"])
    assert res["spec-c"]["status"] == "successful"
    spec_items = [e for e in _evidence(ref["id"]) if e["source_institution"] == "spec-c"]
    assert spec_items

    inval = ok(dr.post(f"/patient-links/{link['id']}/invalidate", {"note": "Wrong person - card belonged to a relative"}))
    assert inval["status"] == "invalidated"
    assert any(a["referral_id"] == ref["id"] for a in inval["affected"])
    after = [e for e in _evidence(ref["id"]) if e["source_institution"] == "spec-c"]
    assert after and all(e["verification_status"] == "invalidated" and not e["selected"] for e in after)
    items = ok(dr.get(f"/referrals/{ref['id']}/review-items"))
    assert any(i["kind"] == "link_invalidated" and i["status"] == "open" for i in items)
    # history is kept
    links = ok(staff.get("/patient-links", params={"institution": "clinic-a", "local_id": "MR-418"}))
    statuses = {x["status"] for x in links}
    assert {"rejected", "invalidated"} <= statuses
    assert any(e["action"] == "invalidated" for x in links for e in x["events"])


def test_lab_correction_creates_new_record_version_not_duplicate():
    import httpx
    from helpers import LAB, token

    ref = new_referral("MR-102")
    ok(central(DR).post(f"/referrals/{ref['id']}/retrieve"))
    lab_hdr = {"Authorization": f"Bearer {token('lab.b')}"}
    results = httpx.get(f"{LAB}/lab/patients/LB-5531/results", headers=lab_hdr).json()
    plt = next(r for r in results if r["id"] == "OBS-5531-3")
    corrected = httpx.post(f"{LAB}/lab/results/OBS-5531-3/correct", headers=lab_hdr,
                           json={"value_num": plt["value_num"] + 1, "reason": "Analyser recalibration (test)",
                                 "expected_version": plt["version"]})
    assert corrected.status_code == 200
    res = _by_source(ok(central(DR).post(f"/referrals/{ref['id']}/retrieve"))["results"])
    assert res["lab-b"]["new_count"] == 1
    all_items = _evidence(ref["id"], include_superseded=True)
    versions = [e for e in all_items if e["source_record_id"] == "OBS-5531-3"]
    assert len(versions) == 2 and sum(1 for v in versions if v["superseded_by"] is None) == 1


@pytest.mark.parametrize("user,expect", [("staff.a", 200), ("lab.b", 403), ("dr.ortho", 403)])
def test_patient_search_restricted_to_own_clinic(user, expect):
    assert central(user).get("/patients/search", params={"q": "Khan"}).status_code in (expect, 404 if expect == 403 else expect)
