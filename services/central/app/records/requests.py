"""Requesting a referral's records from the institutions the patient consented to (spec v4 2 step 3, 5.6, 6.3).

For each custodian the patient named, the platform sends one signed request: which organisation and which doctor
ask, for what purpose, the link to the patient's consent and the referral, valid for minutes. The institution's
adapter checks everything itself and answers with titles, ciphertext and wrapped data keys, with a structured
refusal, or later (after its staff review). The platform stores the answer as received.
"""
from __future__ import annotations

import hashlib
import uuid
from concurrent.futures import ThreadPoolExecutor

import httpx
from refcommon import e2e
from refcommon.auth import Principal
from refcommon.db import utcnow
from refcommon.participants import registry
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import institution_name
from ..consent.router import active_consent
from ..integration.retrieval import history_start, linked_sources
from ..keys import platform
from ..keys.router import current_entry, patient_entry_for_cnic
from ..models import Consent, EncryptedBatch, EncryptedItem, RecordRequest, Referral, WrappedKey
from ..notifications import notify_doctor, notify_staff
from ..referrals.state import event
from ..security import audit, error

ITEM_KINDS = {"lab", "imaging", "note", "prescription", "scan", "other"}
STATUS_TEXT = {
    "answered": "Records received (encrypted)",
    "partial": "Some records received; some were refused",
    "refused": "Refused",
    "pending_manual_review": "Waiting for the institution's staff to review",
    "no_records": "Answered: holds no matching records",
    "unavailable": "Could not be reached; try again",
    "not_linked": "Patient not confirmed there yet",
    "failed": "Rejected the request",
    "sent": "Sent",
}


def ciphertext_hash(sealed: dict) -> str:
    return hashlib.sha256(e2e.canonical(sealed)).hexdigest()


def store_batch(db: Session, r: Referral, batch: dict, *, origin: str, source: str | None, created_by: str,
                request_id: int | None = None) -> EncryptedBatch:
    """Store titles, ciphertext and wrapped keys exactly as received (idempotent by batch id)."""
    existing = db.scalars(select(EncryptedBatch).where(EncryptedBatch.batch_id == batch["batch_id"])).first()
    if existing:
        return existing
    b = EncryptedBatch(referral_id=r.id, batch_id=batch["batch_id"], origin=origin, source_institution=source,
                       record_request_id=request_id, created_by=created_by)
    db.add(b)
    for it in batch.get("items", []):
        t = it["title"]
        sealed = it["sealed"]
        db.add(EncryptedItem(referral_id=r.id, batch_id=b.batch_id, item_id=t["item_id"][:120],
                             kind=t["kind"] if t.get("kind") in ITEM_KINDS else "other", category=t.get("category"),
                             label=str(t.get("label") or "Record")[:300], item_date=t.get("date"),
                             source_institution=t.get("source_institution") or source,
                             sensitive=bool(t.get("sensitive")), sealed=sealed,
                             size=sum(len(c.get("ciphertext", "")) for c in sealed.get("chunks", [sealed])),
                             ciphertext_sha256=ciphertext_hash(sealed)))
    for w in batch.get("wraps", []):
        db.add(WrappedKey(referral_id=r.id, batch_id=b.batch_id, recipient_type=w["recipient_type"],
                          recipient_subject=w["recipient_subject"], recipient_key_id=w["recipient_key_id"],
                          key_version=w.get("key_version"), wrapped=w["wrapped"], created_by=created_by))
    db.flush()
    return b


def apply_result(db: Session, r: Referral, row: RecordRequest, result: dict) -> None:
    """Record an adapter's answer: status and reason codes, and the encrypted batch if any."""
    row.status = result.get("status") or "failed"
    row.refusals = list(result.get("refusals") or [])
    row.policy_version = result.get("policy_version")
    notes = list(result.get("notes") or [])
    batch = result.get("batch")
    if batch:
        b = store_batch(db, r, batch, origin="custodian", source=row.custodian, created_by=f"adapter {row.custodian}",
                        request_id=row.id)
        row.batch_id, row.item_count = b.batch_id, len(batch.get("items", []))
    reasons = "; ".join(f"{x['reason']}: {x.get('message', '')}" for x in row.refusals)
    row.message = " ".join(filter(None, [STATUS_TEXT.get(row.status, row.status) + ".", reasons, *notes]))
    if row.status != "pending_manual_review":
        row.answered_at = utcnow()


def _call(custodian: str, payload: dict, claims: dict, token: str) -> tuple[int | None, dict | str]:
    from ..config import institution_url

    try:
        resp = httpx.post(institution_url(custodian) + "/e2e/record-requests", json=payload,
                          headers={"Authorization": f"Bearer {token}"}, timeout=30)
    except httpx.HTTPError as exc:
        return None, str(exc) or exc.__class__.__name__
    try:
        return resp.status_code, resp.json()
    except ValueError:
        return resp.status_code, resp.text[:300]


