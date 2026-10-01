"""Lab B's own database."""
from __future__ import annotations

from datetime import date, datetime

from refcommon.db import utcnow
from refcommon.sourcekit import AccessGrantMixin, AuditMixin
from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, String, Text
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


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.local_id"), index=True)
    code: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(120))
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="final")
    conclusion: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Result(Base):
    __tablename__ = "results"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.local_id"), index=True)
    report_id: Mapped[str | None] = mapped_column(ForeignKey("reports.id"), nullable=True)
    loinc: Mapped[str | None] = mapped_column(String(20), nullable=True)
    test_name: Mapped[str] = mapped_column(String(120))
    value_num: Mapped[float | None] = mapped_column(nullable=True)
    value_text: Mapped[str | None] = mapped_column(String(120), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(30), nullable=True)
    reference_range: Mapped[str | None] = mapped_column(String(60), nullable=True)
    specimen: Mapped[str | None] = mapped_column(String(60), nullable=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resulted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="final")
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ResultRevision(Base):
    """Prior versions of a corrected result are retained, never overwritten."""
    __tablename__ = "result_revisions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    result_id: Mapped[str] = mapped_column(ForeignKey("results.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict] = mapped_column(JSON)
    reason: Mapped[str] = mapped_column(Text)
    changed_by: Mapped[str] = mapped_column(String(200))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AccessGrant(AccessGrantMixin, Base):
    __tablename__ = "access_grants"


class AuditEvent(AuditMixin, Base):
    __tablename__ = "audit_events"
