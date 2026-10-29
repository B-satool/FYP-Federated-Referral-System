"""What still has to be done before staff can send the referral (one list, no repetition).

Order (decision 2026-10-29: only the doctor sees clinical content):
1. the doctor submits the request;
2. staff gather the records (retrieval) and upload the patient's papers, then mark it ready for the doctor;
3. the doctor checks the papers' fields, confirms the medicine list with the patient (including over-the-counter
   medicines), resolves different doses, reviews the medication flags and the records chosen for the packet,
   then marks the packet reviewed;
4. staff send.
The receiving institution confirms the patient when the referral arrives, so that is not a condition for sending.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import INSTITUTIONS
from ..identity.links import verified_counterparts
from ..integration.retrieval import latest_by_source, retrieval_targets
from ..medications import service as med
from ..models import Document, EvidenceItem, Referral

# Staff items: done before the referral is marked ready for the doctor
PREPARE_KEYS = ("records", "documents_read")
# Doctor items: done before the doctor marks the packet reviewed
REVIEW_KEYS = ("documents", "meds_checked", "dose_differences", "evaluation", "flags")


def _item(key: str, label: str, ok: bool, detail: str = "", who: str = "staff", tab: str | None = None,
          blocking: bool = True) -> dict:
    return {"key": key, "label": label, "ok": ok, "detail": detail, "who": who, "tab": tab, "blocking": blocking}


def staff_items(db: Session, r: Referral) -> list[dict]:
    items: list[dict] = []
    latest = latest_by_source(db, r)
    targets = retrieval_targets(db, r)
    missing = [INSTITUTIONS[t[0]]["name"] for t in targets if t[0] not in latest]
    problems = [f"{INSTITUTIONS[s.source_institution]['name']} ({s.status})" for s in latest.values()
                if s.status in ("unavailable", "denied", "expired", "invalid")]
    items.append(_item("records", "Records retrieved", not missing,
                       ("Retrieve records from: " + ", ".join(missing)) if missing else
                       ("Could not retrieve from " + ", ".join(problems) + ". This is sent as a limitation, not as 'no history'."
                        if problems else ""), tab="records"))
    pending_docs = db.scalars(select(Document).where(Document.referral_id == r.id,
                                                     Document.status.in_(("uploaded", "queued", "processing")))).all()
    items.append(_item("documents_read", "Papers from the patient uploaded and read", not pending_docs,
                       f"{len(pending_docs)} paper(s) still being read" if pending_docs else "", tab="papers"))
    return items


def doctor_items(db: Session, r: Referral, clinical: bool = True) -> list[dict]:
    items: list[dict] = []
    unchecked = db.scalars(select(EvidenceItem).where(
        EvidenceItem.referral_id == r.id, EvidenceItem.origin == "document", EvidenceItem.superseded_by.is_(None),
        EvidenceItem.review_state.notin_(("excluded",)), EvidenceItem.verification_status == "unverified")).all()
    items.append(_item("documents", "Papers from the patient checked", not unchecked,
                       f"{len(unchecked)} item(s) read from papers still to check" if unchecked else "",
                       who="doctor", tab="papers"))
    items.append(_item("meds_checked", "Medicine list confirmed with the patient (including over-the-counter)",
                       r.meds_checked_at is not None,
                       f"By {r.meds_checked_by}" if r.meds_checked_at else "Ask the patient, add any missing medicine, then confirm",
                       who="doctor", tab="medicines"))
    differs = sorted({e.ingredient or e.original_name for e in med.current_entries(db, r.id) if e.dose_differs})
    detail = ""
    if differs:
        detail = (("Different doses recorded for: " + ", ".join(differs) + ". Exclude the one that is not current.")
                  if clinical else f"{len(differs)} medicine(s) recorded with different doses")
    items.append(_item("dose_differences", "Different doses resolved", not differs, detail, who="doctor", tab="medicines"))
    run = med.latest_run(db, r.id)
    items.append(_item("evaluation", "Medicines checked against the rules", run is not None and run.status == "completed",
                       "" if run is not None and run.status == "completed" else
                       ("Evaluation failed; re-run it" if run else "Not evaluated yet"), who="system", tab="medicines"))
    unack = med.unacknowledged_flags(db, r.id)
    items.append(_item("flags", "Doctor reviewed the medication flags", not unack,
                       f"{len(unack)} flag(s) waiting for {r.requesting_doctor_name}" if unack else "",
                       who="doctor", tab="medicines"))
    return items


def readiness(db: Session, r: Referral, clinical: bool = True) -> list[dict]:
    items = [_item("request", "Doctor's request submitted", r.status != "draft",
                   "" if r.status != "draft" else f"{r.requesting_doctor_name} has not submitted the request yet",
                   who="doctor", tab="request")]
    if r.kind == "test":
        return items
    items += staff_items(db, r)
    items.append(_item("prepared", "Marked ready for the doctor's review", r.prepared_at is not None,
                       f"By {r.prepared_by}" if r.prepared_at else
                       "When the records are retrieved and the papers uploaded, mark it ready for the doctor", tab="send"))
    review = doctor_items(db, r, clinical)
    if r.prepared_at is None:  # the doctor's part starts once staff mark it ready
        review = [{**i, "ok": False, "detail": "After staff mark it ready"} if not i["ok"] else i for i in review]
    items += review
    items.append(_item("packet_reviewed", "Doctor reviewed the packet (records, papers, medicines and flags)",
                       r.packet_reviewed_at is not None,
                       f"By {r.packet_reviewed_by}" if r.packet_reviewed_at else
                       "The doctor confirms what goes in the packet, then staff can send it", who="doctor", tab="send"))

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
