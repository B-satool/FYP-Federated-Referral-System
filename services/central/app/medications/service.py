"""The referral's current-medicine list and flag (re)evaluation.

* Only current medicines enter the list: sources return active prescriptions only;
  medicines read from uploaded papers enter once staff have verified them; medicines
  staff add after asking the patient (including over-the-counter ones) enter directly.
* The same medicine at the same strength from several places is one entry
  (the others are kept as duplicates, with their sources). A different strength for
  the same medicine is highlighted as "dose differs" for staff to resolve.
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache

from refcommon.db import utcnow
from refcommon.exchange import content_hash
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import DRUG_CLASSES, INSTITUTIONS, institution_name, settings
from ..integration.retrieval import latest_by_source, linked_sources
from ..models import EvaluationRun, EvidenceItem, FlagReview, MedicationEntry, MedicationFlag, Referral
from ..security import audit
from . import mapping, rules
from .evaluator import EvalInput, MedInput, SourceState, evaluate_medications
from .label_validation import patient_categories

log = logging.getLogger("medications")
USABLE = {"source_record", "verified"}
KIND_RANK = {"prescription": 0, "document": 1, "manual": 2}


def _source_label(ev: EvidenceItem) -> str:
    if ev.origin == "source":
        return f"{institution_name(ev.source_institution)} record"
    if ev.origin == "document":
        return f"Paper brought by patient (document #{ev.document_id}, page {ev.page or '?'})"
    otc = " (over the counter)" if (ev.current or {}).get("over_the_counter") else ""
    return f"Told by the patient, recorded by {ev.author or 'staff'}{otc}"


def current_medicine_evidence(db: Session, referral_id: int) -> list[EvidenceItem]:
    return list(db.scalars(select(EvidenceItem).where(
        EvidenceItem.referral_id == referral_id, EvidenceItem.category == "medication",
        EvidenceItem.superseded_by.is_(None), EvidenceItem.review_state != "excluded",
        EvidenceItem.selected.is_(True), EvidenceItem.verification_status.in_(USABLE),
    ).order_by(EvidenceItem.id)))


def sync_entries(db: Session, referral: Referral) -> None:
    evidence = current_medicine_evidence(db, referral.id)
    usable_ids = {e.id for e in evidence}
    existing = {e.evidence_id: e for e in db.scalars(select(MedicationEntry).where(MedicationEntry.referral_id == referral.id))}
    index = mapping.name_index(db)
    parts = rules.components(db)
    for ev in evidence:
        cur = ev.current or ev.original
        name = cur.get("medication") or ev.display
        entry = existing.get(ev.id)
        if entry is None:
            entry = MedicationEntry(referral_id=referral.id, evidence_id=ev.id, original_name=name,
                                    mapping_status="unmapped", source_label="", record_kind="manual")
            db.add(entry)
            existing[ev.id] = entry
        renamed = entry.original_name != name
        entry.record_kind = "prescription" if ev.origin == "source" else ev.origin
        entry.original_name = name
        entry.brand = cur.get("brand")
        entry.strength = cur.get("strength") or mapping.strength_of(name, cur.get("dosage_text"), cur.get("dose"))
        entry.dose = cur.get("dosage_text") or cur.get("dose")
        entry.route = cur.get("route")
        entry.frequency = cur.get("frequency")
        entry.start_date = cur.get("start") or cur.get("date")
        entry.over_the_counter = bool(cur.get("over_the_counter"))
        entry.source_label = _source_label(ev)
        if entry.mapping_status != "staff_mapped" or renamed:
            m = index.map(name, entry.brand)
            entry.mapping_status, entry.ingredient, entry.drug_class, entry.mapping_note = (
                m.status, m.ingredient, m.drug_class, m.note)
            entry.mapping_choices = list(m.choices) or None
        entry.ingredients = parts.get(entry.ingredient or "", [entry.ingredient] if entry.ingredient else [])
    db.flush()
    # group: same ingredient (or same name when unrecognised)
    groups: dict[str, list[MedicationEntry]] = {}
    for e in existing.values():
        e.duplicate_of, e.dose_differs = None, False
        if e.evidence_id in usable_ids and not e.excluded:
            groups.setdefault(e.ingredient or mapping.normalize(e.original_name), []).append(e)
    for members in groups.values():
        members.sort(key=lambda e: (KIND_RANK.get(e.record_kind, 9), e.id))
        strengths = {e.strength for e in members if e.strength}
        if len(strengths) > 1:
            for e in members:
                e.dose_differs = True
        # one representative per strength; an entry without a recorded strength joins the first one
        reps: dict[str, MedicationEntry] = {}
        first: MedicationEntry | None = None
        for e in members:
            rep = reps.get(e.strength) if e.strength else first
            if rep is None:
                if e.strength:
                    reps[e.strength] = e
                first = first or e
            else:
                e.duplicate_of = rep.id
    db.flush()


def current_entries(db: Session, referral_id: int, include_duplicates: bool = False) -> list[MedicationEntry]:
    usable = {e.id for e in current_medicine_evidence(db, referral_id)}
    rows = db.scalars(select(MedicationEntry).where(MedicationEntry.referral_id == referral_id)
                      .order_by(MedicationEntry.id)).all()
    return [e for e in rows if e.evidence_id in usable and not e.excluded and (include_duplicates or e.duplicate_of is None)]


def all_entries(db: Session, referral_id: int) -> list[MedicationEntry]:
    usable = {e.id for e in current_medicine_evidence(db, referral_id)}
    return [e for e in db.scalars(select(MedicationEntry).where(MedicationEntry.referral_id == referral_id)
                                  .order_by(MedicationEntry.id)) if e.evidence_id in usable]


def source_states(db: Session, referral: Referral) -> list[SourceState]:
    """Medicine-holding sources (clinics and hospitals) used for this referral."""
    latest = latest_by_source(db, referral)
    out = []
    for inst, _local, _link in linked_sources(db, referral):
        if INSTITUTIONS[inst]["kind"] == "laboratory":
            continue
        sr = latest.get(inst)
        if sr is not None and sr.status == "skipped":
            continue
        out.append(SourceState(inst, institution_name(inst) or inst, sr.status if sr else "not_retrieved"))
    return out


@lru_cache(maxsize=1)
def _vocab() -> dict:
    path = settings.repo_root / "rules" / "vocab" / "label-targets.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


INACTIVE = {"resolved", "inactive", "remission", "entered-in-error", "refuted"}


def patient_conditions(db: Session, referral: Referral) -> tuple[str, ...]:
    """Condition categories from the patient's current recorded conditions (resolved ones are left out)."""
    texts = []
    for ev in db.scalars(select(EvidenceItem).where(
            EvidenceItem.referral_id == referral.id, EvidenceItem.category == "condition",
            EvidenceItem.superseded_by.is_(None), EvidenceItem.review_state != "excluded",
            EvidenceItem.selected.is_(True), EvidenceItem.verification_status.in_(USABLE))):
        cur = ev.current or ev.original or {}
        if (cur.get("clinical_status") or "").lower() in INACTIVE:
            continue
        texts.append(cur.get("condition") or ev.display)
    return tuple(sorted(patient_categories(texts, _vocab())))


