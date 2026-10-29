"""Consent API (spec v4 6.4; T-CONSENT-1).

* Staff at the referring institution request consent for a referral. They choose which places are asked to
  release records; they cannot grant, edit or approve a consent.
* The patient answers in the patient portal: grant (all or some of the places, any sensitive category named
  specifically, for 1 day, 1 week or 30 days), decline, or later revoke. Granting and revoking are signed with
  the patient's own key; the signature is checked here and again by every institution that releases records.
* Adapters fetch the signed consent through the link in the request assertion (signed request, see docs/auth.md).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from refcommon import e2e
from refcommon.auth import Principal
from refcommon.participants import registry
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import SOURCES, institution_name
from ..db import get_db
from ..integration.retrieval import history_start, linked_sources
from ..keys import platform
from ..keys.router import current_entry, patient_entry_for_cnic
from ..models import Consent, Referral
from ..notifications import notify_staff
from ..patient_access import require_patient
from ..referrals.state import TERMINAL, event
from ..security import CLINIC_ROLES, audit, error, get_principal, load_referral
from . import document

router = APIRouter(tags=["consent"])
NO_STORE = {"Cache-Control": "no-store", "Pragma": "no-cache"}


def effective_status(c: Consent) -> str:
    if c.status == "granted" and c.period_end and c.period_end < datetime.now(timezone.utc):
        return "expired"
    return c.status


def consent_out(c: Consent, referral: Referral | None = None) -> dict:
    return {"id": c.id, "reference": c.reference, "referral_id": c.referral_id,
            "referral_reference": referral.reference if referral else None, "status": effective_status(c),
            "purpose": c.purpose, "requesting_org": c.requesting_org,
            "requesting_org_name": institution_name(c.requesting_org),
            "requesting_practitioner": c.requesting_practitioner_name, "destination_org": c.destination_org,
            "destination_name": institution_name(c.destination_org),
            "custodians_requested": [{"institution_id": x, "name": institution_name(x)} for x in c.custodians_requested],
            "custodians_granted": [{"institution_id": x, "name": institution_name(x)} for x in c.custodians_granted],
            "categories": c.categories, "sensitive_offered": c.sensitive_offered,
            "sensitive_specific": c.sensitive_specific, "data_period_start": c.data_period_start,
            "requested_by": c.requested_by_name, "requested_at": c.requested_at,
            "period_start": c.period_start, "period_end": c.period_end, "decided_at": c.decided_at,
            "decline_reason": c.decline_reason, "revoked_at": c.revoked_at, "signed": c.document is not None}


def active_consent(db: Session, referral: Referral) -> Consent | None:
    for c in db.scalars(select(Consent).where(Consent.referral_id == referral.id).order_by(Consent.id.desc())):
        if effective_status(c) == "granted":
            return c
    return None


# --------------------------------------------------------------------------- staff
class ConsentRequestIn(BaseModel):
    custodians: list[str] | None = None  # default: the referring institution and every verified linked source


@router.post("/referrals/{referral_id}/consents", status_code=201)
def request_consent(referral_id: int, body: ConsentRequestIn, db: Session = Depends(get_db),
                    principal: Principal = Depends(get_principal)):
    """Staff ask the patient (through the patient portal) for permission to fetch records for this referral."""
    r = load_referral(db, referral_id, principal, "consent_request", roles=("clinic_staff",))
    if r.kind != "referral" or r.status in TERMINAL or r.status == "draft":
        raise error(409, "not_available", "Consent is requested for a referral the doctor has submitted")
    if not r.patient_cnic or len(r.patient_cnic) != 13:
        raise error(409, "no_cnic", "The patient's CNIC is not recorded, so the patient portal cannot find the request")
    linked = [inst for inst, _, _ in linked_sources(db, r)]
    custodians = sorted(set(body.custodians or linked))
    bad = [x for x in custodians if x not in SOURCES]
    if bad or not custodians:
        raise error(422, "invalid_custodians", "Choose institutions that take part in the network")
    for open_c in db.scalars(select(Consent).where(Consent.referral_id == r.id, Consent.status == "requested")):
        open_c.status = "withdrawn"  # a newer request replaces one the patient has not answered
    c = Consent(reference="pending", referral_id=r.id, patient_cnic=r.patient_cnic, patient_name=r.patient_name,
                purpose="TREAT", requesting_org=r.source_institution, requesting_practitioner_id=r.requesting_doctor_id,
                requesting_practitioner_name=r.requesting_doctor_name, destination_org=r.destination_institution,
                custodians_requested=custodians, categories=list(document.RECORD_CATEGORIES),
                sensitive_offered=sorted(document.SENSITIVE), data_period_start=history_start(r).isoformat(),
                requested_by_id=principal.subject, requested_by_name=principal.display_name)
    db.add(c)
    db.flush()
    c.reference = f"CNS-{datetime.now(timezone.utc).year}-{c.id:05d}"
    event(db, r, "consent_requested", principal.display_name, principal.institution_id,
          {"consent": c.reference, "custodians": custodians})
    audit(db, principal, "consent.request", "consent", c.reference, "success", r.id, {"custodians": custodians})
    db.commit()
    return consent_out(c, r)


@router.get("/referrals/{referral_id}/consents")
def referral_consents(referral_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    r = load_referral(db, referral_id, principal, "view", roles=CLINIC_ROLES)
    rows = db.scalars(select(Consent).where(Consent.referral_id == r.id).order_by(Consent.id.desc())).all()
    return [consent_out(c, r) for c in rows]


# --------------------------------------------------------------------------- patient
def _own(db: Session, principal: Principal, reference: str, action: str) -> tuple[Consent, Referral, str]:
    cnic = require_patient(principal, action)
    c = db.scalars(select(Consent).where(Consent.reference == reference)).first()
    if c is None or c.patient_cnic != cnic:
        raise error(404, "not_found", "No such consent request for you")
    return c, db.get(Referral, c.referral_id), cnic


def _patient_key(db: Session, principal: Principal) -> dict:
    row = current_entry(db, f"patient:{principal.subject}")
    if row is None:
        raise error(409, "no_patient_key", "Set up your device key first: your consent is signed with it")
    return row.entry


@router.get("/patient-access/consents")
def my_consents(db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    cnic = require_patient(principal, "consent.list")
    rows = db.scalars(select(Consent).where(Consent.patient_cnic == cnic, Consent.status != "withdrawn")
                      .order_by(Consent.id.desc())).all()
    refs = {r.id: r for r in db.scalars(select(Referral).where(Referral.id.in_({c.referral_id for c in rows})))} if rows else {}
    audit(db, principal, "consent.list", "patient", "self", "success", None, {"count": len(rows)})
    db.commit()
    body = [consent_out(c, refs.get(c.referral_id)) | {"durations": list(document.DURATIONS),
                                                       "sensitive_labels": document.SENSITIVE} for c in rows]
    return JSONResponse(jsonable_encoder(body), headers=NO_STORE)


class PrepareIn(BaseModel):
    custodians: list[str] = Field(min_length=1)
    sensitive: list[str] = []
    duration_days: int


@router.post("/patient-access/consents/{reference}/prepare")
def prepare_consent(reference: str, body: PrepareIn, db: Session = Depends(get_db),
                    principal: Principal = Depends(get_principal)):
    """The exact document for the patient's choices, for the patient's device to show and sign."""
    c, r, _ = _own(db, principal, reference, "consent.prepare")
    if c.status != "requested":
        raise error(409, "not_open", f"This request is {effective_status(c)}")
    if not set(body.custodians) <= set(c.custodians_requested) or not set(body.sensitive) <= set(c.sensitive_offered):
        raise error(422, "invalid_choice", "Choose from the places and categories in the request")
    if body.duration_days not in document.DURATIONS:
        raise error(422, "invalid_duration", "Choose 1 day, 1 week or 30 days")
    entry = _patient_key(db, principal)
    return document.build(c, r.reference, custodians=body.custodians, sensitive=body.sensitive,
                          start=datetime.now(timezone.utc), days=body.duration_days,
                          patient_signing_key_id=e2e.key_id(entry["sig_public_key"]))


class DecisionIn(BaseModel):
    decision: str = Field(pattern="^(grant|decline)$")
    document: dict | None = None
    reason: str | None = None


@router.post("/patient-access/consents/{reference}/decision")
def decide_consent(reference: str, body: DecisionIn, db: Session = Depends(get_db),
                   principal: Principal = Depends(get_principal)):
    c, r, _ = _own(db, principal, reference, "consent.decide")
    if c.status != "requested":
        raise error(409, "not_open", f"This request is {effective_status(c)}")
    if body.decision == "decline":
        c.status, c.decided_at, c.decline_reason = "declined", datetime.now(timezone.utc), (body.reason or "").strip() or None
        event(db, r, "consent_declined", "patient", None, {"consent": c.reference})
        notify_staff(db, r, "consent_declined", f"{r.reference}: the patient declined consent",
                     "Records cannot be requested. Talk to the patient or the doctor.", tab="records")
        audit(db, principal, "consent.decline", "consent", c.reference, "success", r.id)
        db.commit()
        return consent_out(c, r)
    entry = _patient_key(db, principal)
    problem, choice = document.check_signed(c, body.document or {}, entry, r.reference)
    if problem:
        audit(db, principal, "consent.grant", "consent", c.reference, "rejected", r.id, {"reason": problem})
        db.commit()
        raise error(422, "invalid_consent", problem)
    c.status, c.document, c.decided_at = "granted", body.document, datetime.now(timezone.utc)
    c.custodians_granted, c.sensitive_specific = sorted(choice["custodians"]), sorted(choice["sensitive"])
    c.period_start, c.period_end = choice["start"], choice["start"] + timedelta(days=choice["days"])
    c.patient_key_id = e2e.key_id(entry["sig_public_key"])
    event(db, r, "consent_granted", "patient", None,
          {"consent": c.reference, "custodians": c.custodians_granted, "until": c.period_end.isoformat()})
    notify_staff(db, r, "consent_granted", f"{r.reference}: the patient gave consent",
                 f"Records can now be requested from {len(c.custodians_granted)} place(s).", tab="records")
    audit(db, principal, "consent.grant", "consent", c.reference, "success", r.id,
          {"custodians": c.custodians_granted, "sensitive": c.sensitive_specific, "days": choice["days"]})
    db.commit()
    return consent_out(c, r)


class RevokeIn(BaseModel):
    revocation: dict


@router.post("/patient-access/consents/{reference}/revoke")
def revoke_consent(reference: str, body: RevokeIn, db: Session = Depends(get_db),
                   principal: Principal = Depends(get_principal)):
    """Future requests are refused. Records a doctor already opened cannot be recalled (stated in the portal)."""
    c, r, _ = _own(db, principal, reference, "consent.revoke")
    if c.status != "granted":
        raise error(409, "not_granted", "Only a consent you gave can be revoked")
    entry = _patient_key(db, principal)
    rev = body.revocation
    if rev.get("type") != document.REVOCATION_TYPE or rev.get("consent") != c.reference \
            or not e2e.verify_object(entry["sig_public_key"], rev):
        raise error(422, "invalid_revocation", "The revocation must be signed with your current key")
    c.status, c.revocation, c.revoked_at = "revoked", rev, datetime.now(timezone.utc)
    event(db, r, "consent_revoked", "patient", None, {"consent": c.reference})
    notify_staff(db, r, "consent_revoked", f"{r.reference}: the patient revoked consent",
                 "No further records will be released for this referral.", tab="records")
    audit(db, principal, "consent.revoke", "consent", c.reference, "success", r.id)
    db.commit()
    return consent_out(c, r)


# --------------------------------------------------------------------------- adapters
@router.get("/e2e/adapter/consents/{reference}")
def adapter_consent(reference: str, request: Request, db: Session = Depends(get_db)):
    """The signed consent behind a request, for the institution to check itself. Only a custodian named by the
    patient may read it."""
    claims = platform.verify_adapter(request, db)
    issuer = claims["iss"]
    c = db.scalars(select(Consent).where(Consent.reference == reference)).first()
    if c is None or c.document is None or issuer not in c.custodians_granted:
        audit(db, None, "consent.fetch", "consent", reference, "denied", c.referral_id if c else None,
              {"institution": issuer}, actor=(issuer, f"adapter {issuer}", issuer))
        db.commit()
        raise error(404, "not_found", "No signed consent naming your institution")
    patient = patient_entry_for_cnic(db, c.patient_cnic)
    key_row = None
    if patient is not None and patient.entry.get("sig_public_key") and \
            e2e.key_id(patient.entry["sig_public_key"]) == c.patient_key_id:
        key_row = patient
    else:  # the patient replaced their key after signing: return the entry that signed it (revoked or not)
        from ..models import DirectoryEntry
        for row in db.scalars(select(DirectoryEntry).where(DirectoryEntry.subject_type == "patient")):
            if row.entry.get("patient_cnic") == c.patient_cnic and row.entry.get("sig_public_key") \
                    and e2e.key_id(row.entry["sig_public_key"]) == c.patient_key_id:
                key_row = row
                break
    audit(db, None, "consent.fetch", "consent", reference, "success", c.referral_id, {"institution": issuer},
          actor=(issuer, f"adapter {issuer}", issuer))
    db.commit()
    return {"reference": c.reference, "status": effective_status(c), "document": c.document,
            "revocation": c.revocation, "patient_entry": key_row.entry if key_row else None,
            "agreement": {"purposes": sorted(registry.allowed_purposes())}}
