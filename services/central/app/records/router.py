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
from ..models import EncryptedBatch, EncryptedItem, Referral, WrappedKey
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


# --------------------------------------------------------------------------- the doctor's device
MAX_BATCH_BYTES = 25 * 1024 * 1024


def require_referring_doctor(db: Session, referral_id: int, principal: Principal, action: str) -> Referral:
    """Ciphertext goes only to the doctor it is wrapped for (the referring doctor here); nobody else can open it,
    and staff are not even sent it (T-STAFF-1)."""
    r = load_referral(db, referral_id, principal, action, roles=("clinician",))
    if r.requesting_doctor_id and r.requesting_doctor_id != principal.subject:
        raise error(403, "not_your_referral", "Only the referring doctor reads this referral's records")
    return r


@router.get("/referrals/{referral_id}/encrypted")
def encrypted_items(referral_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """Titles, ciphertext and the data keys wrapped to the caller's own keys. Decryption happens on the device."""
    r = require_referring_doctor(db, referral_id, principal, "records_fetch")
    if r.working_set_purged_at is not None:
        raise error(410, "purged", "This referral's encrypted content was purged")
    items = db.scalars(select(EncryptedItem).where(EncryptedItem.referral_id == r.id).order_by(EncryptedItem.id)).all()
    wraps = db.scalars(select(WrappedKey).where(WrappedKey.referral_id == r.id,
                                                WrappedKey.recipient_subject == principal.subject)).all()
    batches = db.scalars(select(EncryptedBatch).where(EncryptedBatch.referral_id == r.id)).all()
    audit(db, principal, "records.ciphertext_fetch", "referral", r.reference, "success", r.id,
          {"items": len(items), "wraps": len(wraps)})
    db.commit()
    return {"reference": r.reference,
            "items": [title_out(it) | {"sealed": it.sealed, "ciphertext_sha256": it.ciphertext_sha256} for it in items],
            "wraps": [{"batch_id": w.batch_id, "recipient_type": w.recipient_type, "recipient_key_id": w.recipient_key_id,
                       "key_version": w.key_version, "wrapped": w.wrapped} for w in wraps],
            "batches": [{"batch_id": b.batch_id, "origin": b.origin, "source_institution": b.source_institution,
                         "source_name": institution_name(b.source_institution), "created_at": b.created_at}
                        for b in batches]}


class BatchIn(BaseModel):
    batch_id: str
    items: list[dict]
    wraps: list[dict]


def allowed_recipients(db: Session, r: Referral, principal: Principal) -> dict[str, tuple[str, str]]:
    """Key ids a doctor may wrap their own items to: their own current key and the patient's current key."""
    from ..keys.router import current_entry, patient_entry_for_cnic

    out: dict[str, tuple[str, str]] = {}
    mine = current_entry(db, principal.subject)
    if mine:
        out[mine.enc_key_id] = ("doctor", principal.subject)
    patient = patient_entry_for_cnic(db, r.patient_cnic or "")
    if patient:
        out[patient.enc_key_id] = ("patient", patient.subject_id)
    return out


@router.post("/referrals/{referral_id}/encrypted-batches", status_code=201)
def upload_batch(referral_id: int, body: BatchIn, db: Session = Depends(get_db),
                 principal: Principal = Depends(get_principal)):
    """The doctor's own items (consultation notes, the medicine list asked from the patient, scans), encrypted on
    the doctor's device. The platform checks only the shape: who the keys are wrapped to and the size."""
    r = require_referring_doctor(db, referral_id, principal, "records_upload")
    if r.status in TERMINAL or r.working_set_purged_at is not None:
        raise error(409, "not_available", "This referral no longer accepts records")
    if not body.batch_id.startswith("doc-") or len(body.batch_id) > 60:
        raise error(422, "invalid_batch", "Batch ids from a doctor's device start with 'doc-'")
    if not body.items or len(body.items) > 200:
        raise error(422, "invalid_batch", "A batch holds 1 to 200 items")
    allowed = allowed_recipients(db, r, principal)
    for w in body.wraps:
        who = allowed.get(w.get("recipient_key_id", ""))
        if who is None:
            raise error(422, "invalid_recipient", "Items can be wrapped only to your own current key and the patient's")
        w["recipient_type"], w["recipient_subject"] = who
    if not any(w["recipient_type"] == "doctor" for w in body.wraps):
        raise error(422, "no_own_wrap", "Wrap the data key to your own key, or you could not open your own items")
    size = sum(len(str(it.get("sealed", ""))) for it in body.items)
    if size > MAX_BATCH_BYTES:
        raise error(413, "too_large", "A batch is at most 25 MB")
    for it in body.items:
        t = it.get("title") or {}
        if not str(t.get("item_id", "")).startswith(f"{body.batch_id}:") or "sealed" not in it:
            raise error(422, "invalid_item", "Each item needs an id inside its batch, a title and ciphertext")
        t["source_institution"] = r.source_institution
    from .requests import store_batch

    b = store_batch(db, r, {"batch_id": body.batch_id, "items": body.items, "wraps": body.wraps}, origin="doctor",
                    source=r.source_institution, created_by=principal.display_name)
    audit(db, principal, "records.upload", "referral", r.reference, "success", r.id,
          {"batch": b.batch_id, "items": len(body.items), "kinds": sorted({(i.get("title") or {}).get("kind") for i in body.items})})
    db.commit()
    return {"batch_id": b.batch_id, "items": len(body.items)}
