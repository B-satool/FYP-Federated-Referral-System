"""Checks applied to every rule read from a drug label before it is stored (pure, stdlib only).

Used by scripts/extract_label_rules.py and tested in services/central/tests. A candidate is kept only if:
* the quoted sentence appears verbatim (ignoring whitespace) in the label section it cites,
* the ingredient is one of ours,
* the target is in the controlled vocabulary for its kind,
* the summary does not advise starting, stopping or changing a medicine (FR-71).
Sentences are matched to targets by fixed word patterns, so the same label always gives the same rules.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

ADVICE = re.compile(r"\b(stop|stopping|discontinue|discontinuing|withhold|withholding|do not take|start taking|increase the dose|"
                    r"reduce the dose|decrease the dose|switch to|should be stopped|hold the)\b", re.I)
KINDS = ("drug_condition", "drug_procedure")
SECTION_TITLES = {"boxed_warning": "Boxed warning", "contraindications": "Contraindications",
                  "warnings_and_cautions": "Warnings and precautions", "warnings": "Warnings", "precautions": "Precautions"}


@dataclass(frozen=True)
class Candidate:
    ingredient: str
    kind: str
    target: str
    severity_hint: str
    summary: str
    quote: str
    section: str


def squash(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def term_regex(term: str) -> re.Pattern:
    """Whole words, case-insensitive; a trailing * matches any ending (procedure* -> procedures)."""
    body = re.escape(term.rstrip("*")).replace(r"\ ", r"\s+")
    end = r"\w*" if term.endswith("*") else r"\b"
    return re.compile(r"\b" + body + end, re.I)


def matches(sentence: str, spec: dict) -> bool:
    if any(term_regex(t).search(sentence) for t in spec.get("exclude", [])):
        return False
    return all(any(term_regex(t).search(sentence) for t in group) for group in spec["groups"])


def sentences(text: str) -> list[str]:
    """Split label text into sentences (labels use '. ' and bullet characters)."""
    text = squash(re.sub(r"[•▪◦]", ". ", text or ""))
    parts = re.split(r"(?<=[.;!?])\s+(?=[A-Z(])", text)
    return [p.strip() for p in parts if 20 <= len(p.strip()) <= 600]


def validate(c: Candidate, section_text: str, ingredients: set[str], vocab: dict) -> list[str]:
    """Reasons to reject the candidate (empty list = accepted)."""
    problems = []
    if c.kind not in KINDS:
        problems.append(f"unknown kind {c.kind!r}")
    targets = vocab.get("procedure" if c.kind == "drug_procedure" else "condition", {})
    if c.target not in targets:
        problems.append(f"target {c.target!r} is not in the vocabulary")
    if c.ingredient not in ingredients:
        problems.append(f"ingredient {c.ingredient!r} is not one of ours")
    if not c.quote or squash(c.quote).lower() not in squash(section_text).lower():
        problems.append("quote is not found verbatim in the label section")
    if ADVICE.search(c.summary):
        problems.append("summary advises starting, stopping or changing a medicine")
    if len(c.summary.split()) > 25:
        problems.append("summary longer than 25 words")
    if c.section not in SECTION_TITLES:
        problems.append(f"section {c.section!r} is not a section used for rules")
    return problems


def summary_for(ingredient: str, section: str, target_label: str) -> str:
    """Fixed wording: says where the label mentions the topic, never what to do."""
    return f"The {ingredient} label ({SECTION_TITLES[section].lower()}) refers to {target_label}."


def patient_categories(condition_texts: list[str], vocab: dict) -> set[str]:
    """Condition categories for a patient's recorded current conditions (fixed word lists)."""
    out = set()
    for text in condition_texts:
        for key, spec in vocab.get("condition", {}).items():
            if any(term_regex(t).search(text) for t in spec.get("patient_terms", [])):
                out.add(key)
    return out
