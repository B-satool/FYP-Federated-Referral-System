"""The doctor's signed package and sending it (spec v4 5.8, steps 5 to 7; approval A4).

Approval happens on the doctor's device: it builds the package manifest (the ordered items with the hash of each
item's plaintext and ciphertext, the doctor's notes as an encrypted item, the receiving department's key and the
referral), signs it with the doctor's signing key, and re-wraps each included batch's data key to the receiving
department's group key and the patient's key. The platform checks the signature against the doctor's
hospital-signed key, checks the ciphertext hashes against what it stores, and keeps the manifest as an immutable
version. It never sees a data key.

Sending (staff) delivers a notice to the receiving hospital's system: administrative data and record titles only.
No copy is kept for the sending side (D16): the patient's own copy is the only one that lasts.
"""
from __future__ import annotations

import hashlib

from refcommon import e2e
from refcommon.auth import Principal
from refcommon.db import utcnow
from refcommon.exchange import ReferralNotice
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import department_name, institution_name
from ..identity.links import verified_counterparts
from ..identity.router import create_request
from ..keys.router import current_department_entry, current_entry, patient_entry_for_cnic
from ..models import EncryptedItem, Outbox, PackageManifest, Referral, WrappedKey
from ..notifications import notify_staff
from ..referrals.state import IN_FLIGHT, event
from ..security import audit, bump, error
from .readiness import blocking, readiness

MANIFEST_TYPE = e2e.MANIFEST_TYPE


def manifest_hash(manifest: dict) -> str:
    return hashlib.sha256(e2e.canonical(manifest)).hexdigest()


def latest_manifest(db: Session, r: Referral) -> PackageManifest | None:
    return db.scalars(select(PackageManifest).where(PackageManifest.referral_id == r.id)
                      .order_by(PackageManifest.version.desc())).first()


