"""Deterministic medication flag evaluator.

Pure function over typed input: the same current medicines, procedure, conditions and rule set
always produce the same candidates. No language model is involved at evaluation time.

Three kinds of rule, all stored data:
* approved manual rules: drug class x procedure features, approved by a clinical reviewer;
* drug-drug interactions imported from DDInter (severity is DDInter's, unchanged);
* drug-condition and drug-procedure rules read from US drug labels by script, each with the exact
  sentence it relies on. Imported rules are marked automatically generated, not clinically reviewed.

Flags never advise starting, stopping or changing a medicine, never prescribe treatment and never
assign urgency. Their wording comes from approved rules, the label summary template, or the fixed
system wording below. Nothing is ever reported as "safe": no match means no matching rule on file.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from itertools import combinations
from typing import Iterable

UNRECOGNISED_TITLE = "Medicine not recognised"
PROCEDURE_TITLE = "Procedure not known yet: medicine not checked against it"
INCOMPLETE_TITLE = "Medicine records incomplete"
NOT_IN_SOURCE_TITLE = "Interactions not checked"
NO_RULE = "No matching rule on file"
DDINTER = "DDInter 2.0"


@dataclass(frozen=True)
class Rule:
    """An approved manual rule (drug class x procedure features)."""
    rule_id: str
    version: int
    drug_class: str
    procedure_tags: tuple[str, ...]
    title: str
    message: str
    rationale: str = ""
    reference: str = ""


@dataclass(frozen=True)
class Interaction:
    ingredient_a: str
    ingredient_b: str
    severity: str  # Major | Moderate | Minor | Unknown (DDInter's level)
    source_ref: str
    source_version: str


@dataclass(frozen=True)
class LabelRule:
    rule_key: str
    kind: str  # drug_condition | drug_procedure
    ingredient: str
    target: str
    target_label: str
    severity_hint: str  # high | moderate | low
    summary: str
    quote: str
    section: str
    source_name: str
    source_ref: str
    source_version: str


@dataclass(frozen=True)
class MedInput:
    entry_id: int
    original_name: str
    ingredient: str | None
    drug_class: str | None
    mapping_status: str  # mapped | staff_mapped | ambiguous | unmapped
    source_label: str
    evidence_ids: tuple[int, ...] = ()
    ingredients: tuple[str, ...] = ()  # all parts of a combination product (defaults to the ingredient)


@dataclass(frozen=True)
class SourceState:
    institution: str
    name: str
    status: str  # successful | empty | partial | denied | unavailable | invalid | not_retrieved


@dataclass(frozen=True)
class EvalInput:
    procedure_status: str  # planned | none | unknown
    planned_procedure: str | None
    procedure_tags: tuple[str, ...]
    medications: tuple[MedInput, ...]
    sources: tuple[SourceState, ...]
    rules: tuple[Rule, ...]
    class_labels: dict = field(default_factory=dict)
    interactions: tuple[Interaction, ...] = ()
    label_rules: tuple[LabelRule, ...] = ()
    conditions: tuple[str, ...] = ()  # condition categories from the patient's current recorded conditions
    interaction_coverage: frozenset[str] = frozenset()  # ingredients present in the interaction source


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
    severity: str | None = None
    ingredients: list[str] = field(default_factory=list)
    source_type: str | None = None
    source_name: str | None = None
    source_ref: str | None = None
    source_version: str | None = None
    source_quote: str | None = None
    auto_generated: bool = False
    requires_decision: bool = True

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


def _parts(m: MedInput) -> tuple[str, ...]:
    return m.ingredients or ((m.ingredient,) if m.ingredient else ())


def _by_ingredient(mapped: list[MedInput]) -> dict[str, list[MedInput]]:
    out: dict[str, list[MedInput]] = {}
    for m in mapped:
        for i in _parts(m):
            out.setdefault(i, []).append(m)
    return out


def _who(meds: list[MedInput]) -> tuple[str, str, list[int]]:
    return (", ".join(sorted({m.original_name for m in meds})), "; ".join(sorted({m.source_label for m in meds})),
            sorted({e for m in meds for e in m.evidence_ids}))


def _interaction_flags(inp: EvalInput, by_ing: dict[str, list[MedInput]]) -> list[FlagCandidate]:
    table = {(x.ingredient_a, x.ingredient_b): x for x in inp.interactions}
    out = []
    for a, b in combinations(sorted(by_ing), 2):
        # two parts of one combination product are not reported as interacting with each other
        if {m.entry_id for m in by_ing[a]} == {m.entry_id for m in by_ing[b]} and len(by_ing[a]) == 1:
            continue
        x = table.get((a, b))
        if x is None:
            continue
        meds = by_ing[a] + by_ing[b]
        name, src, ev = _who(meds)
        level = "not graded by DDInter" if x.severity == "Unknown" else x.severity.lower()
        out.append(FlagCandidate(
            flag_key=f"ddi:{a}:{b}", kind="interaction", title=f"Drug interaction recorded: {a} and {b}",
            message=(f"{DDINTER} records an interaction between {a} and {b} (severity: {level}). "
                     "Shown for the doctor to read; it is not advice to change either medicine."),
            medication=name, source_label=src, evidence_ids=ev, severity=x.severity, ingredients=[a, b],
            source_type="ddinter", source_name=DDINTER, source_ref=x.source_ref, source_version=x.source_version,
            auto_generated=True, requires_decision=x.severity == "Major"))
    return out


def _label_flags(inp: EvalInput, by_ing: dict[str, list[MedInput]], tags: set[str]) -> list[FlagCandidate]:
    conditions = set(inp.conditions)
    out = []
    for r in sorted(inp.label_rules, key=lambda r: r.rule_key):
        if r.ingredient not in by_ing:
            continue
        if r.kind == "drug_procedure" and not (inp.procedure_status == "planned" and r.target in tags):
            continue
        if r.kind == "drug_condition" and r.target not in conditions:
            continue
        name, src, ev = _who(by_ing[r.ingredient])
        what = "the planned procedure" if r.kind == "drug_procedure" else "a recorded condition"
        out.append(FlagCandidate(
            flag_key=r.rule_key, kind="label_warning", title=f"Drug label: {r.ingredient} and {r.target_label} ({what})",
            message=r.summary, medication=name, source_label=src, evidence_ids=ev, severity=r.severity_hint,
            ingredients=[r.ingredient], source_type="drug_label", source_name=r.source_name, source_ref=r.source_ref,
            source_version=r.source_version, source_quote=r.quote, auto_generated=True,
            requires_decision=r.severity_hint == "high"))
    return out


def evaluate_medications(inp: EvalInput) -> EvalOutput:
    if inp.procedure_status not in {"planned", "none", "unknown"}:
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
                message=("This medicine could not be matched to an ingredient, so it was not checked against the "
                         "medication rules, drug interactions or drug labels. Check the name, or ask a clinical "
                         "reviewer to add it."),
                medication=m.original_name, source_label=m.source_label, medication_entry_id=m.entry_id,
                evidence_ids=list(m.evidence_ids), source_type="system"))

    tags = set(inp.procedure_tags)
    mapped = [m for m in inp.medications if m.mapping_status in {"mapped", "staff_mapped"}]
    label_proc_ingredients = {r.ingredient for r in inp.label_rules if r.kind == "drug_procedure"}
    for (ingredient, drug_class), meds in sorted(_group(mapped).items()):
        matching = sorted((r for r in inp.rules if r.drug_class == drug_class), key=lambda r: r.rule_id)
        name, src, ev = _who(meds)
        if inp.procedure_status == "unknown" or (inp.procedure_status == "planned" and not tags):
            if not matching and not ({i for m in meds for i in _parts(m)} & label_proc_ingredients):
                continue
            # 2. Missing procedure context is never guessed
            why = ("which is not known yet" if inp.procedure_status == "unknown"
                   else "whose features (surgery, anaesthesia, contrast and so on) were not recorded")
            candidates.append(FlagCandidate(
                flag_key=f"procedure:{ingredient}", kind="procedure_not_checked", title=PROCEDURE_TITLE,
                message=(f"{name} ({label(drug_class)}) is a current medicine. Some medication rules depend on the "
                         f"planned procedure, {why}, so they have not been checked. They are checked "
                         "once this is recorded."),
                medication=name, drug_class=drug_class, source_label=src, evidence_ids=ev, source_type="system"))
            continue
        if inp.procedure_status == "none":
            continue
        for r in matching:
            if tags & set(r.procedure_tags):
                candidates.append(FlagCandidate(
                    flag_key=f"rule:{r.rule_id}:{ingredient}", kind="confirmed", title=r.title, message=r.message,
                    medication=name, drug_class=drug_class, source_label=src, rule_id=r.rule_id,
                    rule_version=r.version, evidence_ids=ev, ingredients=[ingredient], source_type="manual_rule",
                    source_name="Rule approved by a clinical reviewer", source_ref=r.reference or None,
                    source_version=f"{r.rule_id} v{r.version}"))

    # 3. Drug-drug interactions and drug-label rules (imported, automatically generated)
    by_ing = _by_ingredient(mapped)
    candidates += _interaction_flags(inp, by_ing)
    candidates += _label_flags(inp, by_ing, tags)
    if inp.interactions:
        missing = sorted(i for i in by_ing if i not in inp.interaction_coverage)
        if missing:
            candidates.append(FlagCandidate(
                flag_key="interactions_not_checked", kind="interactions_not_checked", title=NOT_IN_SOURCE_TITLE,
                message=(f"Not in the interaction source ({DDINTER}): {', '.join(missing)}. Interactions involving "
                         "these medicines could not be checked; this does not mean there are none."),
                ingredients=missing, source_type="system"))

    # 4. Incomplete records can coexist with flags; absence of a flag is not absence of a medicine
    incomplete = [s for s in inp.sources if s.status not in ("successful", "empty")]
    if incomplete:
        detail = ", ".join(f"{s.name} ({s.status.replace('_', ' ')})" for s in incomplete)
        candidates.append(FlagCandidate(
            flag_key="records_incomplete", kind="records_incomplete", title=INCOMPLETE_TITLE,
            message=(f"Medicine records are incomplete: {detail}. Flags reflect only the medicines available; "
                     "the absence of a flag does not mean the absence of a relevant medicine."), source_type="system"))

    count = {k: sum(1 for c in candidates if c.kind == k) for k in ("confirmed", "interaction", "label_warning")}
    if not inp.rules and not inp.interactions and not inp.label_rules:
        outcome = "no_rules"
        summary = ("No medication rules or interaction data are loaded, so medicines cannot be checked. "
                   "A doctor must review the medicines. This is not a negative result.")
    elif any(count.values()):
        outcome = "flags"
        parts = [f"{count['confirmed']} from approved rules" if count["confirmed"] else "",
                 f"{count['interaction']} drug interaction(s) from {DDINTER}" if count["interaction"] else "",
                 f"{count['label_warning']} from drug labels" if count["label_warning"] else ""]
        summary = "Medication flags: " + ", ".join(p for p in parts if p) + ". Imported flags are automatically generated and not clinically reviewed."
    elif inp.procedure_status == "none":
        outcome = "no_match"
        summary = (f"{NO_RULE} for these medicines. No procedure is planned (consultation only), so procedure "
                   "rules do not apply. This is not treatment clearance.")
    else:
        outcome = "no_match"
        summary = (f"{NO_RULE} for the available current medicines, the planned procedure and the recorded conditions. "
                   "This is not treatment clearance and does not mean that no relevant interaction exists.")
    return EvalOutput(outcome=outcome, summary_message=summary, candidates=candidates)
