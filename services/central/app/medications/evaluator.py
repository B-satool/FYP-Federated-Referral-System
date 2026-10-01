"""Deterministic referral-specific medication flag evaluator (FR-61 to FR-72).

Pure function over typed input: the same verified inputs and rule versions
always produce the same candidates (NFR 10.6). No language model is involved.

Outputs are *candidates*; the service layer persists them as versioned flags.
Flags never advise starting/stopping/changing medication, prescribe treatment
or assign urgency (FR-71) - messages come only from clinician-approved rules
or the fixed system wording below.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Iterable

POSSIBLE_USE_TITLE = "Possible medication use—please confirm"
HISTORY_INCOMPLETE_TITLE = "Medication history incomplete"
PROCEDURE_REQUIRED_TITLE = "Procedure context required for a medication rule"
MAPPING_TITLE = "Medication mapping unresolved"

CLASS_LABELS = {
    "anticoagulant": "anticoagulant",
    "antiplatelet": "antiplatelet agent",
    "bisphosphonate": "bisphosphonate",
    "systemic_corticosteroid": "systemic corticosteroid",
}


@dataclass(frozen=True)
class Rule:
    rule_id: str
    version: int
    drug_class: str
    specialty: str
    requires_procedure: bool
    procedures: tuple[str, ...]
    title: str
    message: str
    rationale: str = ""
    reference: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "Rule":
        return cls(
            rule_id=d["rule_id"], version=int(d["version"]), drug_class=d["drug_class"], specialty=d["specialty"],
            requires_procedure=bool(d["requires_procedure"]), procedures=tuple(d.get("procedures") or ()),
            title=d["title"], message=d["message"], rationale=d.get("rationale", ""), reference=d.get("reference", ""),
        )


@dataclass(frozen=True)
class MedInput:
    entry_id: int
    original_name: str
    ingredient: str | None
    drug_class: str | None
    mapping_status: str  # mapped | clinician_mapped | ambiguous | unmapped
    use_status: str  # unverified | confirmed_current | historical_stopped | uncertain | conflicting
    source_label: str
    evidence_ids: tuple[int, ...] = ()


@dataclass(frozen=True)
class SourceState:
    institution: str
    name: str
    medication_source: bool
    status: str  # successful | empty | partial | denied | unavailable | invalid | not_retrieved


@dataclass(frozen=True)
class EvalInput:
    specialty: str
    procedure_status: str  # known | unknown | not_stated
    planned_procedure: str | None
    medications: tuple[MedInput, ...]
    sources: tuple[SourceState, ...]
    rules: tuple[Rule, ...]


@dataclass
class FlagCandidate:
    flag_key: str
    kind: str
    title: str
    message: str
    medication: str | None = None
    drug_class: str | None = None
    current_use_status: str | None = None
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
    outcome: str  # flags | no_match | unsupported_coverage
    summary_message: str
    candidates: list[FlagCandidate]


def _label(drug_class: str | None) -> str:
    return CLASS_LABELS.get(drug_class or "", drug_class or "unclassified medication")


def _group(meds: Iterable[MedInput]) -> dict[tuple[str, str], list[MedInput]]:
    """Group by (ingredient, class) so one medication/rule match yields one visible flag."""
    groups: dict[tuple[str, str], list[MedInput]] = {}
    for m in meds:
        if m.ingredient and m.drug_class:
            groups.setdefault((m.ingredient, m.drug_class), []).append(m)
    return groups


def evaluate_medications(inp: EvalInput) -> EvalOutput:
    if inp.procedure_status not in {"known", "unknown", "not_stated"}:
        raise ValueError(f"invalid procedure_status {inp.procedure_status!r}")
    for r in inp.rules:
        if r.requires_procedure and not r.procedures:
            raise ValueError(f"rule {r.rule_id} requires a procedure but lists none")

    rules = [r for r in inp.rules if r.specialty == inp.specialty]
    candidates: list[FlagCandidate] = []

    # 1. Mapping problems: never presented as confirmed matches (FR-62)
    for m in inp.medications:
        if m.use_status == "historical_stopped":
            continue
        if m.mapping_status in {"ambiguous", "unmapped"}:
            candidates.append(FlagCandidate(
                flag_key=f"mapping:{m.entry_id}", kind="ambiguous_mapping", title=f"{MAPPING_TITLE}: {m.original_name}",
                message=("This medication could not be mapped to a verified ingredient and drug class, so it was not "
                         "evaluated against medication rules. Clarify the medication."),
                medication=m.original_name, current_use_status=m.use_status, source_label=m.source_label,
                medication_entry_id=m.entry_id, evidence_ids=list(m.evidence_ids),
            ))

    mapped = [m for m in inp.medications if m.mapping_status in {"mapped", "clinician_mapped"}]
    for (ingredient, drug_class), meds in sorted(_group(mapped).items()):
        matching_rules = sorted((r for r in rules if r.drug_class == drug_class), key=lambda r: r.rule_id)
        if not matching_rules:
            continue
        confirmed = [m for m in meds if m.use_status == "confirmed_current"]
        possible = [m for m in meds if m.use_status in {"unverified", "uncertain", "conflicting"}]
        if not confirmed:
            if possible:
                # 2. Uncertain use: prompt, never a confirmed flag (FR-63, FR-66)
                candidates.append(FlagCandidate(
                    flag_key=f"possible:{ingredient}", kind="possible_use", title=POSSIBLE_USE_TITLE,
                    message=(f"{', '.join(sorted({m.original_name for m in possible}))} ({_label(drug_class)}) is recorded "
                             f"but current use is not confirmed ({', '.join(sorted({m.use_status for m in possible}))}). "
                             "Confirm current use; related rules have not been applied as confirmed."),
                    medication=", ".join(sorted({m.original_name for m in possible})), drug_class=drug_class,
                    current_use_status=sorted({m.use_status for m in possible})[0],
                    source_label="; ".join(sorted({m.source_label for m in possible})),
                    evidence_ids=sorted({e for m in possible for e in m.evidence_ids}),
                ))
            continue  # historical/stopped only -> no current-use flag
        ev = sorted({e for m in confirmed for e in m.evidence_ids})
        src = "; ".join(sorted({m.source_label for m in confirmed}))
        name = ", ".join(sorted({m.original_name for m in confirmed}))
        for r in matching_rules:
            if r.requires_procedure:
                if inp.procedure_status != "known" or not inp.planned_procedure:
                    # 3. Missing procedure context is never guessed (FR-64)
                    candidates.append(FlagCandidate(
                        flag_key=f"procedure:{r.rule_id}:{ingredient}", kind="procedure_context_required",
                        title=PROCEDURE_REQUIRED_TITLE,
                        message=(f"{name} ({_label(drug_class)}) is confirmed current. Rule {r.rule_id} depends on the planned "
                                 "procedure, which is not known, so it has not been evaluated. Clarify the planned procedure."),
                        medication=name, drug_class=drug_class, current_use_status="confirmed_current", source_label=src,
                        rule_id=r.rule_id, rule_version=r.version, evidence_ids=ev,
                    ))
                    continue
                if inp.planned_procedure not in r.procedures:
                    continue
            candidates.append(FlagCandidate(
                flag_key=f"rule:{r.rule_id}:{ingredient}", kind="confirmed", title=r.title, message=r.message,
                medication=name, drug_class=drug_class, current_use_status="confirmed_current", source_label=src,
                rule_id=r.rule_id, rule_version=r.version, evidence_ids=ev,
            ))

    # 4. Incomplete history may coexist with confirmed flags (FR-66)
    incomplete = [s for s in inp.sources if s.medication_source and s.status != "successful"]
    if incomplete:
        detail = ", ".join(f"{s.name} ({s.status.replace('_', ' ')})" for s in incomplete)
        candidates.append(FlagCandidate(
            flag_key="history_incomplete", kind="history_incomplete", title=HISTORY_INCOMPLETE_TITLE,
            message=(f"Medication records are incomplete: {detail}. Flags reflect only the available verified records; "
                     "absence of a flag does not mean absence of relevant medication."),
        ))

    confirmed_count = sum(1 for c in candidates if c.kind == "confirmed")
    supported = sorted({_label(r.drug_class) for r in rules})
    if not rules:
        outcome = "unsupported_coverage"
        summary = (f"No approved medication rules are active for {inp.specialty}. Medication flags cannot be evaluated; "
                   "manual clinician review is required. This is not a negative result.")
    elif confirmed_count:
        outcome = "flags"
        summary = f"{confirmed_count} referral-specific medication flag(s) from approved rules."
    else:
        outcome = "no_match"
        summary = ("No matching medication flag within the available verified records and the supported rules "
                   f"({', '.join(supported)}). This is not treatment clearance and does not mean that no relevant "
                   "medications exist.")
    return EvalOutput(outcome=outcome, summary_message=summary, candidates=candidates)
