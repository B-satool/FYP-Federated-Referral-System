"""Readiness, the doctor's signed package, sending, delivery status, and verifying a stored copy (spec v4 5.8, 11.2)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from refcommon import e2e
from refcommon.auth import Principal
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Outbox, PackageManifest, PurgeReceipt, Referral
from ..security import CLINIC_ROLES, DOCTOR, STAFF, audit, check_version, error, get_principal, load_referral, \
    require_scope, sees_clinical
from ..serializers import referral_out
from ..tasks import enqueue
from . import packages
from .readiness import readiness

router = APIRouter(tags=["sending"])


@router.get("/referrals/{referral_id}/readiness")
def get_readiness(referral_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    r = load_referral(db, referral_id, principal, "view")
    return {"items": readiness(db, r, sees_clinical(principal)), "status": r.status, "amendment_open": r.amendment_open}


class ApproveIn(BaseModel):
    manifest: dict
    wraps: list[dict]


@router.post("/referrals/{referral_id}/packages", status_code=201)
def approve_package(referral_id: int, body: ApproveIn, db: Session = Depends(get_db),
                    principal: Principal = Depends(get_principal)):
    """The referring doctor approves: a manifest signed on their device, and the data keys re-wrapped to the
    receiving department's group key and the patient's key."""
    require_scope(principal, "package:approve", "package.approve")
    r = load_referral(db, referral_id, principal, "approve", roles=(DOCTOR,))
    if r.requesting_doctor_id and r.requesting_doctor_id != principal.subject:
        raise error(403, "not_your_referral", "Only the referring doctor approves this referral")
    pm = packages.approve(db, r, principal, body.manifest, body.wraps)
    db.commit()
    return packages.manifest_out(pm, True)


@router.get("/referrals/{referral_id}/packages")
def list_packages(referral_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """Every approved version. Staff see who signed what and when; the manifest itself (item hashes) for doctors."""
    r = load_referral(db, referral_id, principal, "view", roles=CLINIC_ROLES)
    rows = db.scalars(select(PackageManifest).where(PackageManifest.referral_id == r.id)
                      .order_by(PackageManifest.version.desc())).all()
    clinical = sees_clinical(principal)
    return [packages.manifest_out(pm, clinical) for pm in rows]


class SendIn(BaseModel):
    expected_version: int


@router.post("/referrals/{referral_id}/send")
def send(referral_id: int, body: SendIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """Staff send the approved version to the receiving hospital."""
    require_scope(principal, "referral:send", "referral.send")
    r = load_referral(db, referral_id, principal, "send", roles=(STAFF,))
    check_version(r, body.expected_version)
    pm = packages.send(db, r, principal)
    db.commit()
    enqueue("deliver_outbox")
    return {"referral": referral_out(r, sees_clinical(principal)), "package_version": pm.version,
            "manifest_sha256": pm.manifest_sha256}


@router.post("/referrals/{referral_id}/retry-delivery")
def retry_delivery(referral_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """Retry reuses the same delivery key, so the receiver never gets a duplicate."""
    r = load_referral(db, referral_id, principal, "send")
    n = packages.retry(db, r, principal)
    db.commit()
    enqueue("deliver_outbox")
    return {"retried": n}


@router.get("/referrals/{referral_id}/delivery")
def delivery(referral_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    r = load_referral(db, referral_id, principal, "view")
    rows = db.scalars(select(Outbox).where(Outbox.referral_id == r.id).order_by(Outbox.id)).all()
    return [{"id": b.id, "kind": b.kind, "target_institution": b.target_institution, "message_key": b.message_key,
             "status": b.status, "attempts": b.attempts, "last_error": b.last_error, "next_attempt_at": b.next_attempt_at,
             "created_at": b.created_at, "sent_at": b.sent_at} for b in rows]


class VerifyIn(BaseModel):
    reference: str
    manifest: dict


@router.post("/e2e/verify-manifest")
def verify_manifest(body: VerifyIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """Given a stored copy of a signed manifest (the receiver's, or the patient's), say whether it is the version
    the platform recorded, whether its signature verifies against the signer's key, and whether the referral was
    purged (then only the manifest hash remains). The holder checks the item hashes against its decrypted copy."""
    r = db.scalars(select(Referral).where(Referral.reference == body.reference)).first()
    if r is None:
        raise error(404, "not_found", "No such referral")
    digest = packages.manifest_hash(body.manifest)
    row = db.scalars(select(PackageManifest).where(PackageManifest.referral_id == r.id,
                                                   PackageManifest.version == body.manifest.get("version"))).first()
    receipt = db.scalars(select(PurgeReceipt).where(PurgeReceipt.referral_id == r.id)).first()
    sig_ok, signer = False, None
    if row is not None:
        from ..models import DirectoryEntry

        for entry in db.scalars(select(DirectoryEntry).where(DirectoryEntry.subject_id == row.signer_subject)):
            if entry.entry.get("sig_public_key") and e2e.key_id(entry.entry["sig_public_key"]) == row.signer_key_id:
                signer, sig_ok = entry, e2e.verify_object(entry.entry["sig_public_key"], body.manifest)
                break
    if row is None:
        result = "unknown_version"
    elif row.manifest_sha256 != digest:
        result = "mismatch"
    else:
        result = "purged" if r.working_set_purged_at is not None else "match"
    audit(db, principal, "package.verify", "package_manifest", f"{r.reference}v{body.manifest.get('version')}", result, r.id)
    db.commit()
    return {"result": result, "signature_valid": sig_ok, "manifest_sha256": digest,
            "recorded_sha256": row.manifest_sha256 if row else (receipt.manifest_hash if receipt else None),
            "signer_entry": signer.entry if signer else None,
            "purged_at": receipt.purged_at if receipt else None}
