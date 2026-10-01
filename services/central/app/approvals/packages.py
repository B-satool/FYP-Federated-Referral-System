"""Approval gates and immutable ReferralPackage versions (FR-15, FR-47, FR-48, FR-68)."""
from __future__ import annotations

from refcommon import fhir
from refcommon.auth import Principal
from refcommon.db import utcnow
from refcommon.exchange import PackageEnvelope, package_hash
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import INSTITUTIONS, PROCEDURES
from ..generation.brief import latest_brief, permitted_evidence, system_limitations
from ..identity.links import verified_counterparts
from ..integration.sources import source_name
from ..medications import service as med
from ..models import Brief, EvidenceItem, FlagReview, Outbox, Referral, ReferralPackage, ReviewItem
from ..referrals.state import IN_FLIGHT, event, transition
from ..reviews.checklist import checklist_summary
from ..security import audit, bump, error

PRIORITY_TO_FHIR = {"routine": "routine", "soon": "asap", "urgent": "urgent"}


def approval_blockers(db: Session, referral: Referral, acknowledge_evaluation_failure: bool = False) -> list[dict]:
    blockers: list[dict] = []
    for ri in db.scalars(select(ReviewItem).where(ReviewItem.referral_id == referral.id, ReviewItem.status == "open",
                                                  ReviewItem.blocking.is_(True)).order_by(ReviewItem.id)):
        blockers.append({"type": "review_item", "id": ri.id, "message": ri.title,
                         "how": "Resolve it, or record a clinician override with rationale" if ri.override_allowed
                         else "Provide the missing information"})
    if latest_brief(db, referral.id) is None:
        blockers.append({"type": "brief", "message": "No referral brief yet", "how": "Generate, use the template, or write it manually"})
    run = med.latest_run(db, referral.id)
    if run is None:
        blockers.append({"type": "medication_evaluation", "message": "Medication rules have not been evaluated",
                         "how": "Run medication evaluation"})
    elif run.status == "failed" and not acknowledge_evaluation_failure:
        blockers.append({"type": "medication_evaluation_failed", "message": "Medication rule evaluation failed",
                         "how": "Re-run evaluation, or confirm a manual clinician medication review at approval"})
    for f in med.unreviewed_flags(db, referral.id):
        blockers.append({"type": "flag_review", "id": f.id, "message": f"Medication flag not reviewed: {f.title}",
                         "how": "Mark the flag Reviewed (or request clarification and resolve it)"})
    return blockers


def _evidence_snapshot(ev: EvidenceItem) -> dict:
    return {
        "evidence_id": ev.id, "category": ev.category, "display": ev.display, "original": ev.current or ev.original,
        "origin": ev.origin, "source_institution": ev.source_institution, "source_record_type": ev.source_record_type,
        "source_record_id": ev.source_record_id, "source_record_version": ev.source_record_version,
        "clinical_time": ev.clinical_time.isoformat() if ev.clinical_time else None,
        "verification_status": "unresolved" if ev.review_state == "unresolved" else ev.verification_status,
        "document_ref": {"document_id": ev.document_id, "page": ev.page, "source_text": ev.source_text}
        if ev.origin == "document" else None,
    }


def _flag_snapshot(db: Session, f) -> dict:
    review = med.referring_review(db, f)
    return {
        "flag_id": f.id, "version": f.version, "kind": f.kind, "title": f.title, "message": f.message,
        "medication": f.medication, "drug_class": f.drug_class, "current_use_status": f.current_use_status,
        "source_label": f.source_label, "rule_id": f.rule_id, "rule_version": f.rule_version,
        "evidence_ids": f.evidence_ids,
        "clinic_review": {"reviewer": review.reviewer, "reviewed_at": review.created_at.isoformat()} if review else None,
    }


