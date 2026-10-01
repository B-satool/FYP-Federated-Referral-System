"""Referral drafts, search, retrieval and lifecycle (FR-11 to FR-16, FR-21)."""
from __future__ import annotations

from datetime import date, datetime, time, timezone

import httpx
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from refcommon.auth import Principal
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..approvals.packages import approval_blockers
from ..config import INSTITUTIONS, PRIORITIES, PROCEDURES, SOURCES, SPECIALTIES, settings
from ..db import get_db
from ..identity.links import links_for, verified_counterparts
from ..integration import retrieval
from ..integration.sources import source_name
from ..models import Referral, ReferralEvent, ReferralPackage, SourceRetrieval
from ..reviews.checklist import checklist_summary
from ..security import CLINIC_ROLES, audit, bump, check_version, error, get_principal, load_referral, require_roles
from ..serializers import referral_out, retrieval_out
from ..workflow import after_change
from .state import PRE_SUBMISSION, TERMINAL, ensure_clinical_edit_allowed, mark_clinical_change, transition

router = APIRouter(tags=["referrals"])


@router.get("/patients/search")
def search_patients(q: str = "", principal: Principal = Depends(get_principal)):
    """Search the caller's own institution patient index through its source service."""
    require_roles(principal, *CLINIC_ROLES, action="patients.search")
    if principal.institution_id not in SOURCES or principal.institution_id == "lab-b":
        raise error(404, "no_patient_index", "Your institution has no connected patient index in this demonstration")
    url = getattr(settings, SOURCES[principal.institution_id]["url_attr"]) + "/patients"
    try:
        resp = httpx.get(url, params={"q": q}, headers={"Authorization": f"Bearer {principal.token}"},
                         timeout=settings.source_timeout_seconds)
    except httpx.HTTPError as exc:
        raise error(503, "source_unavailable", f"{source_name(principal.institution_id)} is unavailable") from exc
    if resp.status_code != 200:
        raise error(resp.status_code, "source_error", resp.json().get("detail", {}).get("message", "Source error"))
    return resp.json()


class ReferralCreate(BaseModel):
    patient_local_id: str
    destination_institution: str = "spec-c"
    specialty: str = "orthodontics"
    reason: str = ""
    priority: str | None = None
    planned_procedure: str | None = None
    procedure_status: str = "not_stated"


def _validate_fields(priority, planned_procedure, procedure_status, principal, existing_priority=None):
    if priority is not None and priority not in PRIORITIES:
        raise error(422, "invalid_priority", f"Priority must be one of {', '.join(PRIORITIES)}")
    if priority is not None and priority != existing_priority and "clinician" not in principal.roles:
        raise error(403, "clinician_priority", "Priority is clinician-selected; only a clinician can set it")
    if procedure_status not in ("not_stated", "known", "unknown"):
        raise error(422, "invalid_procedure_status", "procedure_status must be not_stated, known or unknown")
    if procedure_status == "known" and planned_procedure not in PROCEDURES:
        raise error(422, "invalid_procedure", "Choose a supported planned procedure or record it as unknown")


