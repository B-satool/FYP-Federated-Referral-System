"""Close temporary access when a referral is finished.

Central never writes an institution's database. When a referral reaches a final status
(closed, declined, cancelled) it asks every institution to revoke the grants that were opened
for that referral. The call uses the central service token and each institution revokes its own
grants. A failure leaves the referral unmarked so the next sweep retries; each grant's expiry
date is the final backstop.
"""
from __future__ import annotations

from typing import Callable

import httpx

from ..config import SOURCES, institution_url

GRANTS_CLOSED_EVENT = "grants_closed"


def close_grants(reference: str, post: Callable[[str, dict], dict]) -> dict[str, str]:
    """Ask every institution to revoke grants for this referral. Returns institution -> 'ok' or an error text."""
    results: dict[str, str] = {}
    for source_id in sorted(SOURCES):
        url = institution_url(source_id) + "/grants/revoke-by-referral"
        try:
            post(url, {"referral_ref": reference, "reason": "referral finished"})
            results[source_id] = "ok"
        except Exception as exc:  # noqa: BLE001 - recorded, retried on the next sweep
            results[source_id] = f"{type(exc).__name__}: {exc}"
    return results


def http_post(url: str, body: dict) -> dict:
    from ..security import service_tokens

    resp = httpx.post(url, json=body, headers={"Authorization": f"Bearer {service_tokens.get()}"}, timeout=10.0)
    resp.raise_for_status()
    return resp.json()
