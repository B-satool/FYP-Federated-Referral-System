"""T6 - completeness, clarification with a participating source, and brief generation (FR-35 to FR-46, FR-58)."""
from __future__ import annotations

import pytest
from conftest import new_referral
from helpers import central, ok, wait_for

DR, STAFF = "dr.malik", "staff.a"


def test_missing_information_request_answered_by_lab_and_resolved():
    dr, staff, lab = central(DR), central(STAFF), central("lab.b")
    ref = new_referral("MR-102", procedure=None)
    rid = ref["id"]
    ok(dr.post(f"/referrals/{rid}/retrieve"))
    items = ok(dr.get(f"/referrals/{rid}/review-items"))
    meds_item = next(i for i in items if i["checklist_item_id"] == "CL-MEDS-VERIFIED")
    # clarifications can only go to participants with a verified link
    assert staff.post(f"/referrals/{rid}/clarifications", {"question": "Send records please", "assignee_institution": "spec-c"}).status_code == 422
    c = ok(staff.post(f"/referrals/{rid}/clarifications", {
        "question": "Please confirm whether a coagulation result after 05/09/2026 is available",
        "assignee_institution": "lab-b", "review_item_id": meds_item["id"], "due_date": "2026-10-20"}), 201)
    assert c["status"] == "open"
    assert ok(dr.get(f"/referrals/{rid}"))["status"] == "awaiting_information"

    queue = ok(lab.get("/work-queue"))
    mine = next(x for x in queue["clarifications"] if x["id"] == c["id"])
    assert mine["patient_ref_at_assignee"] == "LB-5531"  # lab sees its own identifier
    assert mine["patient_name"] is None  # and not the clinic's patient record
    assert lab.get(f"/referrals/{rid}").status_code == 403  # no access to the referral itself
    assert central("staff.x").post(f"/clarifications/{c['id']}/answer", {"response_text": "x" * 5}).status_code == 403
    ok(lab.post(f"/clarifications/{c['id']}/answer", {"response_text": "No later coagulation result on file at Lab B"}))

    answered = next(x for x in ok(staff.get(f"/referrals/{rid}/clarifications")) if x["id"] == c["id"])
    assert answered["status"] == "answered" and answered["answered_by"] == "Kamran Butt"
    ok(staff.post(f"/clarifications/{c['id']}/resolve", {"note": "Answer recorded"}))
    assert ok(dr.get(f"/referrals/{rid}"))["status"] == "draft"


def test_checklist_reports_missing_items_and_override_rules():
    staff, dr = central(STAFF), central(DR)
    body = {"patient_local_id": "MR-418", "reason": "", "procedure_status": "not_stated"}
    ref = ok(staff.post("/referrals", body), 201)
    rid = ref["id"]
    detail = ok(staff.get(f"/referrals/{rid}"))
    states = {c["id"]: c["state"] for c in detail["checklist"]}
    for item in ("CL-REASON", "CL-PRIORITY", "CL-PROCEDURE", "CL-CLINICIAN"):
        assert states[item] == "missing", item
    items = ok(dr.get(f"/referrals/{rid}/review-items"))
    reason_item = next(i for i in items if i["checklist_item_id"] == "CL-REASON")
    # required administrative fields cannot be overridden
    assert dr.post(f"/review-items/{reason_item['id']}/resolve", {"action": "overridden", "rationale": "skip it please"}).status_code == 409
    r = ok(staff.get(f"/referrals/{rid}"))
    ok(staff.patch(f"/referrals/{rid}", {"expected_version": r["row_version"], "reason": "Crossbite; orthodontic opinion requested"}))
    items = ok(dr.get(f"/referrals/{rid}/review-items"))
    assert next(i for i in items if i["checklist_item_id"] == "CL-REASON")["status"] == "resolved"
    # staff cannot set the clinician-selected priority
    r = ok(staff.get(f"/referrals/{rid}"))
    assert staff.patch(f"/referrals/{rid}", {"expected_version": r["row_version"], "priority": "urgent"}).status_code == 403


def test_brief_generation_path():
    dr = central(DR)
    ref = new_referral("MR-102")
    rid = ref["id"]
    ok(dr.post(f"/referrals/{rid}/retrieve"))
    info = ok(dr.get(f"/referrals/{rid}/brief"))
    job = ok(dr.post(f"/referrals/{rid}/brief/generate"), 202)
    done = wait_for(lambda: (j := ok(dr.get(f"/jobs/{job['id']}")))["status"] in ("completed", "failed") and j,
                    timeout=240, interval=2, what="generation job")
    if not info["llm_configured"]:
        # FR-58: model unavailable -> visible failure, manual preparation still possible
        assert done["status"] == "failed" and "No language model is configured" in done["error"]
        ok(dr.post(f"/referrals/{rid}/brief/template"), 201)
        assert ok(dr.get(f"/referrals/{rid}/brief"))["latest"]["kind"] == "template"
        pytest.skip("LLM not configured: verified failure path and manual fallback only")
    assert done["status"] == "completed", done
    b = ok(dr.get(f"/referrals/{rid}/brief"))["latest"]
    assert b["kind"] == "generated" and b["model"].startswith("anthropic:")
    supplied = {e["id"] for e in ok(dr.get(f"/referrals/{rid}/evidence")) if e["selected"]}
    for s in b["sections"]:
        for st in s["statements"]:
            assert set(st["evidence_ids"]) <= supplied
            if s["key"] in ("history", "medications", "results"):
                assert st["evidence_ids"], st
    assert "medication_flags" not in {s["key"] for s in b["sections"]}
