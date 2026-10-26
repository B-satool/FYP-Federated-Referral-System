"""The doctor's request, search, retrieval and lifecycle.

Two kinds of request:
* referral: to a doctor or department at another clinic or hospital. Staff gather records,
  papers and medicines, mark it ready, the doctor reviews the medication flags, staff send.
* test: one or more tests or scans at a laboratory, radiology or cardiac department. Staff
  check and send the orders; results come back to the doctor.
"""
from __future__ import annotations

from datetime import date, datetime, time, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from refcommon.auth import Principal
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..config import (CATEGORY_DEPARTMENT_KIND, DEPARTMENTS, INSTITUTIONS, PROCEDURE_STATUSES, PROCEDURE_TAGS, SOURCES,
                      URGENCIES, settings)
from ..db import get_db
from ..identity.links import links_for
from ..identity.router import create_request
from ..integration import retrieval, sources
from ..models import Clarification, DiagnosticRequest, Referral, ReferralEvent, ReferralPackage, SourceRetrieval
from ..notifications import notify_staff
from ..selection import selection
from ..tasks import enqueue
from ..security import CLINIC_ROLES, DOCTOR, audit, bump, check_version, error, get_principal, load_referral, require_roles
from ..serializers import diagnostic_out, link_summary, referral_out, retrieval_out
from ..workflow import after_change
from .state import CLINICAL_LOCKED, IN_FLIGHT, PRE_SUBMISSION, TERMINAL, mark_clinical_change, transition

router = APIRouter(tags=["referrals"])
KINDS = ("referral", "test")


class DiagnosticIn(BaseModel):
    category: str
    test: str = Field(min_length=2)
    body_area: str | None = None
    clinical_question: str = Field(min_length=3)
    urgency: str = "routine"
    destination_institution: str
    destination_department: str


class ReferralForm(BaseModel):
    patient_local_id: str
    kind: str = "referral"
    source_department: str | None = None
    destination_institution: str | None = None
    destination_department: str | None = None
    destination_doctor: str | None = None
    reason: str = ""
    urgency: str = "routine"
    procedure_status: str = "unknown"
    planned_procedure: str | None = None
    procedure_tags: list[str] = Field(default_factory=list)
    diagnostic_requests: list[DiagnosticIn] = Field(default_factory=list)
    submit: bool = False


def validate_diagnostic(d: DiagnosticIn, principal: Principal) -> None:
    inst = INSTITUTIONS.get(d.destination_institution)
    if inst is None or d.destination_institution not in SOURCES or d.destination_department not in inst["departments"]:
        raise error(422, "invalid_destination", "Choose where the test or scan should be done")
    if d.destination_institution == principal.institution_id:
        raise error(422, "same_institution", "Tests done here are ordered in your own system, not sent")
    if DEPARTMENTS[d.destination_department]["kind"] != CATEGORY_DEPARTMENT_KIND.get(d.category):
        raise error(422, "invalid_department", "That department does not do this kind of test")
    if d.urgency not in URGENCIES:
        raise error(422, "invalid_urgency", "Choose an urgency")


