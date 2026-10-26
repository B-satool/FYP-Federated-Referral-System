"""Response shapes shared by the routers."""
from __future__ import annotations

from .config import (DIAGNOSTIC_CATEGORIES, DRUG_CLASSES, PROCEDURE_TAGS, URGENCIES, department_name, institution_name,
                     procedure_label)
from .integration.sources import source_name
from .models import (
    ConsultationResponse,
    DiagnosticRequest,
    Document,
    EvidenceItem,
    FollowupTask,
    Job,
    MedicationEntry,
    MedicationFlag,
    PatientLink,
    Referral,
    SourceRetrieval,
)
from .referrals.state import status_label


def referral_out(r: Referral) -> dict:
    return {
        "id": r.id, "reference": r.reference, "kind": r.kind, "status": r.status, "status_label": status_label(r),
        "row_version": r.row_version, "prepared_by": r.prepared_by, "prepared_at": r.prepared_at,
        "patient": {"institution_id": r.patient_institution, "local_patient_id": r.patient_local_id,
                    "name": r.patient_name, "birth_date": r.patient_birth_date, "sex": r.patient_sex, "cnic": r.patient_cnic},
        "source_institution": r.source_institution, "source_institution_name": institution_name(r.source_institution),
        "source_department": r.source_department, "source_department_name": department_name(r.source_department),
        "requesting_doctor_id": r.requesting_doctor_id, "requesting_doctor_name": r.requesting_doctor_name,
        "destination_institution": r.destination_institution, "destination_name": institution_name(r.destination_institution),
        "destination_department": r.destination_department,
        "destination_department_name": department_name(r.destination_department),
        "destination_doctor": r.destination_doctor, "reason": r.reason, "urgency": r.urgency,
        "urgency_label": URGENCIES.get(r.urgency, {}).get("label", r.urgency),
        "urgency_detail": URGENCIES.get(r.urgency, {}).get("detail"),
        "procedure_status": r.procedure_status, "planned_procedure": r.planned_procedure,
        "procedure_tags": r.procedure_tags or [],
        "procedure_tag_labels": [PROCEDURE_TAGS.get(t, t) for t in r.procedure_tags or []],
        "procedure_label": procedure_label(r.procedure_status, r.planned_procedure),
        "requested_at": r.requested_at, "created_by": r.created_by_name,
        "amendment_open": r.amendment_open, "current_package_version": r.current_package_version,
        "submitted_package_version": r.submitted_package_version, "delivery_status": r.delivery_status,
        "meds_checked_by": r.meds_checked_by, "meds_checked_at": r.meds_checked_at,
        "patient_informed_by": r.patient_informed_by, "patient_informed_at": r.patient_informed_at,
        "patient_informed_note": r.patient_informed_note,
        "cancel_reason": r.cancel_reason, "decline_reason": r.decline_reason,
        "acknowledged_at": r.acknowledged_at, "accepted_at": r.accepted_at,
        "closed_at": r.closed_at, "closed_by": r.closed_by, "created_at": r.created_at, "updated_at": r.updated_at,
    }


def evidence_out(e: EvidenceItem) -> dict:
    revoked = e.verification_status == "access_revoked"
    return {
        "id": e.id, "origin": e.origin, "category": e.category,
        "display": "[withheld - source access revoked]" if revoked else e.display,
        "original": {} if revoked else e.original, "current": {} if revoked else e.current,
        "source_institution": e.source_institution, "source_name": source_name(e.source_institution),
        "source_record_type": e.source_record_type, "source_record_id": e.source_record_id,
        "source_record_version": e.source_record_version, "link_id": e.link_id,
        "clinical_time": e.clinical_time, "retrieved_at": e.retrieved_at, "document_id": e.document_id,
        "page": e.page, "region": e.region, "source_text": None if revoked else e.source_text,
        "confidence": e.confidence, "review_state": e.review_state, "verification_status": e.verification_status,
        "verified_by": e.verified_by, "verified_at": e.verified_at, "selected": e.selected,
        "superseded_by": e.superseded_by, "author": e.author, "row_version": e.row_version,
    }


def retrieval_out(s: SourceRetrieval) -> dict:
    return {
        "id": s.id, "source_institution": s.source_institution, "source_name": source_name(s.source_institution),
        "institution_kind": s.institution_kind, "last_activity": s.last_activity, "window_start": s.window_start,
        "local_patient_id": s.local_patient_id, "link_id": s.link_id, "status": s.status,
        "record_count": s.record_count, "new_count": s.new_count, "duplicate_count": s.duplicate_count,
        "invalid_count": s.invalid_count, "withheld": s.withheld, "message": s.message, "retryable": s.retryable,
        "attempts": s.attempts, "duration_ms": s.duration_ms, "requested_by": s.requested_by,
        "requested_at": s.requested_at,
    }


