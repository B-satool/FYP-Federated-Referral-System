"""One institution's own database (clinic, laboratory or hospital).

The same service runs once per institution, each instance with its own database
and credentials. Only that instance can read or write its rows.
"""
from __future__ import annotations

from datetime import date, datetime

from refcommon.db import utcnow
from refcommon.sourcekit import AccessGrantMixin, AuditMixin
from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
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
    local_patient_id: Mapped[str | None] = mapped_column(String(30), nullable=True)
    urgency: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(30), default="received")
    latest_version: Mapped[int] = mapped_column(Integer)
    acknowledged_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision: Mapped[str | None] = mapped_column(String(20), nullable=True)
    decision_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    decision_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decline_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    local_patient_id: Mapped[str | None] = mapped_column(String(30), nullable=True)
    requested_by: Mapped[str] = mapped_column(String(200))
    # requested | accepted | rejected | scheduled | done | reported
    status: Mapped[str] = mapped_column(String(20), default="requested")
    reject_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    report_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    values: Mapped[list] = mapped_column(JSON, default=list)
    reported_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    history: Mapped[list] = mapped_column(JSON, default=list)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


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
