import sys, time, json
sys.path.insert(0, "/tmp/s6")
from h import call, ref, ver, wait_status, prepare, parallel

# --- A1 drafts: save, reopen, required fields
s, r = call("A1-create-minimal", "staff.a", "POST", "central", "/referrals", {"patient_local_id": "MR-418"}, quiet=True)
rid = r["id"]; REF = r["reference"]
print(f"[A1] minimal draft -> {s} {REF} status={r['status']} reason={r.get('reason')!r}")
call("A1-edit", "staff.a", "PATCH", "central", f"/referrals/{rid}", {"expected_version": ver(rid), "reason": "Draft saved part-way (Stage 6)"}, quiet=True)
r2 = ref(rid, "staff.a")
print(f"[A1] reopened: reason={r2.get('reason')!r} version={r2['row_version']}")
call("A1-invalid-priority", "dr.malik", "PATCH", "central", f"/referrals/{rid}", {"expected_version": ver(rid), "priority": "critical"})
call("A1-invalid-procedure", "dr.malik", "PATCH", "central", f"/referrals/{rid}", {"expected_version": ver(rid), "procedure_status": "known", "planned_procedure": "brain_surgery"})
s, o = call("A1-request-approval-incomplete", "staff.a", "POST", "central", f"/referrals/{rid}/request-approval", {"expected_version": ver(rid)}, quiet=True)
print(f"[A1] request approval with missing fields -> {s} status={o.get('status')} blockers={[b['message'][:45] for b in o.get('blockers', [])]}")
non_over = [b for b in o.get("blockers", []) if "Provide the missing" in b.get("how", "")]
if non_over:
    call("A1-override-required", "dr.malik", "POST", "central", f"/review-items/{non_over[0]['id']}/resolve", {"action": "overridden", "rationale": "probe"})

# --- A2 search and filters
for params in [{"patient": "MR-418"}, {"patient": "siddiqui"}, {"reference": REF}, {"status": "awaiting_information"},
               {"status": "closed"}, {"destination": "spec-c"}, {"destination": "lab-b"},
               {"date_from": "2026-10-25", "date_to": "2026-10-25"}, {"date_from": "2030-01-01"}, {"status": "nonsense"}]:
    s, rows = call("A2-search", "staff.a", "GET", "central", "/referrals", params=params, quiet=True)
    print(f"[A2] {json.dumps(params):55} -> {s} {len(rows) if isinstance(rows, list) else rows} {[x['reference'] for x in rows][:6] if isinstance(rows, list) else ''}")
call("A2-bad-date", "staff.a", "GET", "central", "/referrals", params={"date_from": "25/10/2026"})

# --- A3 two users saving conflicting edits
v = ver(rid)
s1, _ = call("A3-user1-edit", "staff.a", "PATCH", "central", f"/referrals/{rid}", {"expected_version": v, "reason": "Edit by staff.a (Stage 6)"}, quiet=True)
s2, o2 = call("A3-user2-same-version", "dr.malik", "PATCH", "central", f"/referrals/{rid}", {"expected_version": v, "reason": "Edit by dr.malik (Stage 6)"}, quiet=True)
print(f"[A3] same base version: first -> {s1}, second -> {s2} {o2.get('detail', {}).get('code') if s2 != 200 else ''} | stored reason={ref(rid)['reason']!r}")
outs = parallel(5, lambda i: call("A3-parallel-edits", "dr.malik", "PATCH", "central", f"/referrals/{rid}", {"expected_version": ver(rid), "reason": f"parallel edit {i}"}, quiet=True)[0])
print(f"[A3] 5 parallel edits reading the same version -> {sorted(outs)}")
# brief conflict
call("A3-template", "dr.malik", "POST", "central", f"/referrals/{rid}/brief/template", quiet=True)
_, b = call("A3-brief", "dr.malik", "GET", "central", f"/referrals/{rid}/brief", quiet=True)
cur = b["latest"]; secs = [{"key": x["key"], "statements": [{"id": st["id"], "text": st["text"], "evidence_ids": st["evidence_ids"]} for st in x["statements"]]} for x in cur["sections"]]
secs[0]["statements"].append({"text": "Statement A (Stage 6)", "evidence_ids": []})
sA, _ = call("A3-brief-A", "dr.malik", "PUT", "central", f"/referrals/{rid}/brief", {"based_on_version": cur["version"], "expected_version": ver(rid), "sections": secs}, quiet=True)
secs[0]["statements"][-1]["text"] = "Statement B (Stage 6)"
sB, oB = call("A3-brief-B-stale", "staff.a", "PUT", "central", f"/referrals/{rid}/brief", {"based_on_version": cur["version"], "expected_version": ver(rid), "sections": secs}, quiet=True)
print(f"[A3] brief edits on the same base: A -> {sA}, B -> {sB} {oB.get('detail', {}).get('code') if sB != 200 else ''}")
# medication use (no concurrency token in API)
_, meds = call("A3-meds", "dr.malik", "GET", "central", f"/referrals/{rid}/medications", quiet=True)
if meds["entries"]:
    e = meds["entries"][0]
    o1 = call("A3-use-1", "dr.malik", "POST", "central", f"/referrals/{rid}/medications/{e['id']}/use", {"use_status": "confirmed_current", "note": "user 1"}, quiet=True)[0]
    o2 = call("A3-use-2", "dr.locum", "POST", "central", f"/referrals/{rid}/medications/{e['id']}/use", {"use_status": "historical_stopped", "note": "user 2, based on the same screen"}, quiet=True)[0]
    _, m2 = call("A3-meds", "dr.malik", "GET", "central", f"/referrals/{rid}/medications", quiet=True)
    print(f"[A3] two clinicians set use status from the same screen: {o1}, {o2} -> final {[x['use_status'] for x in m2['entries'] if x['id'] == e['id']]} (no conflict detected)")

