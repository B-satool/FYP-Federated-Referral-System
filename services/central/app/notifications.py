"""Notifications: what a person should act on or know about (shown in the work queue)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from refcommon.auth import Principal
from refcommon.db import utcnow
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from .db import get_db
from .models import Notification, Referral
from .security import error, get_principal

router = APIRouter(tags=["notifications"])


def notify(db: Session, kind: str, title: str, *, institution: str, role: str | None = None,
           recipient_id: str | None = None, referral: Referral | None = None, body: str = "",
           link: str | None = None) -> None:
    """Address one user (recipient_id) or everyone with a role at an institution."""
    db.add(Notification(recipient_id=recipient_id, institution_id=institution, role=role,
                        referral_id=referral.id if referral else None, kind=kind, title=title, body=body,
                        link=link or (f"/referrals/{referral.id}" if referral else None)))


def notify_doctor(db: Session, referral: Referral, kind: str, title: str, body: str = "", tab: str | None = None) -> None:
    """The referral's requesting doctor (or, if unknown, the institution's doctors)."""
    link = f"/referrals/{referral.id}" + (f"?tab={tab}" if tab else "")
    if referral.requesting_doctor_id:
        notify(db, kind, title, institution=referral.source_institution, recipient_id=referral.requesting_doctor_id,
               referral=referral, body=body, link=link)
    else:
        notify(db, kind, title, institution=referral.source_institution, role="clinician", referral=referral,
               body=body, link=link)


def notify_staff(db: Session, referral: Referral, kind: str, title: str, body: str = "", tab: str | None = None) -> None:
    link = f"/referrals/{referral.id}" + (f"?tab={tab}" if tab else "")
    notify(db, kind, title, institution=referral.source_institution, role="clinic_staff", referral=referral,
           body=body, link=link)


def notify_patient(db: Session, referral: Referral, kind: str, title: str, body: str = "") -> None:
    """A notice in the patient's app (spec v4 step 9, 11.3): it appears on the referral's timeline there. Patient
    accounts belong to no institution, so they are addressed through their referral, matched by CNIC."""
    from .models import ReferralEvent

    db.add(ReferralEvent(referral_id=referral.id, event_type="patient_notice", actor="system",
                         institution_id=None, detail={"kind": kind, "title": title, "body": body}))


def _mine(principal: Principal):
    return and_(Notification.institution_id == principal.institution_id, or_(
        Notification.recipient_id == principal.subject,
        and_(Notification.recipient_id.is_(None), Notification.role.in_(sorted(principal.roles)))))


def _out(n: Notification) -> dict:
    return {"id": n.id, "kind": n.kind, "title": n.title, "body": n.body, "link": n.link, "referral_id": n.referral_id,
            "created_at": n.created_at, "read_at": n.read_at, "read_by": n.read_by,
            "personal": n.recipient_id is not None}


@router.get("/notifications")
def list_notifications(unread_only: bool = False, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    stmt = select(Notification).where(_mine(principal))
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    return [_out(n) for n in db.scalars(stmt.order_by(Notification.id.desc()).limit(100))]


@router.post("/notifications/{notification_id}/read")
def mark_read(notification_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    n = db.scalars(select(Notification).where(Notification.id == notification_id, _mine(principal))).first()
    if n is None:
        raise error(404, "not_found", "Notification not found")
    if n.read_at is None:
        n.read_at, n.read_by = utcnow(), principal.display_name
        db.commit()
    return _out(n)


@router.post("/notifications/read-all")
def mark_all_read(db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    rows = db.scalars(select(Notification).where(_mine(principal), Notification.read_at.is_(None))).all()
    for n in rows:
        n.read_at, n.read_by = utcnow(), principal.display_name
    db.commit()
    return {"marked": len(rows)}
