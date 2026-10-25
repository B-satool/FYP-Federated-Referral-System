"""Deterministic rule-based field extractor ("rules-extractor/2").

Used when no language model is configured (or EXTRACTION_MODE=rules). It only
proposes medicine and laboratory fields; anything it cannot parse is left
missing rather than guessed. Every proposal is checked by staff before use.
"""
from __future__ import annotations

import re
from datetime import date

VERSION = "rules-extractor/2"

STRENGTH = re.compile(r"(\d+(?:\.\d+)?)\s?(mg|mcg|g|ml|iu|units?)\b", re.I)
FREQUENCIES = [
    # Pakistani prescription notation: morning + afternoon + night
    (re.compile(r"\b1\s*\+\s*0\s*\+\s*0\b"), "once daily (morning)"),
    (re.compile(r"\b0\s*\+\s*1\s*\+\s*0\b"), "once daily (afternoon)"),
    (re.compile(r"\b0\s*\+\s*0\s*\+\s*1\b"), "once daily (night)"),
    (re.compile(r"\b1\s*\+\s*0\s*\+\s*1\b"), "twice daily"),
    (re.compile(r"\b1\s*\+\s*1\s*\+\s*1\b"), "three times daily"),
    (re.compile(r"\b(once daily|od|daily|once a day)\b", re.I), "once daily"),
    (re.compile(r"\b(twice daily|bd|bid|twice a day)\b", re.I), "twice daily"),
    (re.compile(r"\b(three times daily|tds|tid)\b", re.I), "three times daily"),
    (re.compile(r"\b(at night|nocte|hs)\b", re.I), "at night"),
    (re.compile(r"\b(once weekly|weekly)\b", re.I), "once weekly"),
    (re.compile(r"\b(as needed|prn|sos|when required)\b", re.I), "as needed"),
]
ROUTE = re.compile(r"\b(oral|orally|po|by mouth|iv|im|sc|subcutaneous)\b", re.I)
DATE = re.compile(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\b")
NUM = r"[^\d\n]{0,25}?(\d+(?:\.\d+)?)"
LABS = [
    (re.compile(r"\bINR\b" + NUM, re.I), "INR", "6301-6", "{INR}"),
    (re.compile(r"\b(?:h(?:a)?emoglobin|hb)\b(?!\s*a1c)" + NUM, re.I), "Haemoglobin", "718-7", "g/dL"),
    (re.compile(r"\bplatelets?\b" + NUM, re.I), "Platelets", "777-3", "10*9/L"),
    (re.compile(r"\b(?:wbc|white (?:blood )?cells?)\b" + NUM, re.I), "WBC", "6690-2", "10*9/L"),
    (re.compile(r"\bhba1c\b" + NUM, re.I), "HbA1c", "4548-4", "%"),
    (re.compile(r"\bglucose\b" + NUM, re.I), "Glucose", "2345-7", "mg/dL"),
    (re.compile(r"\bcreatinine\b" + NUM, re.I), "Creatinine", "2160-0", "mg/dL"),
    (re.compile(r"\begfr\b" + NUM, re.I), "eGFR", "62238-1", "mL/min/1.73m2"),
    (re.compile(r"\b(?:alt|sgpt)\b" + NUM, re.I), "ALT", "1742-6", "U/L"),
    (re.compile(r"\b(?:ast|sgot)\b" + NUM, re.I), "AST", "1920-8", "U/L"),
    (re.compile(r"\b(?:alp|alkaline phosphatase)\b" + NUM, re.I), "ALP", "6768-6", "U/L"),
    (re.compile(r"\b(?:total )?bilirubin\b" + NUM, re.I), "Total bilirubin", "1975-2", "mg/dL"),
    (re.compile(r"\balbumin\b" + NUM, re.I), "Albumin", "1751-7", "g/dL"),
    (re.compile(r"\b(?:total )?cholesterol\b" + NUM, re.I), "Total cholesterol", "2093-3", "mg/dL"),
    (re.compile(r"\bldl\b" + NUM, re.I), "LDL cholesterol", "13457-7", "mg/dL"),
    (re.compile(r"\btriglycerides?\b" + NUM, re.I), "Triglycerides", "2571-8", "mg/dL"),
    (re.compile(r"\bferritin\b" + NUM, re.I), "Ferritin", "2276-4", "ng/mL"),
    (re.compile(r"\bvitamin d\b" + NUM, re.I), "Vitamin D (25-OH)", "1989-3", "ng/mL"),
    (re.compile(r"\bpotassium\b" + NUM, re.I), "Potassium", "2823-3", "mmol/L"),
    (re.compile(r"\bsodium\b" + NUM, re.I), "Sodium", "2951-2", "mmol/L"),
]


def parse_date(text: str) -> str | None:
    m = DATE.search(text)
    if not m:
        return None
    d, mth, y = (int(x) for x in m.groups())
    try:
        return date(y, mth, d).isoformat()
    except ValueError:
        return None


def extract(lines: list[dict], names: list[str]) -> dict:
    """lines: [{"i", "page", "text"}]; names: known medicine names (lowercase).
    Returns {"medications": [...], "labs": [...], "document_date": str|None}."""
    names = sorted({n for n in names if len(n) >= 3}, key=len, reverse=True)
    meds, labs = [], []
    doc_date = None
    for ln in lines:
        text = ln["text"]
        low = text.lower()
        if doc_date is None and re.search(r"\bdate\b", low):
            doc_date = parse_date(text)
        for name in names:
            m = re.search(rf"(?<![a-z]){re.escape(name)}(?![a-z])", low)
            if not m:
                continue
            strength = STRENGTH.search(text[m.end():]) or STRENGTH.search(text)
            freq = next((label for rx, label in FREQUENCIES if rx.search(text)), None)
            route = ROUTE.search(text)
            med_name = text[m.start():m.end()].strip()
            med_name = med_name.title() if med_name.islower() else med_name
            strength_txt = f"{strength.group(1)} {strength.group(2)}" if strength else None
            if strength_txt:
                med_name = f"{med_name} {strength_txt}"
            meds.append({
                "name": med_name, "strength": strength_txt,
                "dose": " ".join(p for p in [strength_txt, freq] if p) or None,
                "route": ("oral" if route and route.group(1).lower() in ("oral", "orally", "po", "by mouth") else
                          route.group(1).lower() if route else None),
                "frequency": freq, "start_date": parse_date(text), "line_ids": [ln["i"]],
            })
            break
        for rx, test, loinc, unit in LABS:
            m = rx.search(text)
            if m:
                labs.append({"test": test, "loinc": loinc, "value": float(m.group(1)), "unit": unit,
                             "date": parse_date(text), "line_ids": [ln["i"]]})
    return {"medications": meds, "labs": labs, "document_date": doc_date}
