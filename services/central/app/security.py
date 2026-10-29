"""Authentication, authorization and audit for the central platform.

* Tokens are verified (signature, issuer, audience=central-api) and introspected.
* Every user request is also checked against the central account status, so a
  disabled account loses access to centrally retained data immediately.
* Referral access is scoped by institution and role on the server; the UI's
  role-based screens are never the enforcement point.
"""
from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, Request
from refcommon.auth import KeycloakConfig, Principal, ServiceTokenProvider, TokenVerifier, make_principal_dependency
from refcommon.db import utcnow
from sqlalchemy.orm import Session

from .db import SessionLocal, get_db
from .models import AuditEvent, Referral, User

kc_config = KeycloakConfig()
verifier = TokenVerifier(kc_config, audience="central-api")
service_tokens = ServiceTokenProvider(kc_config)
_verified_principal = make_principal_dependency(verifier)

CLINIC_ROLES = ("clinic_staff", "clinician")  # anyone who prepares or requests referrals
DOCTOR = "clinician"
STAFF = "clinic_staff"


def error(status: int, code: str, message: str, **extra: Any) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message, **extra})


def audit(db: Session, principal: Principal | None, action: str, target_type: str, target_id: Any,
          outcome: str = "success", referral_id: int | None = None, detail: dict | None = None,
          actor: tuple[str, str, str | None] | None = None) -> None:
    if actor:
        actor_id, actor_name, institution = actor
    elif principal:
        actor_id, actor_name, institution = principal.subject, principal.display_name, principal.institution_id
    else:
        actor_id, actor_name, institution = "system", "system", None
    db.add(AuditEvent(actor_id=actor_id, actor_name=actor_name, institution_id=institution, action=action,
                      target_type=target_type, target_id=str(target_id), referral_id=referral_id,
                      outcome=outcome, detail=detail or {}))


def audit_now(principal: Principal | None, action: str, target_type: str, target_id: Any, outcome: str,
              referral_id: int | None = None, detail: dict | None = None) -> None:
    """Record in a separate transaction (used for denials that abort the main request)."""
    with SessionLocal() as db:
        audit(db, principal, action, target_type, target_id, outcome, referral_id, detail)
        db.commit()


def deny(principal: Principal, action: str, target_type: str, target_id: Any, message: str,
         referral_id: int | None = None) -> HTTPException:
    audit_now(principal, action, target_type, target_id, "denied", referral_id, {"message": message})
    return error(403, "forbidden", message)


def get_principal(request: Request, principal: Principal = Depends(_verified_principal),
                  db: Session = Depends(get_db)) -> Principal:
    if principal.is_service:
        return principal
    user = db.get(User, principal.subject)
    if user is None:
        user = User(id=principal.subject, username=principal.username, display_name=principal.display_name,
                    institution_id=principal.institution_id, department=principal.department,
                    roles=sorted(principal.roles), account_status="active")
        db.add(user)
    else:
        user.username = principal.username
        user.display_name = principal.display_name
        user.institution_id = principal.institution_id
        user.department = principal.department
        user.roles = sorted(principal.roles)
        user.last_seen_at = utcnow()
    if user.account_status != "active":
        db.rollback()
        audit_now(principal, "access", "user", principal.subject, "denied", detail={"reason": "account disabled"})
        raise error(401, "account_disabled", "This account has been disabled by an administrator")
    db.commit()
    return principal


def require_roles(principal: Principal, *roles: str, action: str = "action", message: str | None = None) -> None:
    if not principal.has_any(*roles):
        raise deny(principal, action, "role", ",".join(roles),
                   message or f"This action requires one of the roles: {', '.join(roles)}")


def sees_clinical(principal: Principal) -> bool:
    """Only roles whose template gives 'content' visibility (doctors) see clinical content, and even then only what
    is encrypted to their own key opens. Staff see titles, statuses and counts (spec v4 4, D3, D14)."""
    from .identity.role_templates import profile

    return profile(set(principal.roles), principal.institution_id)["record_visibility"] == "content"


def require_scope(principal: Principal, scope: str, action: str) -> None:
    """The caller's role templates must include this API scope (spec v4 4.1); refusals are audited."""
    from .identity.role_templates import profile

    if scope not in profile(set(principal.roles), principal.institution_id)["scopes"]:
        raise deny(principal, action, "scope", scope, f"Your role does not include '{scope}'")


def require_doctor(principal: Principal, action: str) -> None:
    require_roles(principal, DOCTOR, action=action,
                  message="Only a doctor sees and changes the patient's clinical records")


def require_service(principal: Principal, role: str) -> None:
    if role not in principal.roles:
        raise deny(principal, "service_call", "service", role, "Only the authorized service identity may call this endpoint")


def load_referral(db: Session, referral_id: int, principal: Principal, action: str = "view",
                  roles: tuple[str, ...] = CLINIC_ROLES) -> Referral:
    """Load a referral the caller may act on. Clinic users only see their institution's referrals."""
    referral = db.get(Referral, referral_id)
    if referral is None:
        raise error(404, "not_found", "Referral not found")
    if principal.institution_id != referral.source_institution:
        raise deny(principal, f"referral.{action}", "referral", referral.reference,
                   "Referral belongs to another institution", referral.id)
    if not principal.has_any(*roles):
        raise deny(principal, f"referral.{action}", "referral", referral.reference,
                   f"Your role cannot perform '{action}' on referrals", referral.id)
    return referral


def check_version(referral: Referral, expected: int | None) -> None:
    if expected is not None and expected != referral.row_version:
        raise error(409, "stale_version",
                    "This referral was changed by someone else since you opened it. Reload to see the latest version.",
                    current_version=referral.row_version)


def bump(referral: Referral) -> None:
    referral.row_version += 1
    referral.updated_at = utcnow()
