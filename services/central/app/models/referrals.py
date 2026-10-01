"""Referral workflow module (Member 1): lifecycle, review, briefs, approvals, delivery, follow-up."""
from __future__ import annotations

from datetime import date, datetime

from refcommon.db import utcnow
from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base


class Referral(Base):
    __tablename__ = "referrals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reference: Mapped[str] = mapped_column(String(30), unique=True)
    patient_institution: Mapped[str] = mapped_column(String(50), index=True)
    patient_local_id: Mapped[str] = mapped_column(String(50), index=True)
    patient_name: Mapped[str] = mapped_column(String(200))
    patient_birth_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    patient_sex: Mapped[str | None] = mapped_column(String(10), nullable=True)
    source_institution: Mapped[str] = mapped_column(String(50), index=True)
    created_by_id: Mapped[str] = mapped_column(String(64))
    created_by_name: Mapped[str] = mapped_column(String(200))
    referring_clinician_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    referring_clinician_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    destination_institution: Mapped[str] = mapped_column(String(50), index=True)
    specialty: Mapped[str] = mapped_column(String(50))
    reason: Mapped[str] = mapped_column(Text, default="")
    priority: Mapped[str | None] = mapped_column(String(20), nullable=True)
    planned_procedure: Mapped[str | None] = mapped_column(String(60), nullable=True)
    # not_stated | known | unknown  (unknown is an explicit, recorded state - FR-12)
    procedure_status: Mapped[str] = mapped_column(String(20), default="not_stated")
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    row_version: Mapped[int] = mapped_column(Integer, default=1)
    amendment_open: Mapped[bool] = mapped_column(Boolean, default=False)
    current_package_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    submitted_package_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    delivery_status: Mapped[str] = mapped_column(String(20), default="none")
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    decline_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ReferralEvent(Base):
    """Ordered timeline: status changes, deliveries and specialist activity."""
    __tablename__ = "referral_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    referral_id: Mapped[int] = mapped_column(ForeignKey("referrals.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(50))
    from_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    actor: Mapped[str] = mapped_column(String(200))
    institution_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ReviewItem(Base):
    """Checklist finding: missing / unresolved / discrepancy (findings produced by Member 3's checker)."""
    __tablename__ = "review_items"
    __table_args__ = (UniqueConstraint("referral_id", "item_key"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    referral_id: Mapped[int] = mapped_column(ForeignKey("referrals.id"), index=True)
    item_key: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(20))  # missing | unresolved | discrepancy | link_invalidated
    checklist_item_id: Mapped[str | None] = mapped_column(String(60), nullable=True)
    checklist_version: Mapped[str | None] = mapped_column(String(30), nullable=True)
    title: Mapped[str] = mapped_column(String(300))
    detail: Mapped[str] = mapped_column(Text, default="")
    evidence_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    blocking: Mapped[bool] = mapped_column(Boolean, default=True)
    override_allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    clinical: Mapped[bool] = mapped_column(Boolean, default=False)
    # open | resolved | not_applicable | uncertainty_recorded | overridden | obsolete
    status: Mapped[str] = mapped_column(String(30), default="open")
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Clarification(Base):
    """Referral-specific request with its own status model (FR-39)."""
    __tablename__ = "clarifications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    referral_id: Mapped[int] = mapped_column(ForeignKey("referrals.id"), index=True)
    review_item_id: Mapped[int | None] = mapped_column(ForeignKey("review_items.id"), nullable=True)
    flag_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    origin: Mapped[str] = mapped_column(String(20), default="clinic")  # clinic | specialist
    question: Mapped[str] = mapped_column(Text)
    assignee_institution: Mapped[str] = mapped_column(String(50), index=True)
    assignee_role: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)  # open|answered|resolved|cancelled
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_by: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    response_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_document_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    answered_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    specialist_clarification_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    package_version: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Brief(Base):
    """Every generated or edited brief is a new immutable row; the latest is the working draft."""
    __tablename__ = "briefs"
    __table_args__ = (UniqueConstraint("referral_id", "version"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    referral_id: Mapped[int] = mapped_column(ForeignKey("referrals.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(20))  # generated | edited | template | manual
    sections: Mapped[list] = mapped_column(JSON)
    limitations: Mapped[list] = mapped_column(JSON, default=list)
    evidence_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    model: Mapped[str | None] = mapped_column(String(80), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    generation_meta: Mapped[dict] = mapped_column(JSON, default=dict)
    based_on_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ReferralPackage(Base):
    """Immutable approved version. Never updated after insert except supersession marker."""
    __tablename__ = "referral_packages"
    __table_args__ = (UniqueConstraint("referral_id", "version"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    referral_id: Mapped[int] = mapped_column(ForeignKey("referrals.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    brief_id: Mapped[int] = mapped_column(ForeignKey("briefs.id"))
    envelope: Mapped[dict] = mapped_column(JSON)
    content_hash: Mapped[str] = mapped_column(String(64))
    delivery_key: Mapped[str] = mapped_column(String(200), unique=True)
    approved_by: Mapped[str] = mapped_column(String(200))
    approved_by_id: Mapped[str] = mapped_column(String(64))
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    overrides: Mapped[list] = mapped_column(JSON, default=list)
    superseded: Mapped[bool] = mapped_column(Boolean, default=False)


class Outbox(Base):
    """Written in the same transaction that schedules a send; a worker delivers it."""
    __tablename__ = "outbox"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    referral_id: Mapped[int] = mapped_column(ForeignKey("referrals.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40))  # deliver_package | clarification_answer
    message_key: Mapped[str] = mapped_column(String(200), unique=True)
    payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending | sent | failed
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    remote_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class InboundMessage(Base):
    """Deduplicates incoming specialist events and responses (FR-57)."""
    __tablename__ = "inbound_messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    message_key: Mapped[str] = mapped_column(String(200), unique=True)
    message_type: Mapped[str] = mapped_column(String(40))
    referral_id: Mapped[int | None] = mapped_column(ForeignKey("referrals.id"), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ConsultationResponse(Base):
    __tablename__ = "consultation_responses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    referral_id: Mapped[int] = mapped_column(ForeignKey("referrals.id"), index=True)
    remote_key: Mapped[str] = mapped_column(String(200), unique=True)
    package_version: Mapped[int] = mapped_column(Integer)
    content: Mapped[dict] = mapped_column(JSON)
    specialist_name: Mapped[str] = mapped_column(String(200))
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    receipt_recorded_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    receipt_recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reviewed_by_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    fhir_task: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class FollowupTask(Base):
    __tablename__ = "followup_tasks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    referral_id: Mapped[int] = mapped_column(ForeignKey("referrals.id"), index=True)
    description: Mapped[str] = mapped_column(Text)
    specified_by: Mapped[str] = mapped_column(String(200))
    assignee_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    assignee_role: Mapped[str | None] = mapped_column(String(40), nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="open")  # open | completed | not_completed
    outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
