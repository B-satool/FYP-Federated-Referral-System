"""Medicines: the referral's current-medicine list, medicine names, rules, evaluation and flags."""
from __future__ import annotations

from datetime import datetime

from refcommon.db import utcnow
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base


class MedicationEntry(Base):
    """One current medicine as recorded by one source. Entries for the same medicine and
    strength from different sources form a group shown once (duplicate_of points at the
    entry that represents the group)."""
    __tablename__ = "medication_entries"
    __table_args__ = (UniqueConstraint("referral_id", "evidence_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    referral_id: Mapped[int] = mapped_column(ForeignKey("referrals.id"), index=True)
    evidence_id: Mapped[int] = mapped_column(ForeignKey("evidence_items.id"))
    record_kind: Mapped[str] = mapped_column(String(20))  # prescription | document | manual
    original_name: Mapped[str] = mapped_column(String(200))
    brand: Mapped[str | None] = mapped_column(String(100), nullable=True)
    strength: Mapped[str | None] = mapped_column(String(60), nullable=True)
    dose: Mapped[str | None] = mapped_column(String(120), nullable=True)
    route: Mapped[str | None] = mapped_column(String(40), nullable=True)
    frequency: Mapped[str | None] = mapped_column(String(100), nullable=True)
    start_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    over_the_counter: Mapped[bool] = mapped_column(Boolean, default=False)
    source_label: Mapped[str] = mapped_column(String(300))
    ingredient: Mapped[str | None] = mapped_column(String(100), nullable=True)
    drug_class: Mapped[str | None] = mapped_column(String(60), nullable=True)
    # mapped | ambiguous | unmapped | staff_mapped
    mapping_status: Mapped[str] = mapped_column(String(20))
    mapping_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    duplicate_of: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dose_differs: Mapped[bool] = mapped_column(Boolean, default=False)
    excluded: Mapped[bool] = mapped_column(Boolean, default=False)
    excluded_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    excluded_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class MedicineName(Base):
    """A medicine name (brand or generic, as written in Pakistan) mapped to its ingredient
    and drug class. Maintained in the app by clinical reviewers."""
    __tablename__ = "medicine_names"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)  # normalised lowercase
    display: Mapped[str] = mapped_column(String(120))
    ingredient: Mapped[str] = mapped_column(String(100))
    drug_class: Mapped[str] = mapped_column(String(60))
    kind: Mapped[str] = mapped_column(String(20), default="generic")  # generic | brand
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | retired
    added_by: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MedicationRule(Base):
    """One version of a drug-against-procedure rule. Edited in the app; a new or changed
    rule is a draft until a clinical reviewer approves that exact version."""
    __tablename__ = "medication_rules"
    __table_args__ = (UniqueConstraint("rule_id", "version"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rule_id: Mapped[str] = mapped_column(String(60), index=True)
    version: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(300))
    drug_class: Mapped[str] = mapped_column(String(60))
    procedure_tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    message: Mapped[str] = mapped_column(Text)
    rationale: Mapped[str] = mapped_column(Text, default="")
    reference: Mapped[str] = mapped_column(Text, default="")
    # draft | approved | rejected | retired | superseded
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    content_hash: Mapped[str] = mapped_column(String(64))
    created_by: Mapped[str] = mapped_column(String(200))
    created_by_id: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    decided_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    decided_by_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reference_checked: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    referral_id: Mapped[int] = mapped_column(ForeignKey("referrals.id"), index=True)
    trigger: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(20))  # completed | failed
    outcome: Mapped[str | None] = mapped_column(String(30), nullable=True)  # flags | no_match | no_rules
    summary_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    context: Mapped[dict] = mapped_column(JSON, default=dict)
    rule_versions: Mapped[dict] = mapped_column(JSON, default=dict)
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
    # confirmed | unrecognised_medicine | procedure_not_checked | records_incomplete
    kind: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(300))
    message: Mapped[str] = mapped_column(Text)
    medication: Mapped[str | None] = mapped_column(String(300), nullable=True)
    drug_class: Mapped[str | None] = mapped_column(String(60), nullable=True)
    source_label: Mapped[str | None] = mapped_column(String(500), nullable=True)
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
    """A doctor's acknowledgment of one flag version for this patient. Acknowledgment means
    the flag has been seen; it is never treatment clearance."""
    __tablename__ = "flag_reviews"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    referral_id: Mapped[int] = mapped_column(ForeignKey("referrals.id"), index=True)
    flag_id: Mapped[int] = mapped_column(ForeignKey("medication_flags.id"), index=True)
    flag_version: Mapped[int] = mapped_column(Integer)
    side: Mapped[str] = mapped_column(String(20), default="referring")
    reviewer: Mapped[str] = mapped_column(String(200))
    reviewer_id: Mapped[str] = mapped_column(String(64))
    institution_id: Mapped[str] = mapped_column(String(50))
    package_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
