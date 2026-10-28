"""Versioned application envelopes exchanged between the central platform and
the institution services.

These are PROJECT API CONTRACTS, not standard FHIR resources. The FHIR Bundle
travels inside the referral envelope unchanged; the brief, structured
medication flags, rule versions and acknowledgments travel alongside it so no
extra fields are ever inserted into standard resources.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

PACKAGE_ENVELOPE_VERSION = "referral-package/2.0"
ORDER_ENVELOPE_VERSION = "diagnostic-order/1.0"
EVENT_ENVELOPE_VERSION = "provider-event/1.0"
CONTRACT_NOTE = "Project API contract (not a standard FHIR resource)"


class BriefStatement(BaseModel):
    id: str
    text: str
    evidence_ids: list[int] = Field(default_factory=list)
    author_kind: Literal["model", "clinician", "template"] = "template"
    author_name: str | None = None
    edited_by: str | None = None
    verification: Literal["verified", "unresolved", "unverified", "mixed", "none"] = "none"
    # For laying the summary out as a report: where it is recorded, when, and grouping (e.g. a lab panel)
    source: str | None = None
    date: str | None = None
    group: str | None = None


class BriefSection(BaseModel):
    key: str
    title: str
    statements: list[BriefStatement] = Field(default_factory=list)


class FlagSnapshot(BaseModel):
    flag_id: int
    version: int
    kind: str
    title: str
    message: str
    medication: str | None = None
    drug_class: str | None = None
    source_label: str | None = None
    rule_id: str | None = None
    rule_version: int | None = None
    evidence_ids: list[int] = Field(default_factory=list)
    acknowledged: dict[str, Any] | None = None  # {by, at, decision: reviewed|ignore|research, note}
    # where the flag came from (approved manual rule, DDInter, drug label), shown beside it
    severity: str | None = None
    ingredients: list[str] = Field(default_factory=list)
    source_type: str | None = None
    source_name: str | None = None
    source_ref: str | None = None
    source_version: str | None = None
    source_quote: str | None = None
    auto_generated: bool = False


class EvidenceSnapshot(BaseModel):
    evidence_id: int
    category: str
    display: str
    original: dict[str, Any] = Field(default_factory=dict)
    origin: str
    source_institution: str
    source_record_type: str | None = None
    source_record_id: str | None = None
    source_record_version: str | None = None
    clinical_time: str | None = None
    verification_status: str
    document_ref: dict[str, Any] | None = None
    also_recorded_in: list[str] = Field(default_factory=list)


class PackageEnvelope(BaseModel):
    """One sent version of a referral. The requesting doctor authorised the request;
    staff compiled and sent this exact version (recorded separately)."""
    envelope_version: str = PACKAGE_ENVELOPE_VERSION
    contract_note: str = CONTRACT_NOTE
    delivery_key: str
    referral_id: str
    package_version: int
    sender_institution: str
    sender_department: str | None = None
    destination_institution: str
    destination_department: str
    destination_doctor: str | None = None
    urgency: str
    reason: str
    procedure_status: str
    planned_procedure: str | None = None
    procedure_label: str | None = None
    patient: dict[str, Any]
    requesting_doctor: dict[str, Any]
    brief_sections: list[BriefSection]
    medication_flags: list[FlagSnapshot]
    medication_evaluation: dict[str, Any]
    evidence: list[EvidenceSnapshot]
    limitations: list[str] = Field(default_factory=list)
    diagnostic_requests: list[dict[str, Any]] = Field(default_factory=list)
    # Possible clashes with no source entry, labelled "AI suggestion, not verified" (never flags)
    ai_suggestions: list[dict[str, Any]] = Field(default_factory=list)
    # How the records in this version were chosen: rule-based default, AI recommendation, staff decision
    selection: dict[str, Any] = Field(default_factory=dict)
    sent_by: str
    sent_by_id: str
    sent_at: datetime
    content_hash: str
    fhir_bundle: dict[str, Any]
    supersedes_version: int | None = None


class DiagnosticOrder(BaseModel):
    """A test or scan request sent to a laboratory or imaging department. It is a separate
    order: it does not depend on the specialist's decision about the referral."""
    envelope_version: str = ORDER_ENVELOPE_VERSION
    contract_note: str = CONTRACT_NOTE
    order_key: str
    order_ref: str
    referral_id: str
    sender_institution: str
    destination_institution: str
    destination_department: str
    category: Literal["laboratory", "imaging", "cardiac"]
    test: str
    body_area: str | None = None
    clinical_question: str
    urgency: str
    patient: dict[str, Any]
    requested_by: str
    requested_at: datetime


class ResultForward(BaseModel):
    """A returned diagnostic report forwarded to the referral's receiving hospital,
    so the specialist sees it next to the brief."""
    contract_note: str = CONTRACT_NOTE
    forward_key: str
    referral_id: str
    order_ref: str
    test: str
    performed_by_institution: str
    report_text: str = ""
    values: list[dict[str, Any]] = Field(default_factory=list)
    reported_by: str
    reported_at: datetime


ProviderEventType = Literal[
    # referral (receiving hospital)
    "acknowledged",
    "accepted",
    "declined",
    "info_requested",
    "response_returned",
    "completed",  # the receiving doctor has finished with the referral
    "hold_extended",  # the receiving doctor needs the shared records for longer
    # diagnostic order (laboratory / imaging department)
    "order_accepted",
    "order_rejected",
    "order_scheduled",
    "order_done",
    "order_reported",
]


class ProviderEvent(BaseModel):
    envelope_version: str = EVENT_ENVELOPE_VERSION
    contract_note: str = CONTRACT_NOTE
    event_key: str
    referral_id: str
    order_ref: str | None = None
    package_version: int | None = None
    type: ProviderEventType
    actor_id: str
    actor_name: str
    institution_id: str
    occurred_at: datetime
    data: dict[str, Any] = Field(default_factory=dict)


class ClarificationAnswer(BaseModel):
    contract_note: str = CONTRACT_NOTE
    answer_key: str
    referral_id: str
    provider_clarification_id: int
    answer: str
    answered_by: str
    answered_at: datetime


def content_hash(payload: Any) -> str:
    """Stable SHA-256 over canonical JSON (sorted keys)."""
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


# Fields covered by the package hash. Transport-level fields (delivery key,
# FHIR bundle timestamp) are excluded so retries do not change the hash.
HASHED_PACKAGE_FIELDS = (
    "referral_id", "package_version", "sender_institution", "sender_department", "destination_institution",
    "destination_department", "destination_doctor", "urgency", "reason", "procedure_status", "planned_procedure",
    "procedure_label", "patient", "requesting_doctor", "brief_sections", "medication_flags", "medication_evaluation",
    "evidence", "limitations", "diagnostic_requests", "ai_suggestions", "selection", "sent_by", "sent_by_id", "sent_at",
)


def package_hash(envelope: dict[str, Any]) -> str:
    sent_at = envelope.get("sent_at")
    if isinstance(sent_at, datetime):
        sent_at = sent_at.isoformat()
    payload = {k: envelope.get(k) for k in HASHED_PACKAGE_FIELDS}
    payload["sent_at"] = sent_at
    return content_hash(payload)