def approve(db: Session, r: Referral, principal: Principal, manifest: dict, wraps: list[dict]) -> PackageManifest:
    """Check and store the doctor-signed manifest and the department and patient wraps (T-APPROVE-1)."""
    if r.kind != "referral" or (r.status not in ("requested",) and not (r.status in IN_FLIGHT and r.amendment_open)) \
            and r.status not in IN_FLIGHT:
        raise error(409, "not_open", "Only an open referral can be approved")
    version = (db.scalar(select(func.max(PackageManifest.version)).where(PackageManifest.referral_id == r.id)) or 0) + 1
    doctor = current_entry(db, principal.subject)
    if doctor is None:
        raise error(409, "no_key", "Set up your device key first")
    m = manifest
    problems = []
    if m.get("type") != MANIFEST_TYPE or m.get("suite") != e2e.SUITE:
        problems.append("not a package manifest of this suite")
    if m.get("referral") != r.reference or m.get("version") != version:
        problems.append(f"manifest must be for {r.reference}, version {version}")
    signer = m.get("signer") or {}
    if signer.get("subject_id") != principal.subject or \
            signer.get("sig_key_id") != e2e.key_id(doctor.entry["sig_public_key"]):
        problems.append("the manifest is not signed with your current signing key")
    elif not e2e.verify_object(doctor.entry["sig_public_key"], m):
        problems.append("the signature does not verify")
    dept = current_department_entry(db, r.destination_institution, r.destination_department)
    recipient = m.get("recipient") or {}
    if dept is None:
        problems.append("the receiving department has no published key yet")
    elif recipient.get("group_key_id") != dept.enc_key_id or recipient.get("hospital_id") != r.destination_institution \
            or recipient.get("department") != r.destination_department:
        problems.append("the package is not addressed to the receiving department's current key")
    items = m.get("items") or []
    if not items:
        problems.append("the package has no items")
    stored = {(it.batch_id, it.item_id): it for it in db.scalars(select(EncryptedItem).where(EncryptedItem.referral_id == r.id))}
    for it in items:
        row = stored.get((it.get("batch_id"), it.get("item_id")))
        if row is None:
            problems.append(f"item {it.get('item_id')} is not stored for this referral")
        elif row.ciphertext_sha256 != it.get("ciphertext_hash"):
            problems.append(f"item {it.get('item_id')} does not match the stored ciphertext")
        if not isinstance(it.get("content_hash"), str) or len(it.get("content_hash", "")) != 64:
            problems.append(f"item {it.get('item_id')} has no content hash")
    batches = {it.get("batch_id") for it in items}
    patient = patient_entry_for_cnic(db, r.patient_cnic or "")
    allowed = {dept.enc_key_id: ("department", dept.subject_id, dept.key_version)} if dept else {}
    if patient:
        allowed[patient.enc_key_id] = ("patient", patient.subject_id, patient.key_version)
    wrapped_dept = set()
    for w in wraps:
        who = allowed.get(w.get("recipient_key_id"))
        if who is None or w.get("batch_id") not in batches:
            problems.append("a wrapped key is addressed to a key or batch outside this package")
            continue
        w["recipient_type"], w["recipient_subject"], w["key_version"] = who
        if who[0] == "department":
            wrapped_dept.add(w["batch_id"])
    if dept and batches - wrapped_dept:
        problems.append("every included batch's data key must be wrapped to the receiving department")
    if problems:
        audit(db, principal, "package.approve", "referral", r.reference, "rejected", r.id, {"reason": problems[:5]})
        db.commit()
        raise error(422, "invalid_package", "; ".join(problems[:5]))
    for w in wraps:
        exists = db.scalars(select(WrappedKey).where(WrappedKey.batch_id == w["batch_id"],
                                                     WrappedKey.recipient_key_id == w["recipient_key_id"])).first()
        if not exists:
            db.add(WrappedKey(referral_id=r.id, batch_id=w["batch_id"], recipient_type=w["recipient_type"],
                              recipient_subject=w["recipient_subject"], recipient_key_id=w["recipient_key_id"],
                              key_version=w["key_version"], wrapped=w["wrapped"], created_by=principal.display_name))
    for old in db.scalars(select(PackageManifest).where(PackageManifest.referral_id == r.id,
                                                        PackageManifest.superseded.is_(False))):
        old.superseded = True  # the only change ever made to a stored manifest
    pm = PackageManifest(referral_id=r.id, version=version, manifest=m, manifest_sha256=manifest_hash(m),
                         signer_subject=principal.subject, signer_key_id=signer["sig_key_id"], item_count=len(items))
    db.add(pm)
    r.packet_reviewed_by, r.packet_reviewed_at = principal.display_name, utcnow()
    if r.status in IN_FLIGHT:
        r.amendment_open = True  # a new approved version after sending: staff send it as an amendment
    bump(r)
    event(db, r, "package_approved", principal.display_name, principal.institution_id,
          {"version": version, "items": len(items), "manifest_sha256": pm.manifest_sha256,
           "recipient_key": dept.enc_key_id if dept else None, "patient_copy": bool(patient)})
    audit(db, principal, "package.approve", "referral", r.reference, "success", r.id,
          {"version": version, "items": len(items), "manifest_sha256": pm.manifest_sha256})
    notify_staff(db, r, "ready_to_send", f"{r.reference}: approved by the doctor",
                 f"{principal.display_name} signed version {version}. Send it to "
                 f"{institution_name(r.destination_institution)}.", tab="send")
    return pm


def _titles(db: Session, r: Referral, pm: PackageManifest) -> list[dict]:
    wanted = {(it["batch_id"], it["item_id"]) for it in pm.manifest["items"]}
    out = []
    for it in db.scalars(select(EncryptedItem).where(EncryptedItem.referral_id == r.id).order_by(EncryptedItem.id)):
        if (it.batch_id, it.item_id) in wanted:
            out.append({"item_id": it.item_id, "kind": it.kind, "category": it.category, "label": it.label,
                        "date": it.item_date, "source_institution": it.source_institution, "sensitive": it.sensitive})
    return out


def intake_details(db: Session, r: Referral, institution: str, principal: Principal, purpose: str) -> dict:
    """Identity details sent with a referral or test order. If the receiver has not confirmed this patient yet,
    an intake link request goes with it: they match their record or register the patient as new on arrival."""
    linked = verified_counterparts(db, r.patient_institution, r.patient_local_id)
    out = {"cnic": r.patient_cnic, "sender_name": institution_name(r.source_institution),
           "local_patient_id": linked[institution][0] if institution in linked else None, "link_request_id": None}
    if out["local_patient_id"] is None:
        link = create_request(db, principal, local_id=r.patient_local_id, target=institution, name=r.patient_name,
                              birth_date=r.patient_birth_date, sex=r.patient_sex, cnic=r.patient_cnic, referral=r,
                              purpose=purpose, kind="intake")
        out["link_request_id"] = link.id
    return out


