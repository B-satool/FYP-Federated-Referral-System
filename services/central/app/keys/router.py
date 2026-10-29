"""Key directory API (spec v4 WP1).

* Adapters publish their hospital-signed entries, revocations and group-key wraps here with a signed request
  assertion. Each entry is checked against the issuing hospital's pinned key; a bad signature is refused and
  audited (T-DIR-1). The platform cannot create or alter a doctor's or department's entry: clients verify the
  hospital signature themselves.
* Patients register keys generated on their own device; the platform signs the patient's entry (a deliberate
  trust point, docs/security-model.md).
* Anyone signed in reads the directory; a doctor reads the group-key wraps addressed to their own key.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from refcommon import e2e
from refcommon.auth import Principal
from refcommon.db import utcnow
from refcommon.participants import PLATFORM_ID, registry
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import DirectoryEntry, GroupKeyWrap
from ..notifications import notify
from ..patient_access import require_patient
from ..security import audit, error, get_principal
from . import platform

router = APIRouter(tags=["end-to-end keys"])
PATIENT_KEY_VALID_DAYS = 730


def entry_out(row: DirectoryEntry) -> dict:
    return {"entry": row.entry, "revocation": row.revocation, "revoked": row.revoked_at is not None,
            "fingerprint": e2e.fingerprint(row.entry["enc_public_key"])}


@router.get("/.well-known/jwks.json", tags=["end-to-end keys"])
def jwks(db: Session = Depends(get_db)):
    """The platform's public signing key, pinned by every adapter at onboarding."""
    row = platform.key_row(db)
    db.commit()
    return {"keys": [e2e.jwk(row.public_spki)], "spki": {row.kid: row.public_spki}}


@router.get("/e2e/participants")
def participants(principal: Principal = Depends(get_principal)):
    """Onboarded institutions as pinned at this installation (for display; clients use their own pinned copy)."""
    return [{"institution_id": p.institution_id, "name": p.name, "key_id": p.key_id, "status": p.status,
             "agreement_version": p.agreement_version, "agreement_date": p.agreement_date,
             "fingerprint": e2e.fingerprint(p.signing_key)} for p in registry.institutions()]


# --------------------------------------------------------------------------- from the adapters
class DirectoryBatch(BaseModel):
    entries: list[dict] = []
    revocations: list[dict] = []
    group_wraps: list[dict] = []
    notices: list[dict] = []


@router.post("/e2e/adapter/directory")
def receive_directory(body: DirectoryBatch, request: Request, db: Session = Depends(get_db)):
    claims = platform.verify_adapter(request, db)
    issuer = claims["iss"]
    pinned = registry.institution(issuer).signing_key
    actor = (issuer, f"adapter {issuer}", issuer)
    stored, rejected = 0, []
    for entry in body.entries:
        problem = None if entry.get("hospital_id") == issuer and entry.get("issued_by") == issuer \
            else "entry is not issued by the calling institution"
        problem = problem or e2e.check_entry(entry, pinned)
        if problem:
            rejected.append({"subject_id": entry.get("subject_id"), "reason": problem})
            audit(db, None, "directory.signature_failure", "directory_entry", entry.get("subject_id", "?"), "denied",
                  None, {"reason": problem, "source": "adapter publish"}, actor=actor)
            continue
        if db.scalars(select(DirectoryEntry).where(DirectoryEntry.enc_key_id == entry["enc_key_id"])).first():
            continue
        db.add(DirectoryEntry(subject_id=entry["subject_id"], subject_type=entry["subject_type"],
                              hospital_id=entry["hospital_id"], department=entry.get("department"),
                              enc_key_id=entry["enc_key_id"], key_version=entry["key_version"], issued_by=issuer,
                              entry=entry))
        audit(db, None, "directory.publish", "directory_entry", entry["subject_id"], "success", None,
              {"enc_key_id": entry["enc_key_id"], "key_version": entry["key_version"],
               "subject_type": entry["subject_type"]}, actor=actor)
        stored += 1
    db.flush()
    for rev in body.revocations:
        row = db.scalars(select(DirectoryEntry).where(DirectoryEntry.enc_key_id == rev.get("enc_key_id"))).first()
        if rev.get("issued_by") != issuer or not e2e.check_revocation(rev, pinned) or row is None \
                or row.issued_by != issuer:
            rejected.append({"subject_id": rev.get("subject_id"), "reason": "revocation signature invalid"})
            audit(db, None, "directory.signature_failure", "revocation", rev.get("subject_id", "?"), "denied", None,
                  {"reason": "revocation not signed by the issuing hospital"}, actor=actor)
            continue
        if row.revoked_at is None:
            row.revocation, row.revoked_at = rev, utcnow()
            # a revoked doctor's group-key wraps are no longer served
            for w in db.scalars(select(GroupKeyWrap).where(GroupKeyWrap.member_key_id == row.enc_key_id)):
                db.delete(w)
            audit(db, None, "directory.revoke", "directory_entry", row.subject_id, "success", None,
                  {"enc_key_id": row.enc_key_id, "reason": rev.get("reason")}, actor=actor)
    for w in body.group_wraps:
        if w.get("hospital_id") != issuer:
            rejected.append({"subject_id": w.get("member_subject_id"), "reason": "wrap for another institution"})
            continue
        exists = db.scalars(select(GroupKeyWrap).where(
            GroupKeyWrap.hospital_id == issuer, GroupKeyWrap.department == w["department"],
            GroupKeyWrap.group_version == w["group_version"], GroupKeyWrap.member_key_id == w["member_key_id"])).first()
        member = db.scalars(select(DirectoryEntry).where(DirectoryEntry.enc_key_id == w["member_key_id"])).first()
        if exists or member is None or member.revoked_at is not None:
            continue
        db.add(GroupKeyWrap(hospital_id=issuer, department=w["department"], group_version=w["group_version"],
                            member_subject_id=w["member_subject_id"], member_key_id=w["member_key_id"],
                            wrapped=w["wrapped"]))
    for n in body.notices:
        if n.get("kind") == "key_recovery" and n.get("hospital_id") == issuer:
            notify(db, "key_recovery", f"Key replaced: {n.get('display_name')}", institution=issuer,
                   role="institution_admin",
                   body=(f"{n.get('display_name')} replaced a lost device key (version {n.get('key_version')}). "
                         "Records are fetched again from the source institutions for their open referrals."))
            audit(db, None, "keys.recovery_notice", "directory_entry", n.get("subject_id", "?"), "success", None,
                  {"key_version": n.get("key_version")}, actor=actor)
    db.commit()
    return {"stored": stored, "rejected": rejected}