@router.post("/referrals", status_code=201)
def create_referral(body: ReferralCreate, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    require_roles(principal, *CLINIC_ROLES, action="referral.create")
    if body.specialty not in SPECIALTIES:
        raise error(422, "unsupported_specialty", "Only orthodontics is supported in this prototype")
    if body.destination_institution != "spec-c":
        raise error(422, "unsupported_destination", "Only Specialist C is connected in this prototype")
    _validate_fields(body.priority, body.planned_procedure, body.procedure_status, principal)
    patients = search_patients(body.patient_local_id, principal)
    match = next((p for p in patients if p["local_patient_id"] == body.patient_local_id), None)
    if match is None:
        raise error(404, "patient_not_found", "Patient not found in your institution's records")
    r = Referral(
        reference="pending", patient_institution=principal.institution_id, patient_local_id=body.patient_local_id,
        patient_name=f"{match['given']} {match['family']}", patient_birth_date=match["birth_date"], patient_sex=match["sex"],
        source_institution=principal.institution_id, created_by_id=principal.subject, created_by_name=principal.display_name,
        destination_institution=body.destination_institution, specialty=body.specialty, reason=body.reason.strip(),
        priority=body.priority, planned_procedure=body.planned_procedure if body.procedure_status == "known" else None,
        procedure_status=body.procedure_status,
    )
    if "clinician" in principal.roles:
        r.referring_clinician_id, r.referring_clinician_name = principal.subject, principal.display_name
    db.add(r)
    db.flush()
    r.reference = f"REF-{datetime.now(timezone.utc).year}-{r.id:05d}"
    db.add(ReferralEvent(referral_id=r.id, event_type="created", to_status="draft", actor=principal.display_name,
                         institution_id=principal.institution_id))
    audit(db, principal, "referral.create", "referral", r.reference, "success", r.id)
    after_change(db, r, "referral_created", principal)
    db.commit()
    return referral_out(r)


@router.get("/referrals")
def list_referrals(patient: str | None = None, reference: str | None = None, status: str | None = None,
                   destination: str | None = None, date_from: date | None = None, date_to: date | None = None,
                   limit: int = Query(100, le=500), db: Session = Depends(get_db),
                   principal: Principal = Depends(get_principal)):
    require_roles(principal, *CLINIC_ROLES, action="referral.search")
    stmt = select(Referral).where(Referral.source_institution == principal.institution_id)
    if patient:
        like = f"%{patient.strip()}%"
        stmt = stmt.where(or_(Referral.patient_local_id.ilike(like), Referral.patient_name.ilike(like)))
    if reference:
        stmt = stmt.where(Referral.reference.ilike(f"%{reference.strip()}%"))
    if status:
        stmt = stmt.where(Referral.status.in_(status.split(",")))
    if destination:
        stmt = stmt.where(Referral.destination_institution == destination)
    if date_from:
        stmt = stmt.where(Referral.created_at >= datetime.combine(date_from, time.min, tzinfo=timezone.utc))
    if date_to:
        stmt = stmt.where(Referral.created_at <= datetime.combine(date_to, time.max, tzinfo=timezone.utc))
    rows = db.scalars(stmt.order_by(Referral.updated_at.desc()).limit(limit)).all()
    return [referral_out(r) for r in rows]


def source_overview(db: Session, referral: Referral) -> list[dict]:
    targets = {t[0]: t for t in retrieval.retrieval_targets(db, referral)}
    out = []
    for inst in SOURCES:
        latest = db.scalars(select(SourceRetrieval).where(SourceRetrieval.referral_id == referral.id,
                                                          SourceRetrieval.source_institution == inst)
                            .order_by(SourceRetrieval.id.desc())).first()
        if inst in targets:
            _, local_id, link_id = targets[inst]
            out.append({"source_institution": inst, "source_name": source_name(inst), "linked": True,
                        "local_patient_id": local_id, "link_id": link_id,
                        "latest": retrieval_out(latest) if latest else None})
        else:
            pending = [link for link in links_for(db, referral.patient_institution, referral.patient_local_id)
                       if inst in (link.a_institution, link.b_institution)]
            out.append({"source_institution": inst, "source_name": source_name(inst), "linked": False,
                        "local_patient_id": None, "link_id": None,
                        "link_states": sorted({link.status for link in pending}),
                        "latest": retrieval_out(latest) if latest else None,
                        "message": "No verified patient link - records are not requested and will not enter the referral"})
    return out


@router.get("/referrals/{referral_id}")
def get_referral(referral_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    r = load_referral(db, referral_id, principal, "view")
    audit(db, principal, "referral.view", "referral", r.reference, "success", r.id)
    packages = db.scalars(select(ReferralPackage).where(ReferralPackage.referral_id == r.id)
                          .order_by(ReferralPackage.version.desc())).all()
    out = {
        **referral_out(r),
        "sources": source_overview(db, r),
        "checklist": checklist_summary(db, r),
        "approval_blockers": approval_blockers(db, r) if r.status in PRE_SUBMISSION or r.amendment_open else [],
        "packages": [{"version": p.version, "approved_by": p.approved_by, "approved_at": p.approved_at,
                      "content_hash": p.content_hash, "superseded": p.superseded, "delivery_key": p.delivery_key,
                      "overrides": p.overrides} for p in packages],
        "verified_links": [{"institution_id": k, "local_patient_id": v[0], "link_id": v[1]}
                           for k, v in verified_counterparts(db, r.patient_institution, r.patient_local_id).items()],
    }
    db.commit()
    return out


class ReferralUpdate(BaseModel):
    expected_version: int
    reason: str | None = None
    priority: str | None = None
    planned_procedure: str | None = None
    procedure_status: str | None = None
    assign_me_as_clinician: bool = False


@router.patch("/referrals/{referral_id}")
def update_referral(referral_id: int, body: ReferralUpdate, db: Session = Depends(get_db),
                    principal: Principal = Depends(get_principal)):
    r = load_referral(db, referral_id, principal, "edit")
    check_version(r, body.expected_version)
    ensure_clinical_edit_allowed(r)
    proc_status = body.procedure_status or r.procedure_status
    planned = body.planned_procedure if body.planned_procedure is not None else r.planned_procedure
    _validate_fields(body.priority, planned, proc_status, principal, existing_priority=r.priority)
    changes = {}
    if body.reason is not None and body.reason.strip() != r.reason:
        changes["reason"] = [r.reason, body.reason.strip()]
        r.reason = body.reason.strip()
    if body.priority is not None and body.priority != r.priority:
        changes["priority"] = [r.priority, body.priority]
        r.priority = body.priority
    new_planned = planned if proc_status == "known" else None
    if proc_status != r.procedure_status or new_planned != r.planned_procedure:
        changes["procedure"] = [[r.procedure_status, r.planned_procedure], [proc_status, new_planned]]
        r.procedure_status, r.planned_procedure = proc_status, new_planned
    if body.assign_me_as_clinician:
        require_roles(principal, "clinician", action="referral.assign_clinician")
        r.referring_clinician_id, r.referring_clinician_name = principal.subject, principal.display_name
        changes["referring_clinician"] = principal.display_name
    if not changes:
        return referral_out(r)
    if r.current_package_version and any(k in changes for k in ("reason", "priority", "procedure")):
        mark_clinical_change(db, r, principal.display_name, ", ".join(changes), principal)
    else:
        bump(r)
    audit(db, principal, "referral.update", "referral", r.reference, "success", r.id, {"changes": changes})
    after_change(db, r, "referral_context_changed" if "procedure" in changes else "referral_updated", principal)
    db.commit()
    return referral_out(r)


@router.post("/referrals/{referral_id}/retrieve")
def retrieve_records(referral_id: int, source: str | None = None, db: Session = Depends(get_db),
                     principal: Principal = Depends(get_principal)):
    r = load_referral(db, referral_id, principal, "retrieve")
    if r.status in TERMINAL:
        raise error(409, "referral_closed", "Retrieval is not available for a closed referral")
    results = retrieval.retrieve(db, r, principal, only=source)
    after_change(db, r, "records_retrieved", principal)
    db.commit()
    return {"results": [retrieval_out(s) for s in results], "sources": source_overview(db, r)}


@router.get("/referrals/{referral_id}/retrievals")
def retrieval_history(referral_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    r = load_referral(db, referral_id, principal, "view")
    rows = db.scalars(select(SourceRetrieval).where(SourceRetrieval.referral_id == r.id).order_by(SourceRetrieval.id.desc()))
    return [retrieval_out(s) for s in rows]


class VersionIn(BaseModel):
    expected_version: int


@router.post("/referrals/{referral_id}/request-approval")
def request_approval(referral_id: int, body: VersionIn, db: Session = Depends(get_db),
                     principal: Principal = Depends(get_principal)):
    r = load_referral(db, referral_id, principal, "edit")
    check_version(r, body.expected_version)
    if r.status not in ("draft", "awaiting_information"):
        raise error(409, "invalid_transition", "Only a draft can be sent for approval")
    after_change(db, r, "approval_requested", principal)
    blocking = [b for b in approval_blockers(db, r) if b["type"] == "review_item"]
    target = "awaiting_information" if blocking else "awaiting_approval"
    transition(db, r, target, principal.display_name, principal, {"blocking_items": len(blocking)})
    db.commit()
    return {**referral_out(r), "blockers": blocking}


@router.post("/referrals/{referral_id}/return-to-draft")
def return_to_draft(referral_id: int, body: VersionIn, db: Session = Depends(get_db),
                    principal: Principal = Depends(get_principal)):
    r = load_referral(db, referral_id, principal, "edit")
    check_version(r, body.expected_version)
    if r.status not in ("awaiting_information", "awaiting_approval"):
        raise error(409, "invalid_transition", "Referral is not awaiting information or approval")
    transition(db, r, "draft", principal.display_name, principal)
    db.commit()
    return referral_out(r)


class CancelIn(BaseModel):
    expected_version: int
    reason: str = Field(min_length=3)


@router.post("/referrals/{referral_id}/cancel")
def cancel(referral_id: int, body: CancelIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    r = load_referral(db, referral_id, principal, "cancel")
    check_version(r, body.expected_version)
    r.cancel_reason = body.reason.strip()
    transition(db, r, "cancelled", principal.display_name, principal, {"reason": r.cancel_reason})
    db.commit()
    return referral_out(r)


@router.get("/referrals/{referral_id}/events")
def events(referral_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    r = load_referral(db, referral_id, principal, "view")
    rows = db.scalars(select(ReferralEvent).where(ReferralEvent.referral_id == r.id).order_by(ReferralEvent.id))
    return [{"id": e.id, "event_type": e.event_type, "from_status": e.from_status, "to_status": e.to_status,
             "actor": e.actor, "institution_id": e.institution_id, "institution_name": INSTITUTIONS.get(e.institution_id or "", {}).get("name"),
             "detail": e.detail, "created_at": e.created_at} for e in rows]
