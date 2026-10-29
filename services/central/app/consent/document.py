"""The consent document the patient signs: a FHIR R4 `Consent`-shaped resource (spec v4 6.4).

The platform prepares the exact document for the patient's choices; the patient's device shows it and signs its
canonical form with the patient's signing key; the platform checks that what came back is the same document it
would have built, signed by the key in the patient's directory entry. Each adapter checks the signature again.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from refcommon import e2e

from ..models import Consent

PURPOSE_SYSTEM = "http://terminology.hl7.org/CodeSystem/v3-ActReason"
CATEGORY_SYSTEM = "urn:refx:record-category"
ORG_SYSTEM = "urn:refx:institution"
CNIC_SYSTEM = "urn:pk:nadra:cnic"
# how long the patient's permission lasts, chosen by the patient (the supervisor's 1 day / 1 week / 30 days)
DURATIONS = (1, 7, 30)
RECORD_CATEGORIES = ("conditions", "surgeries", "visits", "medications", "labs", "imaging")
SENSITIVE = {"psychiatric": "Psychiatric records", "hiv_sexual_health": "HIV and sexual-health records"}
REVOCATION_TYPE = "refx.consent.revocation/v1"


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _org(code: str) -> dict:
    return {"identifier": {"system": ORG_SYSTEM, "value": code}}


def build(c: Consent, referral_ref: str, *, custodians: list[str], sensitive: list[str], start: datetime, days: int,
          patient_signing_key_id: str) -> dict:
    recipients = [x for x in (c.requesting_org, c.destination_org) if x]
    actors = [{"role": {"text": "custodian"}, "reference": _org(x)} for x in sorted(custodians)] + \
             [{"role": {"text": "recipient"}, "reference": _org(x)} for x in recipients]
    return {
        "resourceType": "Consent", "id": c.reference, "status": "active",
        "scope": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/consentscope", "code": "patient-privacy"}]},
        "category": [{"coding": [{"system": "http://loinc.org", "code": "59284-0", "display": "Patient Consent"}]}],
        "patient": {"identifier": {"system": CNIC_SYSTEM, "value": c.patient_cnic}, "display": c.patient_name},
        "dateTime": iso(start),
        "organization": [_org(c.requesting_org)],
        "provision": {
            "type": "permit",
            "period": {"start": iso(start), "end": iso(start + timedelta(days=days))},
            "actor": actors,
            "purpose": [{"system": PURPOSE_SYSTEM, "code": c.purpose}],
            "class": [{"system": CATEGORY_SYSTEM, "code": k} for k in c.categories],
            **({"dataPeriod": {"start": c.data_period_start}} if c.data_period_start else {}),
        },
        "refx": {
            "type": "refx.consent/v1", "referral": referral_ref,
            "requesting_practitioner": c.requesting_practitioner_id,
            "sensitive_categories_specific": sorted(sensitive),
            "evidence": {"method": "patient_portal", "requested_by_staff_id": c.requested_by_id,
                         "requested_at": iso(c.requested_at)},
            "patient_signing_key_id": patient_signing_key_id,
        },
    }


def check_signed(c: Consent, doc: dict, patient_entry: dict, referral_ref: str) -> tuple[str | None, dict]:
    """(problem, choices) for a document the patient signed: it must be what build() makes for some allowed
    choice, and signed by the patient's current signing key."""
    sig_pub = patient_entry.get("sig_public_key")
    if not sig_pub or not e2e.verify_object(sig_pub, doc):
        return "the consent is not signed by your current key", {}
    try:
        prov = doc["provision"]
        custodians = [a["reference"]["identifier"]["value"] for a in prov["actor"] if a["role"]["text"] == "custodian"]
        sensitive = list(doc["refx"]["sensitive_categories_specific"])
        start = e2e.parse_iso(prov["period"]["start"])
        days = round((e2e.parse_iso(prov["period"]["end"]) - start).total_seconds() / 86400)
    except (KeyError, TypeError, ValueError):
        return "the consent document is malformed", {}
    if not custodians or not set(custodians) <= set(c.custodians_requested):
        return "choose one or more of the places that were asked", {}
    if not set(sensitive) <= set(c.sensitive_offered):
        return "a sensitive category was not part of this request", {}
    if days not in DURATIONS:
        return "choose 1 day, 1 week or 30 days", {}
    now = datetime.now(timezone.utc)
    if not now - timedelta(hours=2) <= start <= now + timedelta(minutes=5):
        return "the consent's start time is not now; prepare it again", {}
    expected = build(c, referral_ref, custodians=custodians, sensitive=sensitive, start=start, days=days,
                     patient_signing_key_id=e2e.key_id(sig_pub))
    if e2e.canonical(expected) != e2e.canonical(e2e.unsigned(doc)):
        return "the signed consent differs from the request", {}
    return None, {"custodians": custodians, "sensitive": sensitive, "start": start, "days": days}
