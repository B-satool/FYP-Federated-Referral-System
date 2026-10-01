"""Deterministic rule-based field extractor ("rules-extractor/1").

Used when no language model is configured (or EXTRACTION_MODE=rules). It only
proposes the supported medication and laboratory fields; anything it cannot
parse is left missing rather than guessed (FR-27, FR-32).
"""
from __future__ import annotations

import re
from datetime import date

from ..medications.mapping import dictionary

VERSION = "rules-extractor/1"

STRENGTH = re.compile(r"(\d+(?:\.\d+)?)\s?(mg|mcg|g|ml|iu)\b", re.I)
FREQUENCIES = [
    (re.compile(r"\b(once daily|od|daily|once a day)\b", re.I), "once daily"),
    (re.compile(r"\b(twice daily|bd|bid|twice a day)\b", re.I), "twice daily"),
    (re.compile(r"\b(three times daily|tds|tid)\b", re.I), "three times daily"),
    (re.compile(r"\b(at night|nocte)\b", re.I), "at night"),
    (re.compile(r"\b(once weekly|weekly)\b", re.I), "once weekly"),
]
ROUTE = re.compile(r"\b(oral|orally|po|by mouth|iv|im|sc)\b", re.I)
DATE = re.compile(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\b")
LABS = [
    (re.compile(r"\bINR\b[^\d]{0,12}(\d+(?:\.\d+)?)", re.I), "INR", "6301-6", "{INR}"),
    (re.compile(r"\b(?:h(?:a)?emoglobin|hb)\b(?!a1c)[^\d]{0,12}(\d+(?:\.\d+)?)\s*(g/dl)?", re.I), "Hemoglobin", "718-7", "g/dL"),
    (re.compile(r"\bplatelets?\b[^\d]{0,12}(\d+(?:\.\d+)?)", re.I), "Platelets", "777-3", "10*9/L"),
    (re.compile(r"\bhba1c\b[^\d]{0,12}(\d+(?:\.\d+)?)\s*(%)?", re.I), "HbA1c", "4548-4", "%"),
]


def _names() -> list[str]:
    d = dictionary()
    names = [n for e in d["entries"] for n in e["names"]] + [n for a in d.get("ambiguous", []) for n in a["names"]]
    return sorted(set(names), key=len, reverse=True)


def parse_date(text: str) -> str | None:
    m = DATE.search(text)
    if not m:
        return None
    d, mth, y = (int(x) for x in m.groups())
    try:
        return date(y, mth, d).isoformat()
    except ValueError:
        return None


def extract(lines: list[dict]) -> dict:
    """lines: [{"i", "page", "text"}] -> {"medications": [...], "labs": [...], "document_date": str|None}"""
    names = _names()
    meds, labs = [], []
    doc_date = None
    for ln in lines:
        text = ln["text"]
        low = text.lower()
        if doc_date is None and re.search(r"\bdate\b", low):
            doc_date = parse_date(text)
        for name in names:
            if re.search(rf"(?<![a-z]){re.escape(name)}(?![a-z])", low):
                strength = STRENGTH.search(text)
                freq = next((label for rx, label in FREQUENCIES if rx.search(text)), None)
                route = ROUTE.search(text)
                start = text[low.index(name): low.index(name) + len(name)]
                med_name = start.strip()
                if strength:
                    med_name = f"{med_name} {strength.group(1)} {strength.group(2)}"
                dose_parts = [p for p in [f"{strength.group(1)} {strength.group(2)}" if strength else None, freq] if p]
                meds.append({
                    "name": med_name.title() if med_name.islower() else med_name,
                    "strength": f"{strength.group(1)} {strength.group(2)}" if strength else None,
                    "dose": " ".join(dose_parts) or None,
                    "route": ("oral" if route and route.group(1).lower() in ("oral", "orally", "po", "by mouth") else
                              route.group(1).upper() if route else None),
                    "frequency": freq,
                    "start_date": parse_date(text),
                    "line_ids": [ln["i"]],
                })
                break
        for rx, test, loinc, unit in LABS:
            m = rx.search(text)
            if m:
                labs.append({"test": test, "loinc": loinc, "value": float(m.group(1)), "unit": unit,
                             "date": parse_date(text), "line_ids": [ln["i"]]})
    return {"medications": meds, "labs": labs, "document_date": doc_date}
