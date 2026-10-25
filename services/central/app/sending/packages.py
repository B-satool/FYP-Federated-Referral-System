"""Building and sending one version of a referral (immutable, hashed)."""
from __future__ import annotations

from refcommon import fhir
from refcommon.auth import Principal
from refcommon.db import utcnow
from refcommon.exchange import PackageEnvelope, package_hash
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import INSTITUTIONS, department_name, institution_name, procedure_label
from ..identity.links import verified_counterparts
from ..medications import service as med
from ..models import Brief, DiagnosticRequest, EvidenceItem, MedicationEntry, Outbox, Referral, ReferralPackage
from ..referrals.state import IN_FLIGHT, event
from ..security import audit, bump, error
from . import brief as brief_mod
from .readiness import blocking, readiness

URGENCY_TO_FHIR = {"routine": "routine", "soon": "urgent", "urgent": "asap"}


def _evidence_snapshot(db: Session, ev: EvidenceItem) -> dict:
    also = []
    if ev.category == "medication":
        entry = db.scalars(select(MedicationEntry).where(MedicationEntry.evidence_id == ev.id)).first()
        if entry and entry.duplicate_of:
            rep = db.get(MedicationEntry, entry.duplicate_of)
            also = [rep.source_label] if rep else []
    return {
        "evidence_id": ev.id, "category": ev.category, "display": ev.display, "original": ev.current or ev.original,
        "origin": ev.origin, "source_institution": ev.source_institution, "source_record_type": ev.source_record_type,
        "source_record_id": ev.source_record_id, "source_record_version": ev.source_record_version,
        "clinical_time": ev.clinical_time.isoformat() if ev.clinical_time else None,
        "verification_status": ev.verification_status,
        "document_ref": {"document_id": ev.document_id, "page": ev.page, "source_text": ev.source_text}
        if ev.origin == "document" else None,
        "also_recorded_in": also,
    }


def _flag_snapshot(db: Session, f) -> dict:
    ack = med.acknowledgement(db, f)
    return {"flag_id": f.id, "version": f.version, "kind": f.kind, "title": f.title, "message": f.message,
            "medication": f.medication, "drug_class": f.drug_class, "source_label": f.source_label,
            "rule_id": f.rule_id, "rule_version": f.rule_version, "evidence_ids": f.evidence_ids,
            "acknowledged": {"by": ack.reviewer, "at": ack.created_at.isoformat()} if ack else None}


def _fhir_bundle(r: Referral, evidence: list[EvidenceItem], sent_at, requester: str) -> dict:
    subject = fhir.patient_reference(r.patient_institution, r.patient_local_id)
    origin = {"source": f"urn:referral-demo:institution:{r.source_institution}"}
    dest = INSTITUTIONS[r.destination_institution]["name"]
    patient = {"resourceType": "Patient", "id": r.patient_local_id, "meta": dict(origin),
               "identifier": [fhir.patient_identifier(r.patient_institution, r.patient_local_id)],
               "name": [{"text": r.patient_name}], **({"birthDate": r.patient_birth_date} if r.patient_birth_date else {})}
    sr = {"resourceType": "ServiceRequest", "id": r.reference, "meta": dict(origin),
          "identifier": [{"system": "urn:referral-demo:referral-id", "value": r.reference}],
          "status": fhir.REFERRAL_STATUS_TO_SERVICE_REQUEST["submitted"], "intent": "order",
          "category": [{"text": "Referral"}], "priority": URGENCY_TO_FHIR.get(r.urgency, "routine"),
          "code": {"text": f"Referral to {department_name(r.destination_department)}"
                           + (f" - {procedure_label(r.procedure_status, r.planned_procedure, r.procedure_other)}"
                              if r.procedure_status in ("known", "other") else "")},
          "subject": subject, "authoredOn": sent_at.isoformat(), "requester": {"display": requester},
          "performer": [{"display": f"{dest}, {department_name(r.destination_department)}"
                                    + (f", {r.destination_doctor}" if r.destination_doctor else "")}],
          "reasonCode": [{"text": r.reason}],
          "supportingInfo": [{"reference": fhir.full_url(e.fhir, e.source_institution)} for e in evidence
                             if e.origin == "source" and e.fhir]}
    task = {"resourceType": "Task", "id": f"{r.reference}-task", "meta": dict(origin), "status": "requested",
            "intent": "order", "focus": {"reference": f"ServiceRequest/{r.reference}"}, "for": subject,
            "authoredOn": sent_at.isoformat(), "owner": {"display": dest}}
    resources = [patient, sr, task]
    seen = set()
    for e in evidence:
        if e.origin == "source" and e.fhir and e.fhir.get("resourceType") != "Patient":
            key = (e.fhir["resourceType"], e.fhir["id"], e.source_institution)
            if key not in seen:
                seen.add(key)
                resources.append(e.fhir)
    return fhir.bundle(resources, "collection", bundle_id=f"{r.reference}-bundle", institution_id=r.source_institution)


