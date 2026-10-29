"""Encrypted referral content (spec v4 5.6, 5.8, 5.9; approval A4).

The platform stores what institutions and doctors' devices send it, as received: plaintext titles, ciphertext and
data keys wrapped to recipients' public keys. It never holds a data key or a private key, so it cannot read the
content. Everything here is deleted when the referral is purged (crypto-shredding); the signed manifest's hash
and the counts are kept in the purge receipt.
"""
from __future__ import annotations

from datetime import datetime

from refcommon.db import utcnow
from sqlalchemy import JSON, BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base


class EncryptedBatch(Base):
    """Items encrypted under one data key: one institution's answer to one request, one upload by a doctor or the
    patient, or the receiving hospital's added records."""
    __tablename__ = "encrypted_batches"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    referral_id: Mapped[int] = mapped_column(ForeignKey("referrals.id"), index=True)
    batch_id: Mapped[str] = mapped_column(String(60), unique=True)
    # custodian (a source institution's answer) | doctor (the referring doctor's own items) | patient (patient's
    # scans) | receiving (records the receiving hospital added)
    origin: Mapped[str] = mapped_column(String(20))
    source_institution: Mapped[str | None] = mapped_column(String(50), nullable=True)
    record_request_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EncryptedItem(Base):
    __tablename__ = "encrypted_items"
    __table_args__ = (UniqueConstraint("batch_id", "item_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    referral_id: Mapped[int] = mapped_column(ForeignKey("referrals.id"), index=True)
    batch_id: Mapped[str] = mapped_column(String(60), index=True)
    item_id: Mapped[str] = mapped_column(String(120))
    # title record (spec v4 4.2): never values, results, free text or doses
    kind: Mapped[str] = mapped_column(String(20))  # lab | imaging | note | prescription | scan | other
    category: Mapped[str | None] = mapped_column(String(30), nullable=True)
    label: Mapped[str] = mapped_column(String(300))
    item_date: Mapped[str | None] = mapped_column(String(30), nullable=True)
    source_institution: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sensitive: Mapped[bool] = mapped_column(Boolean, default=False)
    # {"nonce", "ciphertext"} or {"chunks": [{"nonce", "ciphertext"}, ...]} for large files
    sealed: Mapped[dict] = mapped_column(JSON)
    size: Mapped[int] = mapped_column(BigInteger, default=0)
    ciphertext_sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WrappedKey(Base):
    """A batch's data key, wrapped to one recipient key (doctor, patient or department group)."""
    __tablename__ = "wrapped_keys"
    __table_args__ = (UniqueConstraint("batch_id", "recipient_key_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    referral_id: Mapped[int] = mapped_column(ForeignKey("referrals.id"), index=True)
    batch_id: Mapped[str] = mapped_column(String(60), index=True)
    recipient_type: Mapped[str] = mapped_column(String(20))  # doctor | patient | department
    recipient_subject: Mapped[str] = mapped_column(String(100), index=True)
    recipient_key_id: Mapped[str] = mapped_column(String(16), index=True)
    key_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    wrapped: Mapped[dict] = mapped_column(JSON)
    created_by: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PackageManifest(Base):
    """A doctor-signed package version (spec v4 5.8): the ordered item list with plaintext and ciphertext
    hashes, the recipient department key, the referral. Immutable; a change is a new version and signature."""
    __tablename__ = "package_manifests"
    __table_args__ = (UniqueConstraint("referral_id", "version"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    referral_id: Mapped[int] = mapped_column(ForeignKey("referrals.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    manifest: Mapped[dict] = mapped_column(JSON)  # signed by the doctor (signature inside)
    manifest_sha256: Mapped[str] = mapped_column(String(64))
    signer_subject: Mapped[str] = mapped_column(String(64))
    signer_key_id: Mapped[str] = mapped_column(String(16))
    item_count: Mapped[int] = mapped_column(Integer)
    superseded: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PurgeReceipt(Base):
    """What remains after a referral's content is crypto-shredded (spec v4 11.2)."""
    __tablename__ = "purge_receipts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    referral_id: Mapped[int] = mapped_column(ForeignKey("referrals.id"), unique=True)
    purged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    items_count: Mapped[int] = mapped_column(Integer)
    wrapped_keys_count: Mapped[int] = mapped_column(Integer)
    manifest_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    trigger: Mapped[str] = mapped_column(String(40))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    note: Mapped[str] = mapped_column(Text, default="")
