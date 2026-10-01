"""Background worker (Celery + Redis). Redis is only the queue; job state lives in PostgreSQL.

Run: celery -A app.tasks worker -B --loglevel=info
"""
from __future__ import annotations

import logging
from datetime import timedelta

from celery import Celery
from refcommon.db import utcnow
from sqlalchemy import select

from .config import settings
from .db import SessionLocal

log = logging.getLogger("worker")

celery_app = Celery("referral", broker=settings.redis_url, backend=None)
celery_app.conf.update(
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_queue="referral",
    beat_schedule={
        "deliver-outbox": {"task": "deliver_outbox", "schedule": 5.0},
        "retention-sweep": {"task": "retention_sweep", "schedule": 3600.0},
    },
    timezone="UTC",
)


def enqueue(task_name: str, *args) -> None:
    celery_app.send_task(task_name, args=list(args))


def _start(db, job_id: str):
    from .models import Job, Referral, User

    job = db.get(Job, job_id)
    if job is None or job.status not in ("queued", "running"):
        return None, "job not runnable"
    job.status, job.started_at, job.attempts = "running", utcnow(), job.attempts + 1
    db.commit()
    # Re-check permissions at execution time: the requester must still be active and in the referral's institution.
    user = db.get(User, job.created_by_id)
    referral = db.get(Referral, job.referral_id) if job.referral_id else None
    if user is None or user.account_status != "active" or (referral and referral.source_institution != user.institution_id):
        job.status, job.error, job.finished_at = "failed", "Requester is no longer authorized; job not executed", utcnow()
        db.commit()
        return None, job.error
    return job, None


@celery_app.task(name="process_document", bind=True, max_retries=0)
def process_document(self, job_id: str) -> None:
    from .documents.processing import process
    from .models import Document, Referral
    from .workflow import after_change

    with SessionLocal() as db:
        job, err = _start(db, job_id)
        if job is None:
            log.warning("process_document %s skipped: %s", job_id, err)
            return
        doc = db.get(Document, job.document_id)
        try:
            run = process(db, doc, job.id)
            referral = db.get(Referral, doc.referral_id)
            after_change(db, referral, "document_extracted", actor=f"worker (job {job.id})")
            job.status = "completed" if run.status == "completed" else "failed"
            job.result = {"extraction_run_id": run.id, "document_status": doc.status, "notes": run.notes}
            job.error = run.error
        except Exception as exc:  # noqa: BLE001 - make every failure visible on the job
            log.exception("process_document failed")
            db.rollback()
            job = db.merge(job)
            job.status, job.error = "failed", f"Processing failed: {exc}"[:500]
            doc = db.get(Document, job.document_id)
            doc.status, doc.error = "failed", job.error
        job.finished_at = utcnow()
        db.commit()


@celery_app.task(name="generate_brief", bind=True, max_retries=0)
def generate_brief(self, job_id: str) -> None:
    from .generation import brief as brief_mod
    from .generation.provider import ProviderOutputInvalid, ProviderUnavailable, get_provider
    from .models import Brief, Referral
    from .security import audit

    with SessionLocal() as db:
        job, err = _start(db, job_id)
        if job is None:
            log.warning("generate_brief %s skipped: %s", job_id, err)
            return
        referral = db.get(Referral, job.referral_id)
        provider = get_provider()
        try:
            out = brief_mod.generate(db, referral, provider)
            prev = brief_mod.latest_brief(db, referral.id)
            b = Brief(referral_id=referral.id, version=brief_mod.next_version(db, referral.id), kind="generated",
                      sections=out["sections"], limitations=out["limitations"], evidence_ids=out["evidence_ids"],
                      model=f"{provider.name}:{provider.model}", prompt_version=brief_mod.PROMPT_VERSION,
                      generation_meta={"job_id": job.id, "evidence_supplied": out["evidence_ids"]},
                      based_on_version=prev.version if prev else None, created_by=f"{provider.model} (draft for {job.created_by})")
            db.add(b)
            db.flush()
            from .referrals.state import mark_clinical_change
            if referral.current_package_version:
                mark_clinical_change(db, referral, job.created_by, "brief regenerated")
            job.status, job.result = "completed", {"brief_version": b.version}
            audit(db, None, "brief.generate", "brief", f"{referral.reference}:v{b.version}", "success", referral.id,
                  {"model": b.model, "prompt_version": b.prompt_version},
                  actor=(job.created_by_id, job.created_by, job.institution_id))
        except (ProviderUnavailable, ProviderOutputInvalid) as exc:
            db.rollback()
            job = db.merge(job)
            job.status, job.error = "failed", str(exc)
            audit(db, None, "brief.generate", "referral", referral.reference, "failed", referral.id, {"error": str(exc)},
                  actor=(job.created_by_id, job.created_by, job.institution_id))
        except Exception as exc:  # noqa: BLE001
            log.exception("generate_brief failed")
            db.rollback()
            job = db.merge(job)
            job.status, job.error = "failed", f"Brief generation failed: {exc}"[:500]
        job.finished_at = utcnow()
        db.commit()


@celery_app.task(name="deliver_outbox")
def deliver_outbox() -> int:
    from .delivery.outbox import deliver_pending

    with SessionLocal() as db:
        return deliver_pending(db)


@celery_app.task(name="retention_sweep")
def retention_sweep() -> int:
    """Delete uploaded document copies of closed referrals after the retention period.
    Approved package snapshots and audit history are retained by policy."""
    from .documents.storage import storage
    from .models import Document, ExtractionRun, Referral
    from .security import audit

    cutoff = utcnow() - timedelta(days=settings.document_retention_days)
    removed = 0
    with SessionLocal() as db:
        docs = db.scalars(select(Document).join(Referral, Referral.id == Document.referral_id).where(
            Referral.closed_at.is_not(None), Referral.closed_at < cutoff, Document.deleted_at.is_(None))).all()
        for doc in docs:
            for run in db.scalars(select(ExtractionRun).where(ExtractionRun.document_id == doc.id)):
                for page in run.pages or []:
                    storage.delete(page.get("image_key", "x")) if page.get("image_key") else None
                run.raw_text = "[deleted under retention policy]"
                run.pages = []
            storage.delete(doc.storage_key)
            doc.deleted_at = utcnow()
            removed += 1
            audit(db, None, "retention.delete_document", "document", doc.id, "success", doc.referral_id,
                  actor=("system", "retention sweep", "central-platform"))
        db.commit()
    return removed
