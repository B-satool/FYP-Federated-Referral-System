"""T3 - complete manual referral journey (no AI required) with approval, versioning,
idempotent delivery, specialist response and closure (FR-11 to FR-15, FR-47 to FR-57, FR-59)."""
from __future__ import annotations

import httpx
from conftest import new_referral, read_env
from helpers import CENTRAL, SPECIALIST, Api, central, ok, token, wait_for

DR, STAFF = "dr.malik", "staff.a"


def prepare(ref_id: int) -> dict:
    """Retrieve, verify medication use and review flags; returns latest referral detail."""
    dr = central(DR)
    ok(dr.post(f"/referrals/{ref_id}/retrieve"))
    meds = ok(dr.get(f"/referrals/{ref_id}/medications"))
    decisions = {"warfarin": "confirmed_current", "alendronate": "historical_stopped", "atorvastatin": "confirmed_current",
                 "aspirin": "uncertain"}
    for m in meds["entries"]:
        status = decisions.get(m["ingredient"] or "", "uncertain")
        ok(dr.post(f"/referrals/{ref_id}/medications/{m['id']}/use", {"use_status": status, "note": "Confirmed with patient"}))
    return ok(dr.get(f"/referrals/{ref_id}"))


def review_all_flags(ref_id: int) -> list[dict]:
    dr = central(DR)
    flags = ok(dr.get(f"/referrals/{ref_id}/medications"))["flags"]
    for f in flags:
        ok(dr.post(f"/referrals/{ref_id}/flags/{f['id']}/review", {"action": "reviewed", "flag_version": f["version"]}))
    return flags


def resolve_open_overridable(ref_id: int) -> None:
    dr = central(DR)
    for item in ok(dr.get(f"/referrals/{ref_id}/review-items")):
        if item["status"] == "open" and item["blocking"] and item["override_allowed"]:
            ok(dr.post(f"/review-items/{item['id']}/resolve", {"action": "uncertainty_recorded",
                                                                "rationale": "Reviewed by clinician; uncertainty recorded"}))


def detail(ref_id: int, user: str = DR) -> dict:
    return ok(central(user).get(f"/referrals/{ref_id}"))


def central_service_token() -> str:
    env = read_env()
    r = httpx.post("http://localhost:8080/realms/referral/protocol/openid-connect/token",
                   data={"grant_type": "client_credentials"}, auth=("central-api", env.get("CENTRAL_CLIENT_SECRET", "")))
    r.raise_for_status()
    return r.json()["access_token"]


