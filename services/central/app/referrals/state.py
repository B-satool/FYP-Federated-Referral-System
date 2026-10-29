"""Referral status model with server-side transition validation."""
from __future__ import annotations

from refcommon.auth import Principal
from refcommon.db import utcnow
from sqlalchemy.orm import Session

from ..models import Referral, ReferralEvent
from ..security import audit, bump, error

STATUS_LABELS = {
    "draft": "Draft (doctor)",
    "requested": "In progress",
    "submitted": "Sent",
    "acknowledged": "Acknowledged",
    "accepted": "Accepted",
    "response_returned": "Response received",
    "followup_pending": "Follow-up",
    "closed": "Closed",
    "declined": "Declined",
    "cancelled": "Cancelled",
}
# A test request: in progress (staff check and send) -> sent -> results received -> closed
TEST_STATUS_LABELS = {**STATUS_LABELS, "submitted": "Tests sent", "response_returned": "Results received"}


def status_label(referral: Referral) -> str:
    labels = TEST_STATUS_LABELS if referral.kind == "test" else STATUS_LABELS
    if referral.kind == "referral" and referral.status == "requested":
        if referral.packet_reviewed_at:
            return "Ready to send"
        return "With the doctor for review" if referral.prepared_at else "In progress"
    return labels.get(referral.status, referral.status)


TRANSITIONS: dict[str, set[str]] = {
    "draft": {"requested", "cancelled"},
    "requested": {"submitted", "draft", "cancelled"},
    "submitted": {"acknowledged", "declined", "cancelled", "response_returned"},  # tests go straight to results
    "acknowledged": {"accepted", "declined", "cancelled"},
    # a referral needs no specialist response: once accepted, the clinic tells the patient and closes it
    "accepted": {"followup_pending", "closed", "cancelled", "response_returned"},
    "response_returned": {"followup_pending", "closed"},
    "followup_pending": {"closed"},
    "closed": set(),
    "declined": set(),
    "cancelled": set(),
}

PRE_SUBMISSION = {"draft", "requested"}
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
    from ..lifecycle.working_set import on_status

    on_status(referral, to)  # answered or ended: retrieved content is kept only for the grace period
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
    """A clinical change after a version was sent means a new version must be sent (an amendment)."""
    from ..notifications import notify_staff

    ensure_clinical_edit_allowed(referral)
    bump(referral)
    if referral.packet_reviewed_at is not None:  # the doctor reviews the changed packet again
        referral.packet_reviewed_by = referral.packet_reviewed_at = None
    if referral.status in IN_FLIGHT and not referral.amendment_open:
        referral.amendment_open = True
        event(db, referral, "amendment_started", actor, principal.institution_id if principal else None,
              {"reason": f"Clinical content changed after sending ({what}); a new version must be sent",
               "sent_version": referral.submitted_package_version})
        notify_staff(db, referral, "amendment_open", f"{referral.reference}: changed after sending",
                     f"{what.capitalize()}. Check the referral and send the new version.", tab="send")


def touch(referral: Referral) -> None:
    referral.updated_at = utcnow()
