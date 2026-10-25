"""Identity: user references and patient links that the other institution confirms."""
from __future__ import annotations

from datetime import datetime

from refcommon.db import utcnow
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base


class User(Base):
    """Central reference to a Keycloak account. account_status is checked on every request."""
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # Keycloak subject
    username: Mapped[str] = mapped_column(String(100), index=True)
    display_name: Mapped[str] = mapped_column(String(200))
    institution_id: Mapped[str | None] = mapped_column(String(50), index=True, nullable=True)
    department: Mapped[str | None] = mapped_column(String(60), nullable=True)
    roles: Mapped[list[str]] = mapped_column(JSON, default=list)
    account_status: Mapped[str] = mapped_column(String(20), default="active")
    status_changed_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PatientLink(Base):
    """A request from one institution to another to confirm which of the other's patient
    records is the same person. It becomes verified only when staff at the OTHER
    institution check it and approve it. Records are never linked on matching IDs or names."""
    __tablename__ = "patient_links"
    __table_args__ = (UniqueConstraint("requester_institution", "requester_local_id", "target_institution", "status_key"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    requester_institution: Mapped[str] = mapped_column(String(50), index=True)
    requester_local_id: Mapped[str] = mapped_column(String(50), index=True)
    target_institution: Mapped[str] = mapped_column(String(50), index=True)
    target_local_id: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    # Identity details sent with the request (from the requester's own record)
    patient_name: Mapped[str] = mapped_column(String(200))
    patient_birth_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    patient_sex: Mapped[str | None] = mapped_column(String(10), nullable=True)
    patient_cnic: Mapped[str | None] = mapped_column(String(15), nullable=True)
    referral_id: Mapped[int | None] = mapped_column(ForeignKey("referrals.id"), nullable=True)
    purpose: Mapped[str] = mapped_column(Text, default="")
    # requested | verified | rejected | invalidated
    status: Mapped[str] = mapped_column(String(20), default="requested", index=True)
    # lets a rejected/invalidated pair be requested again without violating uniqueness
    status_key: Mapped[str] = mapped_column(String(40), default="current")
    requested_by: Mapped[str] = mapped_column(String(200))
    requested_by_id: Mapped[str] = mapped_column(String(64))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    decided_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    decided_by_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    match_check: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    registered_new: Mapped[bool] = mapped_column(Boolean, default=False)
    invalidated_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    invalidation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class PatientLinkEvent(Base):
    __tablename__ = "patient_link_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    link_id: Mapped[int] = mapped_column(ForeignKey("patient_links.id"), index=True)
    action: Mapped[str] = mapped_column(String(30))
    actor: Mapped[str] = mapped_column(String(200))
    actor_id: Mapped[str] = mapped_column(String(64))
    institution_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
