import sys, time; sys.path.insert(0, "/tmp/s7")
from h import call
phase = sys.argv[1]
if phase == "down":
    t0 = time.monotonic()
    s, o = call("R1-upload-redis-down", "staff.a", "POST", "central", "/referrals/5/documents", files={"file": ("scan.jpg", open("/tmp/s7/scan.jpg", "rb"), "image/jpeg")}, data={"doc_type": "other"}, quiet=True)
    print(f"[R1] upload with Redis down -> HTTP {s} after {time.monotonic()-t0:.1f}s body={str(o)[:120]}")
    s, g = call("R1-generate-redis-down", "dr.malik", "POST", "central", "/referrals/5/brief/generate", quiet=True)
    print(f"[R1] brief generate with Redis down -> HTTP {s} body={str(g)[:120]}")
    s, x = call("R1-retrieve-redis-down", "dr.malik", "POST", "central", "/referrals/5/retrieve", quiet=True)
    print(f"[R1] retrieval (synchronous) with Redis down -> HTTP {s}")
else:
    _, docs = call("R2-docs", "staff.a", "GET", "central", "/referrals/5/documents", quiet=True)
    d = docs[-1]
    print(f"[R2] {phase}: newest document #{d['id']} {d['original_filename']} status={d['status']}")
    _, jobs = call("R2-jobs", "dr.malik", "GET", "central", "/referrals/5/jobs", quiet=True)
    print(f"[R2] {phase}: newest jobs:", [(j['kind'], j['status'], j['created_at'][11:19]) for j in jobs[:3]])
