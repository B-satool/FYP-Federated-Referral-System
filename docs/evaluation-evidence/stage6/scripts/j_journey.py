"""Stage 6 phase J: one complete journey, with the separation and guard checks that belong on that path."""
import json, sys, time
sys.path.insert(0, "/tmp/s6")
from h import call, ref, ver, wait_status, case_for, prepare

def st(rid): r = ref(rid); return r["status"]

s, r = call("J1-create", "staff.a", "POST", "central", "/referrals", {"patient_local_id": "MR-102", "reason": "Crowding assessment (Stage 6 journey, synthetic)"}, quiet=True)
rid, REF = r["id"], r["reference"]; open("/tmp/s6/journey", "w").write(f"{rid} {REF}")
print(f"[J1] created {REF} status={r['status']} by staff.a")
call("J2-submit-unapproved", "staff.a", "POST", "central", f"/referrals/{rid}/submit", {"expected_version": ver(rid)})
call("J2-approve-draft", "dr.malik", "POST", "central", f"/referrals/{rid}/approve", {"expected_version": ver(rid)})
s, o = prepare(rid)
print(f"[J3] request-approval -> {s} status={o.get('status')} blockers={o.get('blockers')}")
_, chk = call("J3-check", "dr.malik", "GET", "central", f"/referrals/{rid}/approval-check", quiet=True)
print("     approval blockers:", chk["blockers"])
call("J4-staff-approve", "staff.a", "POST", "central", f"/referrals/{rid}/approve", {"expected_version": ver(rid)})
s, a = call("J4-approve", "dr.malik", "POST", "central", f"/referrals/{rid}/approve", {"expected_version": ver(rid)})
pv, h = a["package_version"], a["content_hash"]
print(f"[J4] approved v{pv} hash={h[:16]}… status={st(rid)}")
s, sub = call("J5-submit", "staff.a", "POST", "central", f"/referrals/{rid}/submit", {"expected_version": ver(rid)})
r = wait_status(rid, {"submitted"})
print(f"[J5] after delivery: status={r['status']} delivery_status={r.get('delivery_status')} submitted_v={r.get('submitted_package_version')} ack={r.get('acknowledged_at')} accepted={r.get('accepted_at')}")
c = case_for(REF)
print(f"[J6] specialist case: {json.dumps({k: c.get(k) for k in ('id','status','latest_version','acknowledged_at','decision')})}")
cid = c["id"]; open("/tmp/s6/case", "w").write(str(cid))
call("J6-decide-before-ack", "dr.ortho", "POST", "spec", f"/specialist/cases/{cid}/decision", {"decision": "accept"})
call("J6-ack", "dr.ortho", "POST", "spec", f"/specialist/cases/{cid}/acknowledge", quiet=True)
r = wait_status(rid, {"acknowledged"})
print(f"[J6] after ack: central status={r['status']} delivery_status={r.get('delivery_status')} ack_at={r.get('acknowledged_at')} accepted_at={r.get('accepted_at')}")
_, full = call("J7-case", "dr.ortho", "GET", "spec", f"/specialist/cases/{cid}", quiet=True)
for f in full["packages"][0]["envelope"].get("medication_flags", []):
    call("J7-spec-flag-review", "dr.ortho", "POST", "spec", f"/specialist/cases/{cid}/flags/{f['flag_id']}/review", {"flag_version": f["version"], "action": "reviewed"}, quiet=True)
call("J7-accept", "dr.ortho", "POST", "spec", f"/specialist/cases/{cid}/decision", {"decision": "accept"}, quiet=True)
r = wait_status(rid, {"accepted"})
print(f"[J7] after accept: central status={r['status']} accepted_at={r.get('accepted_at')}")
call("J7-decline-after-accept", "dr.ortho", "POST", "spec", f"/specialist/cases/{cid}/decision", {"decision": "decline", "reason": "probe"})

# specialist clarification while accepted -> progress must be preserved
s, q = call("J8-spec-clarification", "dr.ortho", "POST", "spec", f"/specialist/cases/{cid}/clarifications", {"question": "Please confirm the date of the last INR (Stage 6)."})
time.sleep(8)
r = ref(rid)
_, cl = call("J8-clinic-clars", "dr.malik", "GET", "central", f"/referrals/{rid}/clarifications", quiet=True)
spec_cl = [x for x in cl if x["origin"] == "specialist"]
print(f"[J8] central status during specialist clarification: {r['status']} | clarification: {[(x['id'], x['status'], x['question'][:40]) for x in spec_cl]}")
_, wq = call("J8-clinic-queue", "staff.a", "GET", "central", "/work-queue", quiet=True)
print("     clinic work queue has it:", any(x["id"] == spec_cl[0]["id"] for x in wq["clarifications"]) if spec_cl else None)
if spec_cl:
    call("J8-answer", "staff.a", "POST", "central", f"/clarifications/{spec_cl[0]['id']}/answer", {"response_text": "Last INR 2.7 on 05/09/2026 (corrected value)."}, quiet=True)
    time.sleep(8)
    _, full = call("J8-case", "dr.ortho", "GET", "spec", f"/specialist/cases/{cid}", quiet=True)
    print("     specialist sees answer:", [(x.get("status"), (x.get("answer") or "")[:40]) for x in full.get("clarifications", [])])
