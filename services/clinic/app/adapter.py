"""Clinic A adapter: local SQL rows -> pinned FHIR R4 subset.

Mappings are explicit and source-specific. Original text, units and dates are
carried in standard elements (text, dosageInstruction, period) rather than by
adding non-standard fields.
"""
from __future__ import annotations

from datetime import datetime, time, timezone

from refcommon import fhir

from .models import Condition, Encounter, Patient, Prescription, ReportedMedication, SourceDocument

INSTITUTION = "clinic-a"
SNOMED = "http://snomed.info/sct"


def _dt(d) -> str | None:
    if d is None:
        return None
    if isinstance(d, datetime):
        return fhir.utc_iso(d)
    return d.isoformat()


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


def encounter(e: Encounter) -> dict:
    return {
        "resourceType": "Encounter",
        "id": e.id,
        "meta": fhir.meta(INSTITUTION, e.version, e.updated_at),
        "status": e.status,
        "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "AMB", "display": "ambulatory"},
        "type": [fhir.codeable(e.type_text)],
        "subject": fhir.patient_reference(INSTITUTION, e.patient_id),
        "participant": [{"individual": {"display": e.practitioner}}],
        "period": {"start": _dt(e.start)},
        "reasonCode": [fhir.codeable(e.reason_text)],
    }


def condition(c: Condition) -> dict:
    return {
        "resourceType": "Condition",
        "id": c.id,
        "meta": fhir.meta(INSTITUTION, c.version, c.updated_at),
        "clinicalStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": c.clinical_status}]},
        "code": fhir.codeable(c.display, c.code_system, c.code),
        "subject": fhir.patient_reference(INSTITUTION, c.patient_id),
        **({"onsetDateTime": _dt(c.onset)} if c.onset else {}),
        "recordedDate": _dt(c.recorded),
    }


def medication_request(m: Prescription) -> dict:
    dosage: dict = {"text": m.dose_text or ""}
    if m.route:
        dosage["route"] = {"text": m.route}
    if m.frequency:
        dosage["timing"] = {"code": {"text": m.frequency}}
    if m.dose_value is not None:
        dosage["doseAndRate"] = [{"doseQuantity": {"value": m.dose_value, "unit": m.dose_unit or ""}}]
    period: dict = {}
    if m.start_date:
        period["start"] = _dt(m.start_date)
    if m.end_date:
        period["end"] = _dt(m.end_date)
    res = {
        "resourceType": "MedicationRequest",
        "id": m.id,
        "meta": fhir.meta(INSTITUTION, m.version, m.updated_at),
        "status": m.status,
        "intent": "order",
        "medicationCodeableConcept": fhir.codeable(m.medication_text),
        "subject": fhir.patient_reference(INSTITUTION, m.patient_id),
        "authoredOn": _dt(datetime.combine(m.start_date, time(9, 0), tzinfo=timezone.utc)) if m.start_date else None,
        "requester": {"display": m.prescriber},
        "dosageInstruction": [dosage],
    }
    if period:
        res["dispenseRequest"] = {"validityPeriod": period}
    if m.note:
        res["note"] = [{"text": m.note}]
    if res["authoredOn"] is None:
        del res["authoredOn"]
    return res


def medication_statement(m: ReportedMedication) -> dict:
    res = {
        "resourceType": "MedicationStatement",
        "id": m.id,
        "meta": fhir.meta(INSTITUTION, m.version, m.updated_at),
        "status": m.status,
        "medicationCodeableConcept": fhir.codeable(m.medication_text),
        "subject": fhir.patient_reference(INSTITUTION, m.patient_id),
        "dateAsserted": _dt(m.reported_on),
        "informationSource": {"reference": f"Patient/{m.patient_id}"},
        "dosage": [{"text": m.dose_text or ""}],
    }
    notes = [n for n in [m.note, f"Recorded by {m.recorded_by}"] if n]
    res["note"] = [{"text": n} for n in notes]
    return res


def document_reference(d: SourceDocument) -> dict:
    return {
        "resourceType": "DocumentReference",
        "id": d.id,
        "meta": fhir.meta(INSTITUTION, d.version, d.updated_at),
        "status": "current",
        "type": fhir.codeable(d.doc_type),
        "subject": fhir.patient_reference(INSTITUTION, d.patient_id),
        "date": _dt(datetime.combine(d.doc_date, time(12, 0), tzinfo=timezone.utc)),
        "author": [{"display": d.author}],
        "description": d.title,
        "content": [{"attachment": {"contentType": d.content_type, "title": d.title}}],
    }
