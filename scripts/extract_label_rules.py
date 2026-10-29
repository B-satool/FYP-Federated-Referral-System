"""Build drug-condition rules from US drug labels (openFDA). (Drug-procedure rules were removed with spec v4 9.1.)

Run by a person (needs internet); the application only loads the result.
  python scripts/extract_label_rules.py download <cache folder>   # fetch one label per ingredient
  python scripts/extract_label_rules.py extract <cache folder>    # write rules/labels/label-rules.json
  python scripts/extract_label_rules.py interactions <cache folder>  # write rules/labels/interaction-quotes.json:
                                                                     # for each DDInter pair, the label sentence
                                                                     # naming the other drug (verbatim), if any

Extraction is deterministic: each label section is split into sentences, and a sentence becomes a
candidate when it matches a target's fixed word patterns (rules/vocab/label-targets.json). The rule
keeps the exact sentence as its quote. Every candidate passes app/medications/label_validation.py
(verbatim quote, known ingredient, known target, no advice in the summary) or it is dropped and
counted. One rule is kept per ingredient and target: the most serious section, then the shortest sentence.

A language-model reader (the spec's option) is not used: no model key is configured, and the fixed
patterns make every rule reproducible. Its output would have to pass the same validator.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "central"))
from app.medications.label_validation import (  # noqa: E402
    ADVICE, SECTION_TITLES, Candidate, matches, sentences, squash, summary_for, validate)

INGREDIENTS = ROOT / "rules" / "terminology" / "ingredients.json"
VOCAB = ROOT / "rules" / "vocab" / "label-targets.json"
OUT = ROOT / "rules" / "labels" / "label-rules.json"
SOURCES = ROOT / "rules" / "sources.json"
API = "https://api.fda.gov/drug/label.json"
EXTRACTOR = "patterns/1.0"
SALTS = {"hydrochloride", "sodium", "potassium", "calcium", "besylate", "mesylate", "maleate", "tartrate", "succinate",
         "fumarate", "sulfate", "magnesium", "bisulfate", "dihydrate", "monohydrate", "trihydrate", "and", "hcl", "anhydrous",
         "acid", "phosphate", "acetate", "citrate", "propionate", "hyclate", "sesquihydrate"}
SEVERITY_RANK = {"high": 0, "moderate": 1, "low": 2}


def _ingredients() -> list[dict]:
    return [i for i in json.loads(INGREDIENTS.read_text(encoding="utf-8"))["ingredients"] if i.get("standard")]


def _single_ingredient(label: dict, name: str) -> bool:
    """True when the label is for this ingredient alone (not a combination product)."""
    words = set(name.lower().split())
    for g in (label.get("openfda") or {}).get("generic_name", []):
        tokens = set(re.split(r"[\s,/]+", g.lower())) - SALTS - {""}
        if tokens and tokens <= words:
            return True
    return False


def download(cache: Path) -> None:
    import httpx

    cache.mkdir(parents=True, exist_ok=True)

    def get(client, params):
        for attempt in range(4):  # unreliable connections: retry, then give up on this ingredient
            try:
                return client.get(API, params=params)
            except httpx.TransportError:
                time.sleep(2 * (attempt + 1))
        raise SystemExit("openFDA did not answer; run the same command again (labels already saved are kept)")

    with httpx.Client(timeout=60) as client:
        for ing in _ingredients():
            path = cache / f"{ing['name'].replace('/', '+')}.json"
            if path.exists():
                continue  # already downloaded in an earlier run
            name = ing.get("label_name") or ing["standard"]
            chosen = None
            for product_type in ("HUMAN PRESCRIPTION DRUG", "HUMAN OTC DRUG"):
                q = f'openfda.generic_name:"{name}" AND openfda.product_type:"{product_type}"'
                r = get(client, {"search": q, "limit": 25, "sort": "effective_time:desc"})
                if r.status_code == 404:
                    continue
                r.raise_for_status()
                chosen = next((lab for lab in r.json().get("results", []) if _single_ingredient(lab, name)), None)
                if chosen:
                    break
                time.sleep(0.3)
            path = cache / f"{ing['name'].replace('/', '+')}.json"
            if chosen:
                path.write_text(json.dumps(chosen), encoding="utf-8")
            print(f"{ing['name']}: {'label ' + chosen['set_id'] if chosen else 'NO single-ingredient US label found'}")
            time.sleep(0.3)  # openFDA allows 240 requests per minute without a key


def extract(cache: Path) -> None:
    vocab = json.loads(VOCAB.read_text(encoding="utf-8"))
    ours = {i["name"] for i in _ingredients()}
    rules: dict[tuple[str, str, str], dict] = {}
    stats = {"labels": 0, "no_label": [], "sentences": 0, "candidates": 0, "rejected": 0, "reject_reasons": {}}
    for ing in _ingredients():
        path = cache / f"{ing['name'].replace('/', '+')}.json"
        if not path.exists():
            stats["no_label"].append(ing["name"])
            continue
        label = json.loads(path.read_text(encoding="utf-8"))
        stats["labels"] += 1
        brand = ", ".join(((label.get("openfda") or {}).get("brand_name") or [])[:2])
        for section in SECTION_TITLES:
            section_text = squash(" ".join(label.get(section) or []))
            if not section_text:
                continue
            for sentence in sentences(section_text):
                stats["sentences"] += 1
                # drug-condition only: spec v4 9.1 forbids a drug-procedure table (those come from the AI layer)
                for kind, group in (("drug_condition", "condition"),):
                    for target, spec in vocab[group].items():
                        if not matches(sentence, spec):
                            continue
                        severity = vocab["severity_by_section"][section]
                        c = Candidate(ing["name"], kind, target, severity, summary_for(ing["name"], section, spec["label"]),
                                      sentence, section)
                        stats["candidates"] += 1
                        problems = validate(c, section_text, ours, vocab)
                        if problems:
                            stats["rejected"] += 1
                            for p in problems:
                                stats["reject_reasons"][p] = stats["reject_reasons"].get(p, 0) + 1
                            continue
                        key = (c.ingredient, c.kind, c.target)
                        # prefer the most serious section, then a sentence without advice wording, then the shortest
                        rank = (SEVERITY_RANK[severity], bool(ADVICE.search(sentence)), len(sentence))
                        if key in rules and rules[key]["_rank"] <= rank:
                            continue
                        rules[key] = {
                            "_rank": rank, "rule_key": f"label:{c.ingredient}:{c.target}", "kind": c.kind,
                            "ingredient": c.ingredient, "target": c.target, "severity_hint": severity,
                            "summary": c.summary, "quote": c.quote, "section": section,
                            "source_type": "drug_label", "source_ref": label["set_id"],
                            "source_name": f"US label{(' (' + brand + ')') if brand else ''}",
                            "source_version": f"{label.get('version', '?')} ({label.get('effective_time', '?')})",
                            "extractor_version": EXTRACTOR,
                        }
    out = sorted(({k: v for k, v in r.items() if k != "_rank"} for r in rules.values()), key=lambda r: r["rule_key"])
    body = json.dumps(out, sort_keys=True).encode()
    doc = {"version": f"label-rules/{date.today().isoformat()}", "extractor_version": EXTRACTOR,
           "vocabulary": vocab["version"], "content_sha256": hashlib.sha256(body).hexdigest(),
           "status": "auto_extracted: not clinically reviewed", "stats": {**stats, "rules": len(out)}, "rules": out}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    src = json.loads(SOURCES.read_text(encoding="utf-8"))
    src["openfda_labels"]["retrieved"] = date.today().isoformat()
    SOURCES.write_text(json.dumps(src, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(doc["stats"], indent=2))


QUOTES_OUT = ROOT / "rules" / "labels" / "interaction-quotes.json"
DDINTER_SUBSET = ROOT / "rules" / "interactions" / "ddinter-subset.csv"
# where a label explains an interaction, most specific first
INTERACTION_SECTIONS = ("drug_interactions", "warnings_and_cautions", "precautions", "warnings", "contraindications",
                        "boxed_warning")
SECTION_NAMES = {"drug_interactions": "Drug interactions", **SECTION_TITLES}
MAX_QUOTE = 450
# salt words that never name the drug on their own ("calcium" does: calcium carbonate is calcium)
NOT_A_DRUG_NAME = {"sodium", "potassium", "hydrochloride", "acid", "human", "insulin"}
# a name followed by these words is a drug class ("calcium channel blockers"), not the ingredient
NOT_A_CLASS = r"(?![\s-]*(channel|antagonist|blocker|blocking|entry))"
# a quote must say something about the combination, not merely mention the other drug
INTERACTION_WORDS = re.compile(
    r"\b(increas\w*|decreas\w*|risk|bleed\w*|absorption|absorb\w*|concentrations?|levels?|interfer\w*|inhibit\w*|"
    r"potentiat\w*|reduc\w*|enhanc\w*|toxicity|effects?|INR|prothrombin|coadministration|co-administration|"
    r"concomitant\w*|combined|bind\w*|exposure|clearance|synergistic|antagoniz\w*)\b", re.I)


# Pairs whose best sentence was read and found not to be about the interaction (no quote is shown instead)
REVIEWED_NOT_RELEVANT = {
    ("aspirin", "levothyroxine"),  # 2026-10-29: the sentence is about tartrazine (dye) sensitivity
}


def _quotable(sentence: str) -> bool:
    """A whole sentence (not a fragment cut at a heading) that talks about an interaction."""
    return (sentence.count(")") <= sentence.count("(") and sentence.count("]") <= sentence.count("[")
            and len(sentence) >= 40 and bool(INTERACTION_WORDS.search(sentence)))


def _names(ing: dict) -> set[str]:
    """Ways a label may name this ingredient: its names, and the first word of a salt name ("calcium" for
    calcium carbonate) when that word is not itself a salt word."""
    out = {n.lower() for n in (ing["name"], ing.get("standard"), ing.get("label_name")) if n}
    for n in list(out):
        first = n.split()[0]
        if " " in n and len(first) >= 5 and first not in NOT_A_DRUG_NAME:
            out.add(first)
    return out


def interaction_quotes(cache: Path) -> None:
    """For each DDInter pair, the label sentence (verbatim) that names the other ingredient, if any.

    Searches both ingredients' labels, prefers the drug-interactions section, then the shortest sentence.
    Deterministic: the same labels always give the same quotes. Nothing is paraphrased."""
    import csv

    ings = {i["name"]: i for i in _ingredients()}
    labels = {}
    for name in ings:
        path = cache / f"{name.replace('/', '+')}.json"
        if path.exists():
            labels[name] = json.loads(path.read_text(encoding="utf-8"))
    with DDINTER_SUBSET.open(encoding="utf-8") as fh:
        pairs = [(r["ingredient_a"], r["ingredient_b"]) for r in csv.DictReader(fh)]
    quotes, missing = [], 0
    for a, b in pairs:
        best = None
        if (a, b) in REVIEWED_NOT_RELEVANT:
            missing += 1
            continue
        for holder, other in ((a, b), (b, a)):
            label = labels.get(holder)
            if label is None or other not in ings:
                continue
            pattern = re.compile(r"\b(" + "|".join(map(re.escape, sorted(_names(ings[other]), key=len, reverse=True)))
                                 + r")\b" + NOT_A_CLASS, re.I)
            brand = ", ".join(((label.get("openfda") or {}).get("brand_name") or [])[:2])
            for rank, section in enumerate(INTERACTION_SECTIONS):
                text = squash(" ".join(label.get(section) or []))
                for sentence in sentences(text):
                    if (len(sentence) > MAX_QUOTE or not pattern.search(sentence) or sentence not in text
                            or not _quotable(sentence)):
                        continue
                    key = (rank, len(sentence))
                    if best is None or key < best[0]:
                        best = (key, {"ingredient_a": a, "ingredient_b": b, "quote": sentence, "section": section,
                                      "section_title": SECTION_NAMES.get(section, section), "label_ingredient": holder,
                                      "source_ref": label["set_id"],
                                      "source_name": f"US label{(' (' + brand + ')') if brand else ''}",
                                      "source_version": f"{label.get('version', '?')} ({label.get('effective_time', '?')})"})
        if best:
            quotes.append(best[1])
        else:
            missing += 1
    body = json.dumps(quotes, sort_keys=True).encode()
    doc = {"version": f"interaction-quotes/{date.today().isoformat()}", "extractor_version": EXTRACTOR,
           "content_sha256": hashlib.sha256(body).hexdigest(),
           "status": "auto_extracted: verbatim label sentences, not clinically reviewed",
           "stats": {"pairs": len(pairs), "with_quote": len(quotes), "without_quote": missing, "labels": len(labels)},
           "quotes": quotes}
    QUOTES_OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(doc["stats"], indent=2))


if __name__ == "__main__":
    commands = {"download": download, "extract": extract, "interactions": interaction_quotes}
    if len(sys.argv) != 3 or sys.argv[1] not in commands:
        sys.exit(__doc__)
    commands[sys.argv[1]](Path(sys.argv[2]))
