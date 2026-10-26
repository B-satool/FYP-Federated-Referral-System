"""Authenticated calls to the institution services' APIs (never their databases).

The caller's own access token is forwarded so each institution makes its own
decision about this user, institution and patient. Timeouts and bounded
retries apply only to transient failures; denials and invalid data are
returned immediately as distinct outcomes.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

import httpx
from refcommon.auth import Principal

from ..config import institution_name, institution_url, settings
from ..security import error

TRANSIENT = (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError, httpx.ReadError)


@dataclass
class SourceCall:
    status: str  # successful | empty | partial | denied | unavailable | invalid
    message: str
    retryable: bool = False
    attempts: int = 1
    duration_ms: int = 0
    bundle: dict | None = None
    withheld: list[str] = field(default_factory=list)


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


def _ms(start: float) -> int:
    return int((time.monotonic() - start) * 1000)


def _get(institution_id: str, path: str, principal: Principal, referral_ref: str | None, params: dict | None = None):
    """GET with bounded retries on transient failures. Returns (response | None, attempts, error message)."""
    url = institution_url(institution_id) + path
    attempts = 0
    while True:
        attempts += 1
        try:
            resp = httpx.get(url, params=params, headers=_headers(principal, referral_ref),
                             timeout=settings.source_timeout_seconds)
        except TRANSIENT as exc:
            if attempts <= settings.source_max_retries:
                time.sleep(0.4 * attempts)
                continue
            kind = "timed out" if isinstance(exc, httpx.TimeoutException) else "could not be reached"
            return None, attempts, f"{source_name(institution_id)} {kind} after {attempts} attempts"
        if resp.status_code in (502, 503, 504, 429) or resp.status_code >= 500:
            if attempts <= settings.source_max_retries:
                time.sleep(0.4 * attempts)
                continue
            return None, attempts, f"{source_name(institution_id)} returned an error ({resp.status_code})"
        return resp, attempts, ""


def _denied_status(resp) -> str:
    """'expired' when the source says its access grant ran out (shown as access expired, never as no records)."""
    return "expired" if "access grant expired" in _detail_message(resp) else "denied"


def last_activity(institution_id: str, local_id: str, principal: Principal, referral_ref: str) -> tuple[str, str | None, str]:
    """(status, last activity date, message). status: successful | denied | unavailable | empty | invalid."""
    resp, _, err = _get(institution_id, f"/patients/{quote(local_id, safe='')}/activity", principal, referral_ref)
    if resp is None:
        return "unavailable", None, err
    if resp.status_code in (401, 403):
        return _denied_status(resp), None, f"{source_name(institution_id)} denied access: {_detail_message(resp)}"
    if resp.status_code == 404:
        return "empty", None, f"{source_name(institution_id)} has no matching patient record"
    if resp.status_code != 200:
        return "invalid", None, f"{source_name(institution_id)} returned an unexpected response ({resp.status_code})"
    return "successful", resp.json().get("last_activity"), ""


def fetch_records(institution_id: str, local_id: str, principal: Principal, referral_ref: str, since: str) -> SourceCall:
    start = time.monotonic()
    resp, attempts, err = _get(institution_id, f"/fhir/patients/{quote(local_id, safe='')}/records", principal,
                               referral_ref, {"since": since})
    name = source_name(institution_id)
    if resp is None:
        return SourceCall("unavailable", f"{err}. Existing records are kept; retry later.", retryable=True,
                          attempts=attempts, duration_ms=_ms(start))
    duration = _ms(start)
    if resp.status_code in (401, 403):
        return SourceCall(_denied_status(resp), f"{name} denied access: {_detail_message(resp)}", attempts=attempts,
                          duration_ms=duration)
    if resp.status_code == 404:
        return SourceCall("empty", f"{name} has no matching patient record ({_detail_message(resp)})",
                          attempts=attempts, duration_ms=duration)
    if resp.status_code != 200:
        return SourceCall("invalid", f"{name} returned an unexpected response ({resp.status_code})",
                          attempts=attempts, duration_ms=duration)
    try:
        body = resp.json()
    except ValueError:
        return SourceCall("invalid", f"{name} returned data that is not valid JSON", attempts=attempts, duration_ms=duration)
    if not isinstance(body, dict) or body.get("resourceType") != "Bundle":
        return SourceCall("invalid", f"{name} did not return a FHIR Bundle", attempts=attempts, duration_ms=duration)
    withheld = [issue.get("diagnostics", "some categories withheld")
                for entry in body.get("entry", []) if entry.get("resource", {}).get("resourceType") == "OperationOutcome"
                for issue in entry["resource"].get("issue", [])]
    return SourceCall("successful", "", attempts=attempts, duration_ms=duration, bundle=body, withheld=withheld)


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
