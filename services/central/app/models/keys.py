"""Public-key directory (spec v4 5.4, 5.5). The platform stores public keys and signed entries, and group private
keys only as ciphertext wrapped to member doctors. It holds no private key of any doctor, department or patient;
its own platform signing key is the only private key here."""
from __future__ import annotations

from datetime import datetime

from refcommon.db import utcnow
from sqlalchemy import JSON, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base


class DirectoryEntry(Base):
    """A doctor's, department's or patient's public keys, signed by the issuing hospital (or, for a patient, the
    platform). Stored exactly as signed; clients and adapters verify the signature against pinned keys."""
    __tablename__ = "key_directory"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_id: Mapped[str] = mapped_column(String(100), index=True)
    subject_type: Mapped[str] = mapped_column(String(20), index=True)  # doctor | department | patient
    hospital_id: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    department: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    enc_key_id: Mapped[str] = mapped_column(String(16), unique=True)
    key_version: Mapped[int] = mapped_column(Integer)
    issued_by: Mapped[str] = mapped_column(String(50))
    entry: Mapped[dict] = mapped_column(JSON)
    revocation: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class GroupKeyWrap(Base):
    """A department group private key wrapped to one member doctor's encryption key (ciphertext)."""
    __tablename__ = "group_key_wraps"
    __table_args__ = (UniqueConstraint("hospital_id", "department", "group_version", "member_key_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hospital_id: Mapped[str] = mapped_column(String(50))
    department: Mapped[str] = mapped_column(String(60))
    group_version: Mapped[int] = mapped_column(Integer)
    member_subject_id: Mapped[str] = mapped_column(String(64), index=True)
    member_key_id: Mapped[str] = mapped_column(String(16), index=True)
    wrapped: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PlatformKey(Base):
    """The platform's own signing key (request assertions to adapters, patient key entries). Sealed with the
    platform's key-store secret."""
    __tablename__ = "platform_keys"
    kid: Mapped[str] = mapped_column(String(16), primary_key=True)
    public_spki: Mapped[str] = mapped_column(Text)
    private_sealed: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SeenAssertion(Base):
    """Adapter request assertions already accepted (jti), until they expire: a replay is refused."""
    __tablename__ = "seen_assertions"
    jti: Mapped[str] = mapped_column(String(80), primary_key=True)
    issuer: Mapped[str] = mapped_column(String(50))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
