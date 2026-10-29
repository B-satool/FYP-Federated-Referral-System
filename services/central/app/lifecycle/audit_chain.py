"""The audit trail's hash chain (spec v4 11.5, T-AUDIT-1).

Audit events are written by every request as before. Once a minute the worker seals the events written more than
SETTLE_SECONDS ago, in id order: each sealed event gets the next sequence number, the previous event's hash, and its
own hash over the previous hash and its canonical fields. A database trigger keeps the table append-only: an event
cannot be deleted, and once sealed cannot change at all. Verification walks the chain by sequence number and
recomputes every hash, so a removed, inserted or altered event is found.

Events are sealed a short while after they are written (so a transaction still open when the job runs is sealed on
the next run, not skipped); until then they are not yet protected by the chain.
"""
from __future__ import annotations

import hashlib
from datetime import timedelta

from refcommon import e2e
from refcommon.db import utcnow
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from ..models import AuditEvent

GENESIS = "0" * 64
SETTLE_SECONDS = 30
LOCK_ID = 7_311_011  # one sealing job at a time (PostgreSQL advisory lock)


def event_hash(prev: str, e: AuditEvent) -> str:
    fields = {"id": e.id, "actor_id": e.actor_id, "actor_name": e.actor_name, "institution_id": e.institution_id,
              "action": e.action, "target_type": e.target_type, "target_id": e.target_id, "referral_id": e.referral_id,
              "outcome": e.outcome, "detail": e.detail or {}, "created_at": e.created_at.isoformat()}
    return hashlib.sha256(prev.encode() + e2e.canonical(fields)).hexdigest()


def seal(db: Session, limit: int = 5000) -> int:
    if db.bind.dialect.name == "postgresql" and not db.scalar(text(f"SELECT pg_try_advisory_xact_lock({LOCK_ID})")):
        return 0
    last = db.scalars(select(AuditEvent).where(AuditEvent.chain_seq.is_not(None))
                      .order_by(AuditEvent.chain_seq.desc()).limit(1)).first()
    prev, seq = (last.chain_hash, last.chain_seq) if last else (GENESIS, 0)
    rows = db.scalars(select(AuditEvent).where(AuditEvent.chain_hash.is_(None),
                                               AuditEvent.created_at < utcnow() - timedelta(seconds=SETTLE_SECONDS))
                      .order_by(AuditEvent.id).limit(limit)).all()
    for e in rows:
        seq += 1
        e.chain_seq, e.prev_hash = seq, prev
        e.chain_hash = prev = event_hash(prev, e)
    db.commit()
    return len(rows)


def verify(db: Session) -> dict:
    """Recompute the whole chain. Returns how many events are sealed and unsealed, and the first break if any."""
    prev, seq, checked = GENESIS, 0, 0
    first_break = None
    for e in db.scalars(select(AuditEvent).where(AuditEvent.chain_seq.is_not(None)).order_by(AuditEvent.chain_seq)
                        .execution_options(yield_per=2000)):
        seq += 1
        if e.chain_seq != seq or e.prev_hash != prev or e.chain_hash != event_hash(prev, e):
            first_break = {"chain_seq": e.chain_seq, "expected_seq": seq, "event_id": e.id}
            break
        prev = e.chain_hash
        checked += 1
    unsealed = db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.chain_hash.is_(None))) or 0
    return {"ok": first_break is None, "sealed": checked, "unsealed": unsealed, "head": prev if not first_break else None,
            "first_break": first_break}
