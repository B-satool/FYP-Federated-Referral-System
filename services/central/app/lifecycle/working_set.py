"""Referral lifecycle and purge (spec v4 sections 7, 11; approval A9).

* **Open, not yet accepted:** no time limit. The encrypted records stay while the doctors work on the referral.
* **Accepted:** a close reminder to the receiving department's doctors ACCEPTED_HOLD_DAYS after acceptance, repeated
  every REMINDER_INTERVAL_DAYS, and escalated to the receiving staff after ESCALATE_AFTER_REMINDERS reminders. The
  specialist extends (ACCEPTED_HOLD_DAYS more, with a reason, at most MAX_REFERRAL_DAYS after acceptance) or closes.
  Never a silent auto-close: at the maximum lifetime, once escalated, everyone is told and the purge is scheduled.
* **Closed by the specialist:** purged CLOSE_GRACE_DAYS later (the patient is told to keep their copy).
* **Declined, denied or cancelled:** purged DECLINE_GRACE_DAYS later.
* **Test requests:** the earlier rules (WORKING_SET_GRACE_HOURS after the results are back).

Purge is crypto-shredding: the ciphertext, its titles and every wrapped data key for the referral are deleted, and a
purge receipt keeps the signed manifest's hash and the counts (O6). The signed manifests and the audit trail stay
(no plaintext). The receiving hospital is told to drop its notice. Nothing is removed while a delivery that carries
the referral is unconfirmed. A purged referral is shown as "purged", never as "no records".
"""
from __future__ import annotations

from datetime import datetime, timedelta

from refcommon.db import utcnow
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..config import institution_name, settings
from ..models import (Clarification, DiagnosticRequest, Document, EncryptedBatch, EncryptedItem, EvidenceItem, Outbox,
                      PackageManifest, PurgeReceipt, Referral, WrappedKey)
from ..security import audit

TEST_ENDING = {"response_returned", "closed", "cancelled"}
REMOVED = "[removed: purged]"
# Outbox kinds that carry the referral and must be confirmed delivered before anything is removed
MUST_DELIVER = ("deliver_package", "deliver_order")
SYSTEM = ("system", "referral lifecycle", "central-platform")


def _grace(now: datetime) -> datetime:
    return now + timedelta(hours=settings.working_set_grace_hours)


def _sooner(current: datetime | None, candidate: datetime) -> datetime:
    return candidate if current is None else min(current, candidate)


def max_until(referral: Referral) -> datetime | None:
    """The latest the referral may stay open (spec v4 O10)."""
    return referral.accepted_at + timedelta(days=settings.max_referral_days) if referral.accepted_at else None


def start(referral: Referral, now: datetime | None = None) -> None:
    """Something was added to a test request after its results were purged: a new working set."""
    if referral.working_set_purged_at is not None and referral.kind == "test":
        referral.working_set_purged_at = None


def on_status(referral: Referral, status: str, now: datetime | None = None) -> None:
    now = now or utcnow()
    if referral.kind == "test":
        if status in TEST_ENDING:
            referral.working_set_expires_at = _sooner(referral.working_set_expires_at, _grace(now))
        return
    if status == "accepted" and referral.receiver_completed_at is None:
        referral.close_reminder_due_at = now + timedelta(days=settings.accepted_hold_days)
        referral.reminders_sent, referral.last_reminder_at, referral.escalated_at = 0, None, None
    elif status in ("declined", "cancelled"):
        referral.close_reminder_due_at = None
        referral.working_set_expires_at = _sooner(referral.working_set_expires_at,
                                                  now + timedelta(days=settings.decline_grace_days))


def close(referral: Referral, when: datetime) -> datetime:
    """The specialist closed the referral: purged after the grace period."""
    referral.close_reminder_due_at = None
    referral.working_set_expires_at = _sooner(referral.working_set_expires_at,
                                              when + timedelta(days=settings.close_grace_days))
    return referral.working_set_expires_at


complete = close  # the receiving side's "completed" event is the specialist closing it


def extend(referral: Referral, when: datetime, until: datetime | None = None) -> datetime | None:
    """The specialist keeps the referral open longer: the next reminder moves to `until` (default ACCEPTED_HOLD_DAYS
    from the later of now and the current due date), never past the maximum lifetime."""
    if referral.receiver_completed_at is not None or referral.working_set_purged_at is not None or not referral.accepted_at:
        return None
    base = max(when, referral.close_reminder_due_at or when)
    target = until or base + timedelta(days=settings.accepted_hold_days)
    referral.close_reminder_due_at = min(max(target, referral.close_reminder_due_at or target), max_until(referral))
    referral.reminders_sent, referral.last_reminder_at, referral.escalated_at = 0, None, None
    return referral.close_reminder_due_at