def _validate(body: ReferralForm, principal: Principal, for_submit: bool) -> None:
    if body.kind not in KINDS:
        raise error(422, "invalid_kind", "Choose a referral or a test/scan request")
    if body.kind == "test":
        if for_submit and not body.diagnostic_requests:
            raise error(422, "tests_required", "Add at least one test or scan")
        for d in body.diagnostic_requests:
            validate_diagnostic(d, principal)
        return
    dest = INSTITUTIONS.get(body.destination_institution or "")
    if dest is None or body.destination_institution not in SOURCES:
        raise error(422, "invalid_destination", "Choose the clinic or hospital the patient is being referred to")
    if body.destination_institution == principal.institution_id:
        raise error(422, "same_institution", "A referral goes to another institution")
    if body.destination_department not in dest["departments"] or DEPARTMENTS[body.destination_department]["kind"] != "clinical":
        raise error(422, "invalid_department", "Choose a department there")
    if body.urgency not in URGENCIES:
        raise error(422, "invalid_urgency", f"Urgency must be one of {', '.join(URGENCIES)}")
    if body.procedure_status not in PROCEDURE_STATUSES:
        raise error(422, "invalid_procedure_status", "Choose whether a procedure is planned")
    if body.procedure_status == "planned" and len((body.planned_procedure or "").strip()) < 3:
        raise error(422, "procedure_required", "Write the planned procedure")
    bad = set(body.procedure_tags) - set(PROCEDURE_TAGS)
    if bad:
        raise error(422, "invalid_tags", f"Unknown procedure features: {sorted(bad)}")
    if for_submit and len(body.reason.strip()) < 10:
        raise error(422, "reason_required", "Write the reason for referral (what you want the specialist to address)")
    if body.diagnostic_requests:
        raise error(422, "tests_separate", "Request tests and scans separately (New request, then Test or scan)")


def _procedure(body: ReferralForm) -> tuple[str | None, list[str]]:
    if body.kind != "referral" or body.procedure_status != "planned":
        return None, []
    return (body.planned_procedure or "").strip(), sorted(set(body.procedure_tags))


def add_diagnostic(db: Session, r: Referral, d: DiagnosticIn, principal: Principal) -> DiagnosticRequest:
    dx = DiagnosticRequest(reference="pending", referral_id=r.id, category=d.category, test=d.test.strip(),
                           body_area=(d.body_area or None), clinical_question=d.clinical_question.strip(),
                           urgency=d.urgency, destination_institution=d.destination_institution,
                           destination_department=d.destination_department, status="draft",
                           requested_by=principal.display_name, requested_by_id=principal.subject,
                           history=[{"status": "draft", "by": principal.display_name,
                                     "at": datetime.now(timezone.utc).isoformat()}])
    db.add(dx)
    db.flush()
    dx.reference = f"DX-{datetime.now(timezone.utc).year}-{dx.id:05d}"
    return dx


def _submit(db: Session, r: Referral, principal: Principal) -> None:
    """Doctor submits the request; staff are asked to prepare it. The destination is asked to
    confirm the patient only when the referral (or test order) is sent."""
    transition(db, r, "requested", principal.display_name, principal)
    r.requested_at = datetime.now(timezone.utc)
    if r.kind == "test":
        notify_staff(db, r, "test_requested", f"Tests to send: {r.reference}",
                     f"{r.patient_name}, requested by {r.requesting_doctor_name}.", tab="tests")
    else:
        notify_staff(db, r, "referral_requested", f"New referral to prepare: {r.reference}",
                     f"{r.patient_name}, requested by {r.requesting_doctor_name}.", tab="records")
        after_change(db, r, "referral_requested", principal)


