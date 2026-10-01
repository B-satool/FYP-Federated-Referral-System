"""Outbox delivery to the specialist service (run by the worker).

A timed-out request may already have succeeded, so retries reuse the same
delivery key; the specialist side returns the original result for a repeat.
"""
from __future__ import annotations

import logging
from datetime import timedelta

import httpx
from refcommon.db import utcnow
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Outbox, Referral
from ..referrals.state import event, transition
from ..security import audit, service_tokens

log = logging.getLogger("delivery")
MAX_ATTEMPTS = 8
ENDPOINTS = {"deliver_package": "/inbound/referrals", "clarification_answer": "/inbound/clarification-answers"}


def _on_success(db: Session, box: Outbox, result: dict) -> None:
    referral = db.get(Referral, box.referral_id)
    if box.kind == "deliver_package":
        version = box.payload["package_version"]
        referral.submitted_package_version = version
        referral.delivery_status = "delivered"
        was_amendment = referral.amendment_open
        referral.amendment_open = False
        event(db, referral, "delivered", "system", "central-platform",
              {"version": version, "remote": result, "amendment": was_amendment})
        if referral.status == "approved":
            transition(db, referral, "submitted", "system (delivery confirmed)", None,
                       {"version": version}, institution="central-platform")
        audit(db, None, "delivery.confirmed", "referral_package", f"{referral.reference}v{version}", "success",
              referral.id, result, actor=("system", "delivery worker", "central-platform"))
    else:
        event(db, referral, "clarification_answer_delivered", "system", "central-platform", result)


def deliver_pending(db: Session, limit: int = 20) -> int:
    due = db.scalars(select(Outbox).where(Outbox.status == "pending", Outbox.next_attempt_at <= utcnow())
                     .order_by(Outbox.id).limit(limit).with_for_update(skip_locked=True)).all()
    sent = 0
    for box in due:
        box.attempts += 1
        referral = db.get(Referral, box.referral_id)
        try:
            token = service_tokens.get()
            resp = httpx.post(settings.specialist_url + ENDPOINTS[box.kind], json=box.payload,
                              headers={"Authorization": f"Bearer {token}"}, timeout=10.0)
            if resp.status_code < 300:
                box.status, box.sent_at, box.last_error = "sent", utcnow(), None
                box.remote_result = resp.json()
                _on_success(db, box, box.remote_result)
                sent += 1
            elif resp.status_code in (400, 403, 404, 422):
                box.status = "failed"
                box.last_error = f"Rejected by specialist service ({resp.status_code}): {resp.text[:300]}"
                if box.kind == "deliver_package":
                    referral.delivery_status = "failed"
                event(db, referral, "delivery_failed", "system", "central-platform", {"error": box.last_error})
            else:
                raise httpx.HTTPStatusError(f"specialist service returned {resp.status_code}", request=resp.request,
                                            response=resp)
        except httpx.HTTPError as exc:
            box.last_error = str(exc)[:500] or exc.__class__.__name__
            if box.attempts >= MAX_ATTEMPTS:
                box.status = "failed"
                if box.kind == "deliver_package":
                    referral.delivery_status = "failed"
                event(db, referral, "delivery_failed", "system", "central-platform",
                      {"error": box.last_error, "attempts": box.attempts})
            else:
                box.next_attempt_at = utcnow() + timedelta(seconds=min(120, 2 ** box.attempts))
                if box.kind == "deliver_package":
                    referral.delivery_status = "retrying"
        db.commit()
    return sent
