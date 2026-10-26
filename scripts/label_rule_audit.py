"""Accuracy sample for the rules read from drug labels (spec v2, section 7).

  python scripts/label_rule_audit.py sample [n]   # writes evaluation/label-rule-audit.csv (random sample, default 100)
  python scripts/label_rule_audit.py report       # prints the share marked correct

A team member opens the CSV and, for each row, fills `correct` with yes or no (is the rule supported by
the quoted sentence?) and their name and date. The report goes in the project report. It measures
extraction accuracy only; it is not a claim of clinical accuracy.
"""
from __future__ import annotations

import csv
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / "rules" / "labels" / "label-rules.json"
AUDIT = ROOT / "evaluation" / "label-rule-audit.csv"
FIELDS = ["rule_key", "ingredient", "kind", "target", "section", "quote", "source_ref", "correct", "checked_by", "checked_on", "note"]


def sample(n: int) -> None:
    doc = json.loads(RULES.read_text(encoding="utf-8"))
    rules = doc["rules"]
    rng = random.Random(doc["content_sha256"])  # the same rule release always gives the same sample
    picked = rng.sample(rules, min(n, len(rules)))
    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        for r in sorted(picked, key=lambda r: r["rule_key"]):
            w.writerow({k: r.get(k, "") for k in FIELDS} | {"correct": "", "checked_by": "", "checked_on": "", "note": ""})
    print(f"{len(picked)} of {len(rules)} rules written to {AUDIT.relative_to(ROOT)} (release {doc['version']})")


def report() -> None:
    with AUDIT.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    marked = [r for r in rows if r["correct"].strip().lower() in ("yes", "no")]
    yes = sum(1 for r in marked if r["correct"].strip().lower() == "yes")
    print(f"Checked {len(marked)} of {len(rows)} sampled rules; supported by the quote: {yes}"
          + (f" ({100 * yes / len(marked):.0f}%)" if marked else ""))
    for r in marked:
        if r["correct"].strip().lower() == "no":
            print(f"  not supported: {r['rule_key']}  {r['note']}")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("sample", "report"):
        sys.exit(__doc__)
    sample(int(sys.argv[2]) if len(sys.argv) > 2 else 100) if sys.argv[1] == "sample" else report()