print(f"     central status after answer: {st(rid)}")

# specialist response: guards then approve and return
call("J9-return-before-approve", "dr.ortho", "POST", "spec", f"/specialist/cases/{cid}/response/return")
s, d = call("J9-draft", "dr.ortho", "PUT", "spec", f"/specialist/cases/{cid}/response",
            {"findings": "Class II div 1 with lower crowding", "assessment": "Suitable for fixed appliances with extractions",
             "recommendations": "Coordinate extraction timing with the clinic", "follow_up_advice": "Clinic to confirm anticoagulation plan before extractions"}, quiet=True)
call("J9-approve-stale", "dr.ortho", "POST", "spec", f"/specialist/cases/{cid}/response/approve", {"expected_row_version": d["row_version"] - 1})
call("J9-approve", "dr.ortho", "POST", "spec", f"/specialist/cases/{cid}/response/approve", {"expected_row_version": d["row_version"]}, quiet=True)
call("J9-edit-after-approve", "dr.ortho", "PUT", "spec", f"/specialist/cases/{cid}/response", {"findings": "changed after approval"})
call("J9-return", "dr.ortho", "POST", "spec", f"/specialist/cases/{cid}/response/return", quiet=True)
s, again = call("J9-return-again", "dr.ortho", "POST", "spec", f"/specialist/cases/{cid}/response/return", quiet=True)
print(f"[J9] second return -> {s} status={again.get('status')}")
r = wait_status(rid, {"response_returned"})
_, resps = call("J10-responses", "dr.malik", "GET", "central", f"/referrals/{rid}/responses", quiet=True)
print(f"[J10] central status={r['status']} responses={len(resps)} -> {[(x['id'], x.get('specialist_name'), x.get('receipt_recorded_at'), x.get('reviewed_at')) for x in resps]}")
resp_id = resps[0]["id"]
_, wq = call("J10-queue", "dr.malik", "GET", "central", "/work-queue", quiet=True)
print("     'responses to review' in queue:", [x["referral_reference"] for x in wq["responses_to_review"]])
call("J11-close-before-review", "dr.malik", "POST", "central", f"/referrals/{rid}/close", {"expected_version": ver(rid)})
s, rc = call("J11-staff-receipt", "staff.a", "POST", "central", f"/responses/{resp_id}/record-receipt", quiet=True)
print(f"[J11] receipt by staff -> {s} receipt={rc.get('receipt_recorded_by')} @ {rc.get('receipt_recorded_at')} reviewed_at={rc.get('reviewed_at')}")
call("J11-staff-review", "staff.a", "POST", "central", f"/responses/{resp_id}/review", {"note": "staff probe"})
call("J11-close-still-unreviewed", "dr.malik", "POST", "central", f"/referrals/{rid}/close", {"expected_version": ver(rid)})
s, t = call("J12-task-overdue", "dr.malik", "POST", "central", f"/referrals/{rid}/tasks",
            {"description": "Obtain cardiology plan for peri-extraction anticoagulation", "assignee_name": "Hina Raza", "due_date": "2026-10-01"}, quiet=True)
s, rv = call("J12-review", "dr.malik", "POST", "central", f"/responses/{resp_id}/review", {"note": "Plan noted (Stage 6)"}, quiet=True)
print(f"[J12] clinician review -> {s} reviewed_by={rv['response'].get('reviewed_by')} status={rv['referral']['status']}")
_, wq = call("J12-queue", "staff.a", "GET", "central", "/work-queue", quiet=True)
print("     task in queue:", [(x["description"][:30], x["overdue"], x["referral_reference"]) for x in wq["tasks"] if x["referral_reference"] == REF])
call("J13-close-open-task", "dr.malik", "POST", "central", f"/referrals/{rid}/close", {"expected_version": ver(rid)})
call("J13-outcome-no-text", "staff.a", "POST", "central", f"/tasks/{t['id']}/outcome", {"status": "completed", "outcome": ""})
call("J13-outcome", "staff.a", "POST", "central", f"/tasks/{t['id']}/outcome", {"status": "completed", "outcome": "Cardiology plan received and filed"}, quiet=True)
s, c2 = call("J13-close", "dr.malik", "POST", "central", f"/referrals/{rid}/close", {"expected_version": ver(rid)})
print(f"[J13] close -> {s} status={c2.get('status')}")
call("J13-edit-after-close", "dr.malik", "PATCH", "central", f"/referrals/{rid}", {"expected_version": ver(rid), "reason": "edited after close"})
_, ev = call("J14-events", "dr.malik", "GET", "central", f"/referrals/{rid}/events", quiet=True)
print("[J14] timeline:", [(e["event_type"], e.get("to_status")) for e in ev])
