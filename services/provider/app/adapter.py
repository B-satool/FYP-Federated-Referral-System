"""Local rows -> pinned FHIR R4 subset, and incoming envelopes -> local rows.

Mappings are explicit. Original text, units and dates travel in standard elements
(text, dosageInstruction, narrative) rather than non-standard fields.
"""
from __future__ import annotations

import html
from datetime import datetime, time, timezone
from typing import Any

from refcommon import fhir
from refcommon.exchange import ReferralNotice

from .models import Condition, ImagingReport, LabResult, Medication, Patient, Surgery, Visit

SNOMED = "http://snomed.info/sct"
LOINC = "http://loinc.org"
CNIC_SYSTEM = "urn:referral-demo:identifier:pk-cnic"
INTERPRETATION = {"high": ("H", "High"), "low": ("L", "Low"), "critical": ("AA", "Critical abnormal")}


class PackageRejected(Exception):
    pass


def _narrative(text: str) -> dict:
    return {"status": "generated", "div": f'<div xmlns="http://www.w3.org/1999/xhtml">{html.escape(text)}</div>'}


def _at_noon(d) -> str | None:
    if d is None:
        return None
    return fhir.utc_iso(datetime.combine(d, time(12, 0), tzinfo=timezone.utc))


def patient(inst: str, p: Patient) -> dict:
    identifiers = [fhir.patient_identifier(inst, p.local_id)]
    if p.cnic:
        identifiers.append({"system": CNIC_SYSTEM, "value": p.cnic})
    return {
        "resourceType": "Patient",
        "id": p.local_id,
        "meta": fhir.meta(inst, p.version, p.updated_at),
        "identifier": identifiers,
        "name": [{"family": p.family, "given": p.given.split(), "text": f"{p.given} {p.family}"}],
        "gender": {"F": "female", "M": "male"}.get(p.sex, "unknown"),
        "birthDate": p.birth_date.isoformat(),
    }


def condition(inst: str, c: Condition) -> dict:
    res = {
        "resourceType": "Condition",
        "id": c.id,
        "meta": fhir.meta(inst, c.version, c.updated_at),
        "clinicalStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                                       "code": c.clinical_status}]},
        "code": fhir.codeable(c.display, SNOMED if c.snomed else None, c.snomed),
        "subject": fhir.patient_reference(inst, c.patient_id),
    }
    if c.onset:
        res["onsetString"] = c.onset
    return res


def procedure(inst: str, s: Surgery) -> dict:
    res = {
        "resourceType": "Procedure",
        "id": s.id,
        "meta": fhir.meta(inst, s.version, s.updated_at),
        "status": "completed",
        "code": fhir.codeable(s.procedure),
        "subject": fhir.patient_reference(inst, s.patient_id),
    }
    if s.performed:
        res["performedString"] = s.performed
    if s.location:
        res["location"] = {"display": s.location}
    return res


def encounter(inst: str, v: Visit) -> dict:
    res = {
        "resourceType": "Encounter",
        "id": v.id,
        "meta": fhir.meta(inst, v.version, v.updated_at),
        "status": "finished",
        "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "AMB", "display": "ambulatory"},
        "type": [fhir.codeable(v.setting)],
        "subject": fhir.patient_reference(inst, v.patient_id),
        "period": {"start": _at_noon(v.visit_date)},
        "reasonCode": [fhir.codeable(v.reason or "Not recorded")],
    }
    if v.clinician:
        res["participant"] = [{"individual": {"display": v.clinician}}]
    if v.summary:
        res["text"] = _narrative(v.summary)
    return res


def medication_request(inst: str, m: Medication) -> dict:
    dosage: dict = {"text": " ".join(x for x in [m.dose, m.frequency] if x) or "dose not recorded"}
    if m.route:
        dosage["route"] = {"text": m.route}
    if m.frequency:
        dosage["timing"] = {"code": {"text": m.frequency}}
    res = {
        "resourceType": "MedicationRequest",
        "id": m.id,
        "meta": fhir.meta(inst, m.version, m.updated_at),
        "status": {"active": "active", "stopped": "stopped", "completed": "completed"}.get(m.status, "unknown"),
        "intent": "order",
        "medicationCodeableConcept": fhir.codeable(m.name),
        "subject": fhir.patient_reference(inst, m.patient_id),
        "dosageInstruction": [dosage],
    }
    if m.start_date:
        res["authoredOn"] = _at_noon(m.start_date)
        res["dispenseRequest"] = {"validityPeriod": {"start": m.start_date.isoformat()}}
    if m.prescriber:
        res["requester"] = {"display": m.prescriber}
    notes = [n for n in [f"Brand as written: {m.brand_as_written}" if m.brand_as_written else None, m.note] if n]
    if notes:
        res["note"] = [{"text": n} for n in notes]
    return res


