"""Readiness, sending, delivery status and sent versions."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from refcommon.auth import Principal
from sqlalchemy import select
from sqlalchemy.orm import Session

from refcommon.db import utcnow

from ..db import get_db
from ..integration import sources
from ..lifecycle.manifest import verify_copy
from ..medications import service as med
from ..models import Outbox, ReferralPackage
from ..notifications import notify_doctor, notify_staff
from ..referrals.state import event
from ..security import STAFF, audit, bump, check_version, error, get_principal, load_referral
from ..serializers import referral_out
from ..tasks import enqueue
from . import brief as brief_mod
from . import packages
from .readiness import blocking, readiness, staff_items

router = APIRouter(tags=["sending"])


@router.get("/referrals/{referral_id}/readiness")
def get_readiness(referral_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    r = load_referral(db, referral_id, principal, "view")
    return {"items": readiness(db, r), "status": r.status, "amendment_open": r.amendment_open}


@router.get("/referrals/{referral_id}/brief-preview")
def brief_preview(referral_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """What the specialist will receive if the referral is sent now."""
    r = load_referral(db, referral_id, principal, "view")
    return brief_mod.build(db, r)


class SendIn(BaseModel):
    expected_version: int


@router.post("/referrals/{referral_id}/prepared")
def mark_prepared(referral_id: int, body: SendIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """Staff have gathered the records, papers and medicines; the doctor can now review the flags."""
    r = load_referral(db, referral_id, principal, "prepare", roles=(STAFF,))
    check_version(r, body.expected_version)
    if r.kind != "referral" or r.status != "requested":
        raise error(409, "not_preparing", "Only a referral being prepared can be marked ready")
    missing = blocking(staff_items(db, r))
    if missing:
        raise error(409, "not_ready", "Some things still need to be done first", blockers=missing)
    r.prepared_by, r.prepared_at = principal.display_name, utcnow()
    bump(r)
    event(db, r, "prepared", principal.display_name, principal.institution_id)
    audit(db, principal, "referral.prepared", "referral", r.reference, "success", r.id)
    flags = med.unacknowledged_flags(db, r.id)
    notify_doctor(db, r, "ready_for_review", f"{r.reference}: ready for your review",
                  f"{r.patient_name}. Staff have gathered the records and medicines."
                  + (f" {len(flags)} medication flag(s) to review." if flags else " There are no medication flags."),
                  tab="medicines")
    if not flags:
        notify_staff(db, r, "ready_to_send", f"{r.reference}: ready to send", "No medication flags to review.", tab="send")
    db.commit()
    return referral_out(r)


@router.post("/referrals/{referral_id}/send")
def send(referral_id: int, body: SendIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """Staff send the referral once every check is done."""
    r = load_referral(db, referral_id, principal, "send", roles=(STAFF,))
    check_version(r, body.expected_version)
    pkg = packages.send(db, r, principal)
    db.commit()
    enqueue("deliver_outbox")
    return {"referral": referral_out(r), "package_version": pkg.version, "content_hash": pkg.content_hash}


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


@router.get("/referrals/{referral_id}/packages/{version}")
def get_package(referral_id: int, version: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    r = load_referral(db, referral_id, principal, "view")
    pkg = db.scalars(select(ReferralPackage).where(ReferralPackage.referral_id == r.id, ReferralPackage.version == version)).first()
    if pkg is None:
        raise error(404, "not_found", "Version not found")
    return {"version": pkg.version, "sent_by": pkg.sent_by, "sent_at": pkg.sent_at, "content_hash": pkg.content_hash,
            "superseded": pkg.superseded, "envelope": pkg.envelope, "manifest": pkg.manifest,
            "content_purged_at": pkg.content_purged_at}


class VerifyCopyIn(BaseModel):
    package: dict


def _package(db: Session, r, version: int) -> ReferralPackage:
    pkg = db.scalars(select(ReferralPackage).where(ReferralPackage.referral_id == r.id, ReferralPackage.version == version)).first()
    if pkg is None:
        raise error(404, "not_found", "Version not found")
    return pkg


@router.post("/referrals/{referral_id}/packages/{version}/verify")
def verify_package_copy(referral_id: int, version: int, body: VerifyCopyIn, db: Session = Depends(get_db),
                        principal: Principal = Depends(get_principal)):
    """Compare a copy of the package (held by the sender or the receiver) with the fingerprint kept at sending."""
    r = load_referral(db, referral_id, principal, "view")
    pkg = _package(db, r, version)
    result = verify_copy(pkg.content_hash, body.package)
    audit(db, principal, "package.verify_copy", "referral_package", f"{r.reference}v{version}", result["result"], r.id)
    db.commit()
    return {"package_version": version, "content_hash": pkg.content_hash, **result}


@router.post("/referrals/{referral_id}/packages/{version}/verify-own-copy")
def verify_own_copy(referral_id: int, version: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """Fetch this clinic's own stored copy (from its own system, with the user's token) and check it."""
    r = load_referral(db, referral_id, principal, "view")
    pkg = _package(db, r, version)
    copies = sources.call(r.source_institution, "GET", "/outbound-copies", principal, params={"referral_id": r.reference})
    mine = next((c for c in copies if c["kind"] == "package" and c["version"] == version), None)
    result = verify_copy(pkg.content_hash, mine["content"]) if mine else {
        "result": "no_copy", "message": "Your clinic's system holds no copy of this version"}
    audit(db, principal, "package.verify_own_copy", "referral_package", f"{r.reference}v{version}", result["result"], r.id)
    db.commit()
    return {"package_version": version, "content_hash": pkg.content_hash, "copy": mine["content"] if mine else None, **result}
