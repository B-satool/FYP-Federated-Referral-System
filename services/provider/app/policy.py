"""This institution's own release policy (spec v4 section 6.2, layer 2).

The policy lives with the institution's adapter, under its own control: `policies/<institution>.json`, versioned
in the institution's repository and loaded here. The platform cannot change it. Every evaluation records the
policy version it used.
"""
from __future__ import annotations

import hashlib
import json
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
