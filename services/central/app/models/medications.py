"""Medication module (Member 3): entries, rule approvals, evaluation runs, flags and reviews."""
from __future__ import annotations

from datetime import datetime

from refcommon.db import utcnow
from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base


class MedicationEntry(Base):
    __tablename__ = "medication_entries"
    __table_args__ = (UniqueConstraint("referral_id", "evidence_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    referral_id: Mapped[int] = mapped_column(ForeignKey("referrals.id"), index=True)
    evidence_id: Mapped[int] = mapped_column(ForeignKey("evidence_items.id"))
    record_kind: Mapped[str] = mapped_column(String(20))  # prescription | reported | document
    original_name: Mapped[str] = mapped_column(String(200))
    strength: Mapped[str | None] = mapped_column(String(60), nullable=True)
    dose: Mapped[str | None] = mapped_column(String(120), nullable=True)
    route: Mapped[str | None] = mapped_column(String(40), nullable=True)
    frequency: Mapped[str | None] = mapped_column(String(60), nullable=True)
    start_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    end_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    source_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    source_label: Mapped[str] = mapped_column(String(200))
    ingredient: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ingredient_code: Mapped[str | None] = mapped_column(String(30), nullable=True)
    drug_class: Mapped[str | None] = mapped_column(String(60), nullable=True)
    class_code: Mapped[str | None] = mapped_column(String(30), nullable=True)
    mapping_source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mapping_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    # mapped | ambiguous | unmapped | clinician_mapped
    mapping_status: Mapped[str] = mapped_column(String(20))
    mapping_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # unverified | confirmed_current | historical_stopped | uncertain | conflicting
    use_status: Mapped[str] = mapped_column(String(30), default="unverified")
    use_verified_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    use_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    use_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class RuleApproval(Base):
    """Clinical approval of one rule version. Rule content lives in versioned JSON files."""
    __tablename__ = "rule_approvals"
    __table_args__ = (UniqueConstraint("rule_id", "rule_version"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rule_id: Mapped[str] = mapped_column(String(60))
    rule_version: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20))  # approved | retired | rejected
    reviewer: Mapped[str] = mapped_column(String(200))
    reviewer_id: Mapped[str] = mapped_column(String(64))
    reference_checked: Mapped[str] = mapped_column(Text)
    note: Mapped[str] = mapped_column(Text, default="")
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    referral_id: Mapped[int] = mapped_column(ForeignKey("referrals.id"), index=True)
    trigger: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(20))  # completed | failed
    outcome: Mapped[str | None] = mapped_column(String(30), nullable=True)  # flags | no_match | unsupported_coverage
    summary_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    context: Mapped[dict] = mapped_column(JSON, default=dict)
    rule_versions: Mapped[dict] = mapped_column(JSON, default=dict)
    mapping_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    input_hash: Mapped[str] = mapped_column(String(64))
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_flags: Mapped[int] = mapped_column(Integer, default=0)
    triggered_by: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MedicationFlag(Base):
    """A flag version. A material change supersedes the row and creates version+1."""
    __tablename__ = "medication_flags"
    __table_args__ = (UniqueConstraint("referral_id", "flag_key", "version"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    referral_id: Mapped[int] = mapped_column(ForeignKey("referrals.id"), index=True)
    flag_key: Mapped[str] = mapped_column(String(200))
    version: Mapped[int] = mapped_column(Integer, default=1)
    # confirmed | possible_use | procedure_context_required | ambiguous_mapping | history_incomplete
    kind: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(300))
    message: Mapped[str] = mapped_column(Text)
    medication: Mapped[str | None] = mapped_column(String(200), nullable=True)
    drug_class: Mapped[str | None] = mapped_column(String(60), nullable=True)
    current_use_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    source_label: Mapped[str | None] = mapped_column(String(300), nullable=True)
    rule_id: Mapped[str | None] = mapped_column(String(60), nullable=True)
    rule_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    medication_entry_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evidence_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    content_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | superseded | withdrawn
    run_id: Mapped[int] = mapped_column(ForeignKey("evaluation_runs.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class FlagReview(Base):
    __tablename__ = "flag_reviews"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    referral_id: Mapped[int] = mapped_column(ForeignKey("referrals.id"), index=True)
    flag_id: Mapped[int] = mapped_column(ForeignKey("medication_flags.id"), index=True)
    flag_version: Mapped[int] = mapped_column(Integer)
    side: Mapped[str] = mapped_column(String(20))  # referring | specialist
    action: Mapped[str] = mapped_column(String(30))  # reviewed | request_clarification
    reviewer: Mapped[str] = mapped_column(String(200))
    reviewer_id: Mapped[str] = mapped_column(String(64))
    institution_id: Mapped[str] = mapped_column(String(50))
    package_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    clarification_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
