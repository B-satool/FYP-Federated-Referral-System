"""Import DDInter 2.0 drug-drug interactions for our ingredients.

Run by a person after downloading the DDInter CSV files (https://ddinter2.scbdd.com/download/):
  python scripts/import_ddinter.py <folder with ddinter_downloads_code_*.csv>

Writes rules/interactions/ddinter-subset.csv: every DDInter pair where both drugs map to an
ingredient in rules/terminology/ingredients.json (by its international name). Each pair is stored
once, with our ingredient names in alphabetical order. The severity is DDInter's level, unchanged.
Prints a coverage report (also saved next to the subset) on every import.

DDInter is licensed CC BY-NC-SA 4.0; the subset keeps that licence (see rules/interactions/README.md).
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INGREDIENTS = ROOT / "rules" / "terminology" / "ingredients.json"
OUT = ROOT / "rules" / "interactions" / "ddinter-subset.csv"
REPORT = ROOT / "rules" / "interactions" / "ddinter-import-report.json"
SOURCES = ROOT / "rules" / "sources.json"
LEVELS = {"Major", "Moderate", "Minor", "Unknown"}


def main(folder: Path) -> None:
    files = sorted(folder.glob("ddinter_downloads_code_*.csv"))
    if not files:
        sys.exit(f"No ddinter_downloads_code_*.csv files in {folder}")
    ingredients = [i for i in json.loads(INGREDIENTS.read_text(encoding="utf-8"))["ingredients"] if i.get("standard")]
    by_standard = {i["standard"].lower(): i["name"] for i in ingredients}

    rows, ddinter_drugs, bad_levels = 0, {}, 0
    pairs: dict[tuple[str, str], dict] = {}
    for f in files:
        with f.open(encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                rows += 1
                ddinter_drugs[r["Drug_A"].lower()] = r["DDInterID_A"]
                ddinter_drugs[r["Drug_B"].lower()] = r["DDInterID_B"]
                a, b = by_standard.get(r["Drug_A"].lower()), by_standard.get(r["Drug_B"].lower())
                if not a or not b or a == b:
                    continue
                if r["Level"] not in LEVELS:
                    bad_levels += 1
                    continue
                key = tuple(sorted((a, b)))
                ref = "-".join(sorted((r["DDInterID_A"], r["DDInterID_B"])))
                # the same pair can appear in several ATC files; they carry the same level
                pairs.setdefault(key, {"ingredient_a": key[0], "ingredient_b": key[1], "severity": r["Level"],
                                       "source_ref": ref, "source_file": f.name})

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["ingredient_a", "ingredient_b", "severity", "source_ref", "source_file"])
        w.writeheader()
        for key in sorted(pairs):
            w.writerow(pairs[key])

    found = sorted(n for s, n in by_standard.items() if s in ddinter_drugs)
    not_found = sorted(n for s, n in by_standard.items() if s not in ddinter_drugs)
    digest = hashlib.sha256(b"".join(f.read_bytes() for f in files)).hexdigest()
    report = {
        "imported": date.today().isoformat(), "files": [f.name for f in files], "files_sha256": digest,
        "ddinter_rows": rows, "ddinter_drugs": len(ddinter_drugs),
        "ddinter_drugs_not_mapped_to_our_ingredients": len(ddinter_drugs) - len(found),
        "our_ingredients": len(by_standard), "our_ingredients_found_in_ddinter": len(found),
        "our_ingredients_not_in_ddinter": not_found, "pairs_written": len(pairs), "rows_with_unknown_level": bad_levels,
        "by_severity": {lvl: sum(1 for p in pairs.values() if p["severity"] == lvl) for lvl in sorted(LEVELS)},
    }
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    src = json.loads(SOURCES.read_text(encoding="utf-8"))
    src["ddinter"]["retrieved"] = report["imported"]
    src["ddinter"]["files_sha256"] = digest
    SOURCES.write_text(json.dumps(src, indent=2) + "\n", encoding="utf-8")

    print(f"DDInter rows read: {rows}; distinct DDInter drugs: {len(ddinter_drugs)}")
    print(f"DDInter drugs not mapped to our ingredients: {report['ddinter_drugs_not_mapped_to_our_ingredients']}")
    print(f"Our ingredients found in DDInter: {len(found)} of {len(by_standard)}")
    print(f"Our ingredients NOT in DDInter (interactions cannot be checked): {', '.join(not_found) or 'none'}")
    print(f"Pairs written to {OUT.relative_to(ROOT)}: {len(pairs)} {report['by_severity']}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(Path(sys.argv[1]))
