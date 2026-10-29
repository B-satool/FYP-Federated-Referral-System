import json, os, sys, time
sys.path.insert(0, "/tmp/s6")
import httpx
from h import call, ref, ver, wait_status, case_for, prepare, parallel, svc_token

phase = sys.argv[1]
A_RID, A_REF = open("/tmp/s6/aref").read().split(); A_RID = int(A_RID)

if phase == "submit-while-worker-down":
    r = ref(A_RID); print(f"[B1] {A_REF} status={r['status']} current_package=v{r.get('current_package_version')}")
    v = ver(A_RID)
    res = parallel(5, lambda i: call("B1-parallel-submit", "staff.a", "POST", "central", f"/referrals/{A_RID}/submit", {"expected_version": v}, quiet=True))
    print(f"[B1] 5 parallel submits -> {sorted(x[0] for x in res)} outbox ids={sorted({x[1]['outbox']['id'] for x in res if x[0] == 200})} errors={sorted({str(x[1])[:50] for x in res if x[0] != 200})}")
    for i in range(3):
        s, o = call("B1-repeat-click", "staff.a", "POST", "central", f"/referrals/{A_RID}/submit", {"expected_version": ver(A_RID)}, quiet=True)
        print(f"[B1] sequential click {i+1} -> {s} outbox={o.get('outbox') if s == 200 else o}")
    # edit while the approved version is queued for delivery
    s, o = call("B2-edit-while-queued", "dr.malik", "PATCH", "central", f"/referrals/{A_RID}", {"expected_version": ver(A_RID), "reason": "Clinical edit made while delivery was still queued (Stage 6)"}, quiet=True)
    r = ref(A_RID)
    _, p = call("B2-pkg", "dr.malik", "GET", "central", f"/referrals/{A_RID}/packages/{r['current_package_version']}", quiet=True)
    _, d = call("B2-delivery", "dr.malik", "GET", "central", f"/referrals/{A_RID}/delivery", quiet=True)
    print(f"[B2] after edit: status={r['status']} package v{r['current_package_version']} superseded={p['superseded']} | outbox={[(x['id'], x['status'], x['message_key']) for x in d]}")

elif phase == "after-worker-up":
    r = wait_status(A_RID, {"submitted"}, timeout=40)
    _, d = call("B2-delivery", "dr.malik", "GET", "central", f"/referrals/{A_RID}/delivery", quiet=True)
    c = case_for(A_REF)
    print(f"[B2] after worker restart: central status={r['status']} delivery_status={r.get('delivery_status')} submitted_v={r.get('submitted_package_version')} current_v={r.get('current_package_version')}")
    print(f"     outbox={[(x['id'], x['status'], x.get('attempts')) for x in d]} | specialist case={c and {k: c[k] for k in ('id', 'status', 'latest_version')}}")
    _, ev = call("B2-events", "dr.malik", "GET", "central", f"/referrals/{A_RID}/events", quiet=True)
    print("     timeline tail:", [(e["event_type"], e.get("to_status"), (e.get("detail") or {}).get("reason", "")[:50]) for e in ev][-5:])

elif phase == "timeout-prepare":
    s, r = call("B3-create", "staff.a", "POST", "central", "/referrals", {"patient_local_id": "MR-330", "reason": "Stage 6: sender timeout scenario (synthetic)"}, quiet=True)
    rid, REF = r["id"], r["reference"]; open("/tmp/s6/tref", "w").write(f"{rid} {REF}")
    prepare(rid)
    s, a = call("B3-approve", "dr.malik", "POST", "central", f"/referrals/{rid}/approve", {"expected_version": ver(rid)}, quiet=True)
    print(f"[B3] {REF} approved v{a.get('package_version')} -> {s}")

elif phase == "timeout-worker-down":
    rid, REF = open("/tmp/s6/tref").read().split(); rid = int(rid)
    from h import tok
    tok("staff.a"); v = ver(rid)
    res = parallel(5, lambda i: call("B3-parallel-submit", "staff.a", "POST", "central", f"/referrals/{rid}/submit", {"expected_version": v}, quiet=True))
    print(f"[B3] 5 parallel submits (token pre-fetched) -> {sorted(x[0] for x in res)} outbox ids={sorted({x[1]['outbox']['id'] for x in res if x[0] == 200})} errors={sorted({str(x[1])[:70] for x in res if x[0] != 200})}")
    _, p = call("B3-pkg", "dr.malik", "GET", "central", f"/referrals/{rid}/packages/1", quiet=True)
    tok = svc_token("central-api", os.environ["SERVICE_CLIENT_SECRET"])
    first = httpx.post("http://specialist:8000/inbound/referrals", json=p["envelope"], headers={"Authorization": f"Bearer {tok}"}, timeout=30)
    print(f"[B3] first attempt reached the specialist, sender never recorded it: {first.status_code} {first.text[:120]}")
    r = ref(rid)
    print(f"     central meanwhile: status={r['status']} delivery_status={r.get('delivery_status')}")

