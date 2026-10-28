import sys, time; sys.path.insert(0, "/tmp/s7")
from h6 import call, ref, ver, wait_status, case_for, prepare
def up(rid):
    s, o = call("RT-upload", "staff.a", "POST", "central", f"/referrals/{rid}/documents", files={"file": ("scan.jpg", open("/tmp/s7/scan.jpg", "rb"), "image/jpeg")}, data={"doc_type": "referral_note"}, quiet=True)
    d = o["document"]["id"]
    for _ in range(60):
        _, x = call("RT-doc", "staff.a", "GET", "central", f"/documents/{d}", quiet=True)
        if x["document"]["status"] not in ("queued", "processing"): break
        time.sleep(2)
    return d, x
# A: closed referral with a document
s, r = call("RT-A", "staff.a", "POST", "central", "/referrals", {"patient_local_id": "MR-418", "reason": "Stage 7 retention test: closed (synthetic)"}, quiet=True)
a = r["id"]; da, xa = up(a); print(f"[RT] A {r['reference']} document {da}: {xa['document']['status']}, fields={len(xa['fields'])}")
prepare(a)
for f in xa["fields"]:
    call("RT-exclude", "dr.malik", "POST", "central", f"/evidence/{f['id']}/exclude", {"note": "not needed"}, quiet=True)
prepare(a)
s, ap = call("RT-approve", "dr.malik", "POST", "central", f"/referrals/{a}/approve", {"expected_version": ver(a)}, quiet=True); print("     approve", s, str(ap)[:150] if s != 200 else "")
call("RT-submit", "staff.a", "POST", "central", f"/referrals/{a}/submit", {"expected_version": ver(a)}, quiet=True)
wait_status(a, {"submitted"}); c = case_for(r["reference"])
call("RT-ack", "dr.ortho", "POST", "spec", f"/specialist/cases/{c['id']}/acknowledge", quiet=True)
call("RT-accept", "dr.ortho", "POST", "spec", f"/specialist/cases/{c['id']}/decision", {"decision": "accept"}, quiet=True)
_, d = call("RT-draft", "dr.ortho", "PUT", "spec", f"/specialist/cases/{c['id']}/response", {"findings": "Stage 7 retention test"}, quiet=True)
call("RT-approve-resp", "dr.ortho", "POST", "spec", f"/specialist/cases/{c['id']}/response/approve", {"expected_row_version": d["row_version"]}, quiet=True)
call("RT-return", "dr.ortho", "POST", "spec", f"/specialist/cases/{c['id']}/response/return", quiet=True)
wait_status(a, {"response_returned"})
_, rs = call("RT-resps", "dr.malik", "GET", "central", f"/referrals/{a}/responses", quiet=True)
call("RT-review", "dr.malik", "POST", "central", f"/responses/{rs[0]['id']}/review", {"note": "ok"}, quiet=True)
s, cl = call("RT-close", "dr.malik", "POST", "central", f"/referrals/{a}/close", {"expected_version": ver(a)}, quiet=True)
print(f"[RT] A closed -> {s} {cl.get('status')}")
# B: cancelled referral with a document
s, r = call("RT-B", "staff.a", "POST", "central", "/referrals", {"patient_local_id": "MR-215", "reason": "Stage 7 retention test: cancelled (synthetic)"}, quiet=True)
b = r["id"]; db_, xb = up(b)
call("RT-cancel", "staff.a", "POST", "central", f"/referrals/{b}/cancel", {"expected_version": ver(b), "reason": "Stage 7 retention test"}, quiet=True)
print(f"[RT] B {r['reference']} document {db_} cancelled -> {ref(b)['status']}")
open("/tmp/s7/ret", "w").write(f"{a} {da} {b} {db_}")