# --------------------------------------------------------------------------- reading the directory
@router.get("/e2e/directory")
def directory(subject_id: str | None = None, hospital_id: str | None = None, department: str | None = None,
              subject_type: str | None = Query(None, pattern="^(doctor|department|patient)$"),
              include_revoked: bool = False, db: Session = Depends(get_db),
              principal: Principal = Depends(get_principal)):
    stmt = select(DirectoryEntry)
    if subject_id:
        stmt = stmt.where(DirectoryEntry.subject_id == subject_id)
    if hospital_id:
        stmt = stmt.where(DirectoryEntry.hospital_id == hospital_id)
    if department:
        stmt = stmt.where(DirectoryEntry.department == department)
    if subject_type:
        stmt = stmt.where(DirectoryEntry.subject_type == subject_type)
    if not include_revoked:
        stmt = stmt.where(DirectoryEntry.revoked_at.is_(None))
    if principal.has_any("patient") and not subject_id:
        stmt = stmt.where(DirectoryEntry.subject_type != "patient")  # patients look up no one else's key
    rows = db.scalars(stmt.order_by(DirectoryEntry.subject_id, DirectoryEntry.key_version.desc()).limit(500)).all()
    return [entry_out(r) for r in rows if r.subject_type != "patient" or r.subject_id == f"patient:{principal.subject}"
            or not principal.has_any("patient")]


def current_department_entry(db: Session, hospital_id: str, department: str) -> DirectoryEntry | None:
    return db.scalars(select(DirectoryEntry).where(
        DirectoryEntry.subject_type == "department", DirectoryEntry.hospital_id == hospital_id,
        DirectoryEntry.department == department, DirectoryEntry.revoked_at.is_(None))
        .order_by(DirectoryEntry.key_version.desc())).first()


def current_entry(db: Session, subject_id: str) -> DirectoryEntry | None:
    return db.scalars(select(DirectoryEntry).where(DirectoryEntry.subject_id == subject_id,
                                                   DirectoryEntry.revoked_at.is_(None))
                      .order_by(DirectoryEntry.key_version.desc())).first()


