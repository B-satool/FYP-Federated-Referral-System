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
