"""Which institution this instance is. The same code runs once per institution."""
from __future__ import annotations

import os

INSTITUTION = os.environ["INSTITUTION_ID"]  # drali | chughtai | ziauddin | akuh
INSTITUTION_NAME = os.environ.get("INSTITUTION_NAME", INSTITUTION)
LOCAL_ID_PREFIX = os.environ.get("LOCAL_ID_PREFIX", "PT")
CENTRAL_URL = os.environ.get("CENTRAL_URL", "http://central:8000").rstrip("/")
AUDIENCE = os.environ.get("TOKEN_AUDIENCE", f"{INSTITUTION}-api")

# Look-back window for referral retrieval (visits, results, imaging). Conditions,
# surgeries and current medications are returned regardless of date.
DEFAULT_WINDOW_DAYS = int(os.environ.get("REFERRAL_WINDOW_DAYS", "183"))
# a received referral's shared records: kept ACCEPTED_HOLD_DAYS after acceptance (extendable by the referred
# doctor), and removed GRACE_HOURS after they mark it complete (the platform applies the same rules)
ACCEPTED_HOLD_DAYS = int(os.environ.get("ACCEPTED_HOLD_DAYS", "30"))
GRACE_HOURS = int(os.environ.get("WORKING_SET_GRACE_HOURS", "72"))
