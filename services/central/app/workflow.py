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
    reevaluate(db, referral, trigger, name, principal)
