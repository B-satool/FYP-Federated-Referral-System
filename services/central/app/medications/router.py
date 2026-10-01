"""Medication list, current-use verification, flags and flag review; rule governance."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from refcommon.auth import Principal
from refcommon.db import utcnow
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Clarification, FlagReview, MedicationEntry, MedicationFlag, Referral, RuleApproval
from ..referrals.state import CLINICAL_LOCKED, TERMINAL, ensure_clinical_edit_allowed
from ..reviews.checklist import refresh
from ..security import audit, error, get_principal, load_referral, require_roles
from ..serializers import flag_out, medication_out
from ..workflow import after_change
from . import mapping, rules, service

router = APIRouter(tags=["medications"])
USE_STATUSES = ("confirmed_current", "historical_stopped", "uncertain", "conflicting", "unverified")


def _reviews(db: Session, flag_id: int) -> list[FlagReview]:
    return list(db.scalars(select(FlagReview).where(FlagReview.flag_id == flag_id).order_by(FlagReview.id)))


@router.get("/referrals/{referral_id}/medications")
def medications(referral_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    r = load_referral(db, referral_id, principal, "view")
    run = service.latest_run(db, r.id)
    flags = db.scalars(select(MedicationFlag).where(MedicationFlag.referral_id == r.id)
                       .order_by(MedicationFlag.flag_key, MedicationFlag.version.desc())).all()
    return {
        "entries": [medication_out(m) for m in service.current_entries(db, r.id)],
        "evaluation": None if run is None else {
            "id": run.id, "status": run.status, "outcome": run.outcome, "summary_message": run.summary_message,
            "trigger": run.trigger, "rule_versions": run.rule_versions, "mapping_version": run.mapping_version,
            "context": run.context, "error": run.error, "changed_flags": run.changed_flags, "created_at": run.created_at,
        },
        "flags": [flag_out(f, _reviews(db, f.id)) for f in flags if f.status == "active"],
        "flag_history": [flag_out(f, _reviews(db, f.id)) for f in flags if f.status != "active"],
    }


class UseIn(BaseModel):
    use_status: Literal["confirmed_current", "historical_stopped", "uncertain", "conflicting", "unverified"]
    note: str = ""


@router.post("/referrals/{referral_id}/medications/{entry_id}/use")
def set_use(referral_id: int, entry_id: int, body: UseIn, db: Session = Depends(get_db),
            principal: Principal = Depends(get_principal)):
    """Clinician confirms current use separately from prescriptions (FR-30, FR-63)."""
    r = load_referral(db, referral_id, principal, "verify_medication", roles=("clinician",))
    ensure_clinical_edit_allowed(r)
    m = db.get(MedicationEntry, entry_id)
    if m is None or m.referral_id != r.id:
        raise error(404, "not_found", "Medication entry not found")
    prior = m.use_status
    m.use_status, m.use_note = body.use_status, body.note or None
    m.use_verified_by, m.use_verified_at = principal.display_name, utcnow()
    audit(db, principal, "medication.use_status", "medication_entry", m.id, "success", r.id,
          {"from": prior, "to": body.use_status, "medication": m.original_name, "note": body.note})
    after_change(db, r, "medication_use_changed", principal)
    db.commit()
    return medication_out(m)


class MapIn(BaseModel):
    ingredient: str
    note: str = Field(min_length=3)


@router.post("/referrals/{referral_id}/medications/{entry_id}/mapping")
def set_mapping(referral_id: int, entry_id: int, body: MapIn, db: Session = Depends(get_db),
                principal: Principal = Depends(get_principal)):
    """Clinician resolves an ambiguous/unmapped entry by choosing a REVIEWED dictionary entry."""
    r = load_referral(db, referral_id, principal, "map_medication", roles=("clinician",))
    ensure_clinical_edit_allowed(r)
    m = db.get(MedicationEntry, entry_id)
    if m is None or m.referral_id != r.id:
        raise error(404, "not_found", "Medication entry not found")
    entry = next((e for e in mapping.reviewed_entries() if e["ingredient"] == body.ingredient), None)
    if entry is None:
        raise error(422, "unknown_ingredient", "Choose an ingredient from the reviewed mapping list")
    prior = {"status": m.mapping_status, "ingredient": m.ingredient, "class": m.drug_class}
    src, ver = mapping.source_label()
    m.mapping_status = "clinician_mapped"
    m.ingredient, m.ingredient_code = entry["ingredient"], entry.get("rxcui")
    m.drug_class, m.class_code = entry["class"], entry.get("class_code")
    m.mapping_source, m.mapping_version = f"{src} (clinician selection)", ver
    m.mapping_note = f"{principal.display_name}: {body.note}"
    audit(db, principal, "medication.mapping", "medication_entry", m.id, "success", r.id,
          {"from": prior, "to": entry["ingredient"], "original_name": m.original_name, "note": body.note})
    after_change(db, r, "medication_mapping_changed", principal)
    db.commit()
    return medication_out(m)


@router.post("/referrals/{referral_id}/medications/evaluate")
def evaluate(referral_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    r = load_referral(db, referral_id, principal, "evaluate")
    if r.status in CLINICAL_LOCKED:
        raise error(409, "clinical_content_locked", "Referral is past the point where flags can change")
    run = service.reevaluate(db, r, "manual_rerun", principal.display_name, principal)
    refresh(db, r)
    db.commit()
    return {"run_id": run.id, "status": run.status, "outcome": run.outcome, "summary_message": run.summary_message}


class FlagReviewIn(BaseModel):
    action: Literal["reviewed", "request_clarification"]
    flag_version: int
    note: str = ""
    question: str | None = None
    assignee_institution: str | None = None


@router.post("/referrals/{referral_id}/flags/{flag_id}/review")
def review_flag(referral_id: int, flag_id: int, body: FlagReviewIn, db: Session = Depends(get_db),
                principal: Principal = Depends(get_principal)):
    """Referring clinician's review. 'Reviewed' is acknowledgment only, not treatment clearance (FR-69)."""
    r = load_referral(db, referral_id, principal, "review_flag", roles=("clinician",))
    f = db.get(MedicationFlag, flag_id)
    if f is None or f.referral_id != r.id:
        raise error(404, "not_found", "Flag not found")
    if f.status != "active" or f.version != body.flag_version:
        raise error(409, "flag_version_changed", "This flag has changed; review the current version")
    clar = None
    if body.action == "request_clarification":
        if not (body.question or "").strip():
            raise error(422, "question_required", "Enter the clarification question")
        clar = Clarification(referral_id=r.id, flag_id=f.id, origin="clinic", question=body.question.strip(),
                             assignee_institution=body.assignee_institution or r.source_institution,
                             assignee_role="clinician", created_by=principal.display_name)
        db.add(clar)
        db.flush()
    review = FlagReview(referral_id=r.id, flag_id=f.id, flag_version=f.version, side="referring", action=body.action,
                        reviewer=principal.display_name, reviewer_id=principal.subject,
                        institution_id=principal.institution_id, clarification_id=clar.id if clar else None,
                        note=body.note)
    db.add(review)
    audit(db, principal, "flag.review", "medication_flag", f"{f.id}v{f.version}", "success", r.id,
          {"action": body.action, "clarification_id": clar.id if clar else None})
    db.commit()
    return flag_out(f, _reviews(db, f.id))


