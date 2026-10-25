"""What still has to be done before staff can send the referral (one list, no repetition)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import INSTITUTIONS
from ..identity.links import links_for, verified_counterparts
from ..integration.retrieval import latest_by_source, retrieval_targets
from ..medications import service as med
from ..models import Document, EvidenceItem, Referral


def _item(key: str, label: str, ok: bool, detail: str = "", who: str = "staff", tab: str | None = None,
          blocking: bool = True) -> dict:
    return {"key": key, "label": label, "ok": ok, "detail": detail, "who": who, "tab": tab, "blocking": blocking}


def readiness(db: Session, r: Referral) -> list[dict]:
    items: list[dict] = []
    dest = INSTITUTIONS[r.destination_institution]["name"]
    items.append(_item("request", "Doctor's request submitted", r.status != "draft",
                       "" if r.status != "draft" else f"{r.requesting_doctor_name} has not submitted the request yet",
                       who="doctor", tab="request"))

    linked = verified_counterparts(db, r.patient_institution, r.patient_local_id)
    if r.destination_institution in linked:
        items.append(_item("destination_link", f"{dest} confirmed the patient", True,
                           f"Their record: {linked[r.destination_institution][0]}", tab="links"))
    else:
        pending = [x for x in links_for(db, r.patient_institution, r.patient_local_id)
                   if x.target_institution == r.destination_institution and x.status == "requested"]
        items.append(_item("destination_link", f"{dest} confirmed the patient", False,
                           f"Waiting for {dest} staff to check the link request" if pending
                           else f"Send {dest} a patient-link request", tab="links"))

    latest = latest_by_source(db, r)
    targets = retrieval_targets(db, r)
    missing = [INSTITUTIONS[t[0]]["name"] for t in targets if t[0] not in latest]
    problems = [f"{INSTITUTIONS[s.source_institution]['name']} ({s.status})" for s in latest.values()
                if s.status in ("unavailable", "denied", "invalid")]
    items.append(_item("records", "Records retrieved", not missing,
                       ("Retrieve records from: " + ", ".join(missing)) if missing else
                       ("Could not retrieve from " + ", ".join(problems) + ". This is sent as a limitation, not as 'no history'."
                        if problems else ""), tab="records"))

    pending_docs = db.scalars(select(Document).where(Document.referral_id == r.id,
                                                     Document.status.in_(("uploaded", "queued", "processing")))).all()
    unchecked = db.scalars(select(EvidenceItem).where(
        EvidenceItem.referral_id == r.id, EvidenceItem.origin == "document", EvidenceItem.superseded_by.is_(None),
        EvidenceItem.review_state.notin_(("excluded",)), EvidenceItem.verification_status == "unverified")).all()
    detail = []
    if pending_docs:
        detail.append(f"{len(pending_docs)} paper(s) still being read")
    if unchecked:
        detail.append(f"{len(unchecked)} item(s) read from papers still to check")
    items.append(_item("documents", "Papers from the patient checked", not detail, "; ".join(detail), tab="papers"))

    items.append(_item("meds_checked", "Patient asked about all medicines (including over-the-counter)",
                       r.meds_checked_at is not None,
                       f"By {r.meds_checked_by}" if r.meds_checked_at else "Ask the patient, add any missing medicine, then confirm",
                       tab="medicines"))

    differs = sorted({e.ingredient or e.original_name for e in med.current_entries(db, r.id) if e.dose_differs})
    items.append(_item("dose_differences", "Different doses resolved", not differs,
                       ("Different doses recorded for: " + ", ".join(differs) + ". Exclude the one that is not current.")
                       if differs else "", tab="medicines"))

    run = med.latest_run(db, r.id)
    items.append(_item("evaluation", "Medicines checked against the rules", run is not None and run.status == "completed",
                       "" if run is not None and run.status == "completed" else
                       ("Evaluation failed; re-run it" if run else "Not evaluated yet"), tab="medicines"))

    unack = med.unacknowledged_flags(db, r.id)
    items.append(_item("flags", "Doctor acknowledged the medication flags", not unack,
                       f"{len(unack)} flag(s) waiting for {r.requesting_doctor_name}" if unack else "",
                       who="doctor", tab="medicines"))
    return items


def blocking(items: list[dict]) -> list[dict]:
    return [i for i in items if i["blocking"] and not i["ok"]]
