"""Authenticated calls to the source services' APIs (never their databases).

The caller's own access token is forwarded so each source makes its own
decision about this user, institution and patient. Timeouts and bounded
retries apply only to transient failures; denials and invalid data are
returned immediately as distinct outcomes.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from urllib.parse import quote

import httpx
from refcommon.auth import Principal

from ..config import INSTITUTIONS, SOURCES, settings

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


def _detail_message(resp: httpx.Response) -> str:
    try:
        body = resp.json()
        detail = body.get("detail", body)
        if isinstance(detail, dict):
            return str(detail.get("message") or detail)
        return str(detail)
    except ValueError:
        return resp.text[:200]


def source_name(institution_id: str) -> str:
    return INSTITUTIONS.get(institution_id, {}).get("name", institution_id)


def base_url(institution_id: str) -> str:
    return getattr(settings, SOURCES[institution_id]["url_attr"])


def fetch_records(institution_id: str, local_id: str, principal: Principal, referral_ref: str) -> SourceCall:
    cfg = SOURCES[institution_id]
    url = base_url(institution_id) + cfg["path"].format(id=quote(local_id, safe=""))
    headers = {"Authorization": f"Bearer {principal.token}", "X-Referral-Id": referral_ref}
    name = source_name(institution_id)
    start = time.monotonic()
    attempts = 0
    while True:
        attempts += 1
        try:
            resp = httpx.get(url, params={"categories": cfg["categories"]}, headers=headers,
                             timeout=settings.source_timeout_seconds)
        except TRANSIENT as exc:
            if attempts <= settings.source_max_retries:
                time.sleep(0.4 * attempts)
                continue
            kind = "timed out" if isinstance(exc, httpx.TimeoutException) else "could not be reached"
            return SourceCall("unavailable", f"{name} {kind} after {attempts} attempts. Existing evidence is kept; retry later.",
                              retryable=True, attempts=attempts, duration_ms=_ms(start))
        if resp.status_code in (502, 503, 504, 429) or resp.status_code >= 500:
            if attempts <= settings.source_max_retries:
                time.sleep(0.4 * attempts)
                continue
            return SourceCall("unavailable", f"{name} returned an error ({resp.status_code}). Retry later.",
                              retryable=True, attempts=attempts, duration_ms=_ms(start))
        break

    duration = _ms(start)
    if resp.status_code in (401, 403):
        return SourceCall("denied", f"{name} denied access: {_detail_message(resp)}", retryable=False,
                          attempts=attempts, duration_ms=duration)
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
    withheld: list[str] = []
    for entry in body.get("entry", []):
        res = entry.get("resource", {})
        if res.get("resourceType") == "OperationOutcome":
            for issue in res.get("issue", []):
                withheld.append(issue.get("diagnostics", "some categories withheld"))
    return SourceCall("successful", "", attempts=attempts, duration_ms=duration, bundle=body, withheld=withheld)


def identity_match(institution_id: str, payload: dict, principal: Principal, referral_ref: str | None) -> dict:
    url = base_url(institution_id) + "/identity/match"
    headers = {"Authorization": f"Bearer {principal.token}"}
    if referral_ref:
        headers["X-Referral-Id"] = referral_ref
    try:
        resp = httpx.post(url, json=payload, headers=headers, timeout=settings.source_timeout_seconds)
    except TRANSIENT:
        return {"error": f"{source_name(institution_id)} could not be reached"}
    if resp.status_code != 200:
        return {"error": _detail_message(resp)}
    return resp.json()


def _ms(start: float) -> int:
    return int((time.monotonic() - start) * 1000)
