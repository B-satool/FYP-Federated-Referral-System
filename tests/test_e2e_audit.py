"""Spec v4 T-AUDIT-1: the audit trail is append-only and hash-chained, and holds no content.

* The database refuses to delete an audit event or change a sealed one.
* The chain verifies; an event altered behind the trigger's back (as someone with database owner access might) is
  found, and the chain verifies again once it is put back.
* No audit entry holds the canary or a private key (each feature's own test also checks its entries).
"""
from __future__ import annotations

from e2e_client import CANARY
from flows import central_python
from helpers import central, ok

PRELUDE = "from sqlalchemy import text\nfrom app.db import SessionLocal\n"


def sql(statement: str, *, bypass_trigger: bool = False) -> str:
    """Run one SQL statement in the central database; returns the first value, or 'refused <error>'."""
    trigger = "ALTER TABLE audit_events {} TRIGGER audit_events_append_only"
    body = [f"db.execute(text({trigger.format('DISABLE')!r}))"] if bypass_trigger else []
    body += [f"res = db.execute(text({statement!r}))", "out = res.scalar() if res.returns_rows else 'done'"]
    body += [f"db.execute(text({trigger.format('ENABLE')!r}))"] if bypass_trigger else []
    code = (PRELUDE + "with SessionLocal() as db:\n    try:\n" + "".join(f"        {line}\n" for line in body)
            + "        db.commit()\n    except Exception as exc:\n        out = 'refused ' + type(exc).__name__\n    print(out)")
    return central_python(code).splitlines()[-1]


def seal_now() -> None:
    central_python(PRELUDE + "import app.lifecycle.audit_chain as chain\nchain.SETTLE_SECONDS = 0\n"
                   "with SessionLocal() as db:\n    print(chain.seal(db))")


def test_chain_verifies_and_the_table_is_append_only():
    ok(central("dr.ali").get("/me"))
    seal_now()
    chain = ok(central("admin.ali").get("/admin/audit/chain"))
    assert chain["ok"] and chain["sealed"] > 0, chain
    assert central("staff.ali").get("/admin/audit/chain").status_code == 403
    assert sql("DELETE FROM audit_events WHERE id = (SELECT min(id) FROM audit_events)").startswith("refused")
    assert sql("UPDATE audit_events SET outcome = 'success' WHERE id = "
               "(SELECT min(id) FROM audit_events WHERE chain_hash IS NOT NULL)").startswith("refused")


def test_tampering_behind_the_trigger_is_detected():
    seal_now()
    target = sql("SELECT max(id) FROM audit_events WHERE chain_hash IS NOT NULL")
    original = sql(f"SELECT outcome FROM audit_events WHERE id = {target}")
    sql(f"UPDATE audit_events SET outcome = 'tampered' WHERE id = {target}", bypass_trigger=True)
    try:
        chain = ok(central("admin.ali").get("/admin/audit/chain"))
        assert not chain["ok"] and chain["first_break"]["event_id"] == int(target), chain
    finally:
        sql(f"UPDATE audit_events SET outcome = '{original}' WHERE id = {target}", bypass_trigger=True)
    assert ok(central("admin.ali").get("/admin/audit/chain"))["ok"]


def test_audit_holds_no_content():
    hits = sql(f"SELECT count(*) FROM audit_events WHERE detail::text LIKE '%{CANARY}%' OR target_id LIKE '%{CANARY}%' "
               "OR detail::text LIKE '%PRIVATE KEY%'")
    assert hits == "0"
