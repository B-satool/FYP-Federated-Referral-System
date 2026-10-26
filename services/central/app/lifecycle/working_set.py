"""Temporary working set: retrieved records are held only as long as the referral needs them.

Lifetime of a referral's clinical content held centrally (evidence, papers and their OCR text,
medicine list, flags, the letter, package content, results, the response):
* starts at the first retrieval (or the first paper or medicine added) and runs at most
  WORKING_SET_MAX_DAYS from then;
* ends WORKING_SET_GRACE_HOURS after the referral is answered (response or all results back) or ends
  (closed, declined, cancelled), if that is sooner.

At expiry the content is removed; identifiers, status, audit, the package manifest and its
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

ENDING = {"response_returned", "closed", "declined", "cancelled"}
REMOVED = "[removed: working set ended]"
# Outbox kinds that carry content and must be confirmed delivered before anything is removed
MUST_DELIVER = ("deliver_package", "sender_copy", "deliver_order")


def start(referral: Referral, now: datetime | None = None) -> None:
    """The working set exists once anything is retrieved or added."""
    now = now or utcnow()
    if referral.working_set_expires_at is None or referral.working_set_purged_at is not None:
        referral.working_set_expires_at = now + timedelta(days=settings.working_set_max_days)
        referral.working_set_purged_at = None


def on_status(referral: Referral, status: str, now: datetime | None = None) -> None:
    """Once answered or ended, the content is kept only for the grace period."""
    if status not in ENDING or referral.working_set_expires_at is None:
        return
    now = now or utcnow()
    referral.working_set_expires_at = min(referral.working_set_expires_at,
                                          now + timedelta(hours=settings.working_set_grace_hours))


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
    audit(db, None, "retention.purge_working_set", "referral", r.reference, "success", r.id, counts,
          actor=("system", "working-set purge", "central-platform"))
    return counts