elif phase == "timeout-after":
    rid, REF = open("/tmp/s6/tref").read().split(); rid = int(rid)
    r = wait_status(rid, {"submitted"}, timeout=40)
    _, d = call("B3-delivery", "dr.malik", "GET", "central", f"/referrals/{rid}/delivery", quiet=True)
    print(f"[B3] after retry: central status={r['status']} delivery_status={r.get('delivery_status')} | outbox={[(x['status'], x.get('attempts')) for x in d]}")
    _, ev = call("B3-events", "dr.malik", "GET", "central", f"/referrals/{rid}/events", quiet=True)
    print("     delivered event remote result:", [e.get("detail", {}).get("remote") for e in ev if e["event_type"] == "delivered"])

elif phase == "replay-and-cancel":
    # replay specialist events for the journey referral (event-key dedupe)
    J_RID, J_REF = open("/tmp/s6/journey").read().split(); J_RID = int(J_RID)
    tok = svc_token("specialist-api", os.environ["SPEC_SECRET"])
    for p in json.load(open("/tmp/s6/spec_events.json")):
        rr = httpx.post("http://central:8000/inbound/specialist-events", json=p, headers={"Authorization": f"Bearer {tok}"}, timeout=30)
        print(f"[B4] replay {p['type']:22} key={p['event_key'][-30:]} -> {rr.status_code} {rr.text[:80]}")
    _, resps = call("B4-responses", "dr.malik", "GET", "central", f"/referrals/{J_RID}/responses", quiet=True)
    print(f"[B4] responses after replay: {len(resps)} | referral status: {ref(J_RID)['status']}")
    # cancellation / decline reasons
    rid, REF = open("/tmp/s6/tref").read().split(); rid = int(rid)
    c = case_for(REF)
    call("B5-spec-ack", "dr.ortho", "POST", "spec", f"/specialist/cases/{c['id']}/acknowledge", quiet=True)
    wait_status(rid, {"acknowledged"}, timeout=30)
    call("B5-decline-no-reason", "dr.ortho", "POST", "spec", f"/specialist/cases/{c['id']}/decision", {"decision": "decline"})
    call("B5-decline-blank-reason", "dr.ortho", "POST", "spec", f"/specialist/cases/{c['id']}/decision", {"decision": "decline", "reason": "   "})
    call("B5-cancel-no-reason", "staff.a", "POST", "central", f"/referrals/{rid}/cancel", {"expected_version": ver(rid)})
    call("B5-cancel-blank-reason", "staff.a", "POST", "central", f"/referrals/{rid}/cancel", {"expected_version": ver(rid), "reason": "   "})
    s, o = call("B5-cancel", "staff.a", "POST", "central", f"/referrals/{rid}/cancel", {"expected_version": ver(rid), "reason": "Patient moved away (Stage 6)"}, quiet=True)
    print(f"[B5] cancel after delivery -> {s} status={o.get('status')} reason={o.get('cancel_reason')!r}")
    s, x = call("B5-spec-accept-after-cancel", "dr.ortho", "POST", "spec", f"/specialist/cases/{c['id']}/decision", {"decision": "accept"}, quiet=True)
    time.sleep(15)
    _, full = call("B5-case", "dr.ortho", "GET", "spec", f"/specialist/cases/{c['id']}", quiet=True)
    print(f"[B5] specialist case after clinic cancellation: status={full['case']['status']} decision={full['case']['decision']}")
    print("     specialist outbox:", [(o['event_type'], o['status'], o['attempts'], (o['last_error'] or '')[:90]) for o in full["outbox"]])
    print(f"     central status={ref(rid)['status']}")
    # full decline path with a reason, on a fresh referral
    s, r = call("B6-create", "staff.a", "POST", "central", "/referrals", {"patient_local_id": "MR-215", "reason": "Stage 6: decline path (synthetic)"}, quiet=True)
    did = r["id"]; prepare(did)
    call("B6-approve", "dr.malik", "POST", "central", f"/referrals/{did}/approve", {"expected_version": ver(did)}, quiet=True)
    call("B6-submit", "staff.a", "POST", "central", f"/referrals/{did}/submit", {"expected_version": ver(did)}, quiet=True)
    wait_status(did, {"submitted"})
    cd = case_for(r["reference"])
    call("B6-ack", "dr.ortho", "POST", "spec", f"/specialist/cases/{cd['id']}/acknowledge", quiet=True)
    call("B6-decline", "dr.ortho", "POST", "spec", f"/specialist/cases/{cd['id']}/decision", {"decision": "decline", "reason": "Outside our service scope (Stage 6)"}, quiet=True)
    r = wait_status(did, {"declined"})
    print(f"[B6] declined path: central status={r['status']} decline_reason={r.get('decline_reason')!r}")
    call("B6-edit-after-decline", "dr.malik", "PATCH", "central", f"/referrals/{did}", {"expected_version": ver(did), "reason": "x"})