@router.get("/e2e/directory/me")
def my_directory(db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """The caller's own entries, and the department group keys wrapped to their current key."""
    subject = f"patient:{principal.subject}" if principal.has_any("patient") else principal.subject
    rows = db.scalars(select(DirectoryEntry).where(DirectoryEntry.subject_id == subject)
                      .order_by(DirectoryEntry.key_version.desc())).all()
    active = [r.enc_key_id for r in rows if r.revoked_at is None]
    wraps = db.scalars(select(GroupKeyWrap).where(GroupKeyWrap.member_key_id.in_(active))
                       .order_by(GroupKeyWrap.group_version)).all() if active else []
    return {"subject_id": subject, "entries": [entry_out(r) for r in rows],
            "group_wraps": [{"hospital_id": w.hospital_id, "department": w.department, "group_version": w.group_version,
                             "member_key_id": w.member_key_id, "wrapped": w.wrapped} for w in wraps]}


@router.get("/e2e/directory/departments/{hospital_id}/{department}")
def department_entries(hospital_id: str, department: str, db: Session = Depends(get_db),
                       principal: Principal = Depends(get_principal)):
    rows = db.scalars(select(DirectoryEntry).where(
        DirectoryEntry.subject_type == "department", DirectoryEntry.hospital_id == hospital_id,
        DirectoryEntry.department == department).order_by(DirectoryEntry.key_version.desc())).all()
    if not rows:
        raise error(404, "no_department_key", "This department has no published group key yet")
    return [entry_out(r) for r in rows]


# --------------------------------------------------------------------------- patients
class PatientKeyIn(BaseModel):
    registration: dict


REGISTRATION_TYPE = "refx.key.registration/v1"


@router.post("/e2e/patient-keys", status_code=201)
def register_patient_key(body: PatientKeyIn, db: Session = Depends(get_db),
                         principal: Principal = Depends(get_principal)):
    """A patient's keys, generated on the patient's device. The platform signs the entry for the signed-in
    patient (CNIC from the verified token) and revokes the patient's earlier key."""
    cnic = require_patient(principal, "keys.patient_register")
    subject = f"patient:{principal.subject}"
    reg = body.registration
    problem = None
    if reg.get("type") != REGISTRATION_TYPE or reg.get("subject_id") != subject:
        problem = "registration is not for this account"
    else:
        try:
            e2e.load_public(reg["enc_public_key"])
            e2e.load_public(reg["sig_public_key"])
            if reg["enc_public_key"] == reg["sig_public_key"] or not e2e.verify_object(reg["sig_public_key"], reg):
                problem = "proof of possession failed"
        except (KeyError, e2e.CryptoError):
            problem = "public keys are missing or not P-256 keys"
    if problem:
        audit(db, principal, "keys.patient_register", "directory_entry", subject, "rejected", None, {"reason": problem})
        db.commit()
        raise error(422, "invalid_registration", problem)
    enc_id = e2e.key_id(reg["enc_public_key"])
    existing = db.scalars(select(DirectoryEntry).where(DirectoryEntry.enc_key_id == enc_id)).first()
    if existing:
        return entry_out(existing)
    prior = db.scalars(select(DirectoryEntry).where(DirectoryEntry.subject_id == subject)).all()
    signer = platform.key_row(db).kid
    for old in prior:
        if old.revoked_at is None:
            old.revocation = platform.sign(db, e2e.revocation(
                subject_id=subject, enc_key_id=old.enc_key_id, key_version=old.key_version,
                reason="replaced by a new key", issued_by=PLATFORM_ID, signer_key_id=signer))
            old.revoked_at = utcnow()
    version = max((p.key_version for p in prior), default=0) + 1
    entry = platform.sign(db, e2e.directory_entry(
        subject_id=subject, subject_type="patient", role="patient", hospital_id=None, department=None,
        display_name=principal.display_name, enc_public_key=reg["enc_public_key"],
        sig_public_key=reg["sig_public_key"], key_version=version, valid_days=PATIENT_KEY_VALID_DAYS,
        issued_by=PLATFORM_ID, signer_key_id=signer, patient_cnic=cnic))
    row = DirectoryEntry(subject_id=subject, subject_type="patient", hospital_id=None, department=None,
                         enc_key_id=enc_id, key_version=version, issued_by=PLATFORM_ID, entry=entry)
    db.add(row)
    audit(db, principal, "keys.patient_register", "directory_entry", subject, "success", None,
          {"enc_key_id": enc_id, "key_version": version, "replaced": len(prior)})
    db.commit()
    return entry_out(row)


def patient_entry_for_cnic(db: Session, cnic: str) -> DirectoryEntry | None:
    """The current key of the patient whose account has this CNIC (newest registration wins)."""
    rows = db.scalars(select(DirectoryEntry).where(DirectoryEntry.subject_type == "patient",
                                                   DirectoryEntry.revoked_at.is_(None))
                      .order_by(DirectoryEntry.created_at.desc())).all()
    return next((r for r in rows if r.entry.get("patient_cnic") == cnic), None)


# --------------------------------------------------------------------------- client-reported events
CLIENT_EVENTS = {"directory.signature_failure", "decrypt.opened", "decrypt.failed", "manifest.verify_failure",
                 "keys.device_unlock_failed", "flag.ignore", "flag.research"}  # Ignore / Research (spec v4 9.5, T-FLAG-3)


class ClientEventIn(BaseModel):
    action: str
    target_type: str
    target_id: str
    referral_id: int | None = None
    detail: dict = {}


@router.post("/e2e/client-events", status_code=202)
def client_event(body: ClientEventIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """Events only a client can see: a directory signature that failed in the browser, which items a doctor
    opened (decrypted). Best effort: a modified client could skip them (stated in docs/security-model.md).
    The detail must hold ids, counts and reason codes only; text values are cut short and never content."""
    if body.action not in CLIENT_EVENTS:
        raise error(422, "unknown_event", "Unknown client event")
    detail = {k: (v[:200] if isinstance(v, str) else v) for k, v in list(body.detail.items())[:20]
              if k in {"item_ids", "reason", "count", "key_id", "subject_id", "version", "batch", "flag_key", "layer"}}
    audit(db, principal, body.action, body.target_type[:60], body.target_id[:100],
          "denied" if "failure" in body.action or "failed" in body.action else "success", body.referral_id,
          {**detail, "client_reported": True})
    db.commit()
    return {"recorded": True}
