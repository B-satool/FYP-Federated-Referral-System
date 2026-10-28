import sys, time; sys.path.insert(0, "/tmp/s7")
from h import call
t0 = time.monotonic()
s, x = call("T1-retrieve-lab-hung", "dr.malik", "POST", "central", "/referrals/5/retrieve", quiet=True)
el = time.monotonic() - t0
print(f"[T1] retrieve with Lab B hung: HTTP {s} after {el:.1f}s")
for y in x.get("results", []):
    print(f"     {y['source_institution']}: {y['status']} attempts={y['attempts']} duration_ms={y['duration_ms']} | {y['message']}")
t0 = time.monotonic(); s, _ = call("T1-other-screen", "dr.malik", "GET", "central", "/referrals/5/evidence", quiet=True)
print(f"[T1] evidence screen while Lab B hung: HTTP {s} in {(time.monotonic()-t0)*1000:.0f} ms")
