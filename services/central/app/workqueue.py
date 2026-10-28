"""Role-based work queue: doctors see what needs a doctor; staff see what needs preparing."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from refcommon.auth import Principal
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .medications import service as med
from .models import Clarification, ConsultationResponse, DiagnosticRequest, FollowupTask, PatientLink, Referral
from .notifications import list_notifications
from .referrals.state import IN_FLIGHT
from .security import get_principal, require_roles
from .sending.readiness import readiness
from .serializers import diagnostic_out, referral_out

router = APIRouter(tags=["work queue"])
OPEN = ("requested", "submitted", "acknowledged", "accepted", "response_returned", "followup_pending")


def _ref(r: Referral, **extra) -> dict:
    return {**referral_out(r), **extra}


@router.get("/work-queue")
def work_queue(db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    require_roles(principal, "clinician", "clinic_staff", action="work_queue")
    inst = principal.institution_id
    out: dict = {"role": "doctor" if "clinician" in principal.roles else "staff",
                 "notifications": list_notifications(True, db, principal)[:20]}
    referrals = db.scalars(select(Referral).where(Referral.source_institution == inst, Referral.status.in_(OPEN + ("draft",)))
                           .order_by(Referral.updated_at.desc())).all()

    if "clinician" in principal.roles:
        mine = [r for r in referrals if r.requesting_doctor_id == principal.subject]
        out["drafts"] = [_ref(r) for r in mine if r.status == "draft"]
        out["flags_to_acknowledge"] = [_ref(r, unacknowledged=len(u)) for r in mine
                                       if r.kind == "referral" and r.prepared_at is not None
                                       and r.status not in ("draft", "cancelled")
                                       for u in [med.unacknowledged_flags(db, r.id)] if u]
        out["responses_to_review"] = []
        for r in mine:
            resp = db.scalars(select(ConsultationResponse).where(ConsultationResponse.referral_id == r.id,
                                                                 ConsultationResponse.reviewed_at.is_(None))).first()
            if resp:
                out["responses_to_review"].append(_ref(r, specialist_name=resp.specialist_name, received_at=resp.received_at))
        ids = [r.id for r in mine]
        out["results_to_see"] = [{**diagnostic_out(d), "referral_reference": next(x.reference for x in mine if x.id == d.referral_id),
                                  "patient_name": next(x.patient_name for x in mine if x.id == d.referral_id)}
                                 for d in db.scalars(select(DiagnosticRequest).where(
                                     DiagnosticRequest.referral_id.in_(ids), DiagnosticRequest.status == "reported",
                                     DiagnosticRequest.seen_at.is_(None)))] if ids else []
        out["in_progress"] = [_ref(r) for r in mine if r.status in ("requested",) + tuple(IN_FLIGHT)]

    if "clinic_staff" in principal.roles:
        prep = []
        for r in referrals:
            if r.kind == "referral" and (r.status == "requested" or r.amendment_open):
                items = readiness(db, r)
                todo = [i for i in items if i["blocking"] and not i["ok"]]
                prep.append(_ref(r, done=len(items) - len(todo), total=len(items),
                                 next_step=todo[0] if todo else None, ready=not todo))
        out["to_prepare"] = prep
        out["link_requests"] = [{"id": x.id, "patient_name": x.patient_name, "requester": x.requester_institution,
                                 "requested_at": x.requested_at, "purpose": x.purpose}
                                for x in db.scalars(select(PatientLink).where(PatientLink.target_institution == inst,
                                                                              PatientLink.kind == "records",
                                                                              PatientLink.status == "requested"))]
        ref_ids = {r.id: r for r in referrals if r.status != "draft"}
        out["tests_to_send"] = [{**diagnostic_out(d), "referral_reference": ref_ids[d.referral_id].reference,
                                 "patient_name": ref_ids[d.referral_id].patient_name}
                                for d in db.scalars(select(DiagnosticRequest).where(
                                    DiagnosticRequest.referral_id.in_(list(ref_ids)),
                                    DiagnosticRequest.status == "draft"))] if ref_ids else []
        out["delivery_problems"] = [_ref(r) for r in referrals if r.delivery_status == "failed"]
        out["follow_up"] = []
        for r in referrals:
            if r.status in ("response_returned", "followup_pending") or (r.kind == "referral" and r.status == "accepted"):
                open_tasks = db.scalars(select(FollowupTask).where(FollowupTask.referral_id == r.id,
                                                                   FollowupTask.status == "open")).all()
                out["follow_up"].append(_ref(r, patient_informed=r.patient_informed_at is not None,
                                             open_tasks=len(open_tasks)))

    clars = db.scalars(select(Clarification).where(Clarification.status == "open").order_by(Clarification.asked_at)).all()
    by_id = {r.id: r for r in referrals}
    out["info_requests"] = [{"id": c.id, "referral_id": c.referral_id, "referral_reference": by_id[c.referral_id].reference,
                             "patient_name": by_id[c.referral_id].patient_name, "question": c.question,
                             "asked_by": c.asked_by, "asked_at": c.asked_at}
                            for c in clars if c.referral_id in by_id]
    return out