def build_input(db: Session, referral: Referral) -> tuple[EvalInput, dict[str, int], str]:
    rule_list = rules.active_rules(db)
    entries = current_entries(db, referral.id)
    meds = tuple(MedInput(entry_id=e.id, original_name=e.original_name, ingredient=e.ingredient,
                          drug_class=e.drug_class, mapping_status=e.mapping_status, source_label=e.source_label,
                          evidence_ids=tuple(x.evidence_id for x in _group_members(db, e)),
                          ingredients=tuple(e.ingredients or ([e.ingredient] if e.ingredient else [])),
                          mapping_note=e.mapping_note)
                 for e in entries)
    ings = {i for m in meds if m.mapping_status in ("mapped", "staff_mapped") for i in m.ingredients}
    tags = tuple(sorted(referral.procedure_tags or [])) if referral.procedure_status == "planned" else ()
    inp = EvalInput(procedure_status=referral.procedure_status, planned_procedure=referral.planned_procedure,
                    procedure_tags=tags, medications=meds, sources=tuple(source_states(db, referral)),
                    rules=tuple(rule_list), class_labels=DRUG_CLASSES,
                    interactions=tuple(rules.interactions_for(db, ings)), label_rules=tuple(rules.label_rules_for(db, ings)),
                    conditions=patient_conditions(db, referral), interaction_coverage=rules.interaction_coverage(db))
    return inp, {r.rule_id: r.version for r in rule_list}, rules.ruleset_hash(db, rule_list)


def _group_members(db: Session, rep: MedicationEntry) -> list[MedicationEntry]:
    dups = db.scalars(select(MedicationEntry).where(MedicationEntry.duplicate_of == rep.id)).all()
    return [rep, *dups]


