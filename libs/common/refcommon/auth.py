"""OIDC access-token verification shared by every service.

Each service verifies tokens itself (signature, issuer, its own audience) and
then asks Keycloak whether the token is still active (token introspection,
cached briefly). Introspection is what makes a disabled account or revoked
session stop working before the access token's natural expiry (FR-05).

Identity is never taken from arbitrary request headers; only from a verified
token.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass, field

import httpx
import jwt
from fastapi import HTTPException, Request
from jwt import PyJWKClient

log = logging.getLogger("refcommon.auth")

SERVICE_ROLES = frozenset({"svc_central", "svc_specialist"})
INTROSPECTION_CACHE_SECONDS = 10


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Principal:
    subject: str
    username: str
    display_name: str
    institution_id: str | None
    roles: frozenset[str]
    client_id: str | None
    token: str = field(repr=False)

    @property
    def is_service(self) -> bool:
        return bool(self.roles & SERVICE_ROLES)

    def has_any(self, *roles: str) -> bool:
        return bool(self.roles.intersection(roles))


class AuthError(Exception):
    pass


class KeycloakConfig:
    def __init__(self) -> None:
        self.internal_url = os.environ.get("KEYCLOAK_INTERNAL_URL", "http://keycloak:8080").rstrip("/")
        self.public_url = os.environ.get("KEYCLOAK_PUBLIC_URL", "http://localhost:8080").rstrip("/")
        self.realm = os.environ.get("KEYCLOAK_REALM", "referral")
        self.client_id = os.environ.get("SERVICE_CLIENT_ID")
        self.client_secret = os.environ.get("SERVICE_CLIENT_SECRET")
        self.introspect = _env_bool("INTROSPECT_TOKENS", True)

    @property
    def realm_internal(self) -> str:
        return f"{self.internal_url}/realms/{self.realm}"

    @property
    def issuers(self) -> set[str]:
        return {f"{self.public_url}/realms/{self.realm}", self.realm_internal}

    @property
    def token_url(self) -> str:
        return f"{self.realm_internal}/protocol/openid-connect/token"

    @property
    def certs_url(self) -> str:
        return f"{self.realm_internal}/protocol/openid-connect/certs"

    @property
    def introspect_url(self) -> str:
        return f"{self.realm_internal}/protocol/openid-connect/token/introspect"

    @property
    def admin_url(self) -> str:
        return f"{self.internal_url}/admin/realms/{self.realm}"


class TokenVerifier:
    def __init__(self, cfg: KeycloakConfig, audience: str) -> None:
        self.cfg = cfg
        self.audience = audience
        self._jwks = PyJWKClient(cfg.certs_url, cache_keys=True, lifespan=600)
        self._cache: dict[str, tuple[float, bool]] = {}
        self._lock = threading.Lock()

    def _introspect_active(self, token: str) -> bool:
        now = time.monotonic()
        with self._lock:
            hit = self._cache.get(token)
            if hit and hit[0] > now:
                return hit[1]
        if not (self.cfg.client_id and self.cfg.client_secret):
            raise AuthError("service is not configured for token introspection")
        resp = httpx.post(
            self.cfg.introspect_url,
            data={"token": token},
            auth=(self.cfg.client_id, self.cfg.client_secret),
            timeout=5.0,
        )
        resp.raise_for_status()
        active = bool(resp.json().get("active"))
        with self._lock:
            if len(self._cache) > 5000:
                self._cache = {k: v for k, v in self._cache.items() if v[0] > now}
            self._cache[token] = (now + INTROSPECTION_CACHE_SECONDS, active)
        return active

    def invalidate_cache(self) -> None:
        with self._lock:
            self._cache.clear()

    def verify(self, token: str) -> Principal:
        try:
            key = self._jwks.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                key.key,
                algorithms=["RS256"],
                audience=self.audience,
                options={"verify_iss": False, "require": ["exp", "iat", "sub"]},
                leeway=10,
            )
        except jwt.PyJWKClientConnectionError as exc:
            raise httpx.ConnectError(str(exc)) from exc
        except jwt.PyJWTError as exc:
            raise AuthError(f"invalid token: {exc}") from exc
        if claims.get("iss") not in self.cfg.issuers:
            raise AuthError("unexpected token issuer")
        if self.cfg.introspect and not self._introspect_active(token):
            raise AuthError("session is no longer active (account disabled or access revoked)")

        roles = frozenset(claims.get("realm_access", {}).get("roles", []))
        institution = claims.get("institution_id")
        if not institution:
            groups = claims.get("groups") or []
            institution = groups[0].strip("/").split("/")[-1] if groups else None
        username = claims.get("preferred_username") or claims.get("azp") or claims["sub"]
        return Principal(
            subject=claims["sub"],
            username=username,
            display_name=claims.get("name") or username,
            institution_id=institution,
            roles=roles,
            client_id=claims.get("azp"),
            token=token,
        )


def make_principal_dependency(verifier: TokenVerifier):
    """FastAPI dependency returning the verified Principal for the request."""

    def dependency(request: Request) -> Principal:
        header = request.headers.get("authorization", "")
        if not header.lower().startswith("bearer "):
            raise HTTPException(
                status_code=401,
                detail={"code": "unauthenticated", "message": "Sign-in required"},
                headers={"WWW-Authenticate": "Bearer"},
            )
        try:
            principal = verifier.verify(header[7:].strip())
        except AuthError as exc:
            raise HTTPException(
                status_code=401,
                detail={"code": "unauthenticated", "message": str(exc)},
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc
        except httpx.HTTPError as exc:
            log.warning("identity provider unreachable: %s", exc)
            raise HTTPException(
                status_code=503,
                detail={"code": "identity_unavailable", "message": "Identity provider is unavailable; try again shortly"},
            ) from exc
        request.state.principal = principal
        return principal

    return dependency


def forbid(message: str, code: str = "forbidden") -> HTTPException:
    return HTTPException(status_code=403, detail={"code": code, "message": message})


class ServiceTokenProvider:
    """Client-credentials token for service-to-service calls, cached until near expiry."""

    def __init__(self, cfg: KeycloakConfig) -> None:
        self.cfg = cfg
        self._token: str | None = None
        self._expires_at = 0.0
        self._lock = threading.Lock()

    def get(self) -> str:
        with self._lock:
            if self._token and time.monotonic() < self._expires_at - 30:
                return self._token
            resp = httpx.post(
                self.cfg.token_url,
                data={"grant_type": "client_credentials"},
                auth=(self.cfg.client_id or "", self.cfg.client_secret or ""),
                timeout=10.0,
            )
            resp.raise_for_status()
            body = resp.json()
            self._token = body["access_token"]
            self._expires_at = time.monotonic() + float(body.get("expires_in", 60))
            return self._token
