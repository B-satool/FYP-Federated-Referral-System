"""Cross-module refresh hook: after evidence, medication or referral-context changes,
re-run deterministic medication evaluation and the completeness checklist."""
from __future__ import annotations

from refcommon.auth import Principal
from sqlalchemy.orm import Session

from .medications.service import reevaluate
from .models import Referral
from .reviews.checklist import refresh


def after_change(db: Session, referral: Referral, trigger: str, principal: Principal | None = None,
                 actor: str | None = None) -> None:
    name = actor or (principal.display_name if principal else "system")
    reevaluate(db, referral, trigger, name, principal)
    refresh(db, referral)
