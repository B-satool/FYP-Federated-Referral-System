"""Bounded medication terminology mapping (FR-33, FR-34, FR-62).

The original documented name is always preserved by the caller; this module
only proposes an ingredient/class. Unknown names stay unmapped and usable in
their original form; ambiguous or merely 'suggested' names are never treated
as verified mappings.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache

from ..config import settings

FORM_WORDS = {
    "tablet", "tablets", "tab", "tabs", "capsule", "capsules", "cap", "caps", "sachet", "sachets", "syrup",
    "suspension", "injection", "inj", "mg", "mcg", "g", "ml", "oral", "po", "od", "bd", "tds", "daily",
    "once", "twice", "weekly", "film", "coated", "ec", "sr", "xr", "er", "sodium",
}


@dataclass(frozen=True)
class MappingResult:
    status: str  # mapped | ambiguous | unmapped
    ingredient: str | None = None
    ingredient_code: str | None = None
    drug_class: str | None = None
    class_code: str | None = None
    source: str = ""
    version: str = ""
    note: str | None = None


@lru_cache
def dictionary() -> dict:
    path = settings.repo_root / "rules" / "terminology" / "medication-dictionary.v1.json"
    return json.loads(path.read_text(encoding="utf-8"))


def source_label() -> tuple[str, str]:
    d = dictionary()
    return d["dictionary_id"], d["version"]


def normalize(name: str) -> str:
    text = name.lower()
    text = re.sub(r"[\d.,/%()+\-]+", " ", text)
    tokens = [t for t in text.split() if t and t not in FORM_WORDS]
    return " ".join(tokens)


def class_label(drug_class: str | None) -> str:
    if not drug_class:
        return "unknown class"
    return dictionary()["classes"].get(drug_class, {}).get("label", drug_class)


def map_name(name: str) -> MappingResult:
    d = dictionary()
    src, ver = d["dictionary_id"], d["version"]
    norm = normalize(name)
    if not norm:
        return MappingResult("unmapped", source=src, version=ver, note="No recognisable medication name")

    for amb in d.get("ambiguous", []):
        if any(norm == n or norm.startswith(n + " ") for n in amb["names"]):
            return MappingResult("ambiguous", source=src, version=ver, note=amb["reason"])

    hits = []
    for entry in d["entries"]:
        for n in entry["names"]:
            if norm == n or norm.startswith(n + " ") or (" " not in n and n in norm.split()):
                hits.append(entry)
                break
    ingredients = {h["ingredient"] for h in hits}
    if not hits:
        return MappingResult("unmapped", source=src, version=ver,
                             note="Not in the bounded mapping list; kept in original form")
    if len(ingredients) > 1:
        return MappingResult("ambiguous", source=src, version=ver,
                             note=f"Name matches several ingredients: {', '.join(sorted(ingredients))}")
    entry = hits[0]
    if entry.get("review_status") != "reviewed":
        return MappingResult("ambiguous", entry["ingredient"], entry.get("rxcui"), entry["class"], entry.get("class_code"),
                             src, ver, note="Suggested mapping not yet reviewed: " + entry.get("note", "requires review"))
    return MappingResult("mapped", entry["ingredient"], entry.get("rxcui"), entry["class"], entry.get("class_code"), src, ver)


def reviewed_entries() -> list[dict]:
    return [e for e in dictionary()["entries"] if e.get("review_status") == "reviewed"]
