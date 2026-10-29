"""Key endpoints of this institution's adapter (spec v4 WP1).

Doctors register the public keys generated on their own device; this hospital signs the directory entry
(automatically for its clinicians, or after an administrator approves, per its policy). Administrators revoke keys
and rotate department group keys. Every step is audited here.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from refcommon import e2e
from refcommon.auth import Principal, forbid
from refcommon.sourcekit import record_audit
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from . import keys, m2m, policy
from .config import INSTITUTION, INSTITUTION_NAME
from .models import AuditEvent, DoctorKey


class RegisterKeyIn(BaseModel):
    registration: dict
    recovery: bool = False  # this key replaces one the doctor lost


class RevokeIn(BaseModel):
    reason: str = Field(min_length=3)


def serialize_key_changes(db: Session) -> None:
    """One key change at a time at this institution (PostgreSQL advisory lock, released at commit). Keys are created
    automatically on sign-in, so two requests can arrive together (a page reloaded mid-set-up); without this, both
    could create a department's first group key."""
    if db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(7311012)"))


def build_router(get_db, get_principal) -> APIRouter:
    router = APIRouter(tags=["end-to-end keys"])

    def require_clinician(principal: Principal) -> None:
        if principal.institution_id != INSTITUTION or "clinician" not in principal.roles:
            raise forbid(f"Only a doctor of {INSTITUTION_NAME} registers keys here")

    def require_admin(principal: Principal) -> None:
        if principal.institution_id != INSTITUTION or "institution_admin" not in principal.roles:
            raise forbid(f"Only an administrator of {INSTITUTION_NAME} manages doctors' keys")

    @router.get("/.well-known/refx-participant")
    def participant(db: Session = Depends(get_db)):
        """This institution's public signing key, read once at onboarding (scripts/onboard_participants.py) and
        pinned by every other participant. Public information."""
        spki = keys.hospital_public(db)
        db.commit()
        return {"institution_id": INSTITUTION, "name": INSTITUTION_NAME, "suite": e2e.SUITE, "signing_key": spki,
                "key_id": e2e.key_id(spki), "fingerprint": e2e.fingerprint(spki)}

    @router.post("/e2e/keys/doctor", status_code=201)
    def register_doctor_key(body: RegisterKeyIn, db: Session = Depends(get_db),
                            principal: Principal = Depends(get_principal)):
        """A doctor's new public keys (generated on their device), with proof of possession."""
        require_clinician(principal)
        serialize_key_changes(db)
        problem = keys.check_registration(body.registration, principal.subject)
        if problem:
            record_audit(db, AuditEvent, principal, "keys.register", "doctor_key", principal.subject, "rejected",
                         detail={"reason": problem})
            db.commit()
            raise HTTPException(422, {"code": "invalid_registration", "message": problem})
        enc_id = e2e.key_id(body.registration["enc_public_key"])
        existing = db.scalars(select(DoctorKey).where(DoctorKey.subject_id == principal.subject,
                                                      DoctorKey.enc_key_id == enc_id)).first()
        if existing:
            return keys.doctor_out(existing)
        doctor = DoctorKey(subject_id=principal.subject, username=principal.username, display_name=principal.display_name,
                           department=principal.department, enc_key_id=enc_id,
                           key_version=keys.next_doctor_version(db, principal.subject), request=body.registration,
                           recovery=body.recovery)
        db.add(doctor)
        db.flush()
        auto = policy.load()["doctor_keys"]["auto_sign"]
        if auto:
            keys.activate(db, doctor, f"{INSTITUTION_NAME} (policy: clinicians' keys signed automatically)")
        record_audit(db, AuditEvent, principal, "keys.recovery" if body.recovery else "keys.register", "doctor_key",
                     principal.subject, "success",
                     detail={"enc_key_id": enc_id, "key_version": doctor.key_version, "status": doctor.status,
                             "department": doctor.department})
        db.commit()
        m2m.publish_keys(db)
        return keys.doctor_out(doctor)

    @router.get("/e2e/keys/doctor/me")
    def my_keys(db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
        require_clinician(principal)
        rows = db.scalars(select(DoctorKey).where(DoctorKey.subject_id == principal.subject)
                          .order_by(DoctorKey.key_version.desc())).all()
        return [keys.doctor_out(d) for d in rows]

    @router.get("/e2e/keys/doctors")
    def list_doctor_keys(db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
        require_admin(principal)
        rows = db.scalars(select(DoctorKey).order_by(DoctorKey.created_at.desc())).all()
        return [keys.doctor_out(d) for d in rows]

    @router.post("/e2e/keys/doctors/{key_row_id}/approve")
    def approve_doctor_key(key_row_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
        require_admin(principal)
        serialize_key_changes(db)
        doctor = db.get(DoctorKey, key_row_id)
        if doctor is None:
            raise HTTPException(404, {"code": "not_found", "message": "No such key"})
        if doctor.status != "pending":
            raise HTTPException(409, {"code": "not_pending", "message": f"This key is {doctor.status}"})
        keys.activate(db, doctor, principal.display_name)
        record_audit(db, AuditEvent, principal, "keys.sign", "doctor_key", doctor.subject_id, "success",
                     detail={"enc_key_id": doctor.enc_key_id, "key_version": doctor.key_version})
        db.commit()
        m2m.publish_keys(db)
        return keys.doctor_out(doctor)

    @router.post("/e2e/keys/doctors/{key_row_id}/revoke")
    def revoke_doctor_key(key_row_id: int, body: RevokeIn, db: Session = Depends(get_db),
                          principal: Principal = Depends(get_principal)):
        """The doctor left the department (or the key is compromised): a signed revocation, and the department
        group key is rotated so new referrals use a version the doctor never had."""
        require_admin(principal)
        serialize_key_changes(db)
        doctor = db.get(DoctorKey, key_row_id)
        if doctor is None:
            raise HTTPException(404, {"code": "not_found", "message": "No such key"})
        keys.revoke(db, doctor, principal.display_name, body.reason.strip())
        record_audit(db, AuditEvent, principal, "keys.revoke", "doctor_key", doctor.subject_id, "success",
                     detail={"enc_key_id": doctor.enc_key_id, "reason": body.reason.strip(),
                             "department": doctor.department})
        db.commit()
        m2m.publish_keys(db)
        return keys.doctor_out(doctor)

    @router.post("/e2e/keys/departments/{department}/rotate")
    def rotate_department_key(department: str, body: RevokeIn, db: Session = Depends(get_db),
                              principal: Principal = Depends(get_principal)):
        require_admin(principal)
        serialize_key_changes(db)
        row = keys.rotate_group(db, department)
        record_audit(db, AuditEvent, principal, "keys.group_rotate", "department", department, "success",
                     detail={"version": row.version, "reason": body.reason.strip()})
        db.commit()
        m2m.publish_keys(db)
        return {"department": department, "version": row.version}

    @router.post("/e2e/keys/publish")
    def publish(db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
        require_admin(principal)
        return {"published": m2m.publish_keys(db)}

    return router
