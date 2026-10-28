"""What a language model may be sent, and where (docs/decisions/2026-10-28-cloud-model-privacy.md).

Everything sent to a model goes through here, whether the model runs on this computer or not:

* **De-identified always.** No name, CNIC, record number or date of birth (age and sex instead). Those
  identifiers, doctors' names and institution names are removed from the text too, and calendar dates are
  replaced by "N days before the referral". The model gets only what it needs to judge relevance.
* **Off this computer only when allowed.** A cloud model (an Ollama ":cloud" model, ollama.com, Anthropic,
  or any remote server) is used only if LLM_EXTERNAL_ALLOWED=true, and only over https.
* **Audited, never logged.** Callers record where the data went and how much (not the content).
"""
from __future__ import annotations

import re
from datetime import date, datetime
from urllib.parse import urlparse

from ..config import INSTITUTIONS, settings
from .provider import LLMProvider, ProviderUnavailable

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "host.docker.internal", "ollama"}
_DATE = re.compile(
    r"\b(\d{4}-\d{2}-\d{2}|\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}|\d{4}-\d{2}"
    r"|\d{1,2}\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?,?\s+\d{4}"
    r"|(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4})\b", re.I)
_LONG_NUMBER = re.compile(r"\b\d[\d -]{6,}\d\b")  # CNIC, phone and record numbers (lab values are shorter)
_DOCTOR = re.compile(r"\b(Dr|Doctor|Prof)\.?\s+[A-Z][a-zA-Z'-]+(\s+[A-Z][a-zA-Z'-]+){0,2}")


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def destination(provider: LLMProvider) -> tuple[bool, str]:
    """(leaves this computer?, where to). An Ollama ':cloud' model leaves even through a local Ollama."""
    if provider.name == "anthropic":
        return True, "api.anthropic.com"
    if provider.name == "ollama":
        host = getattr(provider, "host", "")
        if getattr(provider, "cloud", False):
            return True, "ollama.com" if _host(host) in LOCAL_HOSTS else _host(host)
        return _host(host) not in LOCAL_HOSTS, _host(host)
    if provider.name == "openai_compatible":
        host = _host(getattr(provider, "base_url", ""))
        return host not in LOCAL_HOSTS, host
    return False, "none"


def check_destination(provider: LLMProvider) -> dict:
    """Refuse to send patient data where it is not allowed. Returns what to record in the audit trail."""
    external, where = destination(provider)
    url = getattr(provider, "host", "") or getattr(provider, "base_url", "")
    if external and not settings.llm_external_allowed:
        raise ProviderUnavailable(f"Sending patient data to an external model ({where}) is switched off. "
                                  "Set LLM_EXTERNAL_ALLOWED=true only once this has been agreed.")
    if url and _host(url) not in LOCAL_HOSTS and urlparse(url).scheme != "https":
        raise ProviderUnavailable(f"The model server {where} must be reached over https")
    return {"external": external, "destination": where, "deidentified": True}


class Scrubber:
    """Removes a referral's identifiers from text sent to a model."""

    def __init__(self, patient_name: str | None, ids: list[str | None], reference: date | None, keep_dates: bool = False):
        self.keep_dates = keep_dates  # reading a paper's fields needs its dates; nothing else does
        parts = [p for p in re.split(r"\W+", patient_name or "") if len(p) >= 3]
        self.name = re.compile(r"\b(" + "|".join(map(re.escape, parts)) + r")\b", re.I) if parts else None
        self.ids = [i for i in ids if i and len(i) >= 3]
        names = sorted({i["name"] for i in INSTITUTIONS.values()}, key=len, reverse=True)
        self.places = [(n, f"a {INSTITUTIONS_KIND.get(n, 'hospital')}") for n in names]
        self.reference = reference

    def text(self, value: str | None) -> str:
        out = value or ""
        for i in self.ids:
            out = out.replace(i, "[id]")
        for n, generic in self.places:
            out = re.sub(re.escape(n), generic, out, flags=re.I)
        out = _DOCTOR.sub("a doctor", out)
        if self.name:
            out = self.name.sub("[patient]", out)
        if not self.keep_dates:
            out = _DATE.sub("[date]", out)
        # ID and phone numbers go; a date kept on purpose looks like one, so it is spared
        return _LONG_NUMBER.sub(lambda m: m.group(0) if self.keep_dates and _DATE.fullmatch(m.group(0)) else "[number]", out)

    def when(self, value: datetime | date | None) -> str | None:
        """A date as days before (or after) the referral, never the calendar date."""
        if value is None or self.reference is None:
            return None
        d = value.date() if isinstance(value, datetime) else value
        days = (self.reference - d).days
        return f"{days} days before the referral" if days >= 0 else f"{-days} days after the referral"


INSTITUTIONS_KIND = {i["name"]: i["kind"] for i in INSTITUTIONS.values()}


def age_years(birth: str | date | None, on: date) -> int | None:
    try:
        b = birth if isinstance(birth, date) else date.fromisoformat(str(birth)[:10])
    except (TypeError, ValueError):
        return None
    return on.year - b.year - ((on.month, on.day) < (b.month, b.day))
