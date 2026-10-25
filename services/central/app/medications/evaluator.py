"""Deterministic medication-against-procedure flag evaluator.

Pure function over typed input: the same current medicines, procedure and rule
versions always produce the same candidates. No language model is involved.

Flags never advise starting, stopping or changing a medicine, never prescribe
treatment and never assign urgency. Their wording comes only from
reviewer-approved rules or the fixed system wording below.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Iterable

UNRECOGNISED_TITLE = "Medicine not recognised"
PROCEDURE_TITLE = "Procedure not known yet: medicine not checked against it"
INCOMPLETE_TITLE = "Medicine records incomplete"


@dataclass(frozen=True)
class Rule:
    rule_id: str
    version: int
    drug_class: str
    procedure_tags: tuple[str, ...]
    title: str
    message: str
    rationale: str = ""
    reference: str = ""


@dataclass(frozen=True)
class MedInput:
    entry_id: int
    original_name: str
    ingredient: str | None
    drug_class: str | None
    mapping_status: str  # mapped | staff_mapped | ambiguous | unmapped
    source_label: str
    evidence_ids: tuple[int, ...] = ()


@dataclass(frozen=True)
class SourceState:
    institution: str
    name: str
    status: str  # successful | empty | partial | denied | unavailable | invalid | not_retrieved


@dataclass(frozen=True)
class EvalInput:
    procedure_status: str  # known | none | unknown | other
    planned_procedure: str | None
    procedure_tags: tuple[str, ...]
    medications: tuple[MedInput, ...]
    sources: tuple[SourceState, ...]
    rules: tuple[Rule, ...]
    class_labels: dict = field(default_factory=dict)


@dataclass
class FlagCandidate:
    flag_key: str
    kind: str
    title: str
    message: str
    medication: str | None = None
    drug_class: str | None = None
    source_label: str | None = None
    rule_id: str | None = None
    rule_version: int | None = None
    medication_entry_id: int | None = None
    evidence_ids: list[int] = field(default_factory=list)

    def content(self) -> dict:
        d = asdict(self)
        d["evidence_ids"] = sorted(set(d["evidence_ids"]))
        return d


@dataclass
class EvalOutput:
    outcome: str  # flags | no_match | no_rules
    summary_message: str
    candidates: list[FlagCandidate]


def _group(meds: Iterable[MedInput]) -> dict[tuple[str, str], list[MedInput]]:
    """One visible flag per medicine (ingredient) and rule, however many sources record it."""
    groups: dict[tuple[str, str], list[MedInput]] = {}
    for m in meds:
        if m.ingredient and m.drug_class:
            groups.setdefault((m.ingredient, m.drug_class), []).append(m)
    return groups


def evaluate_medications(inp: EvalInput) -> EvalOutput:
    if inp.procedure_status not in {"known", "none", "unknown", "other"}:
        raise ValueError(f"invalid procedure_status {inp.procedure_status!r}")
    for r in inp.rules:
        if not r.procedure_tags:
            raise ValueError(f"rule {r.rule_id} lists no procedure tags")
    label = lambda c: inp.class_labels.get(c, c).lower()  # noqa: E731
    candidates: list[FlagCandidate] = []

    # 1. A medicine that could not be identified is reported, never assumed harmless
    for m in inp.medications:
        if m.mapping_status in {"ambiguous", "unmapped"}:
            candidates.append(FlagCandidate(
                flag_key=f"unrecognised:{m.entry_id}", kind="unrecognised_medicine",
                title=f"{UNRECOGNISED_TITLE}: {m.original_name}",
                message=("This medicine could not be matched to an ingredient and drug class, so it was not checked "
                         "against the medication rules. Check the name, or ask a clinical reviewer to add it."),
                medication=m.original_name, source_label=m.source_label, medication_entry_id=m.entry_id,
                evidence_ids=list(m.evidence_ids)))

    tags = set(inp.procedure_tags)
    mapped = [m for m in inp.medications if m.mapping_status in {"mapped", "staff_mapped"}]
    for (ingredient, drug_class), meds in sorted(_group(mapped).items()):
        matching = sorted((r for r in inp.rules if r.drug_class == drug_class), key=lambda r: r.rule_id)
        if not matching:
            continue
        name = ", ".join(sorted({m.original_name for m in meds}))
        src = "; ".join(sorted({m.source_label for m in meds}))
        ev = sorted({e for m in meds for e in m.evidence_ids})
        if inp.procedure_status in {"unknown", "other"}:
            # 2. Missing procedure context is never guessed
            candidates.append(FlagCandidate(
                flag_key=f"procedure:{ingredient}", kind="procedure_not_checked", title=PROCEDURE_TITLE,
                message=(f"{name} ({label(drug_class)}) is a current medicine. Some medication rules depend on the "
                         "planned procedure, which is not known yet, so they have not been checked. They are checked "
                         "once the procedure is recorded."),
                medication=name, drug_class=drug_class, source_label=src, evidence_ids=ev))
            continue
        if inp.procedure_status == "none":
            continue
        for r in matching:
            if tags & set(r.procedure_tags):
                candidates.append(FlagCandidate(
                    flag_key=f"rule:{r.rule_id}:{ingredient}", kind="confirmed", title=r.title, message=r.message,
                    medication=name, drug_class=drug_class, source_label=src, rule_id=r.rule_id,
                    rule_version=r.version, evidence_ids=ev))

    # 3. Incomplete records can coexist with flags; absence of a flag is not absence of a medicine
    incomplete = [s for s in inp.sources if s.status not in ("successful", "empty")]
    if incomplete:
        detail = ", ".join(f"{s.name} ({s.status.replace('_', ' ')})" for s in incomplete)
        candidates.append(FlagCandidate(
            flag_key="records_incomplete", kind="records_incomplete", title=INCOMPLETE_TITLE,
            message=(f"Medicine records are incomplete: {detail}. Flags reflect only the medicines available; "
                     "the absence of a flag does not mean the absence of a relevant medicine.")))

    confirmed = sum(1 for c in candidates if c.kind == "confirmed")
    if not inp.rules:
        outcome = "no_rules"
        summary = ("No approved medication rules are active, so medicines cannot be checked against the procedure. "
                   "A doctor must review the medicines. This is not a negative result.")
    elif confirmed:
        outcome = "flags"
        summary = f"{confirmed} medication flag(s) for the planned procedure, from approved rules."
    elif inp.procedure_status == "none":
        outcome = "no_match"
        summary = ("No procedure is planned (consultation only), so procedure-related medication rules do not apply. "
                   "This is not treatment clearance.")
    else:
        outcome = "no_match"
        summary = ("No medication flag for the planned procedure within the available current medicines and the "
                   "approved rules. This is not treatment clearance and does not mean that no relevant medicine exists.")
    return EvalOutput(outcome=outcome, summary_message=summary, candidates=candidates)
