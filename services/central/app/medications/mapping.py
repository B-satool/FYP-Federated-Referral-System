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
            hits = {(r.ingredient, r.drug_class) for r in self.rows
                    if norm == r.name or norm.startswith(r.name + " ") or f" {r.name} " in padded}
            if len(hits) == 1:
                ingredient, drug_class = hits.pop()
                return MappingResult("mapped", ingredient, drug_class)
            if len(hits) > 1:
                return MappingResult("ambiguous", note="Name matches several medicines: "
                                     + ", ".join(sorted(i for i, _ in hits)))
            notes.append(raw)
        return MappingResult("unmapped", note="Not in the medicine name list; kept as written")


def name_index(db: Session) -> NameIndex:
    return NameIndex(list(db.scalars(select(MedicineName))))
