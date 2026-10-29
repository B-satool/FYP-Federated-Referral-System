"""What still has to happen before staff can send the referral (spec v4 section 2).

1. the doctor submits the request;
2. staff ask the patient for consent (the patient answers in the portal) and request the records;
3. the doctor opens the records on their device, chooses what goes in the package, enters the medicines and
   approves: a signed package, re-wrapped to the receiving department;
4. staff send.
Consent and records are not strictly required (a referral can go with the doctor's own notes only); an approved
package and a published receiving-department key are.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import INSTITUTIONS, department_name
from ..identity.links import verified_counterparts
from ..models import Consent, PackageManifest, Referral


def _item(key: str, label: str, ok: bool, detail: str = "", who: str = "staff", tab: str | None = None,
          blocking: bool = True) -> dict:
    return {"key": key, "label": label, "ok": ok, "detail": detail, "who": who, "tab": tab, "blocking": blocking}


def readiness(db: Session, r: Referral, clinical: bool = True) -> list[dict]:
    from ..consent.router import effective_status
    from ..keys.router import current_department_entry
    from ..records.requests import latest_requests

    items = [_item("request", "Doctor's request submitted", r.status != "draft",
                   "" if r.status != "draft" else f"{r.requesting_doctor_name} has not submitted the request yet",
                   who="doctor", tab="request")]
    if r.kind == "test":
        return items
    consent = db.scalars(select(Consent).where(Consent.referral_id == r.id, Consent.status != "withdrawn")
                         .order_by(Consent.id.desc())).first()
    status = effective_status(consent) if consent else None
    items.append(_item("consent", "Patient's consent", status == "granted",
                       {"granted": "", "requested": "Waiting for the patient to answer in the patient portal",
                        "declined": "The patient declined: the referral can only carry the doctor's own notes",
                        "revoked": "The patient withdrew consent", "expired": "The consent ended; ask again",
                        None: "Ask the patient for consent to fetch records"}.get(status, status or ""),
                       tab="records", blocking=False))
    reqs = latest_requests(db, r)
    problems = [f"{INSTITUTIONS.get(x.custodian, {}).get('name', x.custodian)} ({x.status.replace('_', ' ')})"
                for x in reqs if x.status in ("refused", "unavailable", "failed", "not_linked", "pending_manual_review")]
    items.append(_item("records", "Records requested", bool(reqs),
                       ("Not all institutions sent records: " + ", ".join(problems) +
                        ". This travels as a limitation, never as 'no history'.") if problems else
                       ("" if reqs else "Request the records the patient agreed to"), tab="records", blocking=False))
    approved = db.scalars(select(PackageManifest).where(PackageManifest.referral_id == r.id,
                                                        PackageManifest.superseded.is_(False))).first()
    items.append(_item("approved", "Doctor approved and signed the package", bool(approved and r.packet_reviewed_at),
                       f"Version {approved.version}, signed by {r.packet_reviewed_by}" if approved and r.packet_reviewed_at
                       else "The doctor reviews the records on their device and signs the package", who="doctor",
                       tab="summary"))
    dept = current_department_entry(db, r.destination_institution, r.destination_department)
    items.append(_item("department_key", f"{department_name(r.destination_department)} can receive encrypted referrals",
                       dept is not None, "" if dept else "The receiving department has not published its key yet",
                       who="system", tab="send"))
    dest = INSTITUTIONS[r.destination_institution]["name"]
    linked = verified_counterparts(db, r.patient_institution, r.patient_local_id)
    items.append(_item("destination_patient", f"{dest} confirms the patient when the referral arrives", True,
                       f"Already linked to their record {linked[r.destination_institution][0]}"
                       if r.destination_institution in linked else
                       "The referral carries the patient's name, date of birth, sex and CNIC. "
                       f"{dest} staff match their record, or register the patient as new.",
                       tab="send", blocking=False))
    return items


def blocking(items: list[dict]) -> list[dict]:
    return [i for i in items if i["blocking"] and not i["ok"]]
