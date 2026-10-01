"""Clinic A's own database. Only this service holds credentials for it."""
from __future__ import annotations

from datetime import date, datetime

from refcommon.db import utcnow
from refcommon.sourcekit import AccessGrantMixin, AuditMixin
from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Versioned:
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Patient(Versioned, Base):
    __tablename__ = "patients"
    local_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    given: Mapped[str] = mapped_column(String(100))
    family: Mapped[str] = mapped_column(String(100))
    birth_date: Mapped[date] = mapped_column(Date)
    sex: Mapped[str] = mapped_column(String(10))
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    city: Mapped[str | None] = mapped_column(String(60), nullable=True)
    synthetic: Mapped[bool] = mapped_column(default=True)


class Encounter(Versioned, Base):
    __tablename__ = "encounters"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.local_id"), index=True)
    start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    type_text: Mapped[str] = mapped_column(String(120))
    reason_text: Mapped[str] = mapped_column(Text)
    practitioner: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20), default="finished")


class Condition(Versioned, Base):
    __tablename__ = "conditions"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.local_id"), index=True)
    code_system: Mapped[str | None] = mapped_column(String(100), nullable=True)
    code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    display: Mapped[str] = mapped_column(String(200))
    clinical_status: Mapped[str] = mapped_column(String(20))
    onset: Mapped[date | None] = mapped_column(Date, nullable=True)
    recorded: Mapped[date] = mapped_column(Date)


class Prescription(Versioned, Base):
    __tablename__ = "prescriptions"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.local_id"), index=True)
    medication_text: Mapped[str] = mapped_column(String(200))
    strength: Mapped[str | None] = mapped_column(String(60), nullable=True)
    dose_value: Mapped[float | None] = mapped_column(nullable=True)
    dose_unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    dose_text: Mapped[str | None] = mapped_column(String(120), nullable=True)
    route: Mapped[str | None] = mapped_column(String(40), nullable=True)
    frequency: Mapped[str | None] = mapped_column(String(60), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20))
    prescriber: Mapped[str] = mapped_column(String(120))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class ReportedMedication(Versioned, Base):
    """Patient-reported medication use (FHIR MedicationStatement)."""
    __tablename__ = "reported_medications"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.local_id"), index=True)
    medication_text: Mapped[str] = mapped_column(String(200))
    dose_text: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(20))
    reported_on: Mapped[date] = mapped_column(Date)
    recorded_by: Mapped[str] = mapped_column(String(120))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class SourceDocument(Versioned, Base):
    __tablename__ = "source_documents"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.local_id"), index=True)
    doc_type: Mapped[str] = mapped_column(String(60))
    title: Mapped[str] = mapped_column(String(200))
    doc_date: Mapped[date] = mapped_column(Date)
    author: Mapped[str] = mapped_column(String(120))
    content_type: Mapped[str] = mapped_column(String(60), default="application/pdf")


class AccessGrant(AccessGrantMixin, Base):
    __tablename__ = "access_grants"


class AuditEvent(AuditMixin, Base):
    __tablename__ = "audit_events"
