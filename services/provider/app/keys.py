"""This institution's keys (spec v4 sections 5.3 to 5.5, 5.7).

* The hospital signing key signs this hospital's doctors' and departments' directory entries and its request
  assertions to the platform. It is generated here on first use and never leaves this service.
* Each clinical department has a group key pair. Its private key is wrapped to every current member doctor's
  encryption key, so any member can open referrals sent to the department, and a reassignment needs no re-wrap.
  This service keeps the group private key too (the hospital holds a member copy by policy): a deliberate trust
  point, stated in docs/security-model.md.
* A doctor's key pairs are generated on the doctor's device. The doctor sends only the public keys, with a
  signature made by the new signing key (proof of possession); this hospital signs the directory entry.
* A doctor who leaves (or replaces a lost key) is revoked with a signed revocation and the department group key is
  rotated (version + 1), wrapped to the remaining members only. Whatever a leaver could already decrypt with the
  old version cannot be taken back.
"""
from __future__ import annotations

from refcommon import e2e
from refcommon.db import utcnow
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import DOCTOR_KEY_VALID_DAYS, INSTITUTION, INSTITUTION_NAME, KEYSTORE_SECRET
from .models import DoctorKey, GroupKeyWrap, KeyStore

HOSPITAL_SIGNING = "hospital_signing"
GROUP_KEY_VALID_DAYS = 730


def _store_key() -> bytes:
    if not KEYSTORE_SECRET:
        raise RuntimeError("KEYSTORE_SECRET is not set: this service cannot hold keys")
    return e2e.store_key(KEYSTORE_SECRET)


def _seal(private_key) -> dict:
    return e2e.encrypt(_store_key(), e2e.private_pkcs8(private_key), f"refx/v1|keystore|{INSTITUTION}")


def _unseal(row: KeyStore):
    return e2e.load_private(e2e.decrypt(_store_key(), row.private_sealed, f"refx/v1|keystore|{INSTITUTION}"))


def _current(db: Session, purpose: str) -> KeyStore | None:
    return db.scalars(select(KeyStore).where(KeyStore.purpose == purpose, KeyStore.retired_at.is_(None))
                      .order_by(KeyStore.version.desc())).first()


def hospital_key_row(db: Session) -> KeyStore:
    row = _current(db, HOSPITAL_SIGNING)
    if row is None:
        key = e2e.generate_key()
        row = KeyStore(purpose=HOSPITAL_SIGNING, version=1, public_spki=e2e.public_spki(key), private_sealed=_seal(key))
        db.add(row)
        db.flush()
    return row


def hospital_key(db: Session):
    return _unseal(hospital_key_row(db))


def hospital_public(db: Session) -> str:
    return hospital_key_row(db).public_spki


def _sign(db: Session, obj: dict) -> dict:
    return e2e.sign_object(hospital_key(db), obj)


# --------------------------------------------------------------------------- department group keys
def group_purpose(department: str) -> str:
    return f"group:{department}"


def group_key_row(db: Session, department: str) -> KeyStore:
    """The department's current group key, created (and its directory entry signed) on first use."""
    row = _current(db, group_purpose(department))
    if row is None:
        row = _new_group_version(db, department, 1)
    return row


def _new_group_version(db: Session, department: str, version: int) -> KeyStore:
    key = e2e.generate_key()
    spki = e2e.public_spki(key)
    entry = e2e.directory_entry(
        subject_id=f"dept:{INSTITUTION}:{department}", subject_type="department", role="department_group",
        hospital_id=INSTITUTION, department=department, display_name=f"{department} ({INSTITUTION_NAME})",
        enc_public_key=spki, sig_public_key=None, key_version=version, valid_days=GROUP_KEY_VALID_DAYS,
        issued_by=INSTITUTION, signer_key_id=e2e.key_id(hospital_public(db)))
    row = KeyStore(purpose=group_purpose(department), version=version, public_spki=spki, private_sealed=_seal(key),
                   entry=_sign(db, entry))
    db.add(row)
    db.flush()
    return row


def group_private(db: Session, department: str, version: int | None = None):
    stmt = select(KeyStore).where(KeyStore.purpose == group_purpose(department))
    row = db.scalars(stmt.where(KeyStore.version == version) if version else
                     stmt.where(KeyStore.retired_at.is_(None)).order_by(KeyStore.version.desc())).first()
    if row is None:
        raise LookupError(f"no group key for {department}")
    return _unseal(row), row


def wrap_group_for(db: Session, department: str, doctor: DoctorKey) -> GroupKeyWrap:
    """Give one member doctor the department's current group private key, wrapped to the doctor's key."""
    group_key_row(db, department)
    key, row = group_private(db, department)
    existing = db.scalars(select(GroupKeyWrap).where(GroupKeyWrap.department == department,
                                                     GroupKeyWrap.group_version == row.version,
                                                     GroupKeyWrap.member_key_id == doctor.enc_key_id)).first()
    if existing:
        return existing
    ctx = e2e.group_context(INSTITUTION, department, row.version, doctor.enc_key_id)
    w = GroupKeyWrap(department=department, group_version=row.version, member_subject_id=doctor.subject_id,
                     member_key_id=doctor.enc_key_id,
                     wrapped=e2e.wrap(doctor.entry["enc_public_key"], e2e.private_pkcs8(key), ctx))
    db.add(w)
    db.flush()
    return w


def active_members(db: Session, department: str) -> list[DoctorKey]:
    return list(db.scalars(select(DoctorKey).where(DoctorKey.department == department, DoctorKey.status == "active")))


