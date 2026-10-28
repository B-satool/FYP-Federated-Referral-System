"""Temporary working set: retrieved records are held only as long as the referral needs them.

Lifetime of a referral's clinical content (evidence, papers and their OCR text, medicine list, flags,
the letter, package content, results, the response); see docs/decisions/2026-10-28-referral-expiry.md:
* referral, until the receiving doctor accepts: no time limit;
* accepted: a safety limit of ACCEPTED_HOLD_DAYS, which the receiving doctor can extend (each time to
  ACCEPTED_HOLD_DAYS from then);
* marked complete by the receiving doctor: removed WORKING_SET_GRACE_HOURS later;
* declined: removed straight away; cancelled: removed WORKING_SET_GRACE_HOURS later;
* test request: removed WORKING_SET_GRACE_HOURS after all results are back (or it is closed or cancelled).

At expiry the content is removed, here and at the receiving institution (its copy of the shared
records; it keeps what it wrote itself). Identifiers, status, audit, the package manifest and its
fingerprint stay. Content is never removed while something sent has not been confirmed delivered,
or before the sending clinic has confirmed its own copy of each sent package (its lasting record,
together with the receiving institution's). A removed list is shown as "no longer held",
never as "none".
"""
from __future__ import annotations

from datetime import datetime, timedelta

from refcommon.db import utcnow
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import (Brief, Clarification, ConsultationResponse, DiagnosticRequest, Document, EvidenceItem,
                      EvidenceRevision, ExtractionRun, FlagReview, InboundMessage, MedicationEntry, MedicationFlag,
                      Outbox, Referral, ReferralPackage, SuggestionReview)
from ..security import audit
from .manifest import PURGED_MARKER, is_purged, purged_envelope

TEST_ENDING = {"response_returned", "closed", "cancelled"}
REMOVED = "[removed: working set ended]"
# Outbox kinds that carry content and must be confirmed delivered before anything is removed
MUST_DELIVER = ("deliver_package", "sender_copy", "deliver_order")


def _grace(now: datetime) -> datetime:
    return now + timedelta(hours=settings.working_set_grace_hours)


def _sooner(current: datetime | None, candidate: datetime) -> datetime:
    return candidate if current is None else min(current, candidate)


def start(referral: Referral, now: datetime | None = None) -> None:
    """Something was retrieved or added. After a removal this begins a new working set (fresh copies);
    the expiry is not set here: it follows the referral's status."""
    if referral.working_set_purged_at is not None:
        referral.working_set_purged_at = None
        if referral.receiver_completed_at is None and referral.status not in ("declined", "cancelled", "closed"):
            referral.working_set_expires_at = None
            if referral.kind == "referral" and referral.accepted_at is not None:
                referral.working_set_expires_at = (now or utcnow()) + timedelta(days=settings.accepted_hold_days)


def on_status(referral: Referral, status: str, now: datetime | None = None) -> None:
    now = now or utcnow()
    if referral.kind == "test":
        if status in TEST_ENDING:
            referral.working_set_expires_at = _sooner(referral.working_set_expires_at, _grace(now))
        return
    if status == "accepted" and referral.receiver_completed_at is None:
        referral.working_set_expires_at = now + timedelta(days=settings.accepted_hold_days)
    elif status == "declined":
        referral.working_set_expires_at = now  # removed straight away
    elif status == "cancelled":
        referral.working_set_expires_at = _sooner(referral.working_set_expires_at, _grace(now))


def complete(referral: Referral, when: datetime) -> None:
    """The receiving doctor marked the referral complete: kept for the grace period, then removed."""
    referral.working_set_expires_at = _grace(when)


def extend(referral: Referral, when: datetime) -> datetime | None:
    """The receiving doctor needs the records for longer: the safety limit becomes ACCEPTED_HOLD_DAYS from now."""
    if referral.receiver_completed_at is not None or referral.working_set_purged_at is not None:
        return None
    until = when + timedelta(days=settings.accepted_hold_days)
    referral.working_set_expires_at = max(referral.working_set_expires_at or until, until)
    return referral.working_set_expires_at


def blockers(db: Session, referral: Referral) -> list[str]:
    """Why the content cannot be removed yet (empty list = it can)."""
    out = []
    boxes = db.scalars(select(Outbox).where(Outbox.referral_id == referral.id, Outbox.kind.in_(MUST_DELIVER))).all()
    waiting = sorted({b.kind for b in boxes if b.status != "sent"})
    if waiting:
        out.append("not yet confirmed delivered: " + ", ".join(waiting))
    packages = db.scalars(select(ReferralPackage).where(ReferralPackage.referral_id == referral.id)).all()
    copies = {b.message_key for b in boxes if b.kind == "sender_copy" and b.status == "sent"}
    missing = [p.version for p in packages if f"copy:{p.delivery_key}" not in copies]
    if missing:
        out.append(f"the sending clinic has not confirmed its copy of version(s) {missing}")
    if any(p.manifest is None for p in packages):
        out.append("a sent version has no manifest")
    return out