def reevaluate(db: Session, referral: Referral, trigger: str, actor: str, principal=None) -> EvaluationRun:
    """Run the evaluator and persist flag versions. Material changes create new versions."""
    from ..notifications import notify_doctor
    from ..referrals.state import CLINICAL_LOCKED, mark_clinical_change

    sync_entries(db, referral)
    inp, rule_versions, ruleset = build_input(db, referral)
    input_hash = content_hash({"meds": [m.__dict__ for m in inp.medications], "sources": [s.__dict__ for s in inp.sources],
                               "rules": rule_versions, "ruleset": ruleset, "conditions": list(inp.conditions),
                               "procedure": [inp.procedure_status, inp.planned_procedure, list(inp.procedure_tags)]})
    run = EvaluationRun(referral_id=referral.id, trigger=trigger, status="completed", input_hash=input_hash,
                        rule_versions=rule_versions, triggered_by=actor, ruleset_hash=ruleset,
                        context={"procedure_status": inp.procedure_status, "planned_procedure": inp.planned_procedure,
                                 "procedure_tags": list(inp.procedure_tags), "conditions": list(inp.conditions),
                                 "sources": {s.institution: s.status for s in inp.sources}})
    db.add(run)
    try:
        out = evaluate_medications(inp)
    except Exception as exc:  # noqa: BLE001 - failure must be visible, distinct from "no match"
        log.exception("medication evaluation failed")
        run.status, run.error = "failed", str(exc)[:500]
        run.summary_message = ("Medication rule evaluation failed. Records are kept; a doctor must review the medicines. "
                               "This is not a negative result.")
        db.flush()
        audit(db, principal, "medications.evaluate", "referral", referral.reference, "failed", referral.id,
              {"trigger": trigger, "error": run.error}, actor=None if principal else ("system", actor, None))
        return run
    run.outcome, run.summary_message = out.outcome, out.summary_message
    db.flush()

    active = {f.flag_key: f for f in db.scalars(select(MedicationFlag).where(
        MedicationFlag.referral_id == referral.id, MedicationFlag.status == "active"))}
    changed = 0
    now = utcnow()
    for cand in out.candidates:
        c = cand.content()
        h = content_hash({k: v for k, v in c.items() if k != "medication_entry_id"})
        prev = active.pop(cand.flag_key, None)
        if prev is not None and prev.content_hash == h:
            continue  # identical result: no duplicate visible flag
        if prev is not None:
            prev.status, prev.superseded_at = "superseded", now
        last = db.scalars(select(MedicationFlag).where(MedicationFlag.referral_id == referral.id,
                                                       MedicationFlag.flag_key == cand.flag_key)
                          .order_by(MedicationFlag.version.desc())).first()
        db.add(MedicationFlag(referral_id=referral.id, flag_key=cand.flag_key, version=(last.version + 1) if last else 1,
                              kind=cand.kind, title=cand.title, message=cand.message, medication=cand.medication,
                              drug_class=cand.drug_class, source_label=cand.source_label, rule_id=cand.rule_id,
                              rule_version=cand.rule_version, medication_entry_id=cand.medication_entry_id,
                              evidence_ids=c["evidence_ids"], content_hash=h, run_id=run.id, severity=cand.severity,
                              ingredients=cand.ingredients, source_type=cand.source_type, source_name=cand.source_name,
                              source_ref=cand.source_ref, source_version=cand.source_version,
                              source_quote=cand.source_quote, auto_generated=cand.auto_generated,
                              requires_decision=cand.requires_decision))
        changed += 1
    for stale in active.values():
        stale.status, stale.superseded_at = "withdrawn", now
        changed += 1
    run.changed_flags = changed
    db.flush()
    audit(db, principal, "medications.evaluate", "referral", referral.reference, "success", referral.id,
          {"trigger": trigger, "outcome": out.outcome, "changed_flags": changed, "rule_versions": rule_versions},
          actor=None if principal else ("system", actor, None))
    # The doctor reviews flags once staff have gathered everything (prepared), not while records still arrive.
    if changed and referral.prepared_at is not None and unacknowledged_flags(db, referral.id):
        notify_doctor(db, referral, "flags_to_acknowledge", f"{referral.reference}: medication flags to acknowledge",
                      f"{referral.patient_name}. Flags changed after: {trigger.replace('_', ' ')}.", tab="medicines")
    if changed and referral.current_package_version and referral.status not in CLINICAL_LOCKED:
        mark_clinical_change(db, referral, actor, "medication flags changed", principal)
    return run


def latest_run(db: Session, referral_id: int) -> EvaluationRun | None:
    return db.scalars(select(EvaluationRun).where(EvaluationRun.referral_id == referral_id)
                      .order_by(EvaluationRun.id.desc())).first()


def active_flags(db: Session, referral_id: int) -> list[MedicationFlag]:
    return list(db.scalars(select(MedicationFlag).where(MedicationFlag.referral_id == referral_id,
                                                        MedicationFlag.status == "active").order_by(MedicationFlag.id)))


def acknowledgement(db: Session, flag: MedicationFlag) -> FlagReview | None:
    return db.scalars(select(FlagReview).where(FlagReview.flag_id == flag.id, FlagReview.side == "referring")
                      .order_by(FlagReview.id.desc())).first()


def unacknowledged_flags(db: Session, referral_id: int) -> list[MedicationFlag]:
    """Flags the doctor must decide on before sending (approved rules, Major interactions, label warnings
    from a boxed warning or contraindication, and gaps). The others are shown but optional."""
    return [f for f in active_flags(db, referral_id) if f.requires_decision and acknowledgement(db, f) is None]
