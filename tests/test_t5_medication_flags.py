"""T5 - integrated medication flags: reevaluation, versioning and renewed review (FR-61 to FR-72)."""
from __future__ import annotations

from conftest import compose, new_referral, start_service
from helpers import SPECIALIST, Api, central, ok, wait_for
from test_t3_manual_flow import detail, resolve_open_overridable, review_all_flags

DR, STAFF = "dr.malik", "staff.a"


def set_uses(rid: int, mapping: dict[str, str], default: str = "uncertain") -> None:
    dr = central(DR)
    for m in ok(dr.get(f"/referrals/{rid}/medications"))["entries"]:
        ok(dr.post(f"/referrals/{rid}/medications/{m['id']}/use", {"use_status": mapping.get(m["ingredient"] or "", default)}))


def flags(rid: int) -> list[dict]:
    return ok(central(DR).get(f"/referrals/{rid}/medications"))["flags"]


def approve_and_send(rid: int) -> None:
    dr, staff = central(DR), central(STAFF)
    review_all_flags(rid)
    resolve_open_overridable(rid)
    r = detail(rid)
    if r["status"] in ("draft", "awaiting_information"):
        if r["status"] == "awaiting_information":
            ok(staff.post(f"/referrals/{rid}/return-to-draft", {"expected_version": r["row_version"]}))
            r = detail(rid)
        ok(staff.post(f"/referrals/{rid}/request-approval", {"expected_version": r["row_version"]}))
        r = detail(rid)
    ok(dr.post(f"/referrals/{rid}/approve", {"expected_version": r["row_version"]}))
    r = detail(rid)
    ok(staff.post(f"/referrals/{rid}/submit", {"expected_version": r["row_version"]}))


def test_rules_require_clinical_reviewer_and_drafts_do_not_flag():
    admin, staff = central("admin.a"), central(STAFF)
    rules = ok(staff.get("/rules"))["rules"]
    r0 = rules[0]
    body = {"decision": "approve", "reference_checked": "Checked the guideline", "note": ""}
    assert admin.post(f"/rules/{r0['rule_id']}/versions/{r0['version']}/decision", body).status_code == 403
    assert staff.post(f"/rules/{r0['rule_id']}/versions/{r0['version']}/decision", body).status_code == 403
    # before approval the referral reports unsupported coverage instead of "no match"
    if all(r["approval_state"] != "approved" for r in rules):
        ref = new_referral("MR-102")
        ok(central(DR).post(f"/referrals/{ref['id']}/retrieve"))
        set_uses(ref["id"], {"warfarin": "confirmed_current"})
        meds = ok(central(DR).get(f"/referrals/{ref['id']}/medications"))
        assert meds["evaluation"]["outcome"] == "unsupported_coverage"
        assert not any(f["kind"] == "confirmed" for f in meds["flags"])


def test_procedure_context_and_reevaluation_without_duplicates(approved_rules):
    dr = central(DR)
    ref = new_referral("MR-102", procedure=None)  # explicitly unknown
    rid = ref["id"]
    ok(dr.post(f"/referrals/{rid}/retrieve"))
    set_uses(rid, {"warfarin": "confirmed_current", "alendronate": "historical_stopped", "atorvastatin": "confirmed_current"})
    f1 = flags(rid)
    assert any(f["kind"] == "procedure_context_required" and f["rule_id"] == "ORTHO-ANTICOAG-SURG" for f in f1)
    assert not any(f["kind"] == "confirmed" and f["drug_class"] == "anticoagulant" for f in f1)
    # repeat evaluation -> no duplicate visible flags
    again = ok(dr.post(f"/referrals/{rid}/medications/evaluate"))
    assert again["status"] == "completed"
    assert len(flags(rid)) == len(f1)
    # same medication, different procedure contexts follow the configured rules
    r = detail(rid)
    ok(dr.patch(f"/referrals/{rid}", {"expected_version": r["row_version"], "procedure_status": "known",
                                      "planned_procedure": "fixed_appliance"}))
    assert not any(f["drug_class"] == "anticoagulant" for f in flags(rid))
    r = detail(rid)
    ok(dr.patch(f"/referrals/{rid}", {"expected_version": r["row_version"], "planned_procedure": "tooth_extraction"}))
    anticoag = [f for f in flags(rid) if f["kind"] == "confirmed" and f["drug_class"] == "anticoagulant"]
    assert len(anticoag) == 1
    history = ok(dr.get(f"/referrals/{rid}/medications"))["flag_history"]
    assert any(h["kind"] == "procedure_context_required" and h["status"] == "withdrawn" for h in history)


