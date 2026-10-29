import sys, time; sys.path.insert(0, "/tmp/s7")
from h import call
doc, oldjob = open("/tmp/s7/job").read().split()
s, j = call("J3-reprocess-api", "staff.a", "POST", "central", f"/documents/{doc}/reprocess", quiet=True)
print(f"[J3] API reprocess while stuck -> HTTP {s} new job {j.get('id','')[:8]} status={j.get('status')}")
t0 = time.monotonic()
while time.monotonic() - t0 < 300:
    _, jj = call("J3-job", "staff.a", "GET", "central", f"/jobs/{j['id']}", quiet=True)
    if jj["status"] in ("completed", "failed"): break
    time.sleep(3)
_, d = call("J3-doc", "staff.a", "GET", "central", f"/documents/{doc}", quiet=True)
_, old = call("J3-oldjob", "staff.a", "GET", "central", f"/jobs/{oldjob}", quiet=True)
print(f"[J3] new job {jj['status']} after {time.monotonic()-t0:.0f}s | document {d['document']['status']} pages={d['document'].get('page_count')} fields={len(d['fields'])} | old job still {old['status']}")
