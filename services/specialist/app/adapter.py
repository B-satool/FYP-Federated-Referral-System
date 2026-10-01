"""Specialist C adapter.

* Local consultation history -> FHIR Encounter/Condition for authorized retrieval.
* Incoming approved referral package (project envelope + FHIR Bundle) -> local case fields.
* Approved consultation response -> FHIR Task carried inside the returned event.
"""
from __future__ import annotations

from typing import Any

from refcommon import fhir
from refcommon.exchange import PackageEnvelope, package_hash

from .models import Patient, PriorConsultation

INSTITUTION = "spec-c"


class PackageRejected(Exception):
    pass


def patient(p: Patient) -> dict:
    return {
        "resourceType": "Patient",
        "id": p.local_id,
        "meta": fhir.meta(INSTITUTION, p.version, p.updated_at),
        "identifier": [fhir.patient_identifier(INSTITUTION, p.local_id)],
        "name": [{"family": p.family, "given": [p.given], "text": f"{p.given} {p.family}"}],
        "gender": {"F": "female", "M": "male"}.get(p.sex, "unknown"),
        "birthDate": p.birth_date.isoformat(),
    }


def consultation_encounter(c: PriorConsultation) -> dict:
    return {
        "resourceType": "Encounter",
        "id": c.id,
        "meta": fhir.meta(INSTITUTION, c.version, c.updated_at),
        "status": "finished",
        "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "AMB", "display": "ambulatory"},
        "type": [fhir.codeable("Orthodontic consultation")],
        "subject": fhir.patient_reference(INSTITUTION, c.patient_id),
        "participant": [{"individual": {"display": c.clinician}}],
        "period": {"start": fhir.utc_iso(c.seen_at)},
        "reasonCode": [fhir.codeable(c.summary)],
    }


def consultation_condition(c: PriorConsultation) -> dict | None:
    if not c.diagnosis:
        return None
    return {
        "resourceType": "Condition",
        "id": f"{c.id}-dx",
        "meta": fhir.meta(INSTITUTION, c.version, c.updated_at),
        "clinicalStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": "active"}]},
        "code": fhir.codeable(c.diagnosis, "http://snomed.info/sct" if c.diagnosis_code else None, c.diagnosis_code),
        "subject": fhir.patient_reference(INSTITUTION, c.patient_id),
        "recordedDate": fhir.utc_iso(c.seen_at),
    }


def translate_package(raw: dict[str, Any]) -> tuple[PackageEnvelope, dict[str, Any]]:
    """Validate an incoming approved package and extract the local case fields.

    The specialist side re-checks approval itself: destination, approver,
    approval hash, and the ServiceRequest inside the FHIR Bundle.
    """
    env = PackageEnvelope.model_validate(raw)
    dumped = env.model_dump(mode="json")
    if env.destination_institution != INSTITUTION:
        raise PackageRejected("package is addressed to a different institution")
    if not env.approved_by or not env.approved_by_id:
        raise PackageRejected("package carries no clinician approval")
    if package_hash(dumped) != env.content_hash:
        raise PackageRejected("approval hash mismatch: content differs from the approved version")
    entries = [e.get("resource", {}) for e in env.fhir_bundle.get("entry", [])]
    service_requests = [r for r in entries if r.get("resourceType") == "ServiceRequest"]
    if len(service_requests) != 1:
        raise PackageRejected("bundle must contain exactly one ServiceRequest")
    sr = service_requests[0]
    problems = fhir.validate_resource(sr)
    if problems:
        raise PackageRejected("invalid ServiceRequest: " + "; ".join(problems))
    if sr.get("status") != "active":
        raise PackageRejected("ServiceRequest is not active (unapproved package)")

    specialist_patient_id = None
    for ident in env.patient.get("verified_links", []):
        if ident.get("institution_id") == INSTITUTION:
            specialist_patient_id = ident.get("local_patient_id")
    fields = {
        "central_referral_id": env.referral_id,
        "sender_institution": env.sender_institution,
        "patient_name": env.patient.get("name", "Unknown"),
        "patient_birth_date": env.patient.get("birth_date"),
        "specialist_patient_id": specialist_patient_id,
        "priority": env.priority,
    }
    return env, fields


def response_task(referral_id: str, response_id: int, content: dict, approved_by: str, approved_at: str) -> dict:
    return {
        "resourceType": "Task",
        "id": f"consult-response-{response_id}",
        "status": "completed",
        "intent": "order",
        "focus": {"identifier": {"system": "urn:referral-demo:referral-id", "value": referral_id}},
        "owner": {"display": f"Specialist C - {approved_by}"},
        "lastModified": approved_at,
        "output": [{
            "type": {"text": "Consultation response"},
            "valueString": "\n".join(f"{k}: {v}" for k, v in content.items() if v),
        }],
    }
