"""Specialist C's own database: patients, incoming referrals and consultation responses."""
from __future__ import annotations

from datetime import date, datetime

from refcommon.db import utcnow
from refcommon.sourcekit import AccessGrantMixin, AuditMixin
from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Patient(Base):
    __tablename__ = "patients"
    local_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    given: Mapped[str] = mapped_column(String(100))
    family: Mapped[str] = mapped_column(String(100))
    birth_date: Mapped[date] = mapped_column(Date)
    sex: Mapped[str] = mapped_column(String(10))
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    synthetic: Mapped[bool] = mapped_column(default=True)


class PriorConsultation(Base):
    __tablename__ = "prior_consultations"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.local_id"), index=True)
    seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    clinician: Mapped[str] = mapped_column(String(120))
    summary: Mapped[str] = mapped_column(Text)
    diagnosis: Mapped[str | None] = mapped_column(String(200), nullable=True)
    diagnosis_code: Mapped[str | None] = mapped_column(String(30), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Case(Base):
    """One referral as seen by the specialist, across all received package versions."""
    __tablename__ = "cases"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    central_referral_id: Mapped[str] = mapped_column(String(40), unique=True)
    sender_institution: Mapped[str] = mapped_column(String(50))
    patient_name: Mapped[str] = mapped_column(String(200))
    patient_birth_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    specialist_patient_id: Mapped[str | None] = mapped_column(String(30), nullable=True)
    priority: Mapped[str] = mapped_column(String(20))
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


class FlagReview(Base):
    __tablename__ = "flag_reviews"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    package_version: Mapped[int] = mapped_column(Integer)
    flag_id: Mapped[int] = mapped_column(Integer)
    flag_version: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(30))
    reviewer: Mapped[str] = mapped_column(String(200))
    reviewer_id: Mapped[str] = mapped_column(String(100))
    clarification_id: Mapped[int | None] = mapped_column(ForeignKey("clarifications.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Clarification(Base):
    __tablename__ = "clarifications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    package_version: Mapped[int] = mapped_column(Integer)
    flag_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    question: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="open")
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
    status: Mapped[str] = mapped_column(String(20), default="draft")
    drafted_by: Mapped[str] = mapped_column(String(200))
    drafted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    row_version: Mapped[int] = mapped_column(Integer, default=1)
    approved_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    approved_by_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    returned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    return_key: Mapped[str | None] = mapped_column(String(200), unique=True, nullable=True)


class Outbox(Base):
    """Events for the central platform, written in the same transaction as the change."""
    __tablename__ = "outbox"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_key: Mapped[str] = mapped_column(String(200), unique=True)
    event_type: Mapped[str] = mapped_column(String(40))
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AccessGrant(AccessGrantMixin, Base):
    __tablename__ = "access_grants"


class AuditEvent(AuditMixin, Base):
    __tablename__ = "audit_events"