def send(db: Session, r: Referral, principal: Principal) -> list[RecordRequest]:
    c = active_consent(db, r)
    if c is None:
        raise error(409, "no_consent", "The patient has not given consent (or it expired or was revoked). "
                                       "Request consent first; the patient answers in the patient portal.")
    doctor = current_entry(db, r.requesting_doctor_id or "")
    if doctor is None:
        raise error(409, "doctor_no_key", "The referring doctor has not set up a device key yet, so records cannot be "
                                          "encrypted for them. Ask the doctor to open the referral once.")
    patient = patient_entry_for_cnic(db, r.patient_cnic or "")
    linked = {inst: local for inst, local, _ in linked_sources(db, r)}
    since = history_start(r).isoformat()
    claims = {"refx": {"org": r.source_institution, "practitioner": r.requesting_doctor_id, "purpose": c.purpose,
                       "consent": c.reference, "referral": r.reference}}
    rows: list[RecordRequest] = []
    calls = []
    for custodian in c.custodians_granted:
        row = RecordRequest(referral_id=r.id, consent_id=c.id, custodian=custodian,
                            request_key=f"{r.reference}:{c.reference}:{custodian}:{uuid.uuid4().hex[:10]}",
                            local_patient_id=linked.get(custodian), practitioner_id=r.requesting_doctor_id,
                            status="sent", requested_by=principal.display_name)
        db.add(row)
        rows.append(row)
        if custodian not in linked:
            row.status = "not_linked"
            row.message = (f"{institution_name(custodian)} has not confirmed this patient yet. Ask it to confirm "
                           "the patient (Patient links), then request records again.")
            continue
        payload = {"request_key": row.request_key, "local_patient_id": linked[custodian], "since": since,
                   "reason": r.reason, "practitioner_entry": doctor.entry,
                   "patient_entry": patient.entry if patient else None, "sensitive": c.sensitive_specific}
        participant = registry.institution(custodian)
        if participant is None or not participant.in_good_standing:  # participation suspended (spec v4 6.1)
            row.status, row.message = "failed", f"{institution_name(custodian)} is not a participant in good standing"
            continue
        calls.append((row, custodian, payload, platform.assertion(db, custodian, claims)))
    db.flush()
    with ThreadPoolExecutor(max_workers=max(1, len(calls))) as pool:
        answers = list(pool.map(lambda x: _call(x[1], x[2], claims, x[3]), calls))
    for (row, custodian, _, _), (status, body) in zip(calls, answers):
        name = institution_name(custodian)
        if status is None:
            row.status, row.message = "unavailable", f"{name} could not be reached ({body}). Nothing was received; try again."
        elif status == 200 and isinstance(body, dict):
            apply_result(db, r, row, body)
        elif status == 403 and isinstance(body, dict) and (body.get("detail") or {}).get("refusal"):
            refusal = body["detail"]["refusal"]
            row.status, row.refusals = "refused", [refusal]
            row.message = f"Refused by {name}: {refusal.get('message')}"
        else:
            row.status, row.message = "failed", f"{name} rejected the request ({status}): {str(body)[:200]}"
    for row in rows:
        audit(db, principal, "records.request", "source", row.custodian,
              "pending" if row.status == "pending_manual_review" else row.status, r.id,
              {"consent": c.reference, "items": row.item_count, "reasons": [x.get("reason") for x in row.refusals],
               "request_key": row.request_key})
    event(db, r, "records_requested", principal.display_name, principal.institution_id,
          {"consent": c.reference, "results": {row.custodian: row.status for row in rows}})
    if any(row.item_count for row in rows):
        notify_doctor(db, r, "records_ready", f"{r.reference}: records received",
                      "Encrypted records arrived. Open the referral to decrypt and review them on your device.",
                      tab="records")
    return rows


def receive_later(db: Session, issuer: str, result: dict) -> RecordRequest:
    """An answer that came after the institution's staff reviewed the request."""
    row = db.scalars(select(RecordRequest).where(RecordRequest.request_key == result.get("request_key"))).first()
    if row is None or row.custodian != issuer:
        raise error(404, "not_found", "No such request from your institution")
    if row.status != "pending_manual_review":
        return row
    r = db.get(Referral, row.referral_id)
    apply_result(db, r, row, result)
    event(db, r, "records_answered", f"adapter {issuer}", issuer, {"status": row.status, "items": row.item_count})
    audit(db, None, "records.answer", "source", issuer, row.status, r.id,
          {"items": row.item_count, "reasons": [x.get("reason") for x in row.refusals]},
          actor=(issuer, f"adapter {issuer}", issuer))
    if row.item_count:
        notify_doctor(db, r, "records_ready", f"{r.reference}: more records received",
                      f"{institution_name(issuer)} released records after review.", tab="records")
    notify_staff(db, r, "records_answered", f"{r.reference}: {institution_name(issuer)} answered",
                 STATUS_TEXT.get(row.status, row.status), tab="records")
    return row


def request_out(row: RecordRequest) -> dict:
    return {"id": row.id, "custodian": row.custodian, "custodian_name": institution_name(row.custodian),
            "status": row.status, "status_text": STATUS_TEXT.get(row.status, row.status),
            "refusals": [{"reason": x.get("reason"), "categories": x.get("categories", []), "message": x.get("message")}
                         for x in row.refusals],
            "item_count": row.item_count, "message": row.message, "requested_by": row.requested_by,
            "requested_at": row.requested_at, "answered_at": row.answered_at, "policy_version": row.policy_version}


def latest_requests(db: Session, r: Referral) -> list[RecordRequest]:
    out: dict[str, RecordRequest] = {}
    for row in db.scalars(select(RecordRequest).where(RecordRequest.referral_id == r.id).order_by(RecordRequest.id)):
        out[row.custodian] = row
    return list(out.values())


def consent_for(db: Session, r: Referral) -> Consent | None:
    return active_consent(db, r)