# --------------------------------------------------------------------------- reminders (spec v4 7, O4)
def reminders_due(db: Session, now: datetime | None = None) -> dict:
    """Send due close reminders, escalate, and at the maximum lifetime (after escalation) schedule the purge with
    everyone told. Run by the worker's schedule."""
    from ..notifications import notify, notify_doctor, notify_staff
    from ..referrals.state import event

    now = now or utcnow()
    counts = {"reminded": 0, "escalated": 0, "ended": 0}
    rows = db.scalars(select(Referral).where(Referral.kind == "referral", Referral.close_reminder_due_at.is_not(None),
                                             Referral.close_reminder_due_at <= now,
                                             Referral.receiver_completed_at.is_(None),
                                             Referral.working_set_purged_at.is_(None))).all()
    for r in rows:
        dest, dept = r.destination_institution, r.destination_department
        limit = max_until(r)
        if limit and now >= limit and r.escalated_at and now >= r.escalated_at + timedelta(days=settings.reminder_interval_days):
            r.close_reminder_due_at = None
            r.working_set_expires_at = _sooner(r.working_set_expires_at, now + timedelta(days=settings.close_grace_days))
            when = r.working_set_expires_at.strftime("%d %b %Y")
            text = (f"{r.reference} reached the {settings.max_referral_days}-day limit without being closed. Its encrypted "
                    f"records are purged on {when}; the patient keeps their own copy.")
            notify(db, "referral_limit_reached", f"{r.reference}: maximum time reached", institution=dest, role="clinician",
                   referral=r, body=text, link="/incoming")
            notify(db, "referral_limit_reached", f"{r.reference}: maximum time reached", institution=dest,
                   role="clinic_staff", referral=r, body=text, link="/incoming")
            notify_doctor(db, r, "referral_limit_reached", f"{r.reference}: maximum time reached", text)
            notify_staff(db, r, "referral_limit_reached", f"{r.reference}: maximum time reached", text)
            event(db, r, "max_lifetime_reached", "system", "central-platform", {"purge_at": r.working_set_expires_at.isoformat()})
            audit(db, None, "lifecycle.max_lifetime", "referral", r.reference, "success", r.id,
                  {"purge_at": r.working_set_expires_at.isoformat()}, actor=SYSTEM)
            counts["ended"] += 1
            continue
        if r.last_reminder_at and now < r.last_reminder_at + timedelta(days=settings.reminder_interval_days):
            continue
        r.reminders_sent += 1
        r.last_reminder_at = now
        notify(db, "close_reminder", f"{r.reference}: close or extend",
               institution=dest, role="clinician", referral=r, link="/incoming",
               body=(f"Accepted {r.accepted_at:%d %b %Y}. If you have finished with it, close the referral; if you still need "
                     f"the records, extend it with a reason (at most {settings.max_referral_days} days after acceptance)."))
        event(db, r, "close_reminder", "system", "central-platform", {"reminder": r.reminders_sent, "department": dept})
        audit(db, None, "lifecycle.close_reminder", "referral", r.reference, "success", r.id,
              {"reminder": r.reminders_sent}, actor=SYSTEM)
        counts["reminded"] += 1
        if r.reminders_sent >= settings.escalate_after_reminders and r.escalated_at is None:
            r.escalated_at = now
            notify(db, "close_reminder_escalated", f"{r.reference}: not closed after {r.reminders_sent} reminders",
                   institution=dest, role="clinic_staff", referral=r, link="/incoming",
                   body=f"Ask the {institution_name(dest)} doctor it was assigned to to close or extend it.")
            event(db, r, "close_reminder_escalated", "system", "central-platform", {"reminders": r.reminders_sent})
            audit(db, None, "lifecycle.escalate", "referral", r.reference, "success", r.id,
                  {"reminders": r.reminders_sent}, actor=SYSTEM)
            counts["escalated"] += 1
    db.commit()
    return counts


# --------------------------------------------------------------------------- purge (spec v4 11.2)
def blockers(db: Session, referral: Referral) -> list[str]:
    """Why the content cannot be removed yet (empty list = it can)."""
    boxes = db.scalars(select(Outbox).where(Outbox.referral_id == referral.id, Outbox.kind.in_(MUST_DELIVER))).all()
    waiting = sorted({b.kind for b in boxes if b.status not in ("sent", "failed")})
    return ["not yet confirmed delivered: " + ", ".join(waiting)] if waiting else []


