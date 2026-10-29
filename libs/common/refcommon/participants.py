"""Pinned participant registry (spec v4 section 6.1, layer 1).

Written once per installation by `scripts/onboard_participants.py` at onboarding, outside the platform's API, and
mounted read-only into every service and the web client. It pins each institution's hospital signing key and the
platform's signing key, records the participation agreement (version, date, allowed purposes) and whether each
participant is in good standing. Nothing here is fetched from the platform at run time, so the platform cannot
swap a pinned key.
"""
from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass

PLATFORM_ID = "hub"
# HL7 v3 PurposeOfUse codes allowed by the participation agreement
PURPOSES = {"TREAT": "Treatment and referral", "ETREAT": "Emergency treatment", "PATRQT": "Patient's own request"}


@dataclass(frozen=True)
class Participant:
    institution_id: str
    name: str
    signing_key: str
    key_id: str
    adapter_url: str
    agreement_version: str
    agreement_date: str
    status: str  # active | suspended

    @property
    def in_good_standing(self) -> bool:
        return self.status == "active"


class Registry:
    def __init__(self, path: str | None = None) -> None:
        self.path = path or os.environ.get("PARTICIPANTS_FILE", "/etc/refx/participants/participants.json")
        self._lock = threading.Lock()
        self._mtime: float | None = None
        self._data: dict = {}

    def _load(self) -> dict:
        try:
            mtime = os.path.getmtime(self.path)
        except OSError:
            return {}
        with self._lock:
            if mtime != self._mtime:
                with open(self.path, encoding="utf-8") as fh:
                    self._data = json.load(fh)
                self._mtime = mtime
            return self._data

    @property
    def onboarded(self) -> bool:
        return bool(self._load().get("institutions"))

    def institution(self, institution_id: str | None) -> Participant | None:
        row = self._load().get("institutions", {}).get(institution_id or "")
        if not row:
            return None
        return Participant(institution_id=institution_id, name=row.get("name", institution_id),
                           signing_key=row["signing_key"], key_id=row["key_id"], adapter_url=row.get("adapter_url", ""),
                           agreement_version=row.get("agreement_version", ""), agreement_date=row.get("agreement_date", ""),
                           status=row.get("status", "active"))

    def institutions(self) -> list[Participant]:
        return [p for p in (self.institution(i) for i in sorted(self._load().get("institutions", {}))) if p]

    def platform_key(self) -> str | None:
        return (self._load().get("platform") or {}).get("signing_key")

    def allowed_purposes(self) -> set[str]:
        return set((self._load().get("agreement") or {}).get("purposes") or PURPOSES)

    def issuer_key(self, issuer: str | None) -> str | None:
        """The pinned public signing key of an issuer: the platform or an institution."""
        if issuer == PLATFORM_ID:
            return self.platform_key()
        p = self.institution(issuer)
        return p.signing_key if p else None


registry = Registry()