@router.get("/medication-dictionary")
def dictionary_entries(principal: Principal = Depends(get_principal)):
    d = mapping.dictionary()
    return {"dictionary_id": d["dictionary_id"], "version": d["version"], "classes": d["classes"],
            "reviewed_entries": mapping.reviewed_entries()}


# ---------------------------------------------------------------- rule governance
@router.get("/rules")
def list_rules(db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    rs = rules.ruleset("orthodontics")
    return {"ruleset_id": rs["ruleset_id"], "version": rs["version"], "specialty": rs["specialty"],
            "governance": rs["governance"], "supported_classes": rs["supported_classes"],
            "supported_procedures": rs["supported_procedures"], "rules": rules.all_rules(db, "orthodontics"),
            "can_approve": "rule_reviewer" in principal.roles}


class RuleDecisionIn(BaseModel):
    decision: Literal["approve", "retire", "reject"]
    reference_checked: str = Field(min_length=5)
    note: str = ""


@router.post("/rules/{rule_id}/versions/{version}/decision")
def decide_rule(rule_id: str, version: int, body: RuleDecisionIn, db: Session = Depends(get_db),
                principal: Principal = Depends(get_principal)):
    """Only a clinical rule reviewer may activate a rule. Administrators cannot (NFR 10.6)."""
    require_roles(principal, "rule_reviewer", action="rule.decision",
                  message="Only a clinical rule reviewer can approve or retire medication rules")
    rule = next((x for x in rules.ruleset("orthodontics")["rules"] if x["rule_id"] == rule_id and x["version"] == version), None)
    if rule is None:
        raise error(404, "not_found", "Rule version not found")
    status = {"approve": "approved", "retire": "retired", "reject": "rejected"}[body.decision]
    approval = db.scalars(select(RuleApproval).where(RuleApproval.rule_id == rule_id, RuleApproval.rule_version == version)).first()
    if approval is None:
        approval = RuleApproval(rule_id=rule_id, rule_version=version, content_hash=rules.rule_hash(rule), status=status,
                                reviewer=principal.display_name, reviewer_id=principal.subject,
                                reference_checked=body.reference_checked, note=body.note)
        db.add(approval)
    else:
        approval.status, approval.content_hash = status, rules.rule_hash(rule)
        approval.reviewer, approval.reviewer_id = principal.display_name, principal.subject
        approval.reference_checked, approval.note, approval.decided_at = body.reference_checked, body.note, utcnow()
    audit(db, principal, f"rule.{body.decision}", "medication_rule", f"{rule_id}v{version}", "success",
          detail={"reference_checked": body.reference_checked, "content_hash": approval.content_hash})
    db.flush()
    # Rule-version change triggers re-evaluation of open referrals (FR-70)
    open_refs = db.scalars(select(Referral).where(Referral.specialty == rule["specialty"],
                                                  Referral.status.notin_(list(CLINICAL_LOCKED | TERMINAL)))).all()
    for ref in open_refs:
        after_change(db, ref, f"rule_{body.decision}:{rule_id}v{version}", actor=principal.display_name)
    db.commit()
    return {"rule_id": rule_id, "version": version, "status": status, "reevaluated_referrals": len(open_refs)}