def _fhir_bundle(referral: Referral, brief: Brief, evidence: list[EvidenceItem], approved_at, approver: str) -> dict:
    subject = fhir.patient_reference(referral.patient_institution, referral.patient_local_id)
    resources: list[dict] = [{
        "resourceType": "Patient", "id": referral.patient_local_id,
        "identifier": [fhir.patient_identifier(referral.patient_institution, referral.patient_local_id)],
        "name": [{"text": referral.patient_name}],
        **({"birthDate": referral.patient_birth_date} if referral.patient_birth_date else {}),
    }]
    sr = {
        "resourceType": "ServiceRequest", "id": f"{referral.reference}",
        "identifier": [{"system": "urn:referral-demo:referral-id", "value": referral.reference}],
        "status": fhir.REFERRAL_STATUS_TO_SERVICE_REQUEST["approved"], "intent": "order",
        "category": [{"text": "Referral"}],
        "priority": PRIORITY_TO_FHIR.get(referral.priority or "routine", "routine"),
        "code": {"text": "Referral to orthodontics" + (
            f" - {PROCEDURES.get(referral.planned_procedure, referral.planned_procedure)}"
            if referral.procedure_status == "known" and referral.planned_procedure else "")},
        "subject": subject,
        "authoredOn": approved_at.isoformat(),
        "requester": {"display": approver},
        "performer": [{"display": INSTITUTIONS.get(referral.destination_institution, {}).get("name", referral.destination_institution)}],
        "reasonCode": [{"text": referral.reason}],
        "supportingInfo": [{"reference": f"{e.source_record_type}/{e.source_record_id}"} for e in evidence
                           if e.origin == "source" and e.fhir],
    }
    task = {
        "resourceType": "Task", "id": f"{referral.reference}-task", "status": "requested", "intent": "order",
        "focus": {"reference": f"ServiceRequest/{referral.reference}"},
        "for": subject, "authoredOn": approved_at.isoformat(),
        "owner": {"display": INSTITUTIONS.get(referral.destination_institution, {}).get("name", referral.destination_institution)},
    }
    resources += [sr, task]
    seen = set()
    for e in evidence:
        if e.origin == "source" and e.fhir and e.fhir.get("resourceType") != "Patient":
            key = (e.fhir["resourceType"], e.fhir["id"])
            if key not in seen:
                seen.add(key)
                resources.append(e.fhir)
    return fhir.bundle(resources, "collection", bundle_id=f"{referral.reference}-bundle")


def build_envelope(db: Session, referral: Referral, principal: Principal, version: int, overrides: list[dict]) -> dict:
    brief = latest_brief(db, referral.id)
    approved_at = utcnow()
    evidence = permitted_evidence(db, referral)
    flags = med.active_flags(db, referral.id)
    ev_ids = {e.id for e in evidence}
    extra_ids = set()
    for sec in brief.sections:
        for st in sec["statements"]:
            extra_ids |= set(st.get("evidence_ids", []))
    for f in flags:
        extra_ids |= set(f.evidence_ids)
    missing = extra_ids - ev_ids
    if missing:
        evidence += list(db.scalars(select(EvidenceItem).where(EvidenceItem.id.in_(missing))))
    run = med.latest_run(db, referral.id)
    links = verified_counterparts(db, referral.patient_institution, referral.patient_local_id)
    limitations = list(dict.fromkeys(system_limitations(db, referral) + list(brief.limitations or [])))
    for o in overrides:
        limitations.append(f"Clinician override: {o['message']} - {o['rationale']}")
    for ri in db.scalars(select(ReviewItem).where(ReviewItem.referral_id == referral.id,
                                                  ReviewItem.status.in_(["not_applicable", "overridden", "uncertainty_recorded"]))):
        limitations.append(f"{ri.title}: {ri.status.replace('_', ' ')} by {ri.resolved_by} - {ri.resolution}")
    env = PackageEnvelope(
        delivery_key=f"{referral.source_institution}:{referral.reference}:v{version}",
        referral_id=referral.reference, package_version=version,
        sender_institution=referral.source_institution, destination_institution=referral.destination_institution,
        specialty=referral.specialty, priority=referral.priority or "routine", reason=referral.reason,
        planned_procedure=referral.planned_procedure if referral.procedure_status == "known" else None,
        procedure_known=referral.procedure_status == "known",
        patient={"name": referral.patient_name, "birth_date": referral.patient_birth_date, "sex": referral.patient_sex,
                 "identifier": {"institution_id": referral.patient_institution, "local_patient_id": referral.patient_local_id},
                 "verified_links": [{"institution_id": inst, "local_patient_id": lid} for inst, (lid, _) in sorted(links.items())]},
        referring_clinician={"name": referral.referring_clinician_name, "id": referral.referring_clinician_id,
                             "institution": source_name(referral.source_institution)},
        brief_sections=brief.sections, medication_flags=[_flag_snapshot(db, f) for f in flags],
        medication_evaluation={"status": run.status if run else "not_run", "outcome": run.outcome if run else None,
                               "summary": run.summary_message if run else None,
                               "rule_versions": run.rule_versions if run else {},
                               "mapping_version": run.mapping_version if run else None,
                               "evaluated_at": run.created_at.isoformat() if run else None},
        evidence=[_evidence_snapshot(e) for e in sorted(evidence, key=lambda e: e.id)],
        limitations=limitations, checklist=checklist_summary(db, referral),
        approved_by=principal.display_name, approved_by_id=principal.subject, approved_at=approved_at,
        content_hash="", fhir_bundle=_fhir_bundle(referral, brief, evidence, approved_at, principal.display_name),
        supersedes_version=referral.current_package_version,
    )
    dumped = env.model_dump(mode="json")
    dumped["content_hash"] = package_hash(dumped)
    return dumped


