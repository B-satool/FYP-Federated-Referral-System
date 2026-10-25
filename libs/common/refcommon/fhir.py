"""Pinned, deliberately limited FHIR R4 (4.0.1) exchange subset.

These structural checks protect the importer from malformed source output.
They are NOT a FHIR conformance claim: representative resources are validated
with the official HL7 validator (scripts/fhir-validate.ps1).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

FHIR_VERSION = "4.0.1"
SUBSET_VERSION = "referral-fhir-subset/1.0"

# Identifier system per institution: a local patient ID is only meaningful
# together with its institution (FR-06).
INSTITUTION_SYSTEM = "urn:referral-demo:institution:{institution_id}:patient-id"
RECORD_SYSTEM = "urn:referral-demo:institution:{institution_id}:record"

SUPPORTED_RESOURCES: dict[str, dict[str, Any]] = {
    "Patient": {"required": ["identifier"]},
    "Organization": {"required": ["identifier", "name"]},
    "Encounter": {
        "required": ["status", "class", "subject"],
        "status": {"planned", "arrived", "triaged", "in-progress", "onleave", "finished", "cancelled", "entered-in-error", "unknown"},
    },
    "Condition": {"required": ["code", "subject"]},
    "Procedure": {
        "required": ["status", "code", "subject"],
        "status": {"preparation", "in-progress", "not-done", "on-hold", "stopped", "completed", "entered-in-error", "unknown"},
    },
    "Observation": {
        "required": ["status", "code", "subject"],
        "status": {"registered", "preliminary", "final", "amended", "corrected", "cancelled", "entered-in-error", "unknown"},
        "one_of": ["valueQuantity", "valueString", "valueCodeableConcept", "dataAbsentReason"],
    },
    "DiagnosticReport": {
        "required": ["status", "code", "subject"],
        "status": {"registered", "partial", "preliminary", "final", "amended", "corrected", "appended", "cancelled", "entered-in-error", "unknown"},
    },
    "MedicationRequest": {
        "required": ["status", "intent", "medicationCodeableConcept", "subject"],
        "status": {"active", "on-hold", "cancelled", "completed", "entered-in-error", "stopped", "draft", "unknown"},
    },
    "MedicationStatement": {
        "required": ["status", "medicationCodeableConcept", "subject"],
        "status": {"active", "completed", "entered-in-error", "intended", "stopped", "on-hold", "unknown", "not-taken"},
    },
    "DocumentReference": {
        "required": ["status", "content"],
        "status": {"current", "superseded", "entered-in-error"},
    },
    "Provenance": {"required": ["target", "recorded", "agent"]},
    "ServiceRequest": {
        "required": ["status", "intent", "subject"],
        "status": {"draft", "active", "on-hold", "revoked", "completed", "entered-in-error", "unknown"},
    },
    "Task": {
        "required": ["status", "intent"],
        "status": {"draft", "requested", "received", "accepted", "rejected", "ready", "cancelled", "in-progress", "on-hold", "failed", "completed", "entered-in-error"},
    },
}

CLINICAL_RESOURCES = {"Encounter", "Condition", "Procedure", "Observation", "DiagnosticReport", "MedicationRequest",
                      "MedicationStatement", "DocumentReference"}

# Explicit application-status -> FHIR mapping (never implicit).
REFERRAL_STATUS_TO_SERVICE_REQUEST = {
    "draft": "draft",
    "requested": "draft",
    "submitted": "active",
    "acknowledged": "active",
    "accepted": "active",
    "response_returned": "active",
    "followup_pending": "active",
    "closed": "completed",
    "declined": "revoked",
    "cancelled": "revoked",
}
REFERRAL_STATUS_TO_TASK = {
    "submitted": "requested",
    "acknowledged": "received",
    "accepted": "accepted",
    "response_returned": "completed",
    "followup_pending": "completed",
    "closed": "completed",
    "declined": "rejected",
    "cancelled": "cancelled",
}


def utc_iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def patient_identifier(institution_id: str, local_id: str) -> dict:
    return {"system": INSTITUTION_SYSTEM.format(institution_id=institution_id), "value": local_id}


def patient_reference(institution_id: str, local_id: str) -> dict:
    return {"reference": f"Patient/{local_id}", "identifier": patient_identifier(institution_id, local_id)}


def meta(institution_id: str, version: int | str, last_updated: datetime | None) -> dict:
    out = {"versionId": str(version), "source": f"urn:referral-demo:institution:{institution_id}"}
    if last_updated:
        out["lastUpdated"] = utc_iso(last_updated)
    return out


def codeable(text: str, system: str | None = None, code: str | None = None, display: str | None = None) -> dict:
    out: dict[str, Any] = {"text": text}
    if system and code:
        out["coding"] = [{"system": system, "code": code, "display": display or text}]
    return out


def validate_resource(resource: Any) -> list[str]:
    """Return a list of problems; an empty list means the resource passed the subset checks."""
    problems: list[str] = []
    if not isinstance(resource, dict):
        return ["resource is not a JSON object"]
    rtype = resource.get("resourceType")
    spec = SUPPORTED_RESOURCES.get(rtype or "")
    if spec is None:
        return [f"unsupported resourceType {rtype!r}"]
    if not resource.get("id"):
        problems.append("missing id")
    for name in spec.get("required", []):
        if resource.get(name) in (None, "", [], {}):
            problems.append(f"{rtype}.{name} is required")
    allowed_status = spec.get("status")
    if allowed_status and resource.get("status") not in allowed_status:
        problems.append(f"{rtype}.status {resource.get('status')!r} is not a valid R4 code")
    one_of = spec.get("one_of")
    if one_of and not any(resource.get(k) not in (None, "", {}) for k in one_of):
        problems.append(f"{rtype} needs one of {', '.join(one_of)}")
    if rtype in CLINICAL_RESOURCES:
        meta_block = resource.get("meta") or {}
        if not meta_block.get("versionId"):
            problems.append(f"{rtype}.meta.versionId is required by the project subset (record version)")
    if "valueQuantity" in resource:
        vq = resource["valueQuantity"]
        if not isinstance(vq, dict) or not isinstance(vq.get("value"), (int, float)):
            problems.append("Observation.valueQuantity.value must be numeric")
    return problems


BASE_URL = "https://{institution_id}.referral-demo.example/fhir"


def base_url(institution_id: str) -> str:
    return BASE_URL.format(institution_id=institution_id)


def _origin(resource: dict, default: str) -> str:
    source = (resource.get("meta") or {}).get("source", "")
    prefix = "urn:referral-demo:institution:"
    return source[len(prefix):] if source.startswith(prefix) else default


def full_url(resource: dict, default_institution: str) -> str:
    """RESTful fullUrl so relative references (e.g. Patient/MR-102) resolve inside the Bundle
    against the originating institution's base (FHIR Bundle reference-resolution rules)."""
    return f"{base_url(_origin(resource, default_institution))}/{resource['resourceType']}/{resource['id']}"


def bundle(resources: list[dict], bundle_type: str = "collection", bundle_id: str | None = None,
           institution_id: str = "central-platform", self_link: str | None = None) -> dict:
    out: dict[str, Any] = {
        "resourceType": "Bundle",
        "type": bundle_type,
        "timestamp": utc_iso(datetime.now(timezone.utc)),
        "entry": [{"fullUrl": full_url(r, institution_id), "resource": r} for r in resources],
    }
    if bundle_type == "searchset":
        out["total"] = len(resources)
        out["link"] = [{"relation": "self", "url": self_link or base_url(institution_id)}]
    if bundle_id:
        out["id"] = bundle_id
    return out


def operation_outcome(severity: str, code: str, text: str) -> dict:
    return {
        "resourceType": "OperationOutcome",
        "issue": [{"severity": severity, "code": code, "diagnostics": text}],
    }
