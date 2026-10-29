"""Cross-module refresh hook: after a record, medicine or procedure change, re-run the
deterministic medication evaluation."""
from __future__ import annotations

from refcommon.auth import Principal
from sqlalchemy.orm import Session

from .medications.service import reevaluate
from .models import Referral


def after_change(db: Session, referral: Referral, trigger: str, principal: Principal | None = None,
                 actor: str | None = None) -> None:
    name = actor or (principal.display_name if principal else "system")
    clear_packet_review(db, referral, trigger, name)
    reevaluate(db, referral, trigger, name, principal)


def clear_packet_review(db: Session, referral: Referral, why: str, actor: str) -> None:
    """The doctor's packet review covers the content as it was. A later clinical change needs a fresh review."""
    from .referrals.state import event

    if referral.packet_reviewed_at is not None:
        referral.packet_reviewed_by = referral.packet_reviewed_at = None
        event(db, referral, "packet_review_cleared", actor, referral.source_institution, {"reason": why})
