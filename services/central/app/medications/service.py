"""Medication list maintenance and flag (re)evaluation for a referral."""
from __future__ import annotations

import logging

from refcommon.db import utcnow
from refcommon.exchange import content_hash
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import SOURCES
from ..integration.retrieval import retrieval_targets
from ..integration.sources import source_name
from ..models import EvaluationRun, EvidenceItem, FlagReview, MedicationEntry, MedicationFlag, Referral, SourceRetrieval
from ..security import audit
from . import mapping, rules
from .evaluator import EvalInput, MedInput, SourceState, evaluate_medications

log = logging.getLogger("medications")
USABLE_VERIFICATION = {"source_record", "verified", "unverified"}


def _source_label(ev: EvidenceItem) -> str:
    if ev.origin == "source":
        kind = "prescription" if ev.original.get("record_kind") == "prescription" else "reported medication record"
        return f"{source_name(ev.source_institution)} {kind} {ev.source_record_id} v{ev.source_record_version}"
    if ev.origin == "document":
        return f"Uploaded document #{ev.document_id} page {ev.page or '?'}"
    return f"Manually entered by {ev.author or 'clinician'}"


def active_medication_evidence(db: Session, referral_id: int) -> list[EvidenceItem]:
    return list(db.scalars(select(EvidenceItem).where(
        EvidenceItem.referral_id == referral_id, EvidenceItem.category == "medication",
        EvidenceItem.superseded_by.is_(None), EvidenceItem.review_state != "excluded",
        EvidenceItem.verification_status.in_(USABLE_VERIFICATION),
    ).order_by(EvidenceItem.id)))


def sync_entries(db: Session, referral: Referral) -> None:
    """Create/refresh a MedicationEntry for every usable medication evidence item."""
    evidence = active_medication_evidence(db, referral.id)
    existing = {e.evidence_id: e for e in db.scalars(select(MedicationEntry).where(MedicationEntry.referral_id == referral.id))}
    for ev in evidence:
        cur = ev.current or ev.original
        name = cur.get("medication") or ev.display
        entry = existing.get(ev.id)
        if entry is None:
            entry = MedicationEntry(referral_id=referral.id, evidence_id=ev.id, use_status="unverified",
                                    original_name=name, mapping_status="unmapped", source_label="")
            db.add(entry)
        name_changed = entry.original_name != name
        entry.record_kind = cur.get("record_kind") or ("document" if ev.origin == "document" else "manual")
        entry.original_name = name
        entry.strength = cur.get("strength")
        entry.dose = cur.get("dosage_text") or cur.get("dose")
        entry.route = cur.get("route")
        entry.frequency = cur.get("frequency")
        entry.start_date = cur.get("start") or cur.get("date_asserted") or cur.get("date")
        entry.end_date = cur.get("end")
        entry.source_status = cur.get("status")
        entry.source_label = _source_label(ev)
        if entry.mapping_status != "clinician_mapped" or name_changed:
            m = mapping.map_name(name)
            entry.mapping_status = m.status
            entry.ingredient, entry.ingredient_code = m.ingredient, m.ingredient_code
            entry.drug_class, entry.class_code = m.drug_class, m.class_code
            entry.mapping_source, entry.mapping_version, entry.mapping_note = m.source, m.version, m.note
    db.flush()


def current_entries(db: Session, referral_id: int) -> list[MedicationEntry]:
    usable = {e.id for e in active_medication_evidence(db, referral_id)}
    return [e for e in db.scalars(select(MedicationEntry).where(MedicationEntry.referral_id == referral_id)
                                  .order_by(MedicationEntry.id)) if e.evidence_id in usable]


def source_states(db: Session, referral: Referral) -> list[SourceState]:
    states = []
    for inst, _local, _link in retrieval_targets(db, referral):
        latest = db.scalars(select(SourceRetrieval).where(SourceRetrieval.referral_id == referral.id,
                                                          SourceRetrieval.source_institution == inst)
                            .order_by(SourceRetrieval.id.desc())).first()
        states.append(SourceState(inst, source_name(inst), bool(SOURCES.get(inst, {}).get("medication_source")),
                                  latest.status if latest else "not_retrieved"))
    return states


def build_input(db: Session, referral: Referral) -> tuple[EvalInput, dict[str, int]]:
    rule_list = rules.active_rules(db, referral.specialty)
    meds = tuple(
        MedInput(entry_id=e.id, original_name=e.original_name, ingredient=e.ingredient, drug_class=e.drug_class,
                 mapping_status=e.mapping_status, use_status=e.use_status, source_label=e.source_label,
                 evidence_ids=(e.evidence_id,))
        for e in current_entries(db, referral.id)
    )
    inp = EvalInput(specialty=referral.specialty, procedure_status=referral.procedure_status,
                    planned_procedure=referral.planned_procedure if referral.procedure_status == "known" else None,
                    medications=meds, sources=tuple(source_states(db, referral)), rules=tuple(rule_list))
    return inp, {r.rule_id: r.version for r in rule_list}


