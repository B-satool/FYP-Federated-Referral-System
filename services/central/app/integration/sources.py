"""Authenticated calls to the institution services' APIs (never their databases) on a user's behalf: patient
lookup, link checks, registration, intake. The caller's own access token is forwarded so each institution decides
about this user itself. Records for a referral are not fetched here: they are requested under consent with signed
requests and arrive encrypted (records/requests.py).
"""
from __future__ import annotations

from typing import Any

import httpx
from refcommon.auth import Principal

from ..config import institution_name, institution_url, settings
from ..security import error

def source_name(institution_id: str) -> str:
    return institution_name(institution_id) or institution_id


def _detail_message(resp: httpx.Response) -> str:
    try:
        body = resp.json()
        detail = body.get("detail", body)
        if isinstance(detail, dict):
            return str(detail.get("message") or detail)
        return str(detail)
    except ValueError:
        return resp.text[:200]


def _headers(principal: Principal, referral_ref: str | None = None) -> dict:
    h = {"Authorization": f"Bearer {principal.token}"}
    if referral_ref:
        h["X-Referral-Id"] = referral_ref
    return h


def call(institution_id: str, method: str, path: str, principal: Principal, json: Any = None,
         params: dict | None = None, referral_ref: str | None = None) -> Any:
    """A user action at an institution (search, lookup, register, share). Errors are raised
    as API errors with the institution's own message."""
    url = institution_url(institution_id) + path
    try:
        resp = httpx.request(method, url, json=json, params=params, headers=_headers(principal, referral_ref),
                             timeout=settings.source_timeout_seconds)
    except httpx.HTTPError as exc:
        raise error(503, "source_unavailable", f"{source_name(institution_id)} is unavailable; try again shortly") from exc
    if resp.status_code >= 400:
        raise error(resp.status_code if resp.status_code < 500 else 502, "source_error", _detail_message(resp))
    return resp.json()
