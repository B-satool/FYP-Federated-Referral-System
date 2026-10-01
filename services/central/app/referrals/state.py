"""Referral status model (SRS section 6) with server-side transition validation."""
from __future__ import annotations

from refcommon.auth import Principal
from refcommon.db import utcnow
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Referral, ReferralEvent, ReferralPackage
from ..security import audit, bump, error

STATUS_LABELS = {
    "draft": "Draft",
    "awaiting_information": "Awaiting information",
    "awaiting_approval": "Awaiting approval",
    "approved": "Approved",
    "submitted": "Submitted",
    "acknowledged": "Acknowledged",
    "accepted": "Accepted",
    "response_returned": "Response returned",
    "followup_pending": "Follow-up pending",
    "closed": "Closed",
    "declined": "Declined",
    "cancelled": "Cancelled",
}

TRANSITIONS: dict[str, set[str]] = {
    "draft": {"awaiting_information", "awaiting_approval", "cancelled"},
    "awaiting_information": {"draft", "awaiting_approval", "cancelled"},
    "awaiting_approval": {"draft", "awaiting_information", "approved", "cancelled"},
    "approved": {"submitted", "draft", "cancelled"},
    "submitted": {"acknowledged", "declined", "cancelled"},
    "acknowledged": {"accepted", "declined", "cancelled"},
    "accepted": {"response_returned", "cancelled"},
    "response_returned": {"followup_pending", "closed"},
    "followup_pending": {"closed"},
    "closed": set(),
    "declined": set(),
    "cancelled": set(),
}

PRE_SUBMISSION = {"draft", "awaiting_information", "awaiting_approval", "approved"}
IN_FLIGHT = {"submitted", "acknowledged", "accepted"}
CLINICAL_LOCKED = {"response_returned", "followup_pending", "closed", "declined", "cancelled"}
TERMINAL = {"closed", "declined", "cancelled"}


def transition(db: Session, referral: Referral, to: str, actor: str, principal: Principal | None = None,
               detail: dict | None = None, institution: str | None = None) -> None:
    current = referral.status
    if to == current:
        return
    if to not in TRANSITIONS.get(current, set()):
        raise error(409, "invalid_transition",
                    f"Cannot move a referral from '{STATUS_LABELS[current]}' to '{STATUS_LABELS.get(to, to)}'")
    referral.status = to
    bump(referral)
    db.add(ReferralEvent(referral_id=referral.id, event_type="status_change", from_status=current, to_status=to,
                         actor=actor, institution_id=institution or (principal.institution_id if principal else None),
                         detail=detail or {}))
    audit(db, principal, "referral.status_change", "referral", referral.reference, "success", referral.id,
          {"from": current, "to": to, **(detail or {})},
          actor=None if principal else ("system", actor, institution))


def event(db: Session, referral: Referral, event_type: str, actor: str, institution: str | None, detail: dict | None = None) -> None:
    db.add(ReferralEvent(referral_id=referral.id, event_type=event_type, actor=actor, institution_id=institution,
                         detail=detail or {}))


def ensure_clinical_edit_allowed(referral: Referral) -> None:
    if referral.status in CLINICAL_LOCKED:
        raise error(409, "clinical_content_locked",
                    f"Clinical content cannot change once the referral is '{STATUS_LABELS[referral.status]}'")


def mark_clinical_change(db: Session, referral: Referral, actor: str, what: str, principal: Principal | None = None) -> None:
    """Any change to approved clinical content requires a new version and renewed approval (FR-15)."""
    ensure_clinical_edit_allowed(referral)
    bump(referral)
    if referral.status == "approved":
        pkg = db.scalars(select(ReferralPackage).where(ReferralPackage.referral_id == referral.id,
                                                       ReferralPackage.version == referral.current_package_version)).first()
        if pkg and referral.submitted_package_version != pkg.version:
            pkg.superseded = True
        transition(db, referral, "draft", actor, principal,
                   {"reason": f"Approved content changed ({what}); renewed approval required"})
    elif referral.status in IN_FLIGHT and not referral.amendment_open:
        referral.amendment_open = True
        event(db, referral, "amendment_started", actor, principal.institution_id if principal else None,
              {"reason": f"Clinical content changed after submission ({what}); a new approved version is required",
               "submitted_version": referral.submitted_package_version})


def touch(referral: Referral) -> None:
    referral.updated_at = utcnow()