def test_incomplete_history_coexists_with_confirmed_flags(approved_rules):
    dr = central(DR)
    ref = new_referral("MR-102")
    rid = ref["id"]
    ok(dr.post(f"/referrals/{rid}/retrieve"))
    set_uses(rid, {"warfarin": "confirmed_current"})
    compose("stop", "clinic")
    try:
        res = ok(dr.post(f"/referrals/{rid}/retrieve", params={"source": "clinic-a"}))["results"][0]
    finally:
        start_service("clinic")
    assert res["status"] == "unavailable"
    fl = flags(rid)
    assert any(f["kind"] == "history_incomplete" for f in fl) and any(f["kind"] == "confirmed" for f in fl)
    msg = next(f for f in fl if f["kind"] == "history_incomplete")["message"]
    assert "absence of a flag does not mean absence" in msg


def test_changed_flag_after_submission_needs_new_version_and_review(approved_rules):
    dr, spec = central(DR), Api(SPECIALIST, "dr.ortho")
    ref = new_referral("MR-102", procedure="tooth_extraction")
    rid = ref["id"]
    ok(dr.post(f"/referrals/{rid}/retrieve"))
    set_uses(rid, {"warfarin": "confirmed_current", "alendronate": "historical_stopped", "atorvastatin": "confirmed_current",
                   "aspirin": "uncertain"})
    ok(central(STAFF).post(f"/referrals/{rid}/brief/template"), 201)
    approve_and_send(rid)
    wait_for(lambda: detail(rid)["status"] == "submitted", timeout=60, what="delivery v1")
    case = next(c for c in ok(spec.get("/specialist/cases")) if c["central_referral_id"] == ref["reference"])
    ok(spec.post(f"/specialist/cases/{case['id']}/acknowledge"))
    v1 = ok(spec.get(f"/specialist/cases/{case['id']}"))["packages"][0]["envelope"]
    for f in v1["medication_flags"]:
        ok(spec.post(f"/specialist/cases/{case['id']}/flags/{f['flag_id']}/review", {"flag_version": f["version"], "action": "reviewed"}))
    assert any(f["kind"] == "possible_use" for f in v1["medication_flags"])

    # clinician now confirms aspirin (Ecosprin) is current -> material flag change (FR-70)
    aspirin = next(m for m in ok(dr.get(f"/referrals/{rid}/medications"))["entries"] if m["ingredient"] == "aspirin")
    ok(dr.post(f"/referrals/{rid}/medications/{aspirin['id']}/use", {"use_status": "confirmed_current", "note": "Confirmed by phone"}))
    r = detail(rid)
    assert r["amendment_open"] is True and r["status"] in ("submitted", "acknowledged")
    new = [f for f in flags(rid) if f["kind"] == "confirmed" and f["drug_class"] == "antiplatelet"]
    assert new and not new[0]["reviews"]
    blockers = ok(dr.get(f"/referrals/{rid}/approval-check"))["blockers"]
    assert any(b["type"] == "flag_review" for b in blockers)

    approve_and_send(rid)
    wait_for(lambda: detail(rid)["submitted_package_version"] == 2, timeout=60, what="delivery v2")
    case_detail = ok(spec.get(f"/specialist/cases/{case['id']}"))
    assert case_detail["case"]["latest_version"] == 2 and len(case_detail["packages"]) == 2
    v2 = case_detail["packages"][0]["envelope"]
    assert any(f["drug_class"] == "antiplatelet" and f["kind"] == "confirmed" for f in v2["medication_flags"])
    # earlier acknowledgments retained against version 1
    assert all(rv["package_version"] == 1 for rv in case_detail["flag_reviews"])
    # the new flag must be acknowledged against v2 specifically; old version numbers are refused
    anti = next(f for f in v2["medication_flags"] if f["drug_class"] == "antiplatelet")
    assert spec.post(f"/specialist/cases/{case['id']}/flags/{anti['flag_id']}/review",
                     {"flag_version": anti["version"] + 5, "action": "reviewed"}).status_code == 409
    ok(spec.post(f"/specialist/cases/{case['id']}/flags/{anti['flag_id']}/review",
                 {"flag_version": anti["version"], "action": "request_clarification",
                  "question": "Is aspirin taken for cardiac indication, and who manages it?"}))
    wait_for(lambda: any(c["origin"] == "specialist" and c["flag_id"] == anti["flag_id"]
                         for c in ok(dr.get(f"/referrals/{rid}/clarifications"))), timeout=60, what="clarification relay")
    clar = next(c for c in ok(dr.get(f"/referrals/{rid}/clarifications")) if c["origin"] == "specialist")
    ok(dr.post(f"/clarifications/{clar['id']}/answer", {"response_text": "Prescribed by cardiology for AF; managed by cardiology"}))
    wait_for(lambda: any(c["status"] == "answered" for c in ok(spec.get(f"/specialist/cases/{case['id']}"))["clarifications"]),
             timeout=60, what="answer delivered to specialist")
    pkg1 = ok(dr.get(f"/referrals/{rid}/packages/1"))
    assert not any(f["drug_class"] == "antiplatelet" and f["kind"] == "confirmed" for f in pkg1["envelope"]["medication_flags"])
    audit = {a["action"] for a in ok(dr.get(f"/referrals/{rid}/audit"))}
    assert {"medications.evaluate", "medication.use_status", "inbound.flag_reviewed"} <= audit
