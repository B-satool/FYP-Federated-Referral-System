"""Identity module (Member 2): user references and verified patient links."""
from __future__ import annotations

from datetime import datetime

from refcommon.db import utcnow
from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base


class User(Base):
    """Central reference to a Keycloak account. account_status is checked on every request (FR-05)."""
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # Keycloak subject
    username: Mapped[str] = mapped_column(String(100), index=True)
    display_name: Mapped[str] = mapped_column(String(200))
    institution_id: Mapped[str | None] = mapped_column(String(50), index=True, nullable=True)
    roles: Mapped[list[str]] = mapped_column(JSON, default=list)
    account_status: Mapped[str] = mapped_column(String(20), default="active")
    status_changed_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PatientLink(Base):
    """Explicit link between two institution-specific patient records (never inferred)."""
    __tablename__ = "patient_links"
    __table_args__ = (UniqueConstraint("a_institution", "a_local_id", "b_institution", "b_local_id", "status_key"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    a_institution: Mapped[str] = mapped_column(String(50), index=True)
    a_local_id: Mapped[str] = mapped_column(String(50), index=True)
    b_institution: Mapped[str] = mapped_column(String(50), index=True)
    b_local_id: Mapped[str] = mapped_column(String(50), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending | verified | invalidated | rejected
    # status_key lets an invalidated pair be proposed again without violating uniqueness
    status_key: Mapped[str] = mapped_column(String(40), default="current")
    basis: Mapped[str] = mapped_column(Text, default="")
    match_check: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    proposed_by: Mapped[str] = mapped_column(String(200))
    proposed_by_id: Mapped[str] = mapped_column(String(64))
    proposed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    verified_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    verified_by_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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
    note: Mapped[str] = mapped_column(Text, default="")
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
