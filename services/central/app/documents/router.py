"""Uploads, protected downloads and job status (FR-22, FR-24, NFR 10.1)."""
from __future__ import annotations

import io
import re
import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse
from refcommon.auth import Principal
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import Document, EvidenceItem, ExtractionRun, Job
from ..referrals.state import ensure_clinical_edit_allowed
from ..security import audit, audit_now, error, get_principal, load_referral
from ..serializers import document_out, evidence_out, job_out
from ..tasks import enqueue
from .storage import storage

router = APIRouter(tags=["documents"])

ALLOWED = {"application/pdf": ".pdf", "image/png": ".png", "image/jpeg": ".jpg"}
DOC_TYPES = {"prescription", "lab_report", "referral_note", "other"}


def detect_type(data: bytes) -> str | None:
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    return None


def _new_job(db: Session, kind: str, principal: Principal, referral_id: int, document_id: int | None = None) -> Job:
    job = Job(id=uuid.uuid4().hex, kind=kind, referral_id=referral_id, document_id=document_id,
              created_by=principal.display_name, created_by_id=principal.subject, institution_id=principal.institution_id)
    db.add(job)
    return job


@router.post("/referrals/{referral_id}/documents", status_code=201)
async def upload(referral_id: int, file: UploadFile = File(...), doc_type: str = Form("other"),
                 db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    r = load_referral(db, referral_id, principal, "upload")
    ensure_clinical_edit_allowed(r)
    if doc_type not in DOC_TYPES:
        raise error(422, "invalid_doc_type", f"Document type must be one of {sorted(DOC_TYPES)}")
    data = await file.read(settings.max_upload_bytes + 1)
    declared = (file.content_type or "").lower()
    name = re.sub(r"[^A-Za-z0-9._ -]", "_", file.filename or "upload")[:200]

    def reject(code: str, message: str):
        audit_now(principal, "document.upload", "referral", r.reference, "rejected", r.id,
                  {"filename": name, "declared": declared, "reason": message})
        return error(415 if code == "unsupported_type" else 422, code, message)

    if len(data) > settings.max_upload_bytes:
        raise reject("too_large", f"File exceeds the {settings.max_upload_bytes // (1024 * 1024)} MB limit")
    if not data:
        raise reject("empty_file", "The uploaded file is empty")
    detected = detect_type(data)
    if detected is None:
        raise reject("unsupported_type", "Only PDF, PNG and JPEG files are supported")
    if declared and declared not in (detected, "application/octet-stream") and not (declared == "image/jpg" and detected == "image/jpeg"):
        raise reject("type_mismatch", f"Declared type {declared} does not match the file content ({detected})")
    pages = 1
    if detected == "application/pdf":
        try:
            import pypdfium2 as pdfium
            pages = len(pdfium.PdfDocument(io.BytesIO(data)))
        except Exception as exc:  # noqa: BLE001
            raise reject("unreadable_pdf", "The PDF could not be opened") from exc
        if pages > settings.max_pages:
            raise reject("too_many_pages", f"PDF has {pages} pages; the limit is {settings.max_pages}")
    key, digest = storage.put(data, ALLOWED[detected])
    doc = Document(referral_id=r.id, patient_institution=r.patient_institution, patient_local_id=r.patient_local_id,
                   uploaded_by=principal.display_name, uploaded_by_id=principal.subject, original_filename=name,
                   declared_type=declared or "unknown", detected_type=detected, size_bytes=len(data), sha256=digest,
                   storage_key=key, doc_type=doc_type, page_count=pages, status="queued")
    db.add(doc)
    db.flush()
    from ..lifecycle.working_set import start

    start(r)  # an uploaded paper is part of the temporary working set
    job = _new_job(db, "process_document", principal, r.id, doc.id)
    audit(db, principal, "document.upload", "document", doc.id, "success", r.id,
          {"filename": name, "type": detected, "size": len(data), "sha256": digest})
    db.commit()
    enqueue("process_document", job.id)
    return {"document": document_out(doc), "job": job_out(job)}


@router.get("/referrals/{referral_id}/documents")
def list_documents(referral_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    r = load_referral(db, referral_id, principal, "view")
    return [document_out(d) for d in db.scalars(select(Document).where(Document.referral_id == r.id).order_by(Document.id))]


def _load_doc(db: Session, document_id: int, principal: Principal, action: str = "view") -> Document:
    doc = db.get(Document, document_id)
    if doc is None:
        raise error(404, "not_found", "Document not found")
    load_referral(db, doc.referral_id, principal, action)
    return doc


@router.get("/documents/{document_id}")
def get_document(document_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    doc = _load_doc(db, document_id, principal)
    run = db.scalars(select(ExtractionRun).where(ExtractionRun.document_id == doc.id).order_by(ExtractionRun.id.desc())).first()
    fields = db.scalars(select(EvidenceItem).where(EvidenceItem.document_id == doc.id).order_by(EvidenceItem.page, EvidenceItem.id))
    jobs = db.scalars(select(Job).where(Job.document_id == doc.id).order_by(Job.created_at.desc()))
    return {
        "document": document_out(doc),
        "extraction": None if run is None else {
            "id": run.id, "status": run.status, "error": run.error, "text_source": run.text_source,
            "ocr_engine": run.ocr_engine, "ocr_engine_version": run.ocr_engine_version, "extractor": run.extractor,
            "extractor_version": run.extractor_version, "notes": run.notes, "duration_ms": run.duration_ms,
            "pages": run.pages, "raw_text": run.raw_text, "created_at": run.created_at,
        },
        "fields": [evidence_out(e) for e in fields],
        "jobs": [job_out(j) for j in jobs],
    }


@router.get("/documents/{document_id}/file")
def download(document_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    doc = _load_doc(db, document_id, principal)
    if doc.deleted_at or not storage.exists(doc.storage_key):
        raise error(410, "deleted", "This document copy was deleted under the retention policy")
    audit(db, principal, "document.download", "document", doc.id, "success", doc.referral_id)
    db.commit()
    return FileResponse(storage.path(doc.storage_key), media_type=doc.detected_type,
                        headers={"Content-Disposition": f'inline; filename="{doc.original_filename}"',
                                 "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@router.get("/documents/{document_id}/pages/{page}")
def page_image(document_id: int, page: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    doc = _load_doc(db, document_id, principal)
    key = f"{doc.storage_key}.p{page}.png"
    if doc.deleted_at or not storage.exists(key):
        raise error(404, "not_found", "Page image not available")
    return FileResponse(storage.path(key), media_type="image/png",
                        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@router.post("/documents/{document_id}/reprocess")
def reprocess(document_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    doc = _load_doc(db, document_id, principal, "edit")
    if doc.deleted_at:
        raise error(410, "deleted", "Document deleted under retention policy")
    doc.status = "queued"
    job = _new_job(db, "process_document", principal, doc.referral_id, doc.id)
    audit(db, principal, "document.reprocess", "document", doc.id, "success", doc.referral_id)
    db.commit()
    enqueue("process_document", job.id)
    return job_out(job)


@router.get("/jobs/{job_id}")
def get_job(job_id: str, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    job = db.get(Job, job_id)
    if job is None:
        raise error(404, "not_found", "Job not found")
    if job.referral_id:
        load_referral(db, job.referral_id, principal, "view")
    elif job.created_by_id != principal.subject:
        raise error(403, "forbidden", "Not your job")
    return job_out(job)


@router.get("/referrals/{referral_id}/jobs")
def referral_jobs(referral_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    r = load_referral(db, referral_id, principal, "view")
    return [job_out(j) for j in db.scalars(select(Job).where(Job.referral_id == r.id).order_by(Job.created_at.desc()).limit(50))]