# --- A4 approve then edit clinical content; old version preserved
s, o = prepare(rid)
print(f"[A4] request approval -> {s} status={o.get('status')}")
s, a1 = call("A4-approve-v1", "dr.malik", "POST", "central", f"/referrals/{rid}/approve", {"expected_version": ver(rid)}, quiet=True)
print(f"[A4] approved v{a1.get('package_version')}")
call("A4-edit-after-approval", "dr.malik", "PATCH", "central", f"/referrals/{rid}", {"expected_version": ver(rid), "reason": "Reason changed after approval (Stage 6)"}, quiet=True)
r = ref(rid)
_, p1 = call("A4-pkg1", "dr.malik", "GET", "central", f"/referrals/{rid}/packages/1", quiet=True)
print(f"[A4] after edit: status={r['status']} | v1 superseded={p1['superseded']} | v1 reason still={p1['envelope']['reason']!r}")
call("A4-submit-superseded", "staff.a", "POST", "central", f"/referrals/{rid}/submit", {"expected_version": ver(rid)})

# --- A5 edit while approval in progress (stale version at approve time)
s, o = call("A5-request", "dr.malik", "POST", "central", f"/referrals/{rid}/request-approval", {"expected_version": ver(rid)}, quiet=True)
v_seen = ver(rid)
call("A5-concurrent-edit", "staff.a", "PATCH", "central", f"/referrals/{rid}", {"expected_version": v_seen, "reason": "Edited while the clinician was reviewing (Stage 6)"}, quiet=True)
call("A5-approve-stale", "dr.malik", "POST", "central", f"/referrals/{rid}/approve", {"expected_version": v_seen})
print(f"[A5] status after concurrent edit: {ref(rid)['status']}")

# --- A6 concurrent approval attempts
if ref(rid)["status"] != "awaiting_approval":
    call("A6-request", "dr.malik", "POST", "central", f"/referrals/{rid}/request-approval", {"expected_version": ver(rid)}, quiet=True)
v = ver(rid)
res = parallel(4, lambda i: call("A6-parallel-approve", "dr.malik", "POST", "central", f"/referrals/{rid}/approve", {"expected_version": v}, quiet=True))
print(f"[A6] 4 parallel approvals -> {sorted(x[0] for x in res)} versions={sorted(x[1].get('package_version') for x in res if x[0] == 200)} errors={sorted({(x[1].get('detail') or {}).get('code', str(x[1])[:60]) for x in res if x[0] != 200})}")
_, pk = call("A6-packages", "dr.malik", "GET", "central", f"/referrals/{rid}", quiet=True)
open("/tmp/s6/aref", "w").write(f"{rid} {REF}")
