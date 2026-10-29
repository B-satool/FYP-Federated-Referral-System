"""The AI relay (spec v4 8.4, 9.1; approval A7).

The doctor's browser decrypts the records, de-identifies them, shows the doctor exactly what will be sent, and only
when the doctor confirms posts that text here. The relay forwards it to the configured model and returns the answer:

* **Nothing is stored or logged.** The text is held in memory for the call only: no table, no queue, no log line. The
  audit trail records who asked, for which referral, how many items, the payload's SHA-256, the model, the latency and
  the outcome.
* **A safety net, not the de-identifier.** The browser removes identifiers; the relay refuses a payload that still
  holds the patient's name, CNIC, record number, the referral reference or an institution's name (it refuses rather
  than edits, so the doctor's preview stays exactly what was sent).
* **Answers are checked.** Selection: unknown or repeated item ids are dropped (T-AI-2), reasons with treatment or
  dosing wording are withheld. Flags (Layer 2): schema-checked, labelled "AI suggestion, not verified"; they never
  remove or change a Layer 1 flag (the browser keeps the two apart).
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from refcommon.auth import Principal
from sqlalchemy.orm import Session

from .config import INSTITUTIONS, settings
from .db import get_db
from .generation import privacy
from .generation.provider import ProviderOutputInvalid, ProviderUnavailable, get_provider
from .security import DOCTOR, audit, error, get_principal, load_referral, require_scope
from .selection import selection

router = APIRouter(prefix="/ai/relay", tags=["AI relay (de-identified, on request)"])
MAX_RECORDS = 150
MAX_TEXT = 400


def _digest(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def identifier_problems(text: str, r) -> list[str]:
    """Which kinds of identifier are still in the text (kinds only, never the values)."""
    found = []
    low = text.lower()
    digits = re.sub(r"\D", "", text)
    for part in re.split(r"\W+", r.patient_name or ""):
        if len(part) >= 3 and re.search(rf"\b{re.escape(part.lower())}\b", low):
            found.append("patient name")
            break
    cnic = re.sub(r"\D", "", r.patient_cnic or "")
    if len(cnic) >= 13 and cnic in digits:
        found.append("CNIC")
    for value, kind in ((r.patient_local_id, "record number"), (r.reference, "referral reference")):
        if value and len(value) >= 3 and value.lower() in low:
            found.append(kind)
    if any(i["name"].lower() in low for i in INSTITUTIONS.values()):
        found.append("institution name")
    if r.patient_birth_date and str(r.patient_birth_date)[:10] in text:
        found.append("date of birth")
    return found


def _referral_for(db: Session, referral_id: int, principal: Principal, action: str):
    require_scope(principal, "ai:use", action)
    r = load_referral(db, referral_id, principal, action, roles=(DOCTOR,))
    if r.requesting_doctor_id and r.requesting_doctor_id != principal.subject:
        raise error(403, "not_your_referral", "Only the referring doctor asks the AI about this referral")
    return r


def _relay(db: Session, r, principal: Principal, action: str, system: str, payload: dict, schema: dict,
           max_tokens: int) -> tuple[dict, dict]:
    """Forward the de-identified payload; return (answer, audit detail). Raises a 4xx/5xx error on refusal."""
    text = json.dumps(payload, ensure_ascii=False)
    meta = {"payload_sha256": _digest(payload), "chars": len(text)}
    problems = identifier_problems(text, r)
    if problems:
        audit(db, principal, action, "referral", r.reference, "refused", r.id, {**meta, "identifiers": problems})
        db.commit()
        raise error(422, "identifiers_found", "The text still contains: " + ", ".join(problems) +
                    ". Edit the preview to remove them, then send again.")
    provider = get_provider()
    if not settings.llm_configured:
        audit(db, principal, action, "referral", r.reference, "unavailable", r.id, {**meta, "reason": "no model"})
        db.commit()
        raise error(503, "ai_unavailable", "AI check not available: no model is configured")
    started = time.monotonic()
    try:
        sent = privacy.check_destination(provider)
        raw = provider.structured(system, payload, schema, max_tokens=max_tokens)
    except ProviderUnavailable as exc:
        audit(db, principal, action, "referral", r.reference, "unavailable", r.id,
              {**meta, "model": provider.model, "error": str(exc)[:200]})
        db.commit()
        raise error(503, "ai_unavailable", f"AI check not available: {str(exc)[:200]}") from exc
    except ProviderOutputInvalid as exc:
        audit(db, principal, action, "referral", r.reference, "rejected", r.id,
              {**meta, "model": provider.model, "error": str(exc)[:200]})
        db.commit()
        raise error(502, "ai_answer_rejected", "The AI's answer did not pass the checks and was discarded") from exc
    return raw, {**meta, "model": provider.model, "provider": provider.name, "sent_to": sent,
                 "latency_ms": int((time.monotonic() - started) * 1000)}


# --------------------------------------------------------------------------- record suggestions (spec v4 8)
class SelectionRecord(BaseModel):
    id: int
    category: str = Field(max_length=40)
    when: str | None = Field(None, max_length=60)
    default: bool = False
    text: str = Field(max_length=MAX_TEXT)


class SelectionPayload(BaseModel):
    patient: dict[str, Any] = {}
    referral: dict[str, Any] = {}
    records: list[SelectionRecord] = Field(max_length=MAX_RECORDS)


class SelectionIn(BaseModel):
    referral_id: int
    payload: SelectionPayload


@router.post("/selection")
def relay_selection(body: SelectionIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    r = _referral_for(db, body.referral_id, principal, "ai.relay.selection")
    payload = body.payload.model_dump()
    payload["patient"] = {k: payload["patient"].get(k) for k in ("age_years", "sex")}
    allowed = {x["id"] for x in payload["records"]}
    if not allowed:
        raise error(422, "nothing_to_rank", "No records to rank")
    raw, meta = _relay(db, r, principal, "ai.relay.selection", selection.SYSTEM, payload,
                       selection.schema_for(get_provider(), len(allowed)), min(16000, 400 + 80 * len(allowed)))
    # unknown or repeated ids are dropped, not fatal (T-AI-2); anything else wrong rejects the answer
    items, seen, dropped = [], set(), 0
    for it in (raw.get("items") or []) if isinstance(raw, dict) else []:
        eid = it.get("evidence_id") if isinstance(it, dict) else None
        if not isinstance(eid, int) or isinstance(eid, bool) or eid not in allowed or eid in seen:
            dropped += 1
            continue
        seen.add(eid)
        items.append(it)
    try:
        recs, missing = selection.validate({"items": items, "missing": raw.get("missing", [])}, allowed)
    except ProviderOutputInvalid as exc:
        audit(db, principal, "ai.relay.selection", "referral", r.reference, "rejected", r.id, {**meta, "error": str(exc)})
        db.commit()
        raise error(502, "ai_answer_rejected", "The AI's answer did not pass the checks and was discarded") from exc
    withheld = len(items) - len(recs)
    audit(db, principal, "ai.relay.selection", "referral", r.reference, "success", r.id,
          {**meta, "items": len(allowed), "answered": len(recs), "dropped_ids": dropped, "withheld": withheld,
           "prompt_version": selection.PROMPT_VERSION})
    db.commit()
    return {"recommendations": [{"id": k, **v} for k, v in recs.items()], "missing": missing,
            "dropped_ids": dropped, "withheld": withheld, "model": meta["model"],
            "prompt_version": selection.PROMPT_VERSION, "label": "AI suggestion, unverified"}