def document_out(d: Document) -> dict:
    return {
        "id": d.id, "referral_id": d.referral_id, "original_filename": d.original_filename, "doc_type": d.doc_type,
        "declared_type": d.declared_type, "detected_type": d.detected_type, "size_bytes": d.size_bytes,
        "page_count": d.page_count, "status": d.status, "error": d.error, "uploaded_by": d.uploaded_by,
        "created_at": d.created_at, "deleted": d.deleted_at is not None,
    }


def job_out(j: Job) -> dict:
    return {"id": j.id, "kind": j.kind, "status": j.status, "referral_id": j.referral_id, "document_id": j.document_id,
            "result": j.result, "error": j.error, "attempts": j.attempts, "created_by": j.created_by,
            "created_at": j.created_at, "started_at": j.started_at, "finished_at": j.finished_at}


def medication_out(m: MedicationEntry) -> dict:
    return {
        "id": m.id, "evidence_id": m.evidence_id, "record_kind": m.record_kind, "original_name": m.original_name,
        "brand": m.brand, "strength": m.strength, "dose": m.dose, "route": m.route, "frequency": m.frequency,
        "start_date": m.start_date, "over_the_counter": m.over_the_counter, "source_label": m.source_label,
        "ingredient": m.ingredient, "drug_class": m.drug_class,
        "drug_class_label": DRUG_CLASSES.get(m.drug_class or "", m.drug_class),
        "mapping_status": m.mapping_status, "mapping_note": m.mapping_note, "duplicate_of": m.duplicate_of,
        "dose_differs": m.dose_differs, "excluded": m.excluded, "excluded_by": m.excluded_by,
        "excluded_reason": m.excluded_reason,
    }


def flag_out(f: MedicationFlag, acks: list | None = None) -> dict:
    return {
        "id": f.id, "flag_key": f.flag_key, "version": f.version, "kind": f.kind, "title": f.title,
        "message": f.message, "medication": f.medication, "drug_class": f.drug_class,
        "drug_class_label": DRUG_CLASSES.get(f.drug_class or "", f.drug_class), "source_label": f.source_label,
        "rule_id": f.rule_id, "rule_version": f.rule_version, "evidence_ids": f.evidence_ids, "status": f.status,
        "created_at": f.created_at, "superseded_at": f.superseded_at,
        "acknowledgements": [{"id": a.id, "side": a.side, "by": a.reviewer, "institution_id": a.institution_id,
                              "flag_version": a.flag_version, "note": a.note, "created_at": a.created_at}
                             for a in (acks or [])],
    }


def response_out(r: ConsultationResponse) -> dict:
    return {"id": r.id, "package_version": r.package_version, "content": r.content, "specialist_name": r.specialist_name,
            "returned_at": r.returned_at, "received_at": r.received_at, "reviewed_by": r.reviewed_by,
            "reviewed_at": r.reviewed_at, "review_note": r.review_note}


def task_out(t: FollowupTask) -> dict:
    return {"id": t.id, "referral_id": t.referral_id, "description": t.description, "specified_by": t.specified_by,
            "assignee_name": t.assignee_name, "due_date": t.due_date, "status": t.status, "outcome": t.outcome,
            "completed_by": t.completed_by, "completed_at": t.completed_at, "created_by": t.created_by,
            "created_at": t.created_at}


def diagnostic_out(d: DiagnosticRequest) -> dict:
    return {"id": d.id, "reference": d.reference, "referral_id": d.referral_id, "category": d.category,
            "category_label": DIAGNOSTIC_CATEGORIES.get(d.category, d.category), "test": d.test, "body_area": d.body_area,
            "clinical_question": d.clinical_question, "urgency": d.urgency,
            "urgency_label": URGENCIES.get(d.urgency, {}).get("label", d.urgency),
            "destination_institution": d.destination_institution,
            "destination_name": institution_name(d.destination_institution),
            "destination_department": d.destination_department,
            "destination_department_name": department_name(d.destination_department), "status": d.status,
            "requested_by": d.requested_by, "sent_by": d.sent_by, "sent_at": d.sent_at, "reject_reason": d.reject_reason,
            "scheduled_for": d.scheduled_for, "report": d.report, "local_patient_id": d.local_patient_id,
            "attachments": [{k: v for k, v in a.items() if k != "storage_key"} for a in d.attachments or []],
            "seen_by": d.seen_by, "seen_at": d.seen_at,
            "history": d.history, "created_at": d.created_at, "updated_at": d.updated_at}


def link_summary(link: PatientLink) -> dict:
    from .identity.links import link_out

    return link_out(link)