def rotate_group(db: Session, department: str) -> KeyStore:
    """A member left: a new group key version, wrapped to the remaining members only."""
    old = group_key_row(db, department)
    old.retired_at = utcnow()
    row = _new_group_version(db, department, old.version + 1)
    for doctor in active_members(db, department):
        wrap_group_for(db, department, doctor)
    return row


# --------------------------------------------------------------------------- doctors
REGISTRATION_TYPE = "refx.key.registration/v1"


def check_registration(req: dict, subject_id: str) -> str | None:
    """Why a doctor's key registration is not acceptable (None if it is)."""
    if req.get("type") != REGISTRATION_TYPE or req.get("subject_id") != subject_id:
        return "registration is not for this account"
    try:
        e2e.load_public(req["enc_public_key"])
        e2e.load_public(req["sig_public_key"])
    except (KeyError, e2e.CryptoError):
        return "public keys are missing or not P-256 keys"
    if req["enc_public_key"] == req["sig_public_key"]:
        return "the encryption and signing keys must be different key pairs"
    if not e2e.verify_object(req["sig_public_key"], req):
        return "proof of possession failed: the registration is not signed by the new signing key"
    return None


def next_doctor_version(db: Session, subject_id: str) -> int:
    return (db.scalar(select(func.max(DoctorKey.key_version)).where(DoctorKey.subject_id == subject_id)) or 0) + 1


def activate(db: Session, doctor: DoctorKey, approved_by: str) -> DoctorKey:
    """Sign the doctor's directory entry, revoke any earlier key, and give them the department group key."""
    for old in db.scalars(select(DoctorKey).where(DoctorKey.subject_id == doctor.subject_id, DoctorKey.id != doctor.id,
                                                  DoctorKey.status.in_(("active", "pending")))):
        revoke(db, old, approved_by, "replaced by a new key")
    req = doctor.request
    entry = e2e.directory_entry(
        subject_id=doctor.subject_id, subject_type="doctor", role="doctor", hospital_id=INSTITUTION,
        department=doctor.department, display_name=doctor.display_name, enc_public_key=req["enc_public_key"],
        sig_public_key=req["sig_public_key"], key_version=doctor.key_version, valid_days=DOCTOR_KEY_VALID_DAYS,
        issued_by=INSTITUTION, signer_key_id=e2e.key_id(hospital_public(db)))
    doctor.entry = _sign(db, entry)
    doctor.status, doctor.approved_by, doctor.published_at = "active", approved_by, None
    if doctor.department:
        group_key_row(db, doctor.department)
        wrap_group_for(db, doctor.department, doctor)
    return doctor


def revoke(db: Session, doctor: DoctorKey, by: str, reason: str, rotate: bool = True) -> DoctorKey:
    if doctor.status == "revoked":
        return doctor
    was_member = doctor.status == "active"
    doctor.revocation = _sign(db, e2e.revocation(
        subject_id=doctor.subject_id, enc_key_id=doctor.enc_key_id, key_version=doctor.key_version, reason=reason,
        issued_by=INSTITUTION, signer_key_id=e2e.key_id(hospital_public(db))))
    doctor.status, doctor.revoked_by, doctor.revoked_at, doctor.published_at = "revoked", by, utcnow(), None
    db.flush()
    if rotate and was_member and doctor.department:
        rotate_group(db, doctor.department)
    return doctor


def doctor_out(d: DoctorKey) -> dict:
    return {"id": d.id, "subject_id": d.subject_id, "username": d.username, "display_name": d.display_name,
            "department": d.department, "key_version": d.key_version, "enc_key_id": d.enc_key_id,
            "fingerprint": e2e.fingerprint(d.request["enc_public_key"]), "status": d.status, "recovery": d.recovery,
            "approved_by": d.approved_by, "revoked_by": d.revoked_by, "revoked_at": d.revoked_at,
            "created_at": d.created_at, "published": d.published_at is not None, "entry": d.entry}


# --------------------------------------------------------------------------- what is published to the platform
def unpublished(db: Session) -> dict:
    """Everything the platform's directory does not have yet: signed entries, revocations and group-key wraps."""
    entries, revocations = [], []
    groups = db.scalars(select(KeyStore).where(KeyStore.purpose.like("group:%"), KeyStore.published_at.is_(None))).all()
    entries += [g.entry for g in groups if g.entry]
    doctors = db.scalars(select(DoctorKey).where(DoctorKey.published_at.is_(None),
                                                DoctorKey.status.in_(("active", "revoked")))).all()
    for d in doctors:
        if d.entry:
            entries.append(d.entry)
        if d.revocation:
            revocations.append(d.revocation)
    wraps = db.scalars(select(GroupKeyWrap).where(GroupKeyWrap.published_at.is_(None))).all()
    return {"entries": entries, "revocations": revocations,
            "group_wraps": [{"hospital_id": INSTITUTION, "department": w.department, "group_version": w.group_version,
                             "member_subject_id": w.member_subject_id, "member_key_id": w.member_key_id,
                             "wrapped": w.wrapped} for w in wraps],
            # a key that replaces a lost one: the platform tells this hospital's administrators (spec v4 5.7)
            "notices": [{"kind": "key_recovery", "hospital_id": INSTITUTION, "subject_id": d.subject_id,
                         "display_name": d.display_name, "department": d.department, "key_version": d.key_version}
                        for d in doctors if d.recovery and d.status == "active"],
            "_rows": (groups, doctors, wraps)}


def mark_published(rows) -> None:
    now = utcnow()
    for group in rows:
        for r in group:
            r.published_at = now