def send(db: Session, r: Referral, principal: Principal) -> ReferralPackage:
    """Staff send after checking. Builds the brief and an immutable, hashed version and
    writes the outbox record in the same transaction."""
    amendment = r.amendment_open and r.status in IN_FLIGHT
    if r.status != "requested" and not amendment:
        raise error(409, "not_ready", "Only a referral being prepared (or an open amendment) can be sent")
    missing = blocking(readiness(db, r))
    if missing:
        raise error(409, "not_ready", "Some things still need to be done before sending", blockers=missing)
    content = brief_mod.build(db, r)
    version = (db.scalar(select(func.max(ReferralPackage.version)).where(ReferralPackage.referral_id == r.id)) or 0) + 1
    b = Brief(referral_id=r.id, version=version, kind="template", sections=content["sections"],
              limitations=content["limitations"], evidence_ids=content["evidence_ids"], created_by=principal.display_name)
    db.add(b)
    db.flush()
    sent_at = utcnow()
    evidence = brief_mod.permitted_evidence(db, r)
    flags = med.active_flags(db, r.id)
    have = {e.id for e in evidence}
    extra = (set(content["evidence_ids"]) | {i for f in flags for i in f.evidence_ids}) - have
    if extra:
        evidence += list(db.scalars(select(EvidenceItem).where(EvidenceItem.id.in_(extra))))
    run = med.latest_run(db, r.id)
    links = verified_counterparts(db, r.patient_institution, r.patient_local_id)
    dxs = db.scalars(select(DiagnosticRequest).where(DiagnosticRequest.referral_id == r.id,
                                                      DiagnosticRequest.status != "cancelled"))
    env = PackageEnvelope(
        delivery_key=f"{r.source_institution}:{r.reference}:v{version}", referral_id=r.reference, package_version=version,
        sender_institution=r.source_institution, sender_department=r.source_department,
        destination_institution=r.destination_institution, destination_department=r.destination_department,
        destination_doctor=r.destination_doctor, urgency=r.urgency, reason=r.reason, procedure_status=r.procedure_status,
        planned_procedure=r.planned_procedure, procedure_label=procedure_label(r.procedure_status, r.planned_procedure,
                                                                               r.procedure_other),
        patient={"name": r.patient_name, "birth_date": r.patient_birth_date, "sex": r.patient_sex,
                 "identifier": {"institution_id": r.patient_institution, "local_patient_id": r.patient_local_id},
                 "verified_links": [{"institution_id": i, "local_patient_id": lid} for i, (lid, _) in sorted(links.items())]},
        requesting_doctor={"name": r.requesting_doctor_name, "id": r.requesting_doctor_id,
                           "institution": institution_name(r.source_institution),
                           "department": department_name(r.source_department),
                           "requested_at": r.requested_at.isoformat() if r.requested_at else None},
        brief_sections=content["sections"], medication_flags=[_flag_snapshot(db, f) for f in flags],
        medication_evaluation={"status": run.status if run else "not_run", "outcome": run.outcome if run else None,
                               "summary": run.summary_message if run else None,
                               "rule_versions": run.rule_versions if run else {},
                               "evaluated_at": run.created_at.isoformat() if run else None},
        evidence=[_evidence_snapshot(db, e) for e in sorted(evidence, key=lambda e: e.id)],
        limitations=content["limitations"],
        diagnostic_requests=[{"reference": d.reference, "category": d.category, "test": d.test, "body_area": d.body_area,
                              "clinical_question": d.clinical_question, "status": d.status,
                              "where": f"{institution_name(d.destination_institution)}, {department_name(d.destination_department)}"}
                             for d in dxs],
        sent_by=principal.display_name, sent_by_id=principal.subject, sent_at=sent_at, content_hash="",
        fhir_bundle=_fhir_bundle(r, evidence, sent_at, r.requesting_doctor_name),
        supersedes_version=r.current_package_version,
    )
    dumped = env.model_dump(mode="json")
    dumped["content_hash"] = package_hash(dumped)
    for old in db.scalars(select(ReferralPackage).where(ReferralPackage.referral_id == r.id,
                                                        ReferralPackage.superseded.is_(False))):
        old.superseded = True
    pkg = ReferralPackage(referral_id=r.id, version=version, brief_id=b.id, envelope=dumped,
                          content_hash=dumped["content_hash"], delivery_key=dumped["delivery_key"],
                          sent_by=principal.display_name, sent_by_id=principal.subject, sent_at=sent_at)
    db.add(pkg)
    r.current_package_version = version
    db.add(Outbox(referral_id=r.id, kind="deliver_package", target_institution=r.destination_institution,
                  message_key=pkg.delivery_key, payload=dumped))
    r.delivery_status = "pending"
    bump(r)
    event(db, r, "send_scheduled", principal.display_name, principal.institution_id,
          {"version": version, "delivery_key": pkg.delivery_key, "amendment": amendment})
    audit(db, principal, "referral.send", "referral_package", f"{r.reference}v{version}", "success", r.id,
          {"content_hash": pkg.content_hash, "amendment": amendment})
    return pkg


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
