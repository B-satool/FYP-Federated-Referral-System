"""Shared helpers for the integration checks (run against the local Compose stack)."""
from __future__ import annotations

import os
import time

import httpx

KEYCLOAK = os.environ.get("KEYCLOAK_URL", "http://localhost:8080")
CENTRAL = os.environ.get("CENTRAL_URL", "http://localhost:8000")
INSTITUTION_URLS = {
    "drali": os.environ.get("DRALI_URL", "http://localhost:8001"),
    "chughtai": os.environ.get("CHUGHTAI_URL", "http://localhost:8002"),
    "ziauddin": os.environ.get("ZIAUDDIN_URL", "http://localhost:8003"),
    "akuh": os.environ.get("AKUH_URL", "http://localhost:8004"),
}
PASSWORD = os.environ.get("DEMO_USER_PASSWORD", "demo1234")

_tokens: dict[str, tuple[str, float]] = {}


def token(username: str, fresh: bool = False) -> str:
    hit = _tokens.get(username)
    if hit and not fresh and hit[1] > time.time() + 30:
        return hit[0]
    resp = httpx.post(f"{KEYCLOAK}/realms/referral/protocol/openid-connect/token",
                      data={"grant_type": "password", "client_id": "dev-cli", "username": username, "password": PASSWORD,
                            "scope": "openid"}, timeout=15)
    resp.raise_for_status()
    body = resp.json()
    _tokens[username] = (body["access_token"], time.time() + body["expires_in"])
    return body["access_token"]


class Api:
    def __init__(self, base: str, username: str):
        self.base, self.username = base, username

    def _h(self):
        return {"Authorization": f"Bearer {token(self.username)}"}

    def get(self, path, **kw):
        return httpx.get(self.base + path, headers=self._h(), timeout=60, **kw)

    def post(self, path, json=None, **kw):
        return httpx.post(self.base + path, json=json, headers=self._h(), timeout=60, **kw)

    def put(self, path, json=None, **kw):
        return httpx.put(self.base + path, json=json, headers=self._h(), timeout=60, **kw)

    def patch(self, path, json=None, **kw):
        return httpx.patch(self.base + path, json=json, headers=self._h(), timeout=60, **kw)


def central(user: str) -> Api:
    return Api(CENTRAL, user)


def institution(name: str, user: str) -> Api:
    """An institution's own system (e.g. the receiving hospital's inbox)."""
    return Api(INSTITUTION_URLS[name], user)


def ok(resp: httpx.Response, status: int | tuple = (200, 201, 202)) -> dict:
    expected = status if isinstance(status, tuple) else (status,)
    assert resp.status_code in expected, f"{resp.request.method} {resp.request.url} -> {resp.status_code}: {resp.text[:800]}"
    return resp.json()


def wait_for(fn, timeout: float = 60, interval: float = 1.0, what: str = "condition"):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        last = fn()
        if last:
            return last
        time.sleep(interval)
    raise AssertionError(f"timed out waiting for {what}; last={last!r}")
