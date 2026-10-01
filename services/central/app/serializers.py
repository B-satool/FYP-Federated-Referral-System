"""Response shapes shared by the routers (published as examples in contracts/)."""
from __future__ import annotations

from .config import INSTITUTIONS, PROCEDURES
from .integration.sources import source_name
from .models import (
    Brief,
    Clarification,
    ConsultationResponse,
    Document,
    EvidenceItem,
    FollowupTask,
    Job,
    MedicationEntry,
    MedicationFlag,
    Referral,
    ReviewItem,
    SourceRetrieval,
)
from .referrals.state import STATUS_LABELS


def inst_name(i: str | None) -> str | None:
    return INSTITUTIONS.get(i or "", {}).get("name", i)


def referral_out(r: Referral) -> dict:
    return {
        "id": r.id, "reference": r.reference, "status": r.status, "status_label": STATUS_LABELS.get(r.status, r.status),
        "row_version": r.row_version,
        "patient": {"institution_id": r.patient_institution, "local_patient_id": r.patient_local_id,
                    "name": r.patient_name, "birth_date": r.patient_birth_date, "sex": r.patient_sex},
        "source_institution": r.source_institution, "source_institution_name": inst_name(r.source_institution),
        "destination_institution": r.destination_institution, "destination_name": inst_name(r.destination_institution),
        "specialty": r.specialty, "reason": r.reason, "priority": r.priority,
        "planned_procedure": r.planned_procedure, "procedure_status": r.procedure_status,
        "procedure_label": PROCEDURES.get(r.planned_procedure or "", None) if r.procedure_status == "known"
        else ("Unknown (explicitly recorded)" if r.procedure_status == "unknown" else "Not stated"),
        "created_by": r.created_by_name, "referring_clinician_id": r.referring_clinician_id,
        "referring_clinician_name": r.referring_clinician_name,
        "amendment_open": r.amendment_open, "current_package_version": r.current_package_version,
        "submitted_package_version": r.submitted_package_version, "delivery_status": r.delivery_status,
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
        "patient_ref": {"institution_id": e.patient_institution, "local_patient_id": e.patient_local_id},
    }


def retrieval_out(s: SourceRetrieval) -> dict:
    return {
        "id": s.id, "source_institution": s.source_institution, "source_name": source_name(s.source_institution),
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
        "strength": m.strength, "dose": m.dose, "route": m.route, "frequency": m.frequency,
        "start_date": m.start_date, "end_date": m.end_date, "source_status": m.source_status,
        "source_label": m.source_label, "ingredient": m.ingredient, "ingredient_code": m.ingredient_code,
        "drug_class": m.drug_class, "class_code": m.class_code, "mapping_source": m.mapping_source,
        "mapping_version": m.mapping_version, "mapping_status": m.mapping_status, "mapping_note": m.mapping_note,
        "use_status": m.use_status, "use_verified_by": m.use_verified_by, "use_verified_at": m.use_verified_at,
        "use_note": m.use_note,
    }


def flag_out(f: MedicationFlag, reviews: list | None = None) -> dict:
    return {
        "id": f.id, "flag_key": f.flag_key, "version": f.version, "kind": f.kind, "title": f.title,
        "message": f.message, "medication": f.medication, "drug_class": f.drug_class,
        "current_use_status": f.current_use_status, "source_label": f.source_label, "rule_id": f.rule_id,
        "rule_version": f.rule_version, "evidence_ids": f.evidence_ids, "status": f.status, "created_at": f.created_at,
        "superseded_at": f.superseded_at,
        "reviews": [{"id": r.id, "side": r.side, "action": r.action, "reviewer": r.reviewer,
                     "institution_id": r.institution_id, "flag_version": r.flag_version,
                     "package_version": r.package_version, "clarification_id": r.clarification_id,
                     "note": r.note, "created_at": r.created_at} for r in (reviews or [])],
    }


def review_item_out(r: ReviewItem) -> dict:
    return {
        "id": r.id, "item_key": r.item_key, "kind": r.kind, "checklist_item_id": r.checklist_item_id,
        "checklist_version": r.checklist_version, "title": r.title, "detail": r.detail, "evidence_ids": r.evidence_ids,
        "blocking": r.blocking, "override_allowed": r.override_allowed, "clinical": r.clinical, "status": r.status,
        "resolution": r.resolution, "resolved_by": r.resolved_by, "resolved_at": r.resolved_at,
        "created_at": r.created_at,
    }


def clarification_out(c: Clarification, referral: Referral | None = None) -> dict:
    out = {
        "id": c.id, "referral_id": c.referral_id, "review_item_id": c.review_item_id, "flag_id": c.flag_id,
        "origin": c.origin, "question": c.question, "assignee_institution": c.assignee_institution,
        "assignee_institution_name": inst_name(c.assignee_institution), "assignee_role": c.assignee_role,
        "status": c.status, "due_date": c.due_date, "created_by": c.created_by, "created_at": c.created_at,
        "response_text": c.response_text, "response_document_ids": c.response_document_ids,
        "answered_by": c.answered_by, "answered_at": c.answered_at, "resolved_by": c.resolved_by,
        "resolved_at": c.resolved_at, "resolution_note": c.resolution_note, "package_version": c.package_version,
    }
    if referral is not None:
        out["referral_reference"] = referral.reference
        out["patient_name"] = referral.patient_name if c.assignee_institution == referral.source_institution else None
    return out


def brief_out(b: Brief | None) -> dict | None:
    if b is None:
        return None
    return {"id": b.id, "version": b.version, "kind": b.kind, "sections": b.sections, "limitations": b.limitations,
            "evidence_ids": b.evidence_ids, "model": b.model, "prompt_version": b.prompt_version,
            "generation_meta": b.generation_meta, "based_on_version": b.based_on_version, "created_by": b.created_by,
            "created_at": b.created_at}


def response_out(r: ConsultationResponse) -> dict:
    return {"id": r.id, "package_version": r.package_version, "content": r.content, "specialist_name": r.specialist_name,
            "approved_at": r.approved_at, "received_at": r.received_at, "receipt_recorded_by": r.receipt_recorded_by,
            "receipt_recorded_at": r.receipt_recorded_at, "reviewed_by": r.reviewed_by, "reviewed_at": r.reviewed_at,
            "review_note": r.review_note}


def task_out(t: FollowupTask) -> dict:
    return {"id": t.id, "referral_id": t.referral_id, "description": t.description, "specified_by": t.specified_by,
            "assignee_name": t.assignee_name, "assignee_role": t.assignee_role, "due_date": t.due_date,
            "status": t.status, "outcome": t.outcome, "completed_by": t.completed_by, "completed_at": t.completed_at,
            "created_by": t.created_by, "created_at": t.created_at}
