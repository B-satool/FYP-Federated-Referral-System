"""One institution's own database (clinic, laboratory or hospital).

The same service runs once per institution, each instance with its own database
and credentials. Only that instance can read or write its rows.
"""
from __future__ import annotations

from datetime import date, datetime

from refcommon.db import utcnow
from refcommon.sourcekit import AccessGrantMixin, AuditMixin
from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Versioned:
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


# --------------------------------------------------------------------------- patient records
class Patient(Versioned, Base):
    __tablename__ = "patients"
    local_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    cnic: Mapped[str | None] = mapped_column(String(15), index=True, nullable=True)  # 13 digits, no dashes
    given: Mapped[str] = mapped_column(String(100))
    family: Mapped[str] = mapped_column(String(100))
    birth_date: Mapped[date] = mapped_column(Date)
    sex: Mapped[str] = mapped_column(String(10))
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    city: Mapped[str | None] = mapped_column(String(60), nullable=True)
    registered_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    synthetic: Mapped[bool] = mapped_column(default=True)


class Condition(Versioned, Base):
    __tablename__ = "conditions"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.local_id"), index=True)
    display: Mapped[str] = mapped_column(String(300))
    snomed: Mapped[str | None] = mapped_column(String(30), nullable=True)
    clinical_status: Mapped[str] = mapped_column(String(20))
    onset: Mapped[str | None] = mapped_column(String(10), nullable=True)  # as recorded: YYYY, YYYY-MM or YYYY-MM-DD


class Surgery(Versioned, Base):
    __tablename__ = "surgeries"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.local_id"), index=True)
    procedure: Mapped[str] = mapped_column(String(300))
    performed: Mapped[str | None] = mapped_column(String(10), nullable=True)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)


class Visit(Versioned, Base):
    __tablename__ = "visits"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.local_id"), index=True)
    visit_date: Mapped[date] = mapped_column(Date, index=True)
    setting: Mapped[str] = mapped_column(String(200))
    clinician: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    summary: Mapped[str] = mapped_column(Text, default="")


