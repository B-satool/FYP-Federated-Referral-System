"""Medicine-name mapping (brand or generic name as written -> ingredient and drug class).

Names live in the database (medicine_names) and are maintained in the app by clinical
reviewers. The original name is always kept by the caller; unknown names stay
unmapped and are reported, never guessed. A name that matches more than one
ingredient is ambiguous and is never treated as a match.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import MedicineName

FORM_WORDS = {
    "tablet", "tablets", "tab", "tabs", "capsule", "capsules", "cap", "caps", "sachet", "sachets", "syrup", "susp",
    "suspension", "injection", "inj", "mg", "mcg", "g", "ml", "units", "unit", "iu", "oral", "po", "od", "bd", "tds",
    "daily", "once", "twice", "weekly", "film", "coated", "ec", "sr", "xr", "er", "sodium", "potassium", "with",
    "and", "per", "x", "months", "month", "days", "day", "at", "night",
}
STRENGTH = re.compile(r"(\d+(?:\.\d+)?)\s?(mg|mcg|g|ml|units?|iu)\b", re.I)


# Brand names from the DRAP product register (rules/terminology/drap). Thousands of them, not checked one
# by one, so they are matched more strictly than the hand-checked list: only where the written name starts
# with the brand, never inside other words ("Vitamin" is a register brand), and very short names or
# ordinary words are not loaded at all (see usable_register_name).
REGISTER_KIND = "register_brand"
REGISTER_NOTE = "Brand from the DRAP product register"
AMBIGUOUS_KIND = "register_ambiguous"  # a register name used for two different medicines (ingredient lists them)
COMMON_WORDS = {
    "vitamin", "calcium", "iron", "zinc", "magnesium", "plus", "forte", "extra", "super", "max", "care", "gold", "new",
    "one", "kids", "baby", "junior", "adult", "relief", "pain", "cold", "flu", "cough", "fever", "gel", "cream",
    "drops", "drop", "spray", "neuro", "cardio", "gastro", "liver", "heart", "bone", "joint", "fast", "rapid", "plain",
    "child", "children", "infant", "paed", "ped", "mini", "micro", "tabs", "pharma", "medicine", "tonic", "capsule",
    "insulin", "tablet", "syrup", "dry", "powder", "solution", "liquid", "lotion", "ointment", "injection",
}


def usable_register_name(key: str) -> bool:
    """A normalised register name that is safe to match: at least 3 letters and not an ordinary word."""
    return sum(c.isalpha() for c in key) >= 3 and key not in COMMON_WORDS


@dataclass(frozen=True)
class MappingResult:
    status: str  # mapped | ambiguous | unmapped
    ingredient: str | None = None
    drug_class: str | None = None
    note: str | None = None


def normalize(name: str) -> str:
    text = name.lower().replace("+", " ")
    text = re.sub(r"[\d.,/%()\-:]+", " ", text)
    return " ".join(t for t in text.split() if t and t not in FORM_WORDS)


def strength_of(*texts: str | None) -> str | None:
    """'75 mg' style strength from the first text that has one (for grouping duplicates)."""
    for t in texts:
        if t:
            m = STRENGTH.search(t)
            if m:
                unit = m.group(2).lower().rstrip("s") if m.group(2).lower().startswith("unit") else m.group(2).lower()
                value = float(m.group(1))
                return f"{value:g} {unit}"
    return None


def _kind(row) -> str:
    return getattr(row, "kind", "brand")


class NameIndex:
    def __init__(self, rows: list[MedicineName]):
        self.rows = [r for r in rows if r.status == "active"]

    def map(self, *names: str | None) -> MappingResult:
        """Try each name (e.g. the recorded name, then the brand as written)."""
        notes = []
        for raw in names:
            if not raw:
                continue
            norm = normalize(raw)
            if not norm:
                continue
            padded = f" {norm} "
            matched = [r for r in self.rows
                       if norm == r.name or norm.startswith(r.name + " ")
                       or (_kind(r) not in (REGISTER_KIND, AMBIGUOUS_KIND) and f" {r.name} " in padded)]
            clash = [r for r in matched if _kind(r) == AMBIGUOUS_KIND]
            matched = [r for r in matched if _kind(r) != AMBIGUOUS_KIND]
            if clash and not matched:
                options = clash[0].ingredient.replace(" | ", " or ")
                return MappingResult("ambiguous", note=f"{clash[0].display} is registered in Pakistan for different medicines: "
                                     f"{options}. Check the pack or ask the patient, then add the generic name.")
            hits = {(r.ingredient, r.drug_class) for r in matched}
            if len(hits) == 1:
                ingredient, drug_class = hits.pop()
                register_only = all(_kind(r) == REGISTER_KIND for r in matched)
                return MappingResult("mapped", ingredient, drug_class, REGISTER_NOTE if register_only else None)
            if len(hits) > 1:
                return MappingResult("ambiguous", note="Name matches several medicines: "
                                     + ", ".join(sorted(i for i, _ in hits)))
            notes.append(raw)
        return MappingResult("unmapped", note="Not in the medicine name list; kept as written")


def name_index(db: Session) -> NameIndex:
    return NameIndex(list(db.scalars(select(MedicineName))))
