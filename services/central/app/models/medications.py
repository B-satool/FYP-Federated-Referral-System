"""Medicines: the referral's current-medicine list, medicine names, rules, evaluation and flags."""
from __future__ import annotations

from datetime import datetime

from refcommon.db import utcnow
from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
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
    # every ingredient checked for this medicine (several for a combination product)
    ingredients: Mapped[list[str]] = mapped_column(JSON, default=list)
    drug_class: Mapped[str | None] = mapped_column(String(60), nullable=True)
    # mapped | ambiguous | unmapped | staff_mapped
    mapping_status: Mapped[str] = mapped_column(String(20))
    # ambiguous DRAP brand: the products it could be, for staff or the doctor to pick from by company
    mapping_choices: Mapped[list | None] = mapped_column(JSON, nullable=True)
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
    kind: Mapped[str] = mapped_column(String(20), default="generic")  # generic | brand | register_brand | register_ambiguous (DRAP)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | retired
    # register_ambiguous only: the products behind the name (ingredient, company, DRAP number, strength, form)
    options: Mapped[list | None] = mapped_column(JSON, nullable=True)
    added_by: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Ingredient(Base):
    """An ingredient as named in this project, with its international name (used by DDInter and
    drug labels), RxNorm and ATC codes, and the parts of a combination product."""
    __tablename__ = "ingredients"
    name: Mapped[str] = mapped_column(String(100), primary_key=True)
    standard: Mapped[str | None] = mapped_column(String(100), nullable=True)
    label_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    rxnorm_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    atc_codes: Mapped[list[str]] = mapped_column(JSON, default=list)
    components: Mapped[list[str]] = mapped_column(JSON, default=list)
    in_interaction_source: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class DrugInteraction(Base):
    """A drug-drug interaction pair from an imported source (stored once, ingredient_a < ingredient_b).
    The severity is the source's own level, unchanged."""
    __tablename__ = "drug_interactions"
    __table_args__ = (UniqueConstraint("ingredient_a", "ingredient_b", "source"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ingredient_a: Mapped[str] = mapped_column(String(100), index=True)
    ingredient_b: Mapped[str] = mapped_column(String(100), index=True)
    severity: Mapped[str] = mapped_column(String(20))  # Major | Moderate | Minor | Unknown
    source: Mapped[str] = mapped_column(String(40))  # ddinter
    source_version: Mapped[str] = mapped_column(String(80))
    source_ref: Mapped[str] = mapped_column(String(80))
    # Why, in the source's own words: a sentence quoted verbatim from a US drug label's interaction
    # section that names the other ingredient (rules/labels/interaction-quotes.json). Empty when none exists.
    label_quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    label_source: Mapped[str | None] = mapped_column(String(200), nullable=True)
    label_section: Mapped[str | None] = mapped_column(String(60), nullable=True)


class LabelRule(Base):
    """A drug-condition or drug-procedure rule read from a drug label by script, with the exact
    sentence it relies on. Imported rules are labelled automatically generated, not clinically reviewed."""
    __tablename__ = "label_rules"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rule_key: Mapped[str] = mapped_column(String(200), unique=True)
    kind: Mapped[str] = mapped_column(String(20))  # drug_condition | drug_procedure
    ingredient: Mapped[str] = mapped_column(String(100), index=True)
    target: Mapped[str] = mapped_column(String(60))
    target_label: Mapped[str] = mapped_column(String(120))
    severity_hint: Mapped[str] = mapped_column(String(20))  # high | moderate | low (display only)
    summary: Mapped[str] = mapped_column(Text)
    quote: Mapped[str] = mapped_column(Text)
    section: Mapped[str] = mapped_column(String(40))
    source_type: Mapped[str] = mapped_column(String(40), default="drug_label")
    source_ref: Mapped[str] = mapped_column(String(80))
    source_name: Mapped[str] = mapped_column(String(200))
    source_version: Mapped[str] = mapped_column(String(80))
    extractor_version: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20), default="auto_extracted")  # auto_extracted | withdrawn


class AiSuggestion(Base):
    """A possible clash between two ingredients that have no entry in the interaction source, scored
    offline by a small model. A suggestion is never a flag: it cannot add, remove or change a flag,
    never blocks sending and is not included in the sent referral."""
    __tablename__ = "ai_suggestions"
    pair_key: Mapped[str] = mapped_column(String(210), primary_key=True)  # "a|b" with a < b
    ingredient_a: Mapped[str] = mapped_column(String(100), index=True)
    ingredient_b: Mapped[str] = mapped_column(String(100), index=True)
    score: Mapped[float] = mapped_column(Float)
    reason: Mapped[str] = mapped_column(Text)
    model_version: Mapped[str] = mapped_column(String(60))
    data_version: Mapped[str] = mapped_column(String(200))


class SuggestionReview(Base):
    """A doctor's decision on one AI suggestion for one patient: ignore or research (logged)."""
    __tablename__ = "suggestion_reviews"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    referral_id: Mapped[int] = mapped_column(ForeignKey("referrals.id"), index=True)
    pair_key: Mapped[str] = mapped_column(String(210))
    decision: Mapped[str] = mapped_column(String(20))  # ignore | research
    note: Mapped[str] = mapped_column(Text, default="")
    score: Mapped[float] = mapped_column(Float)
    model_version: Mapped[str] = mapped_column(String(60))
    data_version: Mapped[str] = mapped_column(String(200))
    reviewer: Mapped[str] = mapped_column(String(200))
    reviewer_id: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RulesetRelease(Base):
    """The exact rule set in force: approved manual rules, label rules and interaction data, by hash."""
    __tablename__ = "ruleset_releases"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hash: Mapped[str] = mapped_column(String(64), unique=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    counts: Mapped[dict] = mapped_column(JSON, default=dict)
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
    ruleset_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
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
    # confirmed (approved manual rule) | interaction | label_warning | unrecognised_medicine |
    # interactions_not_checked | procedure_not_checked | records_incomplete
    kind: Mapped[str] = mapped_column(String(40))
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True)  # the source's level, unchanged
    ingredients: Mapped[list[str]] = mapped_column(JSON, default=list)
    source_type: Mapped[str | None] = mapped_column(String(40), nullable=True)  # manual_rule | ddinter | drug_label
    source_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    source_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    source_quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    auto_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    # the doctor must record a decision before sending (approved rules, Major interactions, high label warnings, gaps)
    requires_decision: Mapped[bool] = mapped_column(Boolean, default=True)
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
    """A doctor's decision on one flag version for this patient: reviewed, ignore (not relevant for
    this patient) or research (needs follow-up). Any decision means the flag has been seen; it is
    never treatment clearance. Ignored flags stay visible in the record."""
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
    decision: Mapped[str] = mapped_column(String(20), default="reviewed")  # reviewed | ignore | research
    ruleset_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