class Medication(Versioned, Base):
    __tablename__ = "medications"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.local_id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    brand_as_written: Mapped[str | None] = mapped_column(String(100), nullable=True)
    dose: Mapped[str | None] = mapped_column(String(100), nullable=True)
    route: Mapped[str | None] = mapped_column(String(40), nullable=True)
    frequency: Mapped[str | None] = mapped_column(String(100), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20))  # active | stopped | completed
    prescriber: Mapped[str | None] = mapped_column(String(200), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class LabResult(Versioned, Base):
    __tablename__ = "lab_results"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.local_id"), index=True)
    panel: Mapped[str] = mapped_column(String(200))
    collected: Mapped[date] = mapped_column(Date, index=True)
    test: Mapped[str] = mapped_column(String(120))
    loinc: Mapped[str | None] = mapped_column(String(20), nullable=True)
    value_num: Mapped[float | None] = mapped_column(Float, nullable=True)
    value_text: Mapped[str | None] = mapped_column(String(200), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    reference_range: Mapped[str | None] = mapped_column(String(60), nullable=True)
    abnormal_flag: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="final")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class ImagingReport(Versioned, Base):
    __tablename__ = "imaging_reports"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.local_id"), index=True)
    study_date: Mapped[date] = mapped_column(Date, index=True)
    study: Mapped[str] = mapped_column(String(200))
    body_part: Mapped[str | None] = mapped_column(String(100), nullable=True)
    findings: Mapped[str] = mapped_column(Text, default="")
    impression: Mapped[str] = mapped_column(Text, default="")
    reporter: Mapped[str | None] = mapped_column(String(200), nullable=True)


class AccessGrant(AccessGrantMixin, Base):
    __tablename__ = "access_grants"


class AuditEvent(AuditMixin, Base):
    __tablename__ = "audit_events"


# --------------------------------------------------------------------------- receiving referrals (hospitals)
class Case(Base):
    """One referral received by this institution, across all sent versions."""
    __tablename__ = "cases"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    central_referral_id: Mapped[str] = mapped_column(String(40), unique=True)
    sender_institution: Mapped[str] = mapped_column(String(50))
    sender_name: Mapped[str] = mapped_column(String(200))
    department: Mapped[str] = mapped_column(String(60), index=True)
    requested_doctor: Mapped[str | None] = mapped_column(String(200), nullable=True)
    patient_name: Mapped[str] = mapped_column(String(200))
    patient_birth_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    patient_sex: Mapped[str | None] = mapped_column(String(10), nullable=True)
    patient_cnic: Mapped[str | None] = mapped_column(String(15), nullable=True)
    # set once staff here confirm the patient (match a record or register them as new)
    local_patient_id: Mapped[str | None] = mapped_column(String(30), nullable=True)
    link_request_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # the central intake link request
    urgency: Mapped[str] = mapped_column(String(20))
    # received -> acknowledged (staff) -> assigned (staff) -> accepted | declined (doctor) -> responded -> completed
    status: Mapped[str] = mapped_column(String(30), default="received")
    latest_version: Mapped[int] = mapped_column(Integer)
    assigned_doctor: Mapped[str | None] = mapped_column(String(200), nullable=True)
    assigned_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    assign_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    acknowledged_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision: Mapped[str | None] = mapped_column(String(20), nullable=True)
    decision_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    decision_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decline_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # the referred doctor has finished with it; the shared records are then removed after 72 hours
    completed_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # until when the shared records are kept (mirrors the platform: 30 days after acceptance, extendable)
    hold_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # when the shared records (packages, forwarded results) were removed here; this institution's own
    # decision, questions and response are kept
    shared_removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class IncomingPackage(Base):
    __tablename__ = "incoming_packages"
    __table_args__ = (UniqueConstraint("case_id", "version"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    delivery_key: Mapped[str] = mapped_column(String(200), unique=True)
    envelope: Mapped[dict] = mapped_column(JSON)
    content_hash: Mapped[str] = mapped_column(String(64))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class InfoRequest(Base):
    """'Ask for more information' from the receiving doctor to the referring clinic."""
    __tablename__ = "info_requests"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    package_version: Mapped[int] = mapped_column(Integer)
    question: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="open")  # open | answered
    created_by: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    answered_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    answer_key: Mapped[str | None] = mapped_column(String(200), unique=True, nullable=True)


class ConsultationResponse(Base):
    __tablename__ = "consultation_responses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    package_version: Mapped[int] = mapped_column(Integer)
    content: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft | returned
    drafted_by: Mapped[str] = mapped_column(String(200))
    drafted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    row_version: Mapped[int] = mapped_column(Integer, default=1)
    returned_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    returned_by_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    returned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    return_key: Mapped[str | None] = mapped_column(String(200), unique=True, nullable=True)


class ForwardedResult(Base):
    """A diagnostic report from another department or institution, attached to a case."""
    __tablename__ = "forwarded_results"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    forward_key: Mapped[str] = mapped_column(String(200), unique=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    content: Mapped[dict] = mapped_column(JSON)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# --------------------------------------------------------------------------- diagnostic orders (lab / imaging)
class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_key: Mapped[str] = mapped_column(String(200), unique=True)
    order_ref: Mapped[str] = mapped_column(String(40), index=True)
    central_referral_id: Mapped[str] = mapped_column(String(40))
    sender_institution: Mapped[str] = mapped_column(String(50))
    sender_name: Mapped[str] = mapped_column(String(200))
    department: Mapped[str] = mapped_column(String(60), index=True)
    category: Mapped[str] = mapped_column(String(20))
    test: Mapped[str] = mapped_column(String(200))
    body_area: Mapped[str | None] = mapped_column(String(100), nullable=True)
    clinical_question: Mapped[str] = mapped_column(Text)
    urgency: Mapped[str] = mapped_column(String(20))
    patient_name: Mapped[str] = mapped_column(String(200))
    patient_birth_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    patient_sex: Mapped[str | None] = mapped_column(String(10), nullable=True)
    patient_cnic: Mapped[str | None] = mapped_column(String(15), nullable=True)
    local_patient_id: Mapped[str | None] = mapped_column(String(30), nullable=True)
    link_request_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    requested_by: Mapped[str] = mapped_column(String(200))
    # requested | accepted | rejected | scheduled | done | reported
    status: Mapped[str] = mapped_column(String(20), default="requested")
    reject_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    report_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    findings: Mapped[str | None] = mapped_column(Text, nullable=True)
    impression: Mapped[str | None] = mapped_column(Text, nullable=True)
    values: Mapped[list] = mapped_column(JSON, default=list)
    reported_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    history: Mapped[list] = mapped_column(JSON, default=list)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class OrderAttachment(Base):
    """An image or file returned with a report (scan images, ECG trace, report PDF)."""
    __tablename__ = "order_attachments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    filename: Mapped[str] = mapped_column(String(200))
    content_type: Mapped[str] = mapped_column(String(100))
    data: Mapped[bytes] = mapped_column(LargeBinary)
    uploaded_by: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SentCopy(Base):
    """This institution's own copy of a referral it sent (and the response it received). Delivered by
    the central platform, whose working copy is temporary; this copy is the sender's lasting record."""
    __tablename__ = "sent_copies"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    copy_key: Mapped[str] = mapped_column(String(220), unique=True)
    central_referral_id: Mapped[str] = mapped_column(String(40), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # package | response
    version: Mapped[int] = mapped_column(Integer, default=0)
    content: Mapped[dict] = mapped_column(JSON)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Outbox(Base):
    """Events for the central platform, written in the same transaction as the change."""
    __tablename__ = "outbox"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_key: Mapped[str] = mapped_column(String(200), unique=True)
    event_type: Mapped[str] = mapped_column(String(40))
    case_id: Mapped[int | None] = mapped_column(ForeignKey("cases.id"), index=True, nullable=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), index=True, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# --------------------------------------------------------------------------- end-to-end encryption keys (spec v4 WP1)
class KeyStore(Base):
    """This institution's own private keys: the hospital signing key and each department's group key. The private
    part is sealed with the service's key-store secret (AES-256-GCM); it never leaves this service."""
    __tablename__ = "key_store"
    __table_args__ = (UniqueConstraint("purpose", "version"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # hospital_signing | group:<department>
    purpose: Mapped[str] = mapped_column(String(80), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    public_spki: Mapped[str] = mapped_column(Text)
    private_sealed: Mapped[dict] = mapped_column(JSON)
    # the signed directory entry for a department group key (published to the platform)
    entry: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DoctorKey(Base):
    """A doctor's public keys, signed by this hospital once it accepts them (spec v4 5.4). The doctor's private
    keys stay on the doctor's device."""
    __tablename__ = "doctor_keys"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_id: Mapped[str] = mapped_column(String(64), index=True)
    username: Mapped[str] = mapped_column(String(100))
    display_name: Mapped[str] = mapped_column(String(200))
    department: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    enc_key_id: Mapped[str] = mapped_column(String(16), index=True)
    key_version: Mapped[int] = mapped_column(Integer)
    request: Mapped[dict] = mapped_column(JSON)  # the doctor's signed registration (proof of possession)
    entry: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # the hospital-signed directory entry
    # pending (waits for an administrator) | active | revoked | rejected
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    recovery: Mapped[bool] = mapped_column(default=False)  # replaces a key the doctor lost
    approved_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    revocation: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    revoked_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class GroupKeyWrap(Base):
    """A department group private key, wrapped to one member doctor's encryption key (ciphertext only)."""
    __tablename__ = "group_key_wraps"
    __table_args__ = (UniqueConstraint("department", "group_version", "member_key_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    department: Mapped[str] = mapped_column(String(60), index=True)
    group_version: Mapped[int] = mapped_column(Integer)
    member_subject_id: Mapped[str] = mapped_column(String(64), index=True)
    member_key_id: Mapped[str] = mapped_column(String(16))
    wrapped: Mapped[dict] = mapped_column(JSON)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SeenAssertion(Base):
    """Request assertions already accepted (jti), kept until they expire, so a replay is refused."""
    __tablename__ = "seen_assertions"
    jti: Mapped[str] = mapped_column(String(80), primary_key=True)
    issuer: Mapped[str] = mapped_column(String(50))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