def purge_due(db: Session, now: datetime | None = None) -> int:
    now = now or utcnow()
    due = db.scalars(select(Referral).where(Referral.working_set_expires_at.is_not(None),
                                            Referral.working_set_expires_at <= now,
                                            Referral.working_set_purged_at.is_(None))).all()
    done = 0
    for r in due:
        reasons = blockers(db, r)
        if reasons:
            audit(db, None, "retention.purge", "referral", r.reference, "deferred", r.id, {"reasons": reasons}, actor=SYSTEM)
            continue
        purge(db, r, now)
        done += 1
    db.commit()
    return done


def _trigger(r: Referral) -> str:
    if r.kind == "test":
        return "test_finished"
    if r.receiver_completed_at:
        return "closed_by_specialist"
    if r.status in ("declined", "cancelled"):
        return r.status
    return "max_lifetime" if r.accepted_at else "closed"


def purge(db: Session, r: Referral, now: datetime | None = None) -> dict:
    """Crypto-shred one referral: delete its ciphertext, titles and wrapped data keys; keep a receipt. Idempotent:
    a second run finds nothing to delete and keeps the first receipt."""
    from ..documents.storage import storage

    now = now or utcnow()
    latest = db.scalars(select(PackageManifest).where(PackageManifest.referral_id == r.id)
                        .order_by(PackageManifest.version.desc())).first()
    items = db.scalar(select(func.count()).select_from(EncryptedItem).where(EncryptedItem.referral_id == r.id)) or 0
    wraps = db.scalar(select(func.count()).select_from(WrappedKey).where(WrappedKey.referral_id == r.id)) or 0
    db.execute(delete(WrappedKey).where(WrappedKey.referral_id == r.id))
    db.execute(delete(EncryptedItem).where(EncryptedItem.referral_id == r.id))
    db.execute(delete(EncryptedBatch).where(EncryptedBatch.referral_id == r.id))
    counts = {"items": items, "wrapped_keys": wraps, "legacy_records": 0, "results": 0}
    # anything left from before spec v4 (plaintext working sets) goes too
    for ev in db.scalars(select(EvidenceItem).where(EvidenceItem.referral_id == r.id)):
        ev.display, ev.current, ev.fhir, ev.original, ev.source_text = REMOVED, {}, None, {}, None
        ev.superseded_by = ev.superseded_by or ev.id
        counts["legacy_records"] += 1
    for doc in db.scalars(select(Document).where(Document.referral_id == r.id, Document.deleted_at.is_(None))):
        storage.delete(doc.storage_key)
        doc.deleted_at = now
    for dx in db.scalars(select(DiagnosticRequest).where(DiagnosticRequest.referral_id == r.id)):
        for a in dx.attachments or []:
            storage.delete(a["storage_key"])
        dx.report = {"purged": True} if dx.report else None
        dx.attachments, dx.clinical_question = [], REMOVED
        counts["results"] += 1
    for c in db.scalars(select(Clarification).where(Clarification.referral_id == r.id)):
        c.question, c.answer = REMOVED, (REMOVED if c.answer else None)
    for box in db.scalars(select(Outbox).where(Outbox.referral_id == r.id, Outbox.kind.in_(MUST_DELIVER))):
        box.payload = {k: box.payload.get(k) for k in ("delivery_key", "referral_id", "package_version", "manifest_sha256",
                                                       "order_key") if isinstance(box.payload, dict) and k in box.payload}
    r.meds_checked_note = r.patient_informed_note = None
    r.close_reminder_due_at = None
    r.working_set_purged_at = now
    receipt = db.scalars(select(PurgeReceipt).where(PurgeReceipt.referral_id == r.id)).first()
    if receipt is None:
        receipt = PurgeReceipt(referral_id=r.id, purged_at=now, items_count=items, wrapped_keys_count=wraps,
                               manifest_hash=latest.manifest_sha256 if latest else None, trigger=_trigger(r),
                               detail=counts, note="Ciphertext, titles and wrapped data keys deleted; the signed "
                                                   "manifest and the audit trail remain (no plaintext).")
        db.add(receipt)
    if r.kind == "referral" and r.destination_institution and r.submitted_package_version:
        key = f"expire:{r.reference}"
        if not db.scalars(select(Outbox).where(Outbox.message_key == key)).first():
            db.add(Outbox(referral_id=r.id, kind="expire_shared", target_institution=r.destination_institution,
                          message_key=key, payload={"expire_key": key, "referral_id": r.reference,
                                                    "expired_at": now.isoformat()}))
            counts["receiver_notified"] = 1
    audit(db, None, "retention.purge", "referral", r.reference, "success", r.id,
          {**counts, "manifest_sha256": receipt.manifest_hash, "trigger": receipt.trigger}, actor=SYSTEM)
    return counts
