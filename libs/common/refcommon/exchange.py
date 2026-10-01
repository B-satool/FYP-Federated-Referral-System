"""Versioned application envelopes exchanged between the central platform and
the specialist service.

These are PROJECT API CONTRACTS, not standard FHIR resources. The FHIR Bundle
travels inside the envelope unchanged; approved text, structured medication
flags, rule versions and acknowledgments travel alongside it so no extra
fields are ever inserted into standard resources.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

PACKAGE_ENVELOPE_VERSION = "referral-package/1.0"
EVENT_ENVELOPE_VERSION = "specialist-event/1.0"
CONTRACT_NOTE = "Project API contract (not a standard FHIR resource)"


class BriefStatement(BaseModel):
    id: str
    text: str
    evidence_ids: list[int] = Field(default_factory=list)
    author_kind: Literal["model", "clinician", "template"] = "clinician"
    author_name: str | None = None
    edited_by: str | None = None
    verification: Literal["verified", "unresolved", "unverified", "mixed", "none"] = "none"


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
    current_use_status: str | None = None
    source_label: str | None = None
    rule_id: str | None = None
    rule_version: int | None = None
    evidence_ids: list[int] = Field(default_factory=list)
    clinic_review: dict[str, Any] | None = None


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


class PackageEnvelope(BaseModel):
    envelope_version: str = PACKAGE_ENVELOPE_VERSION
    contract_note: str = CONTRACT_NOTE
    delivery_key: str
    referral_id: str
    package_version: int
    sender_institution: str
    destination_institution: str
    specialty: str
    priority: str
    reason: str
    planned_procedure: str | None = None
    procedure_known: bool = False
    patient: dict[str, Any]
    referring_clinician: dict[str, Any]
    brief_sections: list[BriefSection]
    medication_flags: list[FlagSnapshot]
    medication_evaluation: dict[str, Any]
    evidence: list[EvidenceSnapshot]
    limitations: list[str] = Field(default_factory=list)
    checklist: list[dict[str, Any]] = Field(default_factory=list)
    approved_by: str
    approved_by_id: str
    approved_at: datetime
    content_hash: str
    fhir_bundle: dict[str, Any]
    supersedes_version: int | None = None


SpecialistEventType = Literal[
    "acknowledged",
    "accepted",
    "declined",
    "flag_reviewed",
    "clarification_requested",
    "response_returned",
]


class SpecialistEvent(BaseModel):
    envelope_version: str = EVENT_ENVELOPE_VERSION
    contract_note: str = CONTRACT_NOTE
    event_key: str
    referral_id: str
    package_version: int
    type: SpecialistEventType
    actor_id: str
    actor_name: str
    institution_id: str
    occurred_at: datetime
    data: dict[str, Any] = Field(default_factory=dict)


class ClarificationAnswer(BaseModel):
    contract_note: str = CONTRACT_NOTE
    answer_key: str
    referral_id: str
    specialist_clarification_id: int
    answer: str
    answered_by: str
    answered_at: datetime


def content_hash(payload: Any) -> str:
    """Stable SHA-256 over canonical JSON (sorted keys)."""
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


# Fields covered by the approval hash. Transport-level fields (delivery key,
# FHIR bundle timestamp) are excluded so retries do not change the hash.
HASHED_PACKAGE_FIELDS = (
    "referral_id", "package_version", "sender_institution", "destination_institution", "specialty",
    "priority", "reason", "planned_procedure", "procedure_known", "patient", "referring_clinician",
    "brief_sections", "medication_flags", "medication_evaluation", "evidence", "limitations",
    "checklist", "approved_by", "approved_by_id", "approved_at",
)


def package_hash(envelope: dict[str, Any]) -> str:
    approved_at = envelope.get("approved_at")
    if isinstance(approved_at, datetime):
        approved_at = approved_at.isoformat()
    payload = {k: envelope.get(k) for k in HASHED_PACKAGE_FIELDS}
    payload["approved_at"] = approved_at
    return content_hash(payload)
