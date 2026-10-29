"""The platform's own signing key and its signed request assertions to the institution adapters (docs/auth.md).

The platform signs (a) request assertions it sends to adapters and (b) patients' directory entries, after the
signed-in patient registers keys generated on their device. It never holds a doctor's, department's or patient's
private key.
"""
from __future__ import annotations

from datetime import datetime, timezone

import httpx
from fastapi import HTTPException, Request
from refcommon import e2e
from refcommon.participants import PLATFORM_ID, registry
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import settings
from ..db import SessionLocal
from ..models import PlatformKey, SeenAssertion
from ..security import audit


def _store_key() -> bytes:
    if not settings.keystore_secret:
        raise RuntimeError("KEYSTORE_SECRET is not set: the platform cannot hold its signing key")
    return e2e.store_key(settings.keystore_secret)


def key_row(db: Session) -> PlatformKey:
    row = db.scalars(select(PlatformKey).where(PlatformKey.retired_at.is_(None))
                     .order_by(PlatformKey.created_at.desc())).first()
    if row is None:
        key = e2e.generate_key()
        spki = e2e.public_spki(key)
        row = PlatformKey(kid=e2e.key_id(spki), public_spki=spki,
                          private_sealed=e2e.encrypt(_store_key(), e2e.private_pkcs8(key), "refx/v1|keystore|hub"))
        db.add(row)
        db.flush()
    return row


def signing_key(db: Session):
    row = key_row(db)
    return e2e.load_private(e2e.decrypt(_store_key(), row.private_sealed, "refx/v1|keystore|hub"))


def sign(db: Session, obj: dict) -> dict:
    return e2e.sign_object(signing_key(db), obj)


def assertion(db: Session, audience: str, claims: dict | None = None) -> str:
    return e2e.make_assertion(signing_key(db), issuer=PLATFORM_ID, audience=audience, claims=claims)


def adapter_call(db: Session, institution_id: str, method: str, path: str, json: dict | None = None,
                 claims: dict | None = None, timeout: float = 20.0) -> httpx.Response:
    """A signed request to an institution's adapter, refused here if that institution is not a participant in
    good standing (spec v4 6.1: participation can be suspended)."""
    p = registry.institution(institution_id)
    if p is None or not p.in_good_standing:
        raise PermissionError(f"{institution_id} is not a participant in good standing")
    from ..config import institution_url

    token = assertion(db, institution_id, claims)
    return httpx.request(method, institution_url(institution_id) + path, json=json, timeout=timeout,
                         headers={"Authorization": f"Bearer {token}"})


# --------------------------------------------------------------------------- adapter assertions received here
def _refuse(reason: str, issuer: str | None) -> HTTPException:
    with SessionLocal() as db:
        audit(db, None, "m2m.verify", "assertion", issuer or "unknown", "denied", None, {"reason": reason},
              actor=(issuer or "unknown", f"adapter {issuer or 'unknown'}", issuer))
        db.commit()
    return HTTPException(401, {"code": "assertion_rejected", "message": reason})


def verify_adapter(request: Request, db: Session) -> dict:
    """Claims of a request assertion signed by an institution's pinned hospital key (or 401, audited)."""
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        raise _refuse("no request assertion", None)
    token = header[7:].strip()
    issuer, _ = e2e.assertion_issuer(token)
    p = registry.institution(issuer)
    if p is None:
        raise _refuse("assertion is not from an onboarded institution", issuer)
    if not p.in_good_standing:
        raise _refuse("participation is suspended", issuer)
    try:
        claims = e2e.verify_assertion(token, p.signing_key, audience=PLATFORM_ID, issuer=issuer)
    except e2e.CryptoError as exc:
        raise _refuse(str(exc), issuer) from exc
    db.execute(delete(SeenAssertion).where(SeenAssertion.expires_at < datetime.now(timezone.utc)))
    db.add(SeenAssertion(jti=claims["jti"], issuer=issuer,
                         expires_at=datetime.fromtimestamp(claims["exp"], tz=timezone.utc)))
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise _refuse("assertion was already used (replay)", issuer) from exc
    return claims
