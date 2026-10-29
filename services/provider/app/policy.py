"""This institution's own release policy (spec v4 section 6.2, layer 2).

The policy lives with the institution's adapter, under its own control: `policies/<institution>.json`, versioned
in the institution's repository and loaded here. The platform cannot change it. Every evaluation records the
policy version it used.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from .config import INSTITUTION

POLICY_DIR = Path(__file__).resolve().parent.parent / "policies"

DEFAULTS: dict = {
    "version": "default",
    # answer straight away when the consent is valid and covers the request
    "auto_approve_with_valid_consent": True,
    # released only when the consent names the category specifically
    "excluded_categories": ["psychiatric", "hiv_sexual_health"],
    # requests that wait for this institution's staff: {"categories": [...], "request_types": [...], "always": false}
    "manual_review": {"categories": [], "request_types": [], "always": False},
    "respond_within_consent_window_only": True,
    "allowed_record_types_from_consent": True,
    "sensitive_title_masking": True,
    # categories the law does not allow this institution to release through the network at all
    "prohibited_by_law": [],
    # a doctor's directory entry is signed as soon as a clinician of this hospital registers a key; with false,
    # an institution administrator approves each one
    "doctor_keys": {"auto_sign": True},
}


def load() -> dict:
    path = POLICY_DIR / f"{INSTITUTION}.json"
    raw = path.read_bytes() if path.exists() else b"{}"
    data = {**DEFAULTS, **json.loads(raw or b"{}")}
    data["manual_review"] = {**DEFAULTS["manual_review"], **(data.get("manual_review") or {})}
    data["doctor_keys"] = {**DEFAULTS["doctor_keys"], **(data.get("doctor_keys") or {})}
    data["hash"] = hashlib.sha256(raw).hexdigest()[:16]
    return data


# --------------------------------------------------------------------------- evaluation
# Record categories a referral request can cover, and the sensitive categories released only with specific consent
RECORD_CATEGORIES = ("conditions", "surgeries", "visits", "medications", "labs", "imaging")
SENSITIVE_LABELS = {"psychiatric": "Psychiatric record", "hiv_sexual_health": "HIV or sexual-health record"}
REFUSAL_REASONS = {
    "prohibited_by_law": "The law does not allow this institution to release these records through the network.",
    "sensitive_category_no_specific_consent": "Released only when the patient's consent names this category specifically.",
    "request_incomplete_or_invalid": "The request or its consent link is incomplete or invalid.",
    "consent_expired_or_out_of_range": "The consent has expired, was revoked, or does not cover this request.",
    "pending_manual_review": "Waiting for this institution's staff to review the request.",
}


@dataclass
class Decision:
    """What this institution will release for one request, decided before any record is read."""
    status: str  # answer | refused | pending
    categories: set[str] = field(default_factory=set)
    sensitive: set[str] = field(default_factory=set)  # sensitive categories the patient consented to specifically
    since: str | None = None
    refusals: list[dict] = field(default_factory=list)
    policy_version: str = ""

    def refuse(self, reason: str, categories: list[str] | None = None, message: str | None = None) -> None:
        self.refusals.append({"reason": reason, "categories": sorted(categories or []),
                              "message": message or REFUSAL_REASONS[reason]})


def evaluate(pol: dict, request: dict, consent: dict | None, consent_problem: str | None,
             manual_approved: bool = False) -> Decision:
    """Spec v4 6.2, in order: (the request assertion is already verified) consent valid and covering the request,
    then this institution's rules. A refusal always carries one of the agreed reason codes; it is never an empty
    answer."""
    d = Decision(status="answer", policy_version=f"{pol.get('version')}#{pol.get('hash')}")
    if not request.get("referral") or not request.get("local_patient_id") or not request.get("purpose"):
        d.status = "refused"
        d.refuse("request_incomplete_or_invalid", message="The request does not name the referral, the patient and the purpose.")
        return d
    if consent is None:
        d.status = "refused"
        reason = "consent_expired_or_out_of_range" if consent_problem and consent_problem.startswith("consent ") \
            else "request_incomplete_or_invalid"
        d.refuse(reason, message=consent_problem or REFUSAL_REASONS[reason])
        return d
    provision = consent.get("provision") or {}
    consented = {c.get("code") for c in provision.get("class") or []}
    specific = set((consent.get("refx") or {}).get("sensitive_categories_specific") or [])
    requested = set(request.get("categories") or RECORD_CATEGORIES) & set(RECORD_CATEGORIES)
    if pol.get("allowed_record_types_from_consent", True):
        outside = sorted(requested - consented)
        if outside:
            d.refuse("consent_expired_or_out_of_range", outside, "The patient's consent does not cover these records.")
        requested &= consented
    banned = sorted(requested & set(pol.get("prohibited_by_law") or []))
    if banned:
        d.refuse("prohibited_by_law", banned)
        requested -= set(banned)
    d.categories = requested
    # sensitive categories: asked for explicitly by the request, or named specifically in the consent
    asked_sensitive = set(request.get("sensitive") or []) | specific
    for cat in sorted(asked_sensitive):
        if cat in (pol.get("prohibited_by_law") or []):
            d.refuse("prohibited_by_law", [cat])
        elif cat in (pol.get("excluded_categories") or []) and cat not in specific:
            d.refuse("sensitive_category_no_specific_consent", [cat])
        else:
            d.sensitive.add(cat)
    data_start = (provision.get("dataPeriod") or {}).get("start")
    d.since = request.get("since")
    if pol.get("respond_within_consent_window_only", True) and data_start:
        d.since = max(filter(None, [d.since, data_start]))
    review = pol.get("manual_review") or {}
    needs_review = bool(review.get("always")) or not pol.get("auto_approve_with_valid_consent", True) \
        or request.get("purpose") in (review.get("request_types") or []) \
        or bool((d.categories | d.sensitive) & set(review.get("categories") or []))
    if needs_review and not manual_approved:
        d.status = "pending"
        d.refuse("pending_manual_review")
    if not d.categories and not d.sensitive and d.status == "answer":
        d.status = "refused"
    return d
