"""Lab B adapter: local results/reports -> FHIR R4 Observation / DiagnosticReport."""
from __future__ import annotations

from refcommon import fhir

from .models import Patient, Report, Result

INSTITUTION = "lab-b"
LOINC = "http://loinc.org"
UCUM = "http://unitsofmeasure.org"


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


def observation(r: Result) -> dict:
    res: dict = {
        "resourceType": "Observation",
        "id": r.id,
        "meta": fhir.meta(INSTITUTION, r.version, r.updated_at),
        "status": r.status,
        "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "laboratory"}]}],
        "code": fhir.codeable(r.test_name, LOINC if r.loinc else None, r.loinc),
        "subject": fhir.patient_reference(INSTITUTION, r.patient_id),
        "effectiveDateTime": fhir.utc_iso(r.collected_at),
        "issued": fhir.utc_iso(r.resulted_at),
    }
    if r.value_num is not None:
        vq: dict = {"value": r.value_num}
        if r.unit:
            vq.update({"unit": r.unit})
        res["valueQuantity"] = vq
    elif r.value_text:
        res["valueString"] = r.value_text
    else:
        # A missing value stays explicitly missing (FR-32)
        res["dataAbsentReason"] = {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/data-absent-reason", "code": "unknown"}]}
    if r.reference_range:
        res["referenceRange"] = [{"text": r.reference_range}]
    if r.specimen:
        res["specimen"] = {"display": r.specimen}
    return res


def diagnostic_report(rep: Report, result_ids: list[str]) -> dict:
    res = {
        "resourceType": "DiagnosticReport",
        "id": rep.id,
        "meta": fhir.meta(INSTITUTION, rep.version, rep.updated_at),
        "status": rep.status,
        "code": fhir.codeable(rep.name, LOINC, rep.code),
        "subject": fhir.patient_reference(INSTITUTION, rep.patient_id),
        "effectiveDateTime": fhir.utc_iso(rep.collected_at),
        "issued": fhir.utc_iso(rep.issued_at),
        "result": [{"reference": f"Observation/{rid}"} for rid in result_ids],
    }
    if rep.conclusion:
        res["conclusion"] = rep.conclusion
    return res
