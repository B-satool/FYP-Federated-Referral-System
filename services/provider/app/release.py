"""Releasing a referral's records, encrypted, under consent and this institution's policy (spec v4 5.6, 6).

In order, for every request from the platform:
1. the signed request assertion is verified (m2m.verify_hub): platform key, audience, expiry, replay;
2. the claims are checked: the requesting organisation is a participant in good standing, the purpose is allowed
   by the participation agreement, and the request links a consent;
3. the consent is fetched through that link and checked here, not taken from the platform's word: signed by the
   patient's key, that key's entry signed by the platform's pinned key, the CNIC is this patient's, it names this
   institution as a custodian and the requester as a recipient, the purpose matches, and it is in force;
4. this institution's policy decides (policy.evaluate): answer, structured refusal, or the staff review queue;
5. the released records are encrypted with a fresh data key for this batch; the data key is wrapped to the
   requesting doctor's key (hospital signature verified against the pinned key first) and to the patient's key.
Only titles leave in plain text, and sensitive titles are masked.
"""
from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone

from refcommon import e2e
from refcommon.exchange import record_title
from refcommon.participants import PLATFORM_ID, registry
from refcommon.sourcekit import record_audit
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import adapter, m2m, policy
from .config import INSTITUTION, INSTITUTION_NAME
from .models import AuditEvent, Condition, ImagingReport, LabResult, Medication, Patient, RecordRequest, Surgery, Visit

KINDS = {"condition": "other", "surgery": "other", "visit": "note", "medication": "prescription", "lab": "lab",
         "imaging": "imaging"}
RESTRICTED = "Restricted record"


def actor(claims: dict) -> tuple[str, str, str]:
    return (PLATFORM_ID, "central platform (signed request)", "central-platform")


# --------------------------------------------------------------------------- checks
def check_claims(claims: dict) -> str | None:
    refx = claims.get("refx") or {}
    org = registry.institution(refx.get("org"))
    if org is None or not org.in_good_standing:
        return "the requesting organisation is not a participant in good standing"
    if refx.get("purpose") not in registry.allowed_purposes():
        return f"purpose {refx.get('purpose')!r} is not allowed by the participation agreement"
    if not refx.get("consent") or not refx.get("referral") or not refx.get("practitioner"):
        return "the request does not link a consent, a referral and the requesting doctor"
    return None


def check_practitioner(entry: dict | None, claims: dict) -> str | None:
    """The requesting doctor's key: signed by their own hospital's pinned key, and the doctor the assertion names."""
    refx = claims.get("refx") or {}
    if not entry:
        return "the requesting doctor has no key in the directory"
    if entry.get("subject_id") != refx.get("practitioner") or entry.get("hospital_id") != refx.get("org") \
            or entry.get("subject_type") != "doctor":
        return "the doctor's key does not belong to the requesting doctor"
    pinned = registry.issuer_key(entry.get("hospital_id"))
    problem = e2e.check_entry(entry, pinned) if pinned else "the doctor's hospital is not onboarded"
    return f"doctor's key refused: {problem}" if problem else None


def check_patient_entry(entry: dict | None, patient: Patient) -> bool:
    if not entry:
        return False
    pinned = registry.platform_key()
    return bool(pinned) and e2e.check_entry(entry, pinned) is None and entry.get("issued_by") == PLATFORM_ID \
        and entry.get("subject_type") == "patient" and entry.get("patient_cnic") == patient.cnic


def fetch_consent(db: Session, reference: str, patient: Patient, claims: dict) -> tuple[dict | None, str | None]:
    """The consent document, verified here. (None, problem) if it cannot be relied on. Problems that mean
    'out of range' start with 'consent ' (mapped to consent_expired_or_out_of_range)."""
    try:
        resp = m2m.hub_call(db, "GET", f"/e2e/adapter/consents/{reference}")
    except Exception:  # noqa: BLE001 - the link cannot be followed
        return None, "the consent link could not be followed"
    if resp.status_code != 200:
        return None, "the consent link does not lead to a signed consent naming this institution"
    body = resp.json()
    doc, entry = body.get("document") or {}, body.get("patient_entry")
    refx = claims.get("refx") or {}
    pinned = registry.platform_key()
    if not entry or not pinned or e2e.check_entry(entry, pinned, at=e2e.parse_iso(doc.get("dateTime", e2e.now_iso()))):
        return None, "the patient's key is not signed by the platform"
    if entry.get("patient_cnic") != patient.cnic or \
            ((doc.get("patient") or {}).get("identifier") or {}).get("value") != patient.cnic:
        return None, "the consent is for a different patient"
    if not entry.get("sig_public_key") or not e2e.verify_object(entry["sig_public_key"], doc):
        return None, "the consent is not signed by the patient"
    if body.get("status") == "revoked" or body.get("revocation"):
        rev = body.get("revocation") or {}
        if rev and not e2e.verify_object(entry["sig_public_key"], rev):
            return None, "the consent's revocation is not signed by the patient"
        return None, "consent revoked by the patient"
    prov = doc.get("provision") or {}
    now = datetime.now(timezone.utc)
    try:
        start, end = e2e.parse_iso(prov["period"]["start"]), e2e.parse_iso(prov["period"]["end"])
    except (KeyError, TypeError, ValueError):
        return None, "the consent has no valid period"
    if now < start:
        return None, "consent not in force yet"
    if now > end:
        return None, "consent expired"
    actors = [(a["role"]["text"], a["reference"]["identifier"]["value"]) for a in prov.get("actor") or []]
    if ("custodian", INSTITUTION) not in actors:
        return None, "consent does not name this institution"
    if ("recipient", refx.get("org")) not in actors:
        return None, "consent does not name the requesting organisation"
    if refx.get("purpose") not in [p.get("code") for p in prov.get("purpose") or []]:
        return None, "consent does not cover this purpose"
    if (doc.get("refx") or {}).get("referral") != refx.get("referral") or doc.get("id") != refx.get("consent"):
        return None, "consent is for another referral"
    return doc, None


