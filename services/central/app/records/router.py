"""Records for a referral (spec v4 WP2/WP3).

* Staff and the doctor ask the consented institutions for records; each answer is listed with its outcome. A
  refusal keeps its reason code and an unreachable institution is 'could not be reached': neither is shown as
  'no records' (T-REFUSAL-1).
* Titles (label, kind, date, source) are all the platform can show; staff see nothing else (T-STAFF-1).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from refcommon.auth import Principal
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import institution_name
from ..db import get_db
from ..keys import platform
from ..models import EncryptedItem, Referral
from ..referrals.state import TERMINAL
from ..security import CLINIC_ROLES, audit, error, get_principal, load_referral
from . import requests as rq

router = APIRouter(tags=["records (encrypted)"])


def title_out(it: EncryptedItem) -> dict:
    """A title record (spec v4 4.2): never values, results, free text or doses."""
    return {"item_id": it.item_id, "batch_id": it.batch_id, "kind": it.kind, "category": it.category,
            "label": it.label, "date": it.item_date, "source_institution": it.source_institution,
            "source_name": institution_name(it.source_institution), "sensitive": it.sensitive}


def titles_for(db: Session, r: Referral) -> list[dict]:
    rows = db.scalars(select(EncryptedItem).where(EncryptedItem.referral_id == r.id)
                      .order_by(EncryptedItem.source_institution, EncryptedItem.item_date.desc().nullslast(),
                                EncryptedItem.id)).all()
    seen: dict[str, dict] = {}
    for it in rows:  # a later batch with the same item replaces the earlier one
        seen[it.item_id] = title_out(it)
    return list(seen.values())


@router.post("/referrals/{referral_id}/record-requests")
def request_records(referral_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """Send the records requests the patient's consent allows (staff or the referring doctor)."""
    r = load_referral(db, referral_id, principal, "records_request", roles=CLINIC_ROLES)
    if r.kind != "referral" or r.status in TERMINAL or r.status == "draft":
        raise error(409, "not_available", "Records are requested while the referral is open")
    if r.working_set_purged_at is not None:
        raise error(409, "purged", "This referral's records were purged")
    rows = rq.send(db, r, principal)
    db.commit()
    return {"requests": [rq.request_out(x) for x in rows], "titles": titles_for(db, r)}


@router.get("/referrals/{referral_id}/record-requests")
def list_record_requests(referral_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    r = load_referral(db, referral_id, principal, "view", roles=CLINIC_ROLES)
    consent = rq.consent_for(db, r)
    return {"consent": consent.reference if consent else None,
            "requests": [rq.request_out(x) for x in rq.latest_requests(db, r)]}


@router.get("/referrals/{referral_id}/titles")
def referral_titles(referral_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """What every role at the referring institution may see of the records: titles only."""
    r = load_referral(db, referral_id, principal, "view", roles=CLINIC_ROLES)
    audit(db, principal, "records.titles", "referral", r.reference, "success", r.id)
    db.commit()
    return titles_for(db, r)


class AdapterAnswer(BaseModel):
    request_key: str
    status: str
    refusals: list[dict] = []
    policy_version: str | None = None
    notes: list[str] = []
    batch: dict | None = None


@router.post("/e2e/adapter/record-responses")
def adapter_answer(body: AdapterAnswer, request: Request, db: Session = Depends(get_db)):
    """An institution's answer after its staff reviewed a request (signed request from that institution)."""
    claims = platform.verify_adapter(request, db)
    row = rq.receive_later(db, claims["iss"], body.model_dump())
    db.commit()
    return {"status": row.status}
