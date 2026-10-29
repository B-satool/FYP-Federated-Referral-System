"""Referral workflow: the doctor's request, staff preparation, sending, response and follow-up,
plus diagnostic requests and notifications."""
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
    # The patient as recorded at the referring institution
    patient_institution: Mapped[str] = mapped_column(String(50), index=True)
    patient_local_id: Mapped[str] = mapped_column(String(50), index=True)
    patient_name: Mapped[str] = mapped_column(String(200))
    patient_birth_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    patient_sex: Mapped[str | None] = mapped_column(String(10), nullable=True)
    patient_cnic: Mapped[str | None] = mapped_column(String(15), nullable=True)
    # Referring from
    source_institution: Mapped[str] = mapped_column(String(50), index=True)
    source_department: Mapped[str | None] = mapped_column(String(60), nullable=True)
    requesting_doctor_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    requesting_doctor_name: Mapped[str] = mapped_column(String(200))
    created_by_id: Mapped[str] = mapped_column(String(64))
    created_by_name: Mapped[str] = mapped_column(String(200))
    # referral = to a doctor or department; test = a test or scan only (its orders carry the destinations)
    kind: Mapped[str] = mapped_column(String(20), default="referral", index=True)
    # Referring to (referrals only)
    destination_institution: Mapped[str | None] = mapped_column(String(50), index=True, nullable=True)
    destination_department: Mapped[str | None] = mapped_column(String(60), nullable=True)
    destination_doctor: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Clinical
    reason: Mapped[str] = mapped_column(Text, default="")
    # the doctor's consultation notes under the reason: symptoms, history, examination (clinical content)
    consultation_notes: Mapped[str] = mapped_column(Text, default="", server_default="")
    urgency: Mapped[str] = mapped_column(String(20), default="routine")
    procedure_status: Mapped[str] = mapped_column(String(20), default="unknown")  # planned | none | unknown
    planned_procedure: Mapped[str | None] = mapped_column(String(300), nullable=True)  # in the doctor's words
    procedure_tags: Mapped[list[str]] = mapped_column(JSON, default=list)  # what the procedure involves
    # Workflow
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    row_version: Mapped[int] = mapped_column(Integer, default=1)
    requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Staff checkpoint: records, papers and medicines gathered; the doctor can now review the flags
    prepared_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    prepared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Doctor checkpoint: the doctor reviewed the records, papers, medicines and flags that go in the packet.
    # Staff never see that content (decision 2026-10-29). A later clinical change clears it.
    packet_reviewed_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    packet_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    amendment_open: Mapped[bool] = mapped_column(Boolean, default=False)
    current_package_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    submitted_package_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    delivery_status: Mapped[str] = mapped_column(String(20), default="none")
    # Staff checkpoint: patient asked about all medicines, including over-the-counter ones
    meds_checked_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    meds_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    meds_checked_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Follow-through
    patient_informed_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    patient_informed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    patient_informed_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    decline_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Temporary working set: retrieved records and everything derived from them are held only until
    # working_set_expires_at, then their clinical content is removed (identifiers, status, audit,
    # manifest and fingerprint stay). See lifecycle/working_set.py.
    working_set_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    working_set_purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # the receiving doctor marked the referral complete (its shared records are removed after the grace period)
    receiver_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    receiver_completed_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ReferralEvent(Base):
    """Ordered timeline: status changes, deliveries and receiving-side activity."""
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


class Clarification(Base):
    """A request for more information from the receiving doctor, answered by the referring clinic."""
    __tablename__ = "clarifications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    referral_id: Mapped[int] = mapped_column(ForeignKey("referrals.id"), index=True)
    provider_clarification_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    package_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    question: Mapped[str] = mapped_column(Text)
    asked_by: Mapped[str] = mapped_column(String(200))
    asked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)  # open | answered
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    answered_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Brief(Base):
    """The referral summary built from the verified records when a version is sent. Immutable."""
    __tablename__ = "briefs"
    __table_args__ = (UniqueConstraint("referral_id", "version"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    referral_id: Mapped[int] = mapped_column(ForeignKey("referrals.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(20), default="template")
    sections: Mapped[list] = mapped_column(JSON)
    limitations: Mapped[list] = mapped_column(JSON, default=list)
    evidence_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    created_by: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ReferralPackage(Base):
    """One sent version. Never updated after insert except the supersession marker."""
    __tablename__ = "referral_packages"
    __table_args__ = (UniqueConstraint("referral_id", "version"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    referral_id: Mapped[int] = mapped_column(ForeignKey("referrals.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    brief_id: Mapped[int] = mapped_column(ForeignKey("briefs.id"))
    envelope: Mapped[dict] = mapped_column(JSON)
    content_hash: Mapped[str] = mapped_column(String(64))
    delivery_key: Mapped[str] = mapped_column(String(200), unique=True)
    sent_by: Mapped[str] = mapped_column(String(200))
    sent_by_id: Mapped[str] = mapped_column(String(64))
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    superseded: Mapped[bool] = mapped_column(Boolean, default=False)
    # Reference list of what the package contained (no clinical values); survives the content purge.
    manifest: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    content_purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Outbox(Base):
    """Written in the same transaction that decides to send; a worker delivers it."""
    __tablename__ = "outbox"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    referral_id: Mapped[int] = mapped_column(ForeignKey("referrals.id"), index=True)
    # deliver_package | deliver_order | forward_result | clarification_answer
    kind: Mapped[str] = mapped_column(String(40))
    target_institution: Mapped[str] = mapped_column(String(50))
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
    """Deduplicates incoming events from the institution services."""
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
    returned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
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
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="open")  # open | completed | not_completed
    outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DiagnosticRequest(Base):
    """A test, scan or equipment request added to a referral. It is a separate order with
    its own status; it does not wait for the specialist's decision."""
    __tablename__ = "diagnostic_requests"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reference: Mapped[str] = mapped_column(String(30), unique=True)
    referral_id: Mapped[int] = mapped_column(ForeignKey("referrals.id"), index=True)
    category: Mapped[str] = mapped_column(String(20))  # laboratory | imaging | cardiac
    test: Mapped[str] = mapped_column(String(200))
    body_area: Mapped[str | None] = mapped_column(String(100), nullable=True)
    clinical_question: Mapped[str] = mapped_column(Text)
    urgency: Mapped[str] = mapped_column(String(20), default="routine")
    destination_institution: Mapped[str] = mapped_column(String(50), index=True)
    destination_department: Mapped[str] = mapped_column(String(60))
    # draft (in the referral, not sent yet) | requested | accepted | rejected | scheduled | done | reported | cancelled
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    requested_by: Mapped[str] = mapped_column(String(200))
    requested_by_id: Mapped[str] = mapped_column(String(64))
    sent_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reject_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    report: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Images or report files returned with the result: [{"n", "filename", "content_type", "storage_key", "size"}]
    attachments: Mapped[list] = mapped_column(JSON, default=list)
    local_patient_id: Mapped[str | None] = mapped_column(String(50), nullable=True)  # at the destination, once confirmed
    seen_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    history: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Notification(Base):
    """Something a person should act on or know about. Either addressed to one user, or to a
    role at an institution (for example the referral desk staff)."""
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recipient_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    institution_id: Mapped[str] = mapped_column(String(50), index=True)
    role: Mapped[str | None] = mapped_column(String(40), nullable=True)
    referral_id: Mapped[int | None] = mapped_column(ForeignKey("referrals.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text, default="")
    link: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    read_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
