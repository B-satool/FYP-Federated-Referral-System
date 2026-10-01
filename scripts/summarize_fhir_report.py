"""Summarize contracts/fhir-samples/validation-report.html (HL7 validator output) by issue category."""
from __future__ import annotations

import collections
import re
import sys
from pathlib import Path

report = Path(sys.argv[1] if len(sys.argv) > 1 else "contracts/fhir-samples/validation-report.html")
text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", report.read_text(encoding="utf-8")))

CATEGORIES = [
    ("dom-6", "best practice: resource narrative (dom-6)"),
    ("performer", "best practice: Observation.performer"),
    ("application/pdf", "MIME code needs a terminology server (offline run)"),
    ("System URI could not be determined", "MIME code needs a terminology server (offline run)"),
    ("Unable to check", "value-set check needs a terminology server (offline run)"),
    ("matches the reference", "Bundle reference resolution"),
]
counts: collections.Counter = collections.Counter()
for m in re.finditer(r" (ERROR|WARNING|INFORMATION) \S+ (.{0,200})", text):
    sev, msg = m.group(1), m.group(2)
    label = next((lab for key, lab in CATEGORIES if key in msg), msg[:90])
    counts[(sev, label)] += 1
for (sev, label), n in sorted(counts.items()):
    print(f"{n:4d}  {sev:11s} {label}")
