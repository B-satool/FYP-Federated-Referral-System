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
        "purge-working-sets": {"task": "purge_working_sets", "schedule": 600.0},
        "close-reminders": {"task": "close_reminders", "schedule": 3600.0},
        "seal-audit": {"task": "seal_audit", "schedule": 60.0},
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


@celery_app.task(name="purge_working_sets")
def purge_working_sets() -> int:
    """Crypto-shred referrals whose time is up (see lifecycle/working_set.py); a failure is retried next run."""
    from .lifecycle.working_set import purge_due

    with SessionLocal() as db:
        return purge_due(db)


@celery_app.task(name="seal_audit")
def seal_audit() -> int:
    """Add the audit events written since the last run to the hash chain (spec v4 11.5)."""
    from .lifecycle.audit_chain import seal

    with SessionLocal() as db:
        return seal(db)


@celery_app.task(name="close_reminders")
def close_reminders() -> dict:
    """Close reminders 30 days after acceptance, weekly repeats and escalation (spec v4 7)."""
    from .lifecycle.working_set import reminders_due

    with SessionLocal() as db:
        return reminders_due(db)