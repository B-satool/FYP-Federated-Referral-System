import sys; sys.path.insert(0, "/tmp/s7"); sys.path.insert(0, "/srv")
from h import call
from app.db import SessionLocal
from app.models import AuditEvent
def n():
    with SessionLocal() as db: return db.query(AuditEvent).count()
_, ev = call("A-ev", "dr.malik", "GET", "central", "/referrals/5/evidence", quiet=True)
reads = [("referral list/search", "GET", "/referrals"), ("referral detail", "GET", "/referrals/5"),
         ("evidence list", "GET", "/referrals/5/evidence"), ("evidence detail", "GET", f"/evidence/{ev[0]['id']}"),
         ("documents list", "GET", "/referrals/5/documents"), ("document detail + OCR text", "GET", "/documents/17"),
         ("document original file", "GET", "/documents/17/file"), ("document page image", "GET", "/documents/17/pages/1"),
         ("brief", "GET", "/referrals/5/brief"), ("approved package content", "GET", "/referrals/7/packages/1"),
         ("medications + flags", "GET", "/referrals/5/medications"), ("review items", "GET", "/referrals/5/review-items"),
         ("specialist responses", "GET", "/referrals/7/responses"), ("work queue", "GET", "/work-queue"),
         ("referral audit trail", "GET", "/referrals/5/audit"), ("patient links", "GET", "/patient-links?institution=clinic-a&local_id=MR-102")]
for name, m, path in reads:
    before = n(); p, _, q = path.partition("?")
    params = dict(kv.split("=") for kv in q.split("&")) if q else None
    s, _ = call("A-read", "dr.malik", m, "central", p, params=params, quiet=True)
    print(f"[A1] {name:30} HTTP {s} -> audit rows added: {n() - before}")
