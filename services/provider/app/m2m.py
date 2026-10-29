"""Machine-to-machine requests between this institution and the platform (spec v4 section 6.3; docs/auth.md).

Each request carries a short-lived ES256 request assertion signed by the caller's key: the platform's key for
requests to this institution, this hospital's signing key for requests to the platform. Keys are taken from the
pinned participant registry, never from the request. A request is refused for a bad signature, another audience,
an expired or over-long assertion, a replayed `jti`, or a participant that is not in good standing.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException, Request
from refcommon import e2e
from refcommon.db import utcnow
from refcommon.participants import PLATFORM_ID, registry
from refcommon.sourcekit import record_audit
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import keys
from .config import HUB_URL, INSTITUTION
from .models import AuditEvent, SeenAssertion


# audit actor for requests made by the platform (not a person)
HUB_ACTOR = (PLATFORM_ID, "central platform (signed request)", "central-platform")


def refuse(db: Session, reason: str, detail: dict | None = None) -> HTTPException:
    record_audit(db, AuditEvent, None, "m2m.verify", "assertion", "hub", "denied",
                 detail={"reason": reason, **(detail or {})}, actor_override=HUB_ACTOR)
    db.commit()
    return HTTPException(401, {"code": "assertion_rejected", "message": reason})


def verify_hub(request: Request, db: Session) -> dict:
    """The verified claims of the platform's request assertion (or 401, audited)."""
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        raise refuse(db, "no request assertion")
    token = header[7:].strip()
    issuer, _ = e2e.assertion_issuer(token)
    pinned = registry.issuer_key(PLATFORM_ID)
    if issuer != PLATFORM_ID or not pinned:
        raise refuse(db, "assertion is not from the onboarded platform", {"issuer": issuer})
    try:
        claims = e2e.verify_assertion(token, pinned, audience=INSTITUTION, issuer=PLATFORM_ID)
    except e2e.CryptoError as exc:
        raise refuse(db, str(exc)) from exc
    db.execute(delete(SeenAssertion).where(SeenAssertion.expires_at < utcnow()))
    db.add(SeenAssertion(jti=claims["jti"], issuer=issuer,
                         expires_at=datetime.fromtimestamp(claims["exp"], tz=timezone.utc)))
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise refuse(db, "assertion was already used (replay)", {"jti": claims["jti"]}) from exc
    record_audit(db, AuditEvent, None, "m2m.verify", "assertion", claims["jti"], "success",
                 referral_context=(claims.get("refx") or {}).get("referral"), detail={"path": request.url.path},
                 actor_override=HUB_ACTOR)
    return claims


def hub_call(db: Session, method: str, path: str, json: dict | None = None, claims: dict | None = None,
             timeout: float = 15.0) -> httpx.Response:
    """A request to the platform, signed with this hospital's key."""
    token = e2e.make_assertion(keys.hospital_key(db), issuer=INSTITUTION, audience=PLATFORM_ID, claims=claims)
    return httpx.request(method, HUB_URL + path, json=json, headers={"Authorization": f"Bearer {token}"},
                         timeout=timeout)


def publish_keys(db: Session) -> int:
    """Send unpublished directory entries, revocations and group-key wraps to the platform. Idempotent: the
    platform stores each item once. Returns how many items were sent (0 if nothing was due or it failed)."""
    batch = keys.unpublished(db)
    rows = batch.pop("_rows")
    count = sum(len(v) for v in batch.values())
    if not count:
        return 0
    try:
        resp = hub_call(db, "POST", "/e2e/adapter/directory", json=batch)
    except httpx.HTTPError:
        return 0
    if resp.status_code >= 300:
        return 0
    keys.mark_published(rows)
    db.commit()
    return count


_last_publish = 0.0


def publish_loop_tick(session_factory) -> None:
    """Called from the outbox loop: publish keys at most every few seconds once the installation is onboarded."""
    global _last_publish
    if time.monotonic() - _last_publish < 5 or not registry.onboarded:
        return
    _last_publish = time.monotonic()
    with session_factory() as db:
        publish_keys(db)