def observation(inst: str, r: LabResult) -> dict:
    res: dict[str, Any] = {
        "resourceType": "Observation",
        "id": r.id,
        "meta": fhir.meta(inst, r.version, r.updated_at),
        "status": r.status,
        "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category",
                                  "code": "laboratory"}]}],
        "code": fhir.codeable(r.test, LOINC if r.loinc else None, r.loinc),
        "subject": fhir.patient_reference(inst, r.patient_id),
        "effectiveDateTime": _at_noon(r.collected),
        "note": [{"text": f"Panel: {r.panel}"}] + ([{"text": r.note}] if r.note else []),
    }
    if r.value_num is not None:
        res["valueQuantity"] = {"value": r.value_num, **({"unit": r.unit} if r.unit else {})}
    elif r.value_text:
        res["valueString"] = r.value_text
    else:
        res["dataAbsentReason"] = {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/data-absent-reason",
                                               "code": "unknown"}]}
    if r.reference_range:
        res["referenceRange"] = [{"text": r.reference_range}]
    interp = INTERPRETATION.get((r.abnormal_flag or "").lower())
    if interp:
        res["interpretation"] = [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation",
                                              "code": interp[0], "display": interp[1]}]}]
    return res


def imaging_report(inst: str, i: ImagingReport) -> dict:
    res = {
        "resourceType": "DiagnosticReport",
        "id": i.id,
        "meta": fhir.meta(inst, i.version, i.updated_at),
        "status": "final",
        "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/v2-0074", "code": "RAD",
                                  "display": "Radiology"}]}],
        "code": fhir.codeable(i.study),
        "subject": fhir.patient_reference(inst, i.patient_id),
        "effectiveDateTime": _at_noon(i.study_date),
        "conclusion": i.impression or None,
    }
    if i.findings:
        res["text"] = _narrative(i.findings)
    if i.reporter:
        res["resultsInterpreter"] = [{"display": i.reporter}]
    if res["conclusion"] is None:
        del res["conclusion"]
    return res


TITLE_KEYS = ("item_id", "kind", "category", "label", "date", "source_institution", "sensitive")


def translate_notice(inst: str, raw: dict[str, Any]) -> tuple[ReferralNotice, dict[str, Any]]:
    """Validate an incoming referral notice (spec v4, approval A4) and extract the local case fields.

    A notice carries administrative data and record titles only. The receiving side checks the addressee, that the
    sender and the signer are named, and that the titles hold nothing but title fields: content never reaches this
    system (the department's doctors open the ciphertext from the platform on their own devices; D2)."""
    env = ReferralNotice.model_validate(raw)
    if env.destination_institution != inst:
        raise PackageRejected("notice is addressed to a different institution")
    if not env.sent_by or not env.requesting_doctor.get("name") or not env.signed_by.get("subject_id"):
        raise PackageRejected("notice does not record the requesting doctor, the signer and the sender")
    if len(env.manifest_sha256) != 64:
        raise PackageRejected("notice has no signed manifest hash")
    if any(set(t) - set(TITLE_KEYS) for t in env.titles):
        raise PackageRejected("a record title carries more than title fields")
    local_id = env.patient.get("local_patient_id")
    fields = {
        "central_referral_id": env.referral_id,
        "sender_institution": env.sender_institution,
        "sender_name": env.sender_name or env.requesting_doctor.get("institution", env.sender_institution),
        "department": env.destination_department,
        "requested_doctor": env.destination_doctor,
        "patient_name": env.patient.get("name", "Unknown"),
        "patient_birth_date": env.patient.get("birth_date"),
        "patient_sex": env.patient.get("sex"),
        "patient_cnic": env.patient.get("cnic"),
        "local_patient_id": local_id,
        "link_request_id": env.patient.get("link_request_id"),
        "urgency": env.urgency,
    }
    return env, fields


def response_task(inst_name: str, referral_id: str, response_id: int, content: dict, by: str, at: str) -> dict:
    return {
        "resourceType": "Task",
        "id": f"consult-response-{response_id}",
        "status": "completed",
        "intent": "order",
        "focus": {"identifier": {"system": "urn:referral-demo:referral-id", "value": referral_id}},
        "owner": {"display": f"{inst_name} - {by}"},
        "lastModified": at,
        "output": [{"type": {"text": "Consultation response"},
                    "valueString": "\n".join(f"{k}: {v}" for k, v in content.items() if v)}],
    }