def test_complete_manual_journey(approved_rules):
    dr, staff, spec = central(DR), central(STAFF), Api(SPECIALIST, "dr.ortho")
    ref = new_referral("MR-102", procedure="tooth_extraction")
    rid = ref["id"]
    prepare(rid)

    flags = ok(dr.get(f"/referrals/{rid}/medications"))["flags"]
    kinds = {f["kind"] for f in flags}
    assert "confirmed" in kinds and "possible_use" in kinds and "ambiguous_mapping" in kinds
    anticoag = next(f for f in flags if f["kind"] == "confirmed" and f["drug_class"] == "anticoagulant")
    assert anticoag["rule_id"] == "ORTHO-ANTICOAG-SURG" and anticoag["rule_version"] == 1
    assert "Clinic A" in anticoag["source_label"] and anticoag["current_use_status"] == "confirmed_current"
    assert not any(f["drug_class"] == "bisphosphonate" for f in flags)  # stopped alendronate -> no current-use flag

    # manual (non-AI) brief path
    ok(staff.post(f"/referrals/{rid}/brief/template"), 201)
    brief = ok(dr.get(f"/referrals/{rid}/brief"))["latest"]
    meds_section = next(s for s in brief["sections"] if s["key"] == "medications")
    assert meds_section["statements"] and all(st["evidence_ids"] for st in meds_section["statements"])

    # send for approval; unapproved referral cannot be submitted
    r = detail(rid)
    req = ok(staff.post(f"/referrals/{rid}/request-approval", {"expected_version": r["row_version"]}))
    assert req["status"] in ("awaiting_approval", "awaiting_information")
    r = detail(rid)
    assert staff.post(f"/referrals/{rid}/submit", {"expected_version": r["row_version"]}).status_code == 409

    # approval blocked until flags are reviewed; staff cannot approve at all
    r = detail(rid)
    assert staff.post(f"/referrals/{rid}/approve", {"expected_version": r["row_version"]}).status_code == 403
    resolve_open_overridable(rid)
    r = detail(rid)
    if r["status"] == "awaiting_information":
        ok(staff.post(f"/referrals/{rid}/return-to-draft", {"expected_version": r["row_version"]}))
        r = detail(rid)
        ok(staff.post(f"/referrals/{rid}/request-approval", {"expected_version": r["row_version"]}))
        r = detail(rid)
    blocked = dr.post(f"/referrals/{rid}/approve", {"expected_version": r["row_version"]})
    assert blocked.status_code == 409 and blocked.json()["detail"]["code"] == "approval_blocked"
    assert any(b["type"] == "flag_review" for b in blocked.json()["detail"]["blockers"])
    review_all_flags(rid)

    # stale version is rejected
    assert dr.post(f"/referrals/{rid}/approve", {"expected_version": r["row_version"] - 1}).status_code == 409
    r = detail(rid)
    v1 = ok(dr.post(f"/referrals/{rid}/approve", {"expected_version": r["row_version"]}))
    assert v1["referral"]["status"] == "approved" and v1["package_version"] == 1

    # editing approved clinical content creates a new version and needs renewed approval (FR-15)
    r = detail(rid)
    b = ok(dr.get(f"/referrals/{rid}/brief"))["latest"]
    sections = [{"key": s["key"], "statements": [{"id": st["id"], "text": st["text"], "evidence_ids": st["evidence_ids"]}
                                                 for st in s["statements"]]} for s in b["sections"]]
    sections[0]["statements"].append({"text": "Patient prefers appointments after 3pm.", "evidence_ids": []})
    saved = ok(dr.put(f"/referrals/{rid}/brief", {"based_on_version": b["version"], "expected_version": r["row_version"],
                                                  "sections": sections, "limitations": []}))
    added = saved["brief"]["sections"][0]["statements"][-1]
    assert added["author_kind"] == "clinician" and added["author_name"] == "Sana Malik"  # FR-44
    r = detail(rid)
    assert r["status"] == "draft"
    assert any(p["version"] == 1 and p["superseded"] for p in r["packages"])
    # stale brief save rejected (concurrent edit detection)
    stale = dr.put(f"/referrals/{rid}/brief", {"based_on_version": b["version"], "expected_version": r["row_version"],
                                              "sections": sections, "limitations": []})
    assert stale.status_code == 409

    ok(staff.post(f"/referrals/{rid}/request-approval", {"expected_version": r["row_version"]}))
    r = detail(rid)
    v2 = ok(dr.post(f"/referrals/{rid}/approve", {"expected_version": r["row_version"]}))
    assert v2["package_version"] == 2
    pkg1 = ok(dr.get(f"/referrals/{rid}/packages/1"))
    assert pkg1["envelope"]["package_version"] == 1  # prior version intact

    # submit -> delivered via outbox -> Submitted
    r = detail(rid)
    ok(staff.post(f"/referrals/{rid}/submit", {"expected_version": r["row_version"]}))
    wait_for(lambda: detail(rid)["status"] == "submitted", timeout=60, what="delivery")
    assert detail(rid)["submitted_package_version"] == 2

    # duplicate send with the same delivery key does not create a second referral (FR-57)
    pkg2 = ok(dr.get(f"/referrals/{rid}/packages/2"))["envelope"]
    dup = httpx.post(f"{SPECIALIST}/inbound/referrals", json=pkg2,
                     headers={"Authorization": f"Bearer {central_service_token()}"}, timeout=20)
    assert dup.status_code == 200 and dup.json()["status"] == "already_received"
    cases = [c for c in ok(spec.get("/specialist/cases")) if c["central_referral_id"] == ref["reference"]]
    assert len(cases) == 1
    case_id = cases[0]["id"]

    # tampered package rejected by the specialist's own approval validation
    tampered = {**pkg2, "delivery_key": pkg2["delivery_key"] + "-x", "reason": "altered after approval"}
    bad = httpx.post(f"{SPECIALIST}/inbound/referrals", json=tampered,
                     headers={"Authorization": f"Bearer {central_service_token()}"}, timeout=20)
    assert bad.status_code == 422 and "hash" in bad.text

    # a clinician cannot use the specialist inbound endpoint
    assert httpx.post(f"{SPECIALIST}/inbound/referrals", json=pkg2,
                      headers={"Authorization": f"Bearer {token(DR)}"}).status_code == 403

    # specialist: decide before acknowledging is refused; then acknowledge, review flags, accept
    assert spec.post(f"/specialist/cases/{case_id}/decision", {"decision": "accept"}).status_code == 409
    ok(spec.post(f"/specialist/cases/{case_id}/acknowledge"))
    wait_for(lambda: detail(rid)["status"] == "acknowledged", timeout=60, what="acknowledged")
    case = ok(spec.get(f"/specialist/cases/{case_id}"))
    env = case["packages"][0]["envelope"]
    assert env["medication_flags"], "flags travel as structured content"
    for f in env["medication_flags"]:
        ok(spec.post(f"/specialist/cases/{case_id}/flags/{f['flag_id']}/review",
                     {"flag_version": f["version"], "action": "reviewed"}))
    ok(spec.post(f"/specialist/cases/{case_id}/decision", {"decision": "accept"}))
    wait_for(lambda: detail(rid)["status"] == "accepted", timeout=60, what="accepted")
    meds = ok(dr.get(f"/referrals/{rid}/medications"))
    assert any(rv["side"] == "specialist" for f in meds["flags"] for rv in f["reviews"])

    # response must be approved before return (FR-51)
    draft = ok(spec.put(f"/specialist/cases/{case_id}/response", {
        "findings": "Class II div 1 malocclusion, crowding lower labial segment",
        "assessment": "Suitable for fixed appliance treatment with lower extractions",
        "recommendations": "Coordinate extraction timing with the referring clinic",
        "follow_up_advice": "Referring clinician to review anticoagulation plan before extractions"}))
    assert spec.post(f"/specialist/cases/{case_id}/response/return").status_code == 409
    ok(spec.post(f"/specialist/cases/{case_id}/response/approve", {"expected_row_version": draft["row_version"]}))
    ok(spec.post(f"/specialist/cases/{case_id}/response/return"))
    wait_for(lambda: detail(rid)["status"] == "response_returned", timeout=60, what="response returned")

    # duplicate response event is ignored
    resps = ok(dr.get(f"/referrals/{rid}/responses"))
    assert len(resps) == 1

    # clinic: closure blocked until response reviewed and tasks disposed
    r = detail(rid)
    assert staff.post(f"/referrals/{rid}/close", {"expected_version": r["row_version"]}).status_code == 409
    assert staff.post(f"/responses/{resps[0]['id']}/review", {"note": "x"}).status_code == 403  # clinician only
    ok(staff.post(f"/responses/{resps[0]['id']}/record-receipt"))
    task = ok(dr.post(f"/referrals/{rid}/tasks", {"description": "Discuss peri-extraction anticoagulation with cardiology",
                                                   "assignee_name": "Hina Raza", "due_date": "2026-10-15"}), 201)
    ok(dr.post(f"/responses/{resps[0]['id']}/review", {"note": "Plan noted"}))
    assert detail(rid)["status"] == "followup_pending"
    r = detail(rid)
    assert staff.post(f"/referrals/{rid}/close", {"expected_version": r["row_version"]}).status_code == 409
    queue = ok(staff.get("/work-queue"))
    assert any(t["id"] == task["id"] for t in queue["tasks"])
    ok(staff.post(f"/tasks/{task['id']}/outcome", {"status": "completed", "outcome": "Cardiology advised plan; documented"}))
    r = detail(rid)
    closed = ok(staff.post(f"/referrals/{rid}/close", {"expected_version": r["row_version"]}))
    assert closed["status"] == "closed"

    # audit trail covers the journey (FR-59/60)
    audit = ok(dr.get(f"/referrals/{rid}/audit"))
    actions = {a["action"] for a in audit}
    for needed in ("referral.create", "records.retrieve", "medication.use_status", "flag.review", "referral.approve",
                   "referral.submit", "delivery.confirmed", "inbound.acknowledged", "inbound.response_returned",
                   "response.review", "referral.status_change"):
        assert needed in actions, needed
    assert all(a["actor_name"] and a["created_at"] and a["outcome"] for a in audit)


