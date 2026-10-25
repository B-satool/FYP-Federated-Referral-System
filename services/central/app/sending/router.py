"""Readiness, sending, delivery status and sent versions."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from refcommon.auth import Principal
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Outbox, ReferralPackage
from ..security import STAFF, check_version, error, get_principal, load_referral
from ..serializers import referral_out
from ..tasks import enqueue
from . import brief as brief_mod
from . import packages
from .readiness import readiness

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
            "superseded": pkg.superseded, "envelope": pkg.envelope}