# --------------------------------------------------------------------------- collection
def _iso(d) -> str | None:
    return d.isoformat() if isinstance(d, date) else d


def collect(db: Session, local_id: str, d: policy.Decision) -> tuple[list[dict], int]:
    """(released records, how many sensitive records were left out). Each record: category, date, title, content."""
    since = date.fromisoformat(d.since) if d.since else None
    out: list[dict] = []
    held_back = 0

    def take(category: str, row, record: dict, resource: dict, when: str | None, title_name: dict) -> None:
        nonlocal held_back
        cat_key = {"condition": "conditions", "surgery": "surgeries", "visit": "visits", "medication": "medications",
                   "lab": "labs", "imaging": "imaging"}[category]
        sens = getattr(row, "sensitive_category", None)
        if sens:
            if sens not in d.sensitive:
                held_back += 1
                return
        elif cat_key not in d.categories:
            return
        out.append({"category": category, "sensitive": sens, "date": when, "row_id": row.id,
                    "title": record_title(category, title_name), "record": record, "fhir": resource})

    for c in db.scalars(select(Condition).where(Condition.patient_id == local_id,
                                                Condition.clinical_status != "entered-in-error")):
        take("condition", c, {"display": c.display, "status": c.clinical_status, "onset": c.onset},
             adapter.condition(INSTITUTION, c), c.onset, {})
    for s in db.scalars(select(Surgery).where(Surgery.patient_id == local_id)):
        take("surgery", s, {"procedure": s.procedure, "performed": s.performed, "location": s.location},
             adapter.procedure(INSTITUTION, s), s.performed, {})
    for v in db.scalars(select(Visit).where(Visit.patient_id == local_id).order_by(Visit.visit_date.desc())):
        if since and v.visit_date < since:
            continue
        take("visit", v, {"date": _iso(v.visit_date), "setting": v.setting, "clinician": v.clinician,
                          "reason": v.reason, "summary": v.summary},
             adapter.encounter(INSTITUTION, v), _iso(v.visit_date), {"setting": v.setting})
    for m in db.scalars(select(Medication).where(Medication.patient_id == local_id, Medication.status == "active")):
        take("medication", m, {"name": m.name, "brand": m.brand_as_written, "dose": m.dose, "route": m.route,
                               "frequency": m.frequency, "start_date": _iso(m.start_date), "status": m.status,
                               "prescriber": m.prescriber, "note": m.note},
             adapter.medication_request(INSTITUTION, m), _iso(m.start_date), {})
    latest: dict[str, LabResult] = {}
    for r in db.scalars(select(LabResult).where(LabResult.patient_id == local_id)
                        .order_by(LabResult.collected.desc(), LabResult.id)):
        if since and r.collected < since:
            continue
        latest.setdefault((r.loinc or r.test).lower(), r)
    for r in latest.values():
        value = r.value_text if r.value_num is None else f"{r.value_num:g}"
        take("lab", r, {"date": _iso(r.collected), "panel": r.panel, "test": r.test, "value": value, "unit": r.unit,
                        "reference_range": r.reference_range, "flag": r.abnormal_flag, "note": r.note},
             adapter.observation(INSTITUTION, r), _iso(r.collected), {"test": r.test})
    for i in db.scalars(select(ImagingReport).where(ImagingReport.patient_id == local_id)):
        if since and i.study_date < since:
            continue
        take("imaging", i, {"date": _iso(i.study_date), "study": i.study, "body_part": i.body_part,
                            "findings": i.findings, "impression": i.impression, "reporter": i.reporter},
             adapter.imaging_report(INSTITUTION, i), _iso(i.study_date), {"study": i.study})
    return out, held_back