def test_specialist_decline_and_clinic_cancel_record_reasons(approved_rules):
    dr, staff, spec = central(DR), central(STAFF), Api(SPECIALIST, "dr.ortho")
    ref = new_referral("MR-418", procedure="fixed_appliance")
    rid = ref["id"]
    ok(dr.post(f"/referrals/{rid}/retrieve"))
    for m in ok(dr.get(f"/referrals/{rid}/medications"))["entries"]:
        ok(dr.post(f"/referrals/{rid}/medications/{m['id']}/use", {"use_status": "confirmed_current"}))
    ok(staff.post(f"/referrals/{rid}/brief/template"), 201)
    review_all_flags(rid)
    resolve_open_overridable(rid)
    r = detail(rid)
    ok(staff.post(f"/referrals/{rid}/request-approval", {"expected_version": r["row_version"]}))
    r = detail(rid)
    if r["status"] == "awaiting_information":
        resolve_open_overridable(rid)
        ok(staff.post(f"/referrals/{rid}/return-to-draft", {"expected_version": r["row_version"]}))
        r = detail(rid)
        ok(staff.post(f"/referrals/{rid}/request-approval", {"expected_version": r["row_version"]}))
        r = detail(rid)
    meds = ok(dr.get(f"/referrals/{rid}/medications"))
    assert meds["evaluation"]["outcome"] == "no_match"
    assert "not treatment clearance" in meds["evaluation"]["summary_message"]
    ok(dr.post(f"/referrals/{rid}/approve", {"expected_version": r["row_version"]}))
    r = detail(rid)
    ok(staff.post(f"/referrals/{rid}/submit", {"expected_version": r["row_version"]}))
    wait_for(lambda: detail(rid)["status"] == "submitted", timeout=60, what="delivery")
    case = next(c for c in ok(spec.get("/specialist/cases")) if c["central_referral_id"] == ref["reference"])
    ok(spec.post(f"/specialist/cases/{case['id']}/acknowledge"))
    assert spec.post(f"/specialist/cases/{case['id']}/decision", {"decision": "decline"}).status_code == 422
    ok(spec.post(f"/specialist/cases/{case['id']}/decision", {"decision": "decline", "reason": "Out of catchment area"}))
    wait_for(lambda: detail(rid)["status"] == "declined", timeout=60, what="declined")
    assert detail(rid)["decline_reason"] == "Out of catchment area"

    other = new_referral("MR-418", procedure=None)
    r = detail(other["id"])
    assert staff.post(f"/referrals/{other['id']}/cancel", {"expected_version": r["row_version"], "reason": ""}).status_code == 422
    c = ok(staff.post(f"/referrals/{other['id']}/cancel", {"expected_version": r["row_version"], "reason": "Patient moved away"}))
    assert c["status"] == "cancelled" and c["cancel_reason"] == "Patient moved away"


def test_search_and_filter_referrals():
    staff = central(STAFF)
    ref = new_referral("MR-330", procedure=None)
    by_patient = ok(staff.get("/referrals", params={"patient": "MR-330"}))
    assert any(r["id"] == ref["id"] for r in by_patient)
    by_ref = ok(staff.get("/referrals", params={"reference": ref["reference"]}))
    assert [r["id"] for r in by_ref] == [ref["id"]]
    by_status = ok(staff.get("/referrals", params={"status": "draft", "destination": "spec-c"}))
    assert all(r["status"] == "draft" for r in by_status)
    by_date = ok(staff.get("/referrals", params={"date_from": "2020-01-01", "date_to": "2099-01-01"}))
    assert any(r["id"] == ref["id"] for r in by_date)
    assert CENTRAL
