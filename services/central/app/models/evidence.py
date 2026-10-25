"""Evidence, retrieval outcomes, documents, extraction and jobs.

Source evidence (Member 2) and document evidence (Member 3) share one
EvidenceItem contract so the brief, checklist and medication modules treat
them uniformly while keeping provenance distinct.
"""
from __future__ import annotations

from datetime import datetime

from refcommon.db import utcnow
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base


class SourceRetrieval(Base):
    __tablename__ = "source_retrievals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    referral_id: Mapped[int] = mapped_column(ForeignKey("referrals.id"), index=True)
    source_institution: Mapped[str] = mapped_column(String(50))
    local_patient_id: Mapped[str] = mapped_column(String(50))
    link_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    institution_kind: Mapped[str | None] = mapped_column(String(20), nullable=True)
    last_activity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    window_start: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # successful | empty | partial | denied | unavailable | invalid | skipped (not the most recent of its kind)
    status: Mapped[str] = mapped_column(String(20))
    record_count: Mapped[int] = mapped_column(Integer, default=0)
    new_count: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0)
    invalid_count: Mapped[int] = mapped_column(Integer, default=0)
    withheld: Mapped[list[str]] = mapped_column(JSON, default=list)
    message: Mapped[str] = mapped_column(Text, default="")
    retryable: Mapped[bool] = mapped_column(Boolean, default=False)
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    requested_by: Mapped[str] = mapped_column(String(200))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EvidenceItem(Base):
    __tablename__ = "evidence_items"
    __table_args__ = (
        UniqueConstraint("referral_id", "source_institution", "source_record_type", "source_record_id",
                         "source_record_version", name="uq_evidence_source_version"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    referral_id: Mapped[int] = mapped_column(ForeignKey("referrals.id"), index=True)
    patient_institution: Mapped[str] = mapped_column(String(50))
    patient_local_id: Mapped[str] = mapped_column(String(50))
    origin: Mapped[str] = mapped_column(String(20))  # source | document | manual
    source_institution: Mapped[str] = mapped_column(String(50))
    source_record_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    source_record_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    source_record_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    link_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    category: Mapped[str] = mapped_column(String(30), index=True)
    display: Mapped[str] = mapped_column(Text)
    original: Mapped[dict] = mapped_column(JSON, default=dict)
    current: Mapped[dict] = mapped_column(JSON, default=dict)
    fhir: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    clinical_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    region: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    source_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # imported | proposed | corrected | unresolved | excluded | manual
    review_state: Mapped[str] = mapped_column(String(20))
    # source_record | unverified | verified | invalidated
    verification_status: Mapped[str] = mapped_column(String(20))
    verified_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    selected: Mapped[bool] = mapped_column(Boolean, default=False)
    superseded_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    author: Mapped[str | None] = mapped_column(String(200), nullable=True)
    row_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class EvidenceRevision(Base):
    """Append-only history; raw extraction is never overwritten (FR-28)."""
    __tablename__ = "evidence_revisions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    evidence_id: Mapped[int] = mapped_column(ForeignKey("evidence_items.id"), index=True)
    action: Mapped[str] = mapped_column(String(30))
    prior_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    new_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    prior_state: Mapped[str | None] = mapped_column(String(20), nullable=True)
    new_state: Mapped[str | None] = mapped_column(String(20), nullable=True)
    editor: Mapped[str] = mapped_column(String(200))
    editor_id: Mapped[str] = mapped_column(String(64))
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    referral_id: Mapped[int] = mapped_column(ForeignKey("referrals.id"), index=True)
    patient_institution: Mapped[str] = mapped_column(String(50))
    patient_local_id: Mapped[str] = mapped_column(String(50))
    uploaded_by: Mapped[str] = mapped_column(String(200))
    uploaded_by_id: Mapped[str] = mapped_column(String(64))
    original_filename: Mapped[str] = mapped_column(String(255))
    declared_type: Mapped[str] = mapped_column(String(100))
    detected_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    storage_key: Mapped[str] = mapped_column(String(200))
    doc_type: Mapped[str] = mapped_column(String(40))
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    # uploaded | queued | processing | extracted | failed
    status: Mapped[str] = mapped_column(String(20), default="uploaded")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ExtractionRun(Base):
    __tablename__ = "extraction_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    job_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    text_source: Mapped[str | None] = mapped_column(String(20), nullable=True)  # embedded | ocr | mixed
    ocr_engine: Mapped[str | None] = mapped_column(String(60), nullable=True)
    ocr_engine_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    extractor: Mapped[str | None] = mapped_column(String(80), nullable=True)
    extractor_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, default="")
    pages: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="running")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[list] = mapped_column(JSON, default=list)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    kind: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued | running | completed | failed
    referral_id: Mapped[int | None] = mapped_column(ForeignKey("referrals.id"), nullable=True, index=True)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[str] = mapped_column(String(200))
    created_by_id: Mapped[str] = mapped_column(String(64))
    institution_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
