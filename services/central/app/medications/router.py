"""Current medicines, flags and acknowledgments; medication rules and medicine names (edited in the app)."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from refcommon.auth import Principal
from refcommon.db import utcnow
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import DRUG_CLASSES, PROCEDURE_HINTS, PROCEDURE_TAGS
from ..db import get_db
from ..models import (DrugInteraction, EvidenceItem, EvidenceRevision, FlagReview, LabelRule, MedicationEntry, MedicationFlag,
                      MedicationRule, MedicineName, Referral, RulesetRelease)
from ..notifications import notify_staff
from ..referrals.state import CLINICAL_LOCKED, TERMINAL, ensure_clinical_edit_allowed, mark_clinical_change
from ..security import audit, error, get_principal, load_referral, require_roles
from ..serializers import flag_out, medication_out
from ..workflow import after_change
from . import mapping, rules, service

router = APIRouter(tags=["medications"])


def _acks(db: Session, flag_id: int) -> list[FlagReview]:
    return list(db.scalars(select(FlagReview).where(FlagReview.flag_id == flag_id).order_by(FlagReview.id)))


@router.get("/referrals/{referral_id}/medications")
def medications(referral_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    r = load_referral(db, referral_id, principal, "view")
    run = service.latest_run(db, r.id)
    flags = db.scalars(select(MedicationFlag).where(MedicationFlag.referral_id == r.id)
                       .order_by(MedicationFlag.flag_key, MedicationFlag.version.desc())).all()
    entries = service.all_entries(db, r.id)
    excluded = [e for e in db.scalars(select(MedicationEntry).where(MedicationEntry.referral_id == r.id,
                                                                    MedicationEntry.excluded.is_(True)))]
    return {
        "entries": [medication_out(m) for m in entries if not m.excluded],
        "excluded": [medication_out(m) for m in excluded],
        "meds_checked": {"by": r.meds_checked_by, "at": r.meds_checked_at, "note": r.meds_checked_note},
        "evaluation": None if run is None else {
            "id": run.id, "status": run.status, "outcome": run.outcome, "summary_message": run.summary_message,
            "trigger": run.trigger, "rule_versions": run.rule_versions, "context": run.context, "error": run.error,
            "changed_flags": run.changed_flags, "created_at": run.created_at,
        },
        "flags": [flag_out(f, _acks(db, f.id)) for f in flags if f.status == "active"],
        "flag_history": [flag_out(f, _acks(db, f.id)) for f in flags if f.status != "active"],
    }


class ManualMedIn(BaseModel):
    name: str = Field(min_length=2)
    strength: str | None = None
    dose: str | None = None
    frequency: str | None = None
    route: str | None = None
    over_the_counter: bool = False
    note: str = ""


@router.post("/referrals/{referral_id}/medications/manual", status_code=201)
def add_medicine(referral_id: int, body: ManualMedIn, db: Session = Depends(get_db),
                 principal: Principal = Depends(get_principal)):
    """Staff add a medicine the patient says they take, e.g. an over-the-counter painkiller."""
    r = load_referral(db, referral_id, principal, "edit", roles=("clinic_staff",))
    ensure_clinical_edit_allowed(r)
    fields = {"medication": body.name.strip(), "strength": body.strength, "dosage_text": " ".join(
        x for x in [body.dose, body.frequency] if x) or None, "frequency": body.frequency, "route": body.route,
        "over_the_counter": body.over_the_counter, "record_kind": "manual", "note": body.note or None}
    otc = " (over the counter)" if body.over_the_counter else ""
    ev = EvidenceItem(referral_id=r.id, patient_institution=r.patient_institution, patient_local_id=r.patient_local_id,
                      origin="manual", source_institution=r.source_institution, category="medication",
                      display=f"{body.name.strip()} - {fields['dosage_text'] or 'dose not recorded'}{otc} (told by the patient)",
                      original=fields, current=dict(fields), review_state="manual", verification_status="verified",
                      verified_by=principal.display_name, verified_at=utcnow(), selected=True,
                      author=principal.display_name,
                      source_text=f"Asked the patient; recorded by {principal.display_name}")
    db.add(ev)
    db.flush()
    db.add(EvidenceRevision(evidence_id=ev.id, action="manual_entry", new_value=fields, new_state="manual",
                            editor=principal.display_name, editor_id=principal.subject, note=body.note))
    audit(db, principal, "medication.add_manual", "evidence", ev.id, "success", r.id,
          {"name": body.name, "over_the_counter": body.over_the_counter})
    if r.current_package_version:
        mark_clinical_change(db, r, principal.display_name, "medicine added", principal)
    after_change(db, r, "medicine_added", principal)
    db.commit()
    return {"evidence_id": ev.id}


class ReasonIn(BaseModel):
    reason: str = Field(min_length=3)


def _entry(db: Session, r: Referral, entry_id: int) -> MedicationEntry:
    m = db.get(MedicationEntry, entry_id)
    if m is None or m.referral_id != r.id:
        raise error(404, "not_found", "Medicine not found")
    return m


@router.post("/referrals/{referral_id}/medications/{entry_id}/exclude")
def exclude_medicine(referral_id: int, entry_id: int, body: ReasonIn, db: Session = Depends(get_db),
                     principal: Principal = Depends(get_principal)):
    """Staff mark a recorded medicine as not current (e.g. an old prescription, or the
    other side of a dose difference). The record is kept, with who and why."""
    r = load_referral(db, referral_id, principal, "edit")
    ensure_clinical_edit_allowed(r)
    m = _entry(db, r, entry_id)
    m.excluded, m.excluded_by, m.excluded_reason = True, principal.display_name, body.reason.strip()
    audit(db, principal, "medication.exclude", "medication_entry", m.id, "success", r.id,
          {"medicine": m.original_name, "reason": body.reason})
    if r.current_package_version:
        mark_clinical_change(db, r, principal.display_name, "medicine excluded", principal)
    after_change(db, r, "medicine_excluded", principal)
    db.commit()
    return medication_out(m)


@router.post("/referrals/{referral_id}/medications/{entry_id}/restore")
def restore_medicine(referral_id: int, entry_id: int, db: Session = Depends(get_db),
                     principal: Principal = Depends(get_principal)):
    r = load_referral(db, referral_id, principal, "edit")
    ensure_clinical_edit_allowed(r)
    m = _entry(db, r, entry_id)
    m.excluded, m.excluded_by, m.excluded_reason = False, None, None
    audit(db, principal, "medication.restore", "medication_entry", m.id, "success", r.id)
    if r.current_package_version:
        mark_clinical_change(db, r, principal.display_name, "medicine restored", principal)
    after_change(db, r, "medicine_restored", principal)
    db.commit()
    return medication_out(m)


class MapIn(BaseModel):
    ingredient: str


@router.post("/referrals/{referral_id}/medications/{entry_id}/mapping")
def set_mapping(referral_id: int, entry_id: int, body: MapIn, db: Session = Depends(get_db),
                principal: Principal = Depends(get_principal)):
    """Staff resolve an unrecognised name by choosing a medicine from the reviewed name list."""
    r = load_referral(db, referral_id, principal, "map_medication")
    ensure_clinical_edit_allowed(r)
    m = _entry(db, r, entry_id)
    known = db.scalars(select(MedicineName).where(MedicineName.ingredient == body.ingredient,
                                                  MedicineName.status == "active")).first()
    if known is None:
        raise error(422, "unknown_ingredient", "Choose a medicine from the medicine name list")
    prior = {"status": m.mapping_status, "ingredient": m.ingredient}
    m.mapping_status, m.ingredient, m.drug_class = "staff_mapped", known.ingredient, known.drug_class
    m.mapping_note = f"Matched by {principal.display_name}"
    audit(db, principal, "medication.mapping", "medication_entry", m.id, "success", r.id,
          {"from": prior, "to": known.ingredient, "original_name": m.original_name})
    after_change(db, r, "medicine_mapping_changed", principal)
    db.commit()
    return medication_out(m)


class CheckedIn(BaseModel):
    note: str = ""


@router.post("/referrals/{referral_id}/medications/checked")
def medicines_checked(referral_id: int, body: CheckedIn, db: Session = Depends(get_db),
                      principal: Principal = Depends(get_principal)):
    """Staff confirm they asked the patient about every medicine, including over-the-counter ones."""
    r = load_referral(db, referral_id, principal, "edit")
    ensure_clinical_edit_allowed(r)
    r.meds_checked_by, r.meds_checked_at, r.meds_checked_note = principal.display_name, utcnow(), body.note or None
    audit(db, principal, "medication.checked_with_patient", "referral", r.reference, "success", r.id)
    db.commit()
    return {"by": r.meds_checked_by, "at": r.meds_checked_at, "note": r.meds_checked_note}


class AckIn(BaseModel):
    flag_version: int
    # reviewed | ignore (not relevant for this patient) | research (needs follow-up)
    decision: Literal["reviewed", "ignore", "research"] = "reviewed"
    note: str = ""


@router.post("/referrals/{referral_id}/flags/{flag_id}/acknowledge")
def acknowledge_flag(referral_id: int, flag_id: int, body: AckIn, db: Session = Depends(get_db),
                     principal: Principal = Depends(get_principal)):
    """The doctor records a decision on the flag for this patient: reviewed, ignore or research.
    Any decision means 'seen'; it is never treatment clearance. Ignored flags stay in the record."""
    r = load_referral(db, referral_id, principal, "acknowledge_flag", roles=("clinician",))
    f = db.get(MedicationFlag, flag_id)
    if f is None or f.referral_id != r.id:
        raise error(404, "not_found", "Flag not found")
    if r.prepared_at is None:
        raise error(409, "not_prepared", "Staff are still gathering the records and medicines; review the flags once they are done")
    if f.status != "active" or f.version != body.flag_version:
        raise error(409, "flag_version_changed", "This flag has changed; acknowledge the current version")
    if service.acknowledgement(db, f) is None:
        run = service.latest_run(db, r.id)
        db.add(FlagReview(referral_id=r.id, flag_id=f.id, flag_version=f.version, side="referring",
                          reviewer=principal.display_name, reviewer_id=principal.subject,
                          institution_id=principal.institution_id, note=body.note.strip(), decision=body.decision,
                          ruleset_hash=run.ruleset_hash if run else None))
        audit(db, principal, f"flag.{body.decision}", "medication_flag", f"{f.id}v{f.version}", "success", r.id,
              {"decision": body.decision, "note": body.note, "ruleset": run.ruleset_hash if run else None})
        db.flush()
        if r.status == "requested" and not service.unacknowledged_flags(db, r.id):
            notify_staff(db, r, "ready_to_send", f"{r.reference}: flags reviewed, ready to send",
                         f"{principal.display_name} reviewed every medication flag.", tab="send")
        db.commit()
    return flag_out(f, _acks(db, f.id))


# ---------------------------------------------------------------- medicine names
@router.get("/medicine-names")
def medicine_names(q: str = "", db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    stmt = select(MedicineName).where(MedicineName.status == "active")
    if q.strip():
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where((MedicineName.name.ilike(like)) | (MedicineName.ingredient.ilike(like)))
    rows = db.scalars(stmt.order_by(MedicineName.ingredient, MedicineName.display).limit(500)).all()
    return {"classes": DRUG_CLASSES,
            "names": [{"id": n.id, "display": n.display, "ingredient": n.ingredient, "drug_class": n.drug_class,
                       "kind": n.kind, "added_by": n.added_by} for n in rows],
            "ingredients": sorted({n.ingredient for n in rows}),
            "can_edit": "rule_reviewer" in principal.roles}


class NameIn(BaseModel):
    display: str = Field(min_length=2)
    ingredient: str = Field(min_length=2)
    drug_class: str = Field(min_length=2)
    kind: Literal["generic", "brand"] = "brand"


@router.post("/medicine-names", status_code=201)
def add_name(body: NameIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    require_roles(principal, "rule_reviewer", action="medicine_name.add",
                  message="Only a clinical reviewer can add medicine names")
    key = mapping.normalize(body.display)
    if not key:
        raise error(422, "invalid_name", "Enter a medicine name")
    if db.scalars(select(MedicineName).where(MedicineName.name == key)).first():
        raise error(409, "exists", "This name is already in the list")
    n = MedicineName(name=key, display=body.display.strip(), ingredient=body.ingredient.strip().lower(),
                     drug_class=body.drug_class.strip(), kind=body.kind, added_by=principal.display_name)
    db.add(n)
    audit(db, principal, "medicine_name.add", "medicine_name", body.display, "success",
          detail={"ingredient": n.ingredient, "drug_class": n.drug_class})
    db.flush()
    _reevaluate_open(db, principal, f"medicine_name_added:{n.display}")
    db.commit()
    return {"id": n.id, "display": n.display, "ingredient": n.ingredient, "drug_class": n.drug_class}


@router.post("/medicine-names/{name_id}/retire")
def retire_name(name_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    require_roles(principal, "rule_reviewer", action="medicine_name.retire")
    n = db.get(MedicineName, name_id)
    if n is None:
        raise error(404, "not_found", "Name not found")
    n.status = "retired"
    audit(db, principal, "medicine_name.retire", "medicine_name", n.display, "success")
    _reevaluate_open(db, principal, f"medicine_name_retired:{n.display}")
    db.commit()
    return {"id": n.id, "status": n.status}


# ---------------------------------------------------------------- rules (edited in the app)
def _rule_out(r: MedicationRule) -> dict:
    return {"id": r.id, "rule_id": r.rule_id, "version": r.version, "title": r.title, "drug_class": r.drug_class,
            "drug_class_label": DRUG_CLASSES.get(r.drug_class, r.drug_class), "procedure_tags": r.procedure_tags,
            "procedure_tag_labels": [PROCEDURE_TAGS.get(t, t) for t in r.procedure_tags], "message": r.message,
            "rationale": r.rationale, "reference": r.reference, "status": r.status, "content_hash": r.content_hash,
            "intact": r.content_hash == rules.rule_hash(r), "created_by": r.created_by, "created_at": r.created_at,
            "decided_by": r.decided_by, "decided_at": r.decided_at, "reference_checked": r.reference_checked,
            "decision_note": r.decision_note,
            # words in a procedure name that pre-tick one of this rule's features
            "matching_procedures": sorted(k for k, v in PROCEDURE_HINTS.items() if set(v) & set(r.procedure_tags))}


@router.get("/rules")
def list_rules(db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    require_roles(principal, "rule_reviewer", action="rule.list", message="Only a clinical rule reviewer can view the rules")
    rows =db.scalars(select(MedicationRule).order_by(MedicationRule.rule_id, MedicationRule.version.desc())).all()
    grouped: dict[str, list[dict]] = {}
    for r in rows:
        grouped.setdefault(r.rule_id, []).append(_rule_out(r))
    return {"rules": [{"rule_id": k, "versions": v} for k, v in grouped.items()], "drug_classes": DRUG_CLASSES,
            "procedure_tags": PROCEDURE_TAGS, "can_approve": "rule_reviewer" in principal.roles,
            "can_edit": "rule_reviewer" in principal.roles}


class RuleIn(BaseModel):
    title: str = Field(min_length=5)
    drug_class: str
    procedure_tags: list[str] = Field(min_length=1)
    message: str = Field(min_length=10)
    rationale: str = ""
    reference: str = ""


def _validate_rule(body: RuleIn) -> None:
    if body.drug_class not in DRUG_CLASSES:
        raise error(422, "invalid_class", "Choose a drug class from the list")
    bad = set(body.procedure_tags) - set(PROCEDURE_TAGS)
    if bad:
        raise error(422, "invalid_tags", f"Unknown procedure tags: {sorted(bad)}")
    lowered = body.message.lower()
    if any(w in lowered for w in ("stop taking", "stop the", "discontinue", "do not take", "withhold", "increase the dose")):
        raise error(422, "advice_not_allowed",
                    "A flag message must not advise starting, stopping or changing a medicine. Ask for review instead.")


def _new_version(db: Session, principal: Principal, rule_id: str, body: RuleIn) -> MedicationRule:
    version = (db.scalar(select(func.max(MedicationRule.version)).where(MedicationRule.rule_id == rule_id)) or 0) + 1
    r = MedicationRule(rule_id=rule_id, version=version, title=body.title.strip(), drug_class=body.drug_class,
                       procedure_tags=sorted(set(body.procedure_tags)), message=body.message.strip(),
                       rationale=body.rationale.strip(), reference=body.reference.strip(), status="draft",
                       content_hash="", created_by=principal.display_name, created_by_id=principal.subject)
    r.content_hash = rules.rule_hash(r)
    db.add(r)
    db.flush()
    audit(db, principal, "rule.draft", "medication_rule", f"{rule_id}v{version}", "success")
    return r


@router.post("/rules", status_code=201)
def create_rule(body: RuleIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """Reviewers draft a rule. It does nothing until a reviewer approves it."""
    require_roles(principal, "rule_reviewer", action="rule.create")
    _validate_rule(body)
    n = (db.scalar(select(func.count(func.distinct(MedicationRule.rule_id)))) or 0) + 1
    rule_id = f"RULE-{n:03d}"
    while db.scalars(select(MedicationRule).where(MedicationRule.rule_id == rule_id)).first():
        n += 1
        rule_id = f"RULE-{n:03d}"
    r = _new_version(db, principal, rule_id, body)
    db.commit()
    return _rule_out(r)


@router.put("/rules/{rule_id}")
def edit_rule(rule_id: str, body: RuleIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """An edit is a new draft version; the approved version keeps working until the new one is approved."""
    require_roles(principal, "rule_reviewer", action="rule.edit")
    if not db.scalars(select(MedicationRule).where(MedicationRule.rule_id == rule_id)).first():
        raise error(404, "not_found", "Rule not found")
    _validate_rule(body)
    r = _new_version(db, principal, rule_id, body)
    db.commit()
    return _rule_out(r)


class RuleDecisionIn(BaseModel):
    decision: Literal["approve", "reject", "retire"]
    reference_checked: str = Field(min_length=5)
    note: str = ""


@router.post("/rules/{rule_id}/versions/{version}/decision")
def decide_rule(rule_id: str, version: int, body: RuleDecisionIn, db: Session = Depends(get_db),
                principal: Principal = Depends(get_principal)):
    """Only a clinical rule reviewer may approve, reject or retire a rule version."""
    require_roles(principal, "rule_reviewer", action="rule.decision",
                  message="Only a clinical rule reviewer can approve, reject or retire medication rules")
    r = db.scalars(select(MedicationRule).where(MedicationRule.rule_id == rule_id, MedicationRule.version == version)).first()
    if r is None:
        raise error(404, "not_found", "Rule version not found")
    if body.decision == "approve":
        if r.status != "draft":
            raise error(409, "not_draft", f"Only a draft can be approved; this version is {r.status}")
        if r.content_hash != rules.rule_hash(r):
            raise error(409, "content_changed", "The rule content changed after it was drafted; draft it again")
        for old in db.scalars(select(MedicationRule).where(MedicationRule.rule_id == rule_id,
                                                           MedicationRule.status == "approved")):
            old.status = "superseded"
        r.status = "approved"
    elif body.decision == "reject":
        if r.status != "draft":
            raise error(409, "not_draft", "Only a draft can be rejected")
        r.status = "rejected"
    else:
        if r.status != "approved":
            raise error(409, "not_active", "Only the approved version can be retired")
        r.status = "retired"
    r.decided_by, r.decided_by_id, r.decided_at = principal.display_name, principal.subject, utcnow()
    r.reference_checked, r.decision_note = body.reference_checked, body.note or None
    audit(db, principal, f"rule.{body.decision}", "medication_rule", f"{rule_id}v{version}", "success",
          detail={"reference_checked": body.reference_checked, "content_hash": r.content_hash})
    db.flush()
    count = _reevaluate_open(db, principal, f"rule_{body.decision}:{rule_id}v{version}")
    db.commit()
    return {**_rule_out(r), "reevaluated_referrals": count}


def _reevaluate_open(db: Session, principal: Principal, trigger: str) -> int:
    """A rule or name change re-checks every open referral."""
    open_refs = db.scalars(select(Referral).where(Referral.kind == "referral",
                                                  Referral.status.notin_(list(CLINICAL_LOCKED | TERMINAL)))).all()
    for ref in open_refs:
        after_change(db, ref, trigger, actor=principal.display_name)
    return len(open_refs)


@router.get("/rules/interactions")
def list_interactions(q: str = "", db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """Imported drug-drug interactions (read-only), searchable by ingredient."""
    require_roles(principal, "rule_reviewer", action="rule.list", message="Only a clinical rule reviewer can view the rules")
    rows = rules.search_interactions(db, q)
    total = db.scalar(select(func.count()).select_from(DrugInteraction)) or 0
    return {"total": total, "shown": len(rows), "source": "DDInter 2.0 (CC BY-NC-SA 4.0)",
            "rows": [{"ingredient_a": x.ingredient_a, "ingredient_b": x.ingredient_b, "severity": x.severity,
                      "source": x.source, "source_ref": x.source_ref, "source_version": x.source_version} for x in rows]}


@router.get("/rules/label-rules")
def list_label_rules(q: str = "", kind: str = "", db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """Rules read from drug labels by script (read-only), with the sentence each relies on."""
    require_roles(principal, "rule_reviewer", action="rule.list", message="Only a clinical rule reviewer can view the rules")
    stmt = select(LabelRule)
    if q.strip():
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where((LabelRule.ingredient.ilike(like)) | (LabelRule.target.ilike(like)) | (LabelRule.target_label.ilike(like)))
    if kind:
        stmt = stmt.where(LabelRule.kind == kind)
    rows = db.scalars(stmt.order_by(LabelRule.ingredient, LabelRule.kind, LabelRule.target).limit(300)).all()
    release = db.scalars(select(RulesetRelease).order_by(RulesetRelease.id.desc())).first()
    return {"release": {"hash": release.hash, "created_at": release.created_at, "counts": release.counts, "notes": release.notes}
            if release else None,
            "rows": [{"rule_key": x.rule_key, "kind": x.kind, "ingredient": x.ingredient, "target": x.target,
                      "target_label": x.target_label, "severity_hint": x.severity_hint, "summary": x.summary,
                      "quote": x.quote, "section": x.section, "source_name": x.source_name, "source_ref": x.source_ref,
                      "source_version": x.source_version, "extractor_version": x.extractor_version, "status": x.status}
                     for x in rows]}


@router.get("/drug-classes")
def drug_classes(principal: Principal = Depends(get_principal)):
    return DRUG_CLASSES
