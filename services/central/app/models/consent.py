"""Consent and records requests (spec v4 6.4, 6.2, 5.6).

A consent is administrative data, not clinical content: who may release which kinds of records to whom, for what
purpose and until when. Staff request it; only the patient grants it, in the patient portal, signed with the
patient's own key. The platform stores the signed document; each institution's adapter fetches it and checks the
signature itself.
"""
from __future__ import annotations

from datetime import datetime

from refcommon.db import utcnow
from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base


class Consent(Base):
    __tablename__ = "consents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reference: Mapped[str] = mapped_column(String(30), unique=True)
    referral_id: Mapped[int] = mapped_column(ForeignKey("referrals.id"), index=True)
    patient_cnic: Mapped[str] = mapped_column(String(15), index=True)
    patient_name: Mapped[str] = mapped_column(String(200))
    purpose: Mapped[str] = mapped_column(String(20), default="TREAT")
    requesting_org: Mapped[str] = mapped_column(String(50))
    requesting_practitioner_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    requesting_practitioner_name: Mapped[str] = mapped_column(String(200))
    destination_org: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # what the staff asked for
    custodians_requested: Mapped[list] = mapped_column(JSON, default=list)
    categories: Mapped[list] = mapped_column(JSON, default=list)
    sensitive_offered: Mapped[list] = mapped_column(JSON, default=list)
    data_period_start: Mapped[str | None] = mapped_column(String(20), nullable=True)
    requested_by_id: Mapped[str] = mapped_column(String(64))
    requested_by_name: Mapped[str] = mapped_column(String(200))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # requested | granted | declined | revoked | expired | withdrawn
    status: Mapped[str] = mapped_column(String(20), default="requested", index=True)
    # the patient's answer
    custodians_granted: Mapped[list] = mapped_column(JSON, default=list)
    sensitive_specific: Mapped[list] = mapped_column(JSON, default=list)
    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    document: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # FHIR Consent shape, signed by the patient
    patient_key_id: Mapped[str | None] = mapped_column(String(16), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decline_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    revocation: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # signed by the patient
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RecordRequest(Base):
    """One request to one institution for a referral's records, and its outcome. A refusal keeps its reason code;
    an unreachable institution is 'unavailable'. Neither is ever shown as 'no records' (AGENTS.md)."""
    __tablename__ = "record_requests"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    referral_id: Mapped[int] = mapped_column(ForeignKey("referrals.id"), index=True)
    consent_id: Mapped[int] = mapped_column(ForeignKey("consents.id"), index=True)
    custodian: Mapped[str] = mapped_column(String(50))
    request_key: Mapped[str] = mapped_column(String(200), unique=True)
    local_patient_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    practitioner_id: Mapped[str] = mapped_column(String(64))
    # sent | answered | partial | refused | pending_manual_review | no_records | unavailable | failed
    status: Mapped[str] = mapped_column(String(30), index=True)
    refusals: Mapped[list] = mapped_column(JSON, default=list)
    item_count: Mapped[int] = mapped_column(Integer, default=0)
    batch_id: Mapped[str | None] = mapped_column(String(60), nullable=True)
    policy_version: Mapped[str | None] = mapped_column(String(60), nullable=True)
    message: Mapped[str] = mapped_column(Text, default="")
    requested_by: Mapped[str] = mapped_column(String(200))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