def send(db: Session, r: Referral, principal: Principal) -> PackageManifest:
    """Staff send the approved version: a notice to the receiving hospital (titles only), written to the outbox in
    the same transaction as the decision to send."""
    amendment = r.amendment_open and r.status in IN_FLIGHT
    if r.kind != "referral":
        raise error(409, "test_request", "A test request is sent order by order")
    if r.status != "requested" and not amendment:
        raise error(409, "not_ready", "Only a referral being prepared (or an open amendment) can be sent")
    missing = blocking(readiness(db, r))
    if missing:
        raise error(409, "not_ready", "Some things still need to be done before sending", blockers=missing)
    pm = latest_manifest(db, r)
    if pm is None or pm.superseded:
        raise error(409, "not_approved", "The doctor has not approved a package yet")
    if r.submitted_package_version is not None and pm.version <= r.submitted_package_version and not amendment:
        raise error(409, "already_sent", f"Version {pm.version} was already sent")
    intake = intake_details(db, r, r.destination_institution, principal,
                            f"Referral {r.reference} to {department_name(r.destination_department)}")
    sent_at = utcnow()
    notice = ReferralNotice(
        delivery_key=f"{r.source_institution}:{r.reference}:v{pm.version}", referral_id=r.reference,
        package_version=pm.version, sender_institution=r.source_institution,
        sender_name=institution_name(r.source_institution) or r.source_institution,
        sender_department=r.source_department, destination_institution=r.destination_institution,
        destination_department=r.destination_department, destination_doctor=r.destination_doctor,
        urgency=r.urgency, reason=r.reason,
        patient={"name": r.patient_name, "birth_date": r.patient_birth_date, "sex": r.patient_sex, **intake},
        requesting_doctor={"name": r.requesting_doctor_name, "id": r.requesting_doctor_id,
                           "institution": institution_name(r.source_institution),
                           "department": department_name(r.source_department)},
        titles=_titles(db, r, pm), manifest_sha256=pm.manifest_sha256,
        signed_by={"subject_id": pm.signer_subject, "sig_key_id": pm.signer_key_id},
        sent_by=principal.display_name, sent_at=sent_at, supersedes_version=r.submitted_package_version)
    payload = notice.model_dump(mode="json")
    r.current_package_version = pm.version
    db.add(Outbox(referral_id=r.id, kind="deliver_package", target_institution=r.destination_institution,
                  message_key=notice.delivery_key, payload=payload))
    r.delivery_status = "pending"
    bump(r)
    event(db, r, "send_scheduled", principal.display_name, principal.institution_id,
          {"version": pm.version, "delivery_key": notice.delivery_key, "amendment": amendment,
           "manifest_sha256": pm.manifest_sha256})
    audit(db, principal, "referral.send", "package_manifest", f"{r.reference}v{pm.version}", "success", r.id,
          {"manifest_sha256": pm.manifest_sha256, "amendment": amendment})
    return pm


def retry(db: Session, r: Referral, principal: Principal) -> int:
    boxes = db.scalars(select(Outbox).where(Outbox.referral_id == r.id, Outbox.status == "failed")).all()
    for b in boxes:
        b.status, b.attempts, b.next_attempt_at = "pending", 0, utcnow()
    if boxes:
        if any(b.kind == "deliver_package" for b in boxes):
            r.delivery_status = "pending"
        event(db, r, "delivery_retry", principal.display_name, principal.institution_id, {"items": [b.id for b in boxes]})
        audit(db, principal, "delivery.retry", "referral", r.reference, "success", r.id)
    return len(boxes)


def manifest_out(pm: PackageManifest, full: bool) -> dict:
    out = {"version": pm.version, "manifest_sha256": pm.manifest_sha256, "signer_subject": pm.signer_subject,
           "signer_key_id": pm.signer_key_id, "item_count": pm.item_count, "superseded": pm.superseded,
           "created_at": pm.created_at}
    if full:
        out["manifest"] = pm.manifest
    return out
