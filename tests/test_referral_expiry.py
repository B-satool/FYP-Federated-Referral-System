"""When a referral's shared records expire (docs/decisions/2026-10-28-referral-expiry.md):
no limit until the receiving doctor accepts; then 30 days, which they can extend; 72 hours after they
mark it complete; straight away if they decline. At expiry the receiving hospital's copy goes too."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from conftest import SURGERY, compose, new_referral
from helpers import central, institution, ok, wait_for

DOCTOR, STAFF = central("dr.ali"), central("staff.ali")
# Dr Salman Akhtar (orthopaedics): no other test uses him, so these cases do not disturb test_v2_flow
AKU_STAFF, SURGEON = institution("akuh", "staff.aku"), institution("akuh", "dr.salman")


def _ref(rid):
    return ok(STAFF.get(f"/referrals/{rid}"))


def _at(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _send(patient: str) -> dict:
    r = new_referral(patient, "akuh", "orthopaedics", "Total knee replacement (right)", SURGERY)
    rid = r["id"]
    ok(STAFF.post(f"/referrals/{rid}/retrieve"))
    ok(STAFF.post(f"/referrals/{rid}/medications/checked", {"note": "Asked"}))
    ok(STAFF.post(f"/referrals/{rid}/prepared", {"expected_version": _ref(rid)["row_version"]}))
    for f in ok(DOCTOR.get(f"/referrals/{rid}/medications"))["flags"]:
        ok(DOCTOR.post(f"/referrals/{rid}/flags/{f['id']}/acknowledge", {"flag_version": f["version"]}))
    ok(STAFF.post(f"/referrals/{rid}/send", {"expected_version": _ref(rid)["row_version"]}))
    wait_for(lambda: _ref(rid)["status"] == "submitted", 60, what="delivery")
    return _ref(rid)


def _take_in(reference: str) -> dict:
    """AKUH staff acknowledge, confirm the patient and assign Dr Salman Akhtar."""
    case = wait_for(lambda: next((c for c in ok(AKU_STAFF.get("/cases")) if c["central_referral_id"] == reference), None),
                    30, what="case at AKUH")
    ok(AKU_STAFF.post(f"/cases/{case['id']}/acknowledge"))
    case = ok(AKU_STAFF.get(f"/cases/{case['id']}"))["case"]
    if not case["local_patient_id"]:
        link = case["link_request_id"]
        cands = ok(central("staff.aku").post(f"/patient-links/{link}/lookup"))["candidates"]
        body = ({"local_patient_id": cands[0]["local_patient_id"], "note": "CNIC and date of birth match"} if cands
                else {"register_new": True, "note": "New patient; CNIC and date of birth checked"})
        ok(central("staff.aku").post(f"/patient-links/{link}/approve", body))
    ok(AKU_STAFF.post(f"/cases/{case['id']}/assign", {"doctor": "Dr Salman Akhtar"}))
    return case


def _expire_now(rid: int) -> None:
    """Run the purge as the worker would once the time is up."""
    compose("exec", "-T", "central", "python", "-c",
            "from datetime import timedelta\nfrom refcommon.db import utcnow\nfrom app.db import SessionLocal\n"
            "from app.models import Referral\nfrom app.lifecycle.working_set import purge_due\n"
            f"db = SessionLocal()\nr = db.get(Referral, {rid})\nr.working_set_expires_at = utcnow() - timedelta(seconds=1)\n"
            "db.commit()\nassert purge_due(db) >= 1\n")


def test_accept_extend_complete_then_expire():
    r = _send("Rubina")  # (Imtiaz and Gondal must stay unknown at AKUH for test_v2_flow)
    rid = r["id"]
    assert r["working_set_expires_at"] is None  # sent, not yet accepted: no time limit
    case = _take_in(r["reference"])
    ok(SURGEON.post(f"/cases/{case['id']}/decision", {"decision": "accept"}))
    accepted = wait_for(lambda: (x := _ref(rid))["status"] == "accepted" and x, 60, what="accepted at the clinic")
    hold = _at(accepted["working_set_expires_at"])
    assert abs(hold - (datetime.now(timezone.utc) + timedelta(days=30))) < timedelta(minutes=5)
    assert abs(_at(ok(SURGEON.get(f"/cases/{case['id']}"))["case"]["hold_until"]) - hold) < timedelta(minutes=5)

    # only once the response is sent can it be marked complete; extending is allowed meanwhile, with a reason
    assert SURGEON.post(f"/cases/{case['id']}/complete").status_code == 409
    assert SURGEON.post(f"/cases/{case['id']}/extend-hold", {"reason": ""}).status_code == 422
    assert AKU_STAFF.post(f"/cases/{case['id']}/extend-hold", {"reason": "need more time"}).status_code == 403
    ok(SURGEON.post(f"/cases/{case['id']}/extend-hold", {"reason": "Waiting for the anaesthetic review"}))
    wait_for(lambda: any(e["event_type"] == "hold_extended_by_receiver" for e in ok(STAFF.get(f"/referrals/{rid}/events"))),
             60, what="extension at the platform")
    assert _at(_ref(rid)["working_set_expires_at"]) >= hold

    resp = ok(SURGEON.put(f"/cases/{case['id']}/response", {"assessment": "Severe osteoarthritis of the right knee.", "plan": "Elective list."}))
    ok(SURGEON.post(f"/cases/{case['id']}/response/send", {"expected_row_version": resp["row_version"]}))
    done = ok(SURGEON.post(f"/cases/{case['id']}/complete"))
    assert done["status"] == "completed" and done["completed_by"] == "Dr Salman Akhtar"
    completed = wait_for(lambda: (x := _ref(rid))["receiver_completed_at"] and x, 60, what="completion at the platform")
    removal = _at(completed["working_set_expires_at"])
    assert abs(removal - (_at(completed["receiver_completed_at"]) + timedelta(hours=72))) < timedelta(minutes=1)
    assert any("marked complete" in n["title"] for n in ok(DOCTOR.get("/notifications")))
    assert SURGEON.post(f"/cases/{case['id']}/extend-hold", {"reason": "too late"}).status_code == 409

    # the time is up: the platform's copy and AKUH's copy of the shared records go; AKUH keeps its response
    # (removal waits until everything sent has been delivered, including the clinic's copy of the response)
    wait_for(lambda: all(b["status"] == "sent" for b in ok(STAFF.get(f"/referrals/{rid}/delivery"))), 60, what="deliveries")
    _expire_now(rid)
    assert _ref(rid)["working_set_purged_at"]
    detail = wait_for(lambda: (d := ok(SURGEON.get(f"/cases/{case['id']}")))["case"]["shared_removed_at"] and d,
                      60, what="removal at AKUH")
    assert all(p["envelope"].get("purged") for p in detail["packages"])
    assert detail["packages"][0]["content_hash"]  # the fingerprint stays
    assert detail["responses"][0]["content"]["assessment"] == "Severe osteoarthritis of the right knee."


def test_decline_removes_the_shared_records_straight_away():
    r = _send("Rubina")
    rid = r["id"]
    case = _take_in(r["reference"])
    ok(SURGEON.post(f"/cases/{case['id']}/decision", {"decision": "decline", "reason": "Not an orthopaedic problem"}))
    wait_for(lambda: _ref(rid)["working_set_purged_at"], 90, what="removal at the platform")
    detail = wait_for(lambda: (d := ok(SURGEON.get(f"/cases/{case['id']}")))["case"]["shared_removed_at"] and d,
                      60, what="removal at AKUH")
    assert detail["case"]["decline_reason"] == "Not an orthopaedic problem"  # AKUH's own decision is kept
    assert all(p["envelope"].get("purged") for p in detail["packages"])