@router.post("/referrals", status_code=201)
def create_referral(body: ReferralForm, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """Only a doctor applies for a referral or a test."""
    require_roles(principal, DOCTOR, action="referral.create", message="Only a doctor can make a request")
    _validate(body, principal, body.submit)
    p = sources.call(principal.institution_id, "GET", f"/patients/{body.patient_local_id}", principal)
    planned, tags = _procedure(body)
    is_referral = body.kind == "referral"
    r = Referral(
        reference="pending", kind=body.kind, patient_institution=principal.institution_id,
        patient_local_id=body.patient_local_id,
        patient_name=p["name"], patient_birth_date=p["birth_date"], patient_sex=p["sex"], patient_cnic=p.get("cnic"),
        source_institution=principal.institution_id, source_department=body.source_department or principal.department,
        requesting_doctor_id=principal.subject, requesting_doctor_name=principal.display_name,
        created_by_id=principal.subject, created_by_name=principal.display_name,
        destination_institution=body.destination_institution if is_referral else None,
        destination_department=body.destination_department if is_referral else None,
        destination_doctor=(body.destination_doctor or None) if is_referral else None,
        reason=body.reason.strip(), urgency=body.urgency,
        procedure_status=body.procedure_status if is_referral else "none",
        planned_procedure=planned, procedure_tags=tags,
    )
    db.add(r)
    db.flush()
    r.reference = f"{'REF' if is_referral else 'TST'}-{datetime.now(timezone.utc).year}-{r.id:05d}"
    db.add(ReferralEvent(referral_id=r.id, event_type="created", to_status="draft", actor=principal.display_name,
                         institution_id=principal.institution_id))
    for d in body.diagnostic_requests:
        add_diagnostic(db, r, d, principal)
    audit(db, principal, "referral.create", "referral", r.reference, "success", r.id)
    if body.submit:
        _submit(db, r, principal)
    db.commit()
    return referral_out(r)


@router.get("/referrals")
def list_referrals(patient: str | None = None, reference: str | None = None, status: str | None = None,
                   destination: str | None = None, kind: str | None = None, mine: bool = False,
                   date_from: date | None = None, date_to: date | None = None, limit: int = Query(100, le=500),
                   db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    require_roles(principal, *CLINIC_ROLES, action="referral.search")
    stmt = select(Referral).where(Referral.source_institution == principal.institution_id)
    if kind:
        stmt = stmt.where(Referral.kind == kind)
    if mine:
        stmt = stmt.where(Referral.requesting_doctor_id == principal.subject)
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
    if "clinician" not in principal.roles:
        stmt = stmt.where(Referral.status != "draft")  # a doctor's unsubmitted draft is the doctor's own
    rows = db.scalars(stmt.order_by(Referral.updated_at.desc()).limit(limit)).all()
    return [referral_out(r) for r in rows]


def source_overview(db: Session, referral: Referral) -> list[dict]:
    """Every institution and where this patient stands with it: own record, linked
    (and whether it was used or skipped), link requested, or not linked."""
    latest = retrieval.latest_by_source(db, referral)
    linked = {t[0]: t for t in retrieval.linked_sources(db, referral)}
    links = links_for(db, referral.patient_institution, referral.patient_local_id)
    out = []
    for inst, cfg in INSTITUTIONS.items():
        if inst == "central-platform":
            continue
        sr = latest.get(inst)
        item = {"institution_id": inst, "name": cfg["name"], "kind": cfg["kind"],
                "own": inst == referral.patient_institution, "destination": inst == referral.destination_institution,
                "latest": retrieval_out(sr) if sr else None}
        if inst in linked:
            _, local_id, link_id = linked[inst]
            item.update({"linked": True, "local_patient_id": local_id, "link_id": link_id})
        else:
            states = sorted({x.status for x in links if inst in (x.requester_institution, x.target_institution)})
            item.update({"linked": False, "link_states": states,
                         "pending_link_id": next((x.id for x in links if x.target_institution == inst
                                                  and x.status == "requested"), None)})
        out.append(item)
    return out


@router.get("/referrals/{referral_id}")
def get_referral(referral_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    from ..sending.readiness import readiness

    r = load_referral(db, referral_id, principal, "view")
    if r.status == "draft" and r.requesting_doctor_id != principal.subject and "clinician" not in principal.roles:
        raise error(404, "not_found", "Referral not found")
    audit(db, principal, "referral.view", "referral", r.reference, "success", r.id)
    packages = db.scalars(select(ReferralPackage).where(ReferralPackage.referral_id == r.id)
                          .order_by(ReferralPackage.version.desc())).all()
    dxs = db.scalars(select(DiagnosticRequest).where(DiagnosticRequest.referral_id == r.id).order_by(DiagnosticRequest.id))
    clars = db.scalars(select(Clarification).where(Clarification.referral_id == r.id).order_by(Clarification.id))
    out = {
        **referral_out(r),
        "sources": source_overview(db, r),
        "readiness": readiness(db, r) if r.status in PRE_SUBMISSION or r.amendment_open else None,
        "packages": [{"version": p.version, "sent_by": p.sent_by, "sent_at": p.sent_at, "content_hash": p.content_hash,
                      "superseded": p.superseded, "delivery_key": p.delivery_key} for p in packages],
        "links": [link_summary(x) for x in links_for(db, r.patient_institution, r.patient_local_id)],
        "diagnostics": [diagnostic_out(d) for d in dxs],
        "clarifications": [{"id": c.id, "question": c.question, "asked_by": c.asked_by, "asked_at": c.asked_at,
                            "status": c.status, "answer": c.answer, "answered_by": c.answered_by,
                            "answered_at": c.answered_at} for c in clars],
    }
    db.commit()
    return out


class ReferralUpdate(ReferralForm):
    expected_version: int
    patient_local_id: str | None = None  # the patient cannot change after creation
    submit: bool = False


@router.patch("/referrals/{referral_id}")
def update_referral(referral_id: int, body: ReferralUpdate, db: Session = Depends(get_db),
                    principal: Principal = Depends(get_principal)):
    """Doctors edit their request. After it was sent, a clinical change opens an amendment."""
    r = load_referral(db, referral_id, principal, "edit", roles=(DOCTOR,))
    check_version(r, body.expected_version)
    if r.status in CLINICAL_LOCKED:
        raise error(409, "clinical_content_locked", "This referral can no longer be changed")
    if r.kind == "test":
        raise error(409, "test_request", "Change a test request on its Tests tab")
    body.kind = r.kind
    _validate(body, principal, body.submit or r.status != "draft")
    if r.status not in PRE_SUBMISSION and body.destination_institution != r.destination_institution:
        raise error(409, "destination_locked", "The destination cannot change after the referral was sent; cancel and refer again")
    planned, tags = _procedure(body)
    changes = {}
    for field in ("source_department", "destination_department", "destination_doctor", "reason", "urgency",
                  "procedure_status", "planned_procedure", "procedure_tags", "destination_institution"):
        new = {"planned_procedure": planned, "procedure_tags": tags}.get(field, getattr(body, field))
        if isinstance(new, str):
            new = new.strip() or None
        if field == "reason":
            new = new or ""
        if new != getattr(r, field):
            changes[field] = [getattr(r, field), new]
            setattr(r, field, new)
    if changes:
        if r.status in IN_FLIGHT:
            mark_clinical_change(db, r, principal.display_name, ", ".join(changes).replace("_", " "), principal)
        else:
            bump(r)
        audit(db, principal, "referral.update", "referral", r.reference, "success", r.id, {"changes": changes})
    if body.submit and r.status == "draft":
        _submit(db, r, principal)
    elif changes:
        after_change(db, r, "referral_updated", principal)
    db.commit()
    return referral_out(r)


class VersionIn(BaseModel):
    expected_version: int


@router.post("/referrals/{referral_id}/submit")
def submit_request(referral_id: int, body: VersionIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    r = load_referral(db, referral_id, principal, "submit_request", roles=(DOCTOR,))
    check_version(r, body.expected_version)
    if r.status != "draft":
        raise error(409, "not_draft", "Only a draft request can be submitted")
    if r.kind == "referral" and len(r.reason.strip()) < 10:
        raise error(422, "reason_required", "Write the reason for referral before submitting")
    if r.kind == "test" and not db.scalars(select(DiagnosticRequest).where(DiagnosticRequest.referral_id == r.id)).first():
        raise error(422, "tests_required", "Add at least one test or scan")
    _submit(db, r, principal)
    db.commit()
    return referral_out(r)


class LinkRequestIn(BaseModel):
    target_institution: str


@router.post("/referrals/{referral_id}/links", status_code=201)
def request_referral_link(referral_id: int, body: LinkRequestIn, db: Session = Depends(get_db),
                          principal: Principal = Depends(get_principal)):
    """Staff ask another institution (where the patient has been) to confirm the patient."""
    r = load_referral(db, referral_id, principal, "link")
    if r.status in TERMINAL:
        raise error(409, "referral_closed", "This referral is closed")
    link = create_request(db, principal, local_id=r.patient_local_id, target=body.target_institution, name=r.patient_name,
                          birth_date=r.patient_birth_date, sex=r.patient_sex, cnic=r.patient_cnic, referral=r,
                          purpose=f"Records for referral {r.reference}")
    db.commit()
    return link_summary(link)


@router.post("/referrals/{referral_id}/retrieve")
def retrieve_records(referral_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    r = load_referral(db, referral_id, principal, "retrieve")
    if r.status in TERMINAL or r.status == "draft":
        raise error(409, "not_available", "Records are retrieved while the referral is being prepared")
    results = retrieval.retrieve(db, r, principal)
    if r.current_package_version and r.status in IN_FLIGHT:
        mark_clinical_change(db, r, principal.display_name, "records retrieved again", principal)
    after_change(db, r, "records_retrieved", principal)
    queued = _start_recommendation(db, r, principal)
    db.commit()
    if queued:
        enqueue("recommend_selection", r.id, principal.display_name)
    return {"results": [retrieval_out(s) for s in results], "sources": source_overview(db, r),
            "selection": {"queued": queued, "run": selection.run_out(selection.latest_run(db, r))}}


def _start_recommendation(db: Session, r: Referral, principal: Principal) -> bool:
    """With a model configured the recommendation runs in the background; without one the run is
    recorded straight away as unavailable, so the page can say so (the default selection stands)."""
    if settings.llm_configured:
        return True
    selection.recommend(db, r, principal.display_name, principal)
    return False


@router.get("/referrals/{referral_id}/selection")
def selection_status(referral_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    r = load_referral(db, referral_id, principal, "view")
    snap = selection.snapshot(db, r)
    return {"run": selection.run_out(selection.latest_run(db, r)), "counts": snap["counts"],
            "llm_configured": settings.llm_configured, "prompt_version": selection.PROMPT_VERSION}


@router.post("/referrals/{referral_id}/recommend")
def recommend_selection(referral_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """Staff ask for the AI recommendation again (for example after adding papers)."""
    r = load_referral(db, referral_id, principal, "prepare", roles=("clinic_staff",))
    if r.status in TERMINAL or r.working_set_purged_at is not None:
        raise error(409, "not_available", "This referral's records are no longer held")
    queued = _start_recommendation(db, r, principal)
    audit(db, principal, "selection.requested", "referral", r.reference, "queued" if queued else "unavailable", r.id)
    db.commit()
    if queued:
        enqueue("recommend_selection", r.id, principal.display_name)
    return {"queued": queued, "run": selection.run_out(selection.latest_run(db, r))}


@router.get("/referrals/{referral_id}/retrievals")
def retrieval_history(referral_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    r = load_referral(db, referral_id, principal, "view")
    rows = db.scalars(select(SourceRetrieval).where(SourceRetrieval.referral_id == r.id).order_by(SourceRetrieval.id.desc()))
    return [retrieval_out(s) for s in rows]


class CancelIn(BaseModel):
    expected_version: int
    reason: str = Field(min_length=3)


@router.post("/referrals/{referral_id}/cancel")
def cancel(referral_id: int, body: CancelIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """Only a doctor withdraws a request; staff cannot stop it."""
    r = load_referral(db, referral_id, principal, "cancel", roles=(DOCTOR,))
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
             "actor": e.actor, "institution_id": e.institution_id,
             "institution_name": INSTITUTIONS.get(e.institution_id or "", {}).get("name"),
             "detail": e.detail, "created_at": e.created_at} for e in rows]