def purge_due(db: Session, now: datetime | None = None) -> int:
    now = now or utcnow()
    due = db.scalars(select(Referral).where(Referral.working_set_expires_at.is_not(None),
                                            Referral.working_set_expires_at <= now,
                                            Referral.working_set_purged_at.is_(None))).all()
    done = 0
    for r in due:
        reasons = blockers(db, r)
        if reasons:
            audit(db, None, "retention.purge_working_set", "referral", r.reference, "deferred", r.id, {"reasons": reasons},
                  actor=("system", "working-set purge", "central-platform"))
            continue
        purge(db, r, now)
        done += 1
    db.commit()
    return done


def purge(db: Session, r: Referral, now: datetime | None = None) -> dict:
    """Remove the clinical content of one referral's working set (identifiers, status, audit, manifest and hash stay)."""
    from ..documents.storage import storage

    now = now or utcnow()
    counts = {"evidence": 0, "documents": 0, "packages": 0, "medicines": 0, "flags": 0, "results": 0}
    for ev in db.scalars(select(EvidenceItem).where(EvidenceItem.referral_id == r.id)):
        # the record reference (not a clinical value) moves out of the unique key, so a later
        # retrieval (an amendment after purge) creates fresh rows instead of reusing removed ones
        ev.display, ev.current, ev.fhir = REMOVED, {}, None
        ev.original = {"purged_record_version": ev.source_record_version} if ev.source_record_version else {}
        ev.source_record_version = None
        ev.source_text, ev.region, ev.confidence, ev.ai_reason = None, None, None, None
        ev.selected = False
        ev.superseded_by = ev.superseded_by or ev.id  # out of every list
        for rev in db.scalars(select(EvidenceRevision).where(EvidenceRevision.evidence_id == ev.id)):
            rev.prior_value, rev.new_value, rev.note = None, None, ""
        counts["evidence"] += 1
    for doc in db.scalars(select(Document).where(Document.referral_id == r.id, Document.deleted_at.is_(None))):
        for run in db.scalars(select(ExtractionRun).where(ExtractionRun.document_id == doc.id)):
            for page in run.pages or []:
                if page.get("image_key"):
                    storage.delete(page["image_key"])
            run.raw_text, run.pages = f"[{PURGED_MARKER}]", []
        storage.delete(doc.storage_key)
        doc.deleted_at = now
        counts["documents"] += 1
    for m in db.scalars(select(MedicationEntry).where(MedicationEntry.referral_id == r.id)):
        m.original_name, m.brand, m.strength, m.dose, m.route, m.frequency = REMOVED, None, None, None, None, None
        m.source_label, m.mapping_note, m.excluded_reason = REMOVED, None, None
        counts["medicines"] += 1
    for f in db.scalars(select(MedicationFlag).where(MedicationFlag.referral_id == r.id)):
        f.title, f.message, f.medication, f.source_label, f.source_quote = REMOVED, REMOVED, None, None, None
        f.ingredients = []
        if f.status == "active":
            f.status = "purged"
        counts["flags"] += 1
    for v in db.scalars(select(FlagReview).where(FlagReview.referral_id == r.id)):
        v.note = ""
    for v in db.scalars(select(SuggestionReview).where(SuggestionReview.referral_id == r.id)):
        v.note = ""
    for b in db.scalars(select(Brief).where(Brief.referral_id == r.id)):
        b.sections, b.limitations = [], []
    for p in db.scalars(select(ReferralPackage).where(ReferralPackage.referral_id == r.id)):
        if not is_purged(p.envelope):
            p.envelope = purged_envelope(p.envelope)
            p.content_purged_at = now
            counts["packages"] += 1
    for box in db.scalars(select(Outbox).where(Outbox.referral_id == r.id)):
        box.payload = purged_envelope(box.payload) if isinstance(box.payload, dict) else {}
    for msg in db.scalars(select(InboundMessage).where(InboundMessage.referral_id == r.id)):
        msg.payload = {"purged": True, "type": (msg.payload or {}).get("type")}
    for resp in db.scalars(select(ConsultationResponse).where(ConsultationResponse.referral_id == r.id)):
        resp.content, resp.fhir_task, resp.review_note = {}, None, None
    for c in db.scalars(select(Clarification).where(Clarification.referral_id == r.id)):
        c.question, c.answer = REMOVED, (REMOVED if c.answer else None)
    for dx in db.scalars(select(DiagnosticRequest).where(DiagnosticRequest.referral_id == r.id)):
        for a in dx.attachments or []:
            storage.delete(a["storage_key"])
        dx.report = {"purged": True} if dx.report else None
        dx.attachments, dx.clinical_question = [], REMOVED
        counts["results"] += 1
    r.reason = REMOVED if r.reason else r.reason
    r.meds_checked_note = r.patient_informed_note = None
    r.working_set_purged_at = now
    if r.kind == "referral" and r.destination_institution and r.submitted_package_version:
        # the receiving institution removes its copy of the shared records too (it keeps what it wrote)
        key = f"expire:{r.reference}:{int(now.timestamp())}"
        db.add(Outbox(referral_id=r.id, kind="expire_shared", target_institution=r.destination_institution,
                      message_key=key, payload={"expire_key": key, "referral_id": r.reference,
                                                "expired_at": now.isoformat()}))
        counts["receiver_notified"] = 1
    audit(db, None, "retention.purge_working_set", "referral", r.reference, "success", r.id, counts,
          actor=("system", "working-set purge", "central-platform"))
    return counts