def approve(db: Session, referral: Referral, principal: Principal, acknowledge_evaluation_failure: bool,
            manual_review_note: str | None) -> ReferralPackage:
    amendment = referral.amendment_open and referral.status in IN_FLIGHT
    if referral.status != "awaiting_approval" and not amendment:
        raise error(409, "not_ready_for_approval",
                    "Only a referral awaiting approval (or an open amendment) can be approved")
    blockers = approval_blockers(db, referral, acknowledge_evaluation_failure)
    if blockers:
        raise error(409, "approval_blocked", "Approval is blocked by outstanding items", blockers=blockers)
    overrides = []
    run = med.latest_run(db, referral.id)
    if run and run.status == "failed":
        if not (manual_review_note or "").strip():
            raise error(422, "manual_review_note_required", "Describe the manual medication review performed")
        overrides.append({"type": "medication_evaluation_failed", "message": "Medication rule evaluation failed",
                          "rationale": manual_review_note.strip(), "by": principal.display_name})
    if not referral.referring_clinician_id:
        referral.referring_clinician_id = principal.subject
        referral.referring_clinician_name = principal.display_name
    version = (db.scalar(select(func.max(ReferralPackage.version)).where(ReferralPackage.referral_id == referral.id)) or 0) + 1
    envelope = build_envelope(db, referral, principal, version, overrides)
    for old in db.scalars(select(ReferralPackage).where(ReferralPackage.referral_id == referral.id,
                                                        ReferralPackage.superseded.is_(False))):
        old.superseded = True
    brief = latest_brief(db, referral.id)
    pkg = ReferralPackage(referral_id=referral.id, version=version, brief_id=brief.id, envelope=envelope,
                          content_hash=envelope["content_hash"], delivery_key=envelope["delivery_key"],
                          approved_by=principal.display_name, approved_by_id=principal.subject,
                          approved_at=utcnow(), overrides=overrides)
    db.add(pkg)
    referral.current_package_version = version
    if amendment:
        bump(referral)
        event(db, referral, "amendment_approved", principal.display_name, principal.institution_id, {"version": version})
    else:
        transition(db, referral, "approved", principal.display_name, principal, {"package_version": version})
    audit(db, principal, "referral.approve", "referral_package", f"{referral.reference}v{version}", "success", referral.id,
          {"content_hash": pkg.content_hash, "overrides": overrides})
    return pkg


def schedule_send(db: Session, referral: Referral, principal: Principal) -> Outbox:
    """Persist the outbox record in the same transaction as the decision to send."""
    if not referral.current_package_version:
        raise error(409, "not_approved", "Only an approved referral version can be submitted (FR-48)")
    pkg = db.scalars(select(ReferralPackage).where(ReferralPackage.referral_id == referral.id,
                                                   ReferralPackage.version == referral.current_package_version)).one()
    if pkg.superseded:
        raise error(409, "not_approved", "The approved version was superseded by later changes; approve again")
    if referral.status not in ("approved",) and not (referral.amendment_open and referral.status in IN_FLIGHT):
        if referral.submitted_package_version == pkg.version:
            raise error(409, "already_submitted", "This version has already been delivered")
        raise error(409, "not_approved", "Only an approved referral version can be submitted (FR-48)")
    box = db.scalars(select(Outbox).where(Outbox.message_key == pkg.delivery_key)).first()
    if box is None:
        box = Outbox(referral_id=referral.id, kind="deliver_package", message_key=pkg.delivery_key, payload=pkg.envelope)
        db.add(box)
    elif box.status == "failed":
        box.status, box.attempts, box.next_attempt_at = "pending", 0, utcnow()
    referral.delivery_status = "pending"
    event(db, referral, "send_scheduled", principal.display_name, principal.institution_id,
          {"version": pkg.version, "delivery_key": pkg.delivery_key})
    audit(db, principal, "referral.submit", "referral_package", f"{referral.reference}v{pkg.version}", "success", referral.id)
    return box


def flag_reviews(db: Session, referral_id: int) -> list[FlagReview]:
    return list(db.scalars(select(FlagReview).where(FlagReview.referral_id == referral_id).order_by(FlagReview.id)))