def reevaluate(db: Session, referral: Referral, trigger: str, actor: str, principal=None) -> EvaluationRun:
    """Run the evaluator and persist flag versions. Material changes create new versions (FR-70)."""
    from ..referrals.state import CLINICAL_LOCKED, mark_clinical_change

    sync_entries(db, referral)
    inp, rule_versions = build_input(db, referral)
    input_hash = content_hash({"meds": [m.__dict__ for m in inp.medications], "sources": [s.__dict__ for s in inp.sources],
                               "rules": rule_versions, "procedure": [inp.procedure_status, inp.planned_procedure],
                               "specialty": inp.specialty})
    dict_id, dict_version = mapping.source_label()
    run = EvaluationRun(referral_id=referral.id, trigger=trigger, status="completed", input_hash=input_hash,
                        rule_versions=rule_versions, mapping_version=f"{dict_id}@{dict_version}", triggered_by=actor,
                        context={"specialty": inp.specialty, "procedure_status": inp.procedure_status,
                                 "planned_procedure": inp.planned_procedure,
                                 "sources": {s.institution: s.status for s in inp.sources}})
    db.add(run)
    try:
        out = evaluate_medications(inp)
    except Exception as exc:  # noqa: BLE001 - failure must be visible, distinct from "no match" (FR-72)
        log.exception("medication evaluation failed")
        run.status = "failed"
        run.error = str(exc)[:500]
        run.summary_message = ("Medication rule evaluation failed. Existing evidence is retained; manual clinician "
                               "review is required. This is not a negative result.")
        db.flush()
        audit(db, principal, "medications.evaluate", "referral", referral.reference, "failed", referral.id,
              {"trigger": trigger, "error": run.error}, actor=None if principal else ("system", actor, None))
        return run
    run.outcome = out.outcome
    run.summary_message = out.summary_message
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
        version = 1
        if prev is not None:
            prev.status = "superseded"
            prev.superseded_at = now
            version = prev.version + 1
        else:
            last = db.scalars(select(MedicationFlag).where(MedicationFlag.referral_id == referral.id,
                                                           MedicationFlag.flag_key == cand.flag_key)
                              .order_by(MedicationFlag.version.desc())).first()
            version = (last.version + 1) if last else 1
        db.add(MedicationFlag(referral_id=referral.id, flag_key=cand.flag_key, version=version, kind=cand.kind,
                              title=cand.title, message=cand.message, medication=cand.medication,
                              drug_class=cand.drug_class, current_use_status=cand.current_use_status,
                              source_label=cand.source_label, rule_id=cand.rule_id, rule_version=cand.rule_version,
                              medication_entry_id=cand.medication_entry_id, evidence_ids=c["evidence_ids"],
                              content_hash=h, run_id=run.id))
        changed += 1
    for stale in active.values():
        stale.status = "withdrawn"
        stale.superseded_at = now
        changed += 1
    run.changed_flags = changed
    db.flush()
    audit(db, principal, "medications.evaluate", "referral", referral.reference, "success", referral.id,
          {"trigger": trigger, "outcome": out.outcome, "changed_flags": changed, "rule_versions": rule_versions,
           "mapping_version": run.mapping_version},
          actor=None if principal else ("system", actor, None))
    if changed and referral.current_package_version and referral.status not in CLINICAL_LOCKED:
        mark_clinical_change(db, referral, actor, "medication flags changed", principal)
    return run


def latest_run(db: Session, referral_id: int) -> EvaluationRun | None:
    return db.scalars(select(EvaluationRun).where(EvaluationRun.referral_id == referral_id)
                      .order_by(EvaluationRun.id.desc())).first()


def active_flags(db: Session, referral_id: int) -> list[MedicationFlag]:
    return list(db.scalars(select(MedicationFlag).where(MedicationFlag.referral_id == referral_id,
                                                        MedicationFlag.status == "active").order_by(MedicationFlag.id)))


def referring_review(db: Session, flag: MedicationFlag) -> FlagReview | None:
    return db.scalars(select(FlagReview).where(FlagReview.flag_id == flag.id, FlagReview.side == "referring",
                                               FlagReview.action == "reviewed").order_by(FlagReview.id.desc())).first()


def unreviewed_flags(db: Session, referral_id: int) -> list[MedicationFlag]:
    return [f for f in active_flags(db, referral_id) if referring_review(db, f) is None]
