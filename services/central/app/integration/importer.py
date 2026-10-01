"""Central importer: validated FHIR subset resources -> EvidenceItem fields.

Original values, units, codes and clinical dates are preserved in `original`;
nothing is normalised away. Unknown or invalid resources are counted and
reported, never silently dropped.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from refcommon import fhir

# Categories pre-selected for the referral brief (clinician can change selection).
DEFAULT_SELECTED = {"medication", "lab", "condition", "consultation"}


@dataclass
class Mapped:
    record_type: str
    record_id: str
    version: str
    category: str
    display: str
    original: dict[str, Any]
    clinical_time: datetime | None
    resource: dict


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        if len(value) == 10:
            return datetime.fromisoformat(value + "T00:00:00+00:00")
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _text(cc: dict | None) -> str:
    if not cc:
        return ""
    if cc.get("text"):
        return cc["text"]
    for c in cc.get("coding", []):
        if c.get("display") or c.get("code"):
            return c.get("display") or c.get("code")
    return ""


def _coding(cc: dict | None) -> list[dict]:
    return list((cc or {}).get("coding", []))


def map_resource(res: dict) -> Mapped | None:
    rtype = res["resourceType"]
    rid = str(res["id"])
    version = str((res.get("meta") or {}).get("versionId", "1"))

    if rtype == "Patient":
        name = (res.get("name") or [{}])[0]
        display = name.get("text") or " ".join(name.get("given", []) + [name.get("family", "")])
        original = {"name": display, "birth_date": res.get("birthDate"), "gender": res.get("gender"),
                    "identifier": res.get("identifier")}
        return Mapped(rtype, rid, version, "demographics", f"Patient: {display} (born {res.get('birthDate')})",
                      original, None, res)

    if rtype == "Encounter":
        type_text = _text((res.get("type") or [{}])[0])
        reason = _text((res.get("reasonCode") or [{}])[0])
        start = (res.get("period") or {}).get("start")
        practitioner = ((res.get("participant") or [{}])[0].get("individual") or {}).get("display")
        cat = "consultation" if "orthodont" in type_text.lower() else "encounter"
        return Mapped(rtype, rid, version, cat, f"{type_text}: {reason}".strip(": "),
                      {"type": type_text, "reason": reason, "start": start, "practitioner": practitioner,
                       "status": res.get("status")}, _parse_time(start), res)

    if rtype == "Condition":
        code = res.get("code")
        status = ((res.get("clinicalStatus") or {}).get("coding") or [{}])[0].get("code")
        onset = res.get("onsetDateTime")
        recorded = res.get("recordedDate")
        return Mapped(rtype, rid, version, "condition", f"{_text(code)} ({status or 'status not recorded'})",
                      {"condition": _text(code), "coding": _coding(code), "clinical_status": status,
                       "onset": onset, "recorded": recorded}, _parse_time(onset or recorded), res)

    if rtype == "Observation":
        code = res.get("code")
        value_display: str
        original: dict[str, Any] = {"test": _text(code), "coding": _coding(code), "status": res.get("status"),
                                    "collected": res.get("effectiveDateTime"), "issued": res.get("issued"),
                                    "reference_range": ((res.get("referenceRange") or [{}])[0]).get("text"),
                                    "specimen": (res.get("specimen") or {}).get("display")}
        if "valueQuantity" in res:
            vq = res["valueQuantity"]
            original.update({"value": vq.get("value"), "unit": vq.get("unit")})
            value_display = f"{vq.get('value')} {vq.get('unit') or '(unit not recorded)'}"
        elif "valueString" in res:
            original.update({"value_text": res["valueString"], "unit": None})
            value_display = res["valueString"]
        else:
            original.update({"value": None, "unit": None, "data_absent": True})
            value_display = "value not recorded"
        return Mapped(rtype, rid, version, "lab", f"{_text(code)}: {value_display} ({res.get('status')})",
                      original, _parse_time(res.get("effectiveDateTime")), res)

    if rtype == "DiagnosticReport":
        code = res.get("code")
        conclusion = res.get("conclusion")
        return Mapped(rtype, rid, version, "lab_report",
                      f"{_text(code)} report ({res.get('status')})" + (f": {conclusion}" if conclusion else ""),
                      {"report": _text(code), "status": res.get("status"), "conclusion": conclusion,
                       "collected": res.get("effectiveDateTime"), "issued": res.get("issued"),
                       "results": [r.get("reference") for r in res.get("result", [])]},
                      _parse_time(res.get("effectiveDateTime")), res)

    if rtype == "MedicationRequest":
        med = _text(res.get("medicationCodeableConcept"))
        dosage = (res.get("dosageInstruction") or [{}])[0]
        period = (res.get("dispenseRequest") or {}).get("validityPeriod") or {}
        dq = ((dosage.get("doseAndRate") or [{}])[0]).get("doseQuantity") or {}
        original = {
            "medication": med, "record_kind": "prescription", "status": res.get("status"),
            "dosage_text": dosage.get("text") or None, "route": (dosage.get("route") or {}).get("text"),
            "frequency": ((dosage.get("timing") or {}).get("code") or {}).get("text"),
            "dose_value": dq.get("value"), "dose_unit": dq.get("unit"),
            "start": period.get("start"), "end": period.get("end"), "authored_on": res.get("authoredOn"),
            "prescriber": (res.get("requester") or {}).get("display"),
            "note": "; ".join(n.get("text", "") for n in res.get("note", [])) or None,
        }
        return Mapped(rtype, rid, version, "medication",
                      f"{med} - {original['dosage_text'] or 'dose not recorded'} (prescription {res.get('status')})",
                      original, _parse_time(res.get("authoredOn") or period.get("start")), res)

    if rtype == "MedicationStatement":
        med = _text(res.get("medicationCodeableConcept"))
        dosage = (res.get("dosage") or [{}])[0]
        original = {
            "medication": med, "record_kind": "reported", "status": res.get("status"),
            "dosage_text": dosage.get("text") or None, "date_asserted": res.get("dateAsserted"),
            "note": "; ".join(n.get("text", "") for n in res.get("note", [])) or None,
        }
        return Mapped(rtype, rid, version, "medication",
                      f"{med} - {original['dosage_text'] or 'dose not recorded'} (reported use, status {res.get('status')})",
                      original, _parse_time(res.get("dateAsserted")), res)

    if rtype == "DocumentReference":
        return Mapped(rtype, rid, version, "document",
                      f"Source document: {res.get('description') or _text(res.get('type'))}",
                      {"type": _text(res.get("type")), "description": res.get("description"), "date": res.get("date"),
                       "author": ((res.get("author") or [{}])[0]).get("display")},
                      _parse_time(res.get("date")), res)
    return None


def parse_bundle(bundle: dict) -> tuple[list[Mapped], list[dict]]:
    """Return (mapped resources, invalid entries with reasons)."""
    mapped: list[Mapped] = []
    invalid: list[dict] = []
    for entry in bundle.get("entry", []):
        res = entry.get("resource")
        if not isinstance(res, dict) or res.get("resourceType") == "OperationOutcome":
            continue
        problems = fhir.validate_resource(res)
        if problems:
            invalid.append({"resourceType": res.get("resourceType"), "id": res.get("id"), "problems": problems})
            continue
        m = map_resource(res)
        if m is None:
            invalid.append({"resourceType": res.get("resourceType"), "id": res.get("id"),
                            "problems": ["resource type not used by the referral evidence model"]})
            continue
        mapped.append(m)
    return mapped, invalid