def build_batch(referral_ref: str, records: list[dict], recipients: list[tuple[str, dict]],
                mask_sensitive: bool = True) -> dict:
    """Encrypt the records with a fresh data key and wrap it to each recipient. Returns titles, ciphertext and
    wrapped keys; the data key itself is discarded when this returns."""
    batch_id = f"{INSTITUTION}-{uuid.uuid4().hex[:12]}"
    dek = e2e.new_dek()
    items = []
    for n, rec in enumerate(records, 1):
        item_id = f"{INSTITUTION}:{rec['row_id']}"
        masked = mask_sensitive and bool(rec["sensitive"])
        title = {"item_id": item_id, "kind": "other" if masked else KINDS[rec["category"]],
                 "category": "restricted" if masked else rec["category"],
                 "label": RESTRICTED if masked else rec["title"], "date": rec["date"],
                 "source_institution": INSTITUTION, "sensitive": masked}
        content = {"type": "refx.item/v1", "item_id": item_id, "category": rec["category"], "label": rec["title"],
                   "date": rec["date"], "source_institution": INSTITUTION, "source_name": INSTITUTION_NAME,
                   "sensitive_category": rec["sensitive"], "record": rec["record"], "fhir": rec["fhir"]}
        sealed = e2e.encrypt(dek, json.dumps(content, ensure_ascii=False).encode("utf-8"),
                             e2e.item_aad(referral_ref, item_id, batch_id))
        items.append({"title": title, "sealed": sealed, "order": n})
    wraps = []
    for kind, entry in recipients:
        kid = entry["enc_key_id"]
        wraps.append({"recipient_type": kind, "recipient_subject": entry["subject_id"], "recipient_key_id": kid,
                      "key_version": entry.get("key_version"),
                      "wrapped": e2e.wrap(entry["enc_public_key"], dek, e2e.wrap_context(referral_ref, batch_id, kid))})
    return {"batch_id": batch_id, "suite": e2e.SUITE, "items": items, "wraps": wraps}


# --------------------------------------------------------------------------- the whole answer
def answer(db: Session, req: RecordRequest, claims: dict, manual_approved: bool = False) -> dict:
    """Decide and, if released, encrypt. Updates the request row and audits; the caller commits."""
    pol = policy.load()
    patient = db.get(Patient, req.local_patient_id) if req.local_patient_id else None
    request = {"referral": req.referral_ref, "local_patient_id": req.local_patient_id if patient else None,
               "purpose": req.purpose, "categories": req.categories, "sensitive": req.sensitive, "since": req.since}
    if patient is None:
        decision = policy.Decision(status="refused", policy_version=f"{pol.get('version')}#{pol.get('hash')}")
        decision.refuse("request_incomplete_or_invalid", message=f"{INSTITUTION_NAME} has no such patient record")
        doc = None
    else:
        problem = check_practitioner(req.practitioner_entry, claims)
        if problem:
            record_audit(db, AuditEvent, None, "directory.signature_failure", "doctor_key",
                         str((req.practitioner_entry or {}).get("subject_id")), "denied", req.referral_ref,
                         {"reason": problem}, actor_override=actor(claims))
            doc, consent_problem = None, problem
        else:
            doc, consent_problem = fetch_consent(db, req.consent_ref, patient, claims)
        decision = policy.evaluate(pol, request, doc, consent_problem, manual_approved=manual_approved)
    req.policy_version, req.refusals = decision.policy_version, decision.refusals
    result: dict = {"request_key": req.request_key, "policy_version": decision.policy_version,
                    "refusals": decision.refusals, "notes": [], "batch": None}
    if decision.status == "pending":
        req.status = "pending_manual_review"
    elif decision.status == "refused":
        req.status = "refused"
    else:
        records, held_back = collect(db, req.local_patient_id, decision)
        if held_back:
            result["notes"].append("Records in sensitive categories are released only with the patient's specific "
                                   "consent; any such records were not included.")
        recipients = [("doctor", req.practitioner_entry)]
        if check_patient_entry(req.patient_entry, patient):
            recipients.append(("patient", req.patient_entry))
        else:
            result["notes"].append("The patient has no verified key yet, so the patient's own copy was not prepared.")
        if records:
            result["batch"] = build_batch(req.referral_ref, records, recipients, pol.get("sensitive_title_masking", True))
        req.item_count = len(records)
        req.status = ("partial" if decision.refusals else "answered") if records else \
            ("partial" if decision.refusals else "no_records")
    result["status"] = req.status
    req.decided_at = datetime.now(timezone.utc)
    outcome = "pending" if req.status == "pending_manual_review" else req.status
    record_audit(db, AuditEvent, None, "records.request", "patient", req.local_patient_id or "?", outcome,
                 req.referral_ref, {"requesting_org": req.requesting_org, "practitioner": req.practitioner_id,
                                    "purpose": req.purpose, "consent": req.consent_ref,
                                    "reasons": [r["reason"] for r in decision.refusals], "items": req.item_count,
                                    "policy": decision.policy_version, "manual": manual_approved},
                 actor_override=actor(claims))
    return result
