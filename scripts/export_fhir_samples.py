"""Export one representative resource of each implemented FHIR type from the running source
services (as a clinician with legitimate access) to contracts/fhir-samples/ for HL7 validation."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
from helpers import CLINIC, LAB, SPECIALIST, token  # noqa: E402

OUT = ROOT / "contracts" / "fhir-samples"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.json"):
        old.unlink()
    h = {"Authorization": f"Bearer {token('dr.malik')}"}
    bundles = [
        httpx.get(f"{CLINIC}/fhir/patients/MR-102/records", headers=h, timeout=20).json(),
        httpx.get(f"{LAB}/fhir/patients/LB-5531/results", headers=h, timeout=20).json(),
        httpx.get(f"{SPECIALIST}/fhir/patients/SP-7781/records", headers=h, timeout=20).json(),
    ]
    seen: set[str] = set()
    for b in bundles:
        for e in b.get("entry", []):
            r = e["resource"]
            t = r["resourceType"]
            if t in seen or t == "OperationOutcome":
                continue
            seen.add(t)
            (OUT / f"{t}-{r['id']}.json").write_text(json.dumps(r, indent=2), encoding="utf-8")
    (OUT / "Bundle-clinic-MR-102.json").write_text(json.dumps(bundles[0], indent=2), encoding="utf-8")
    print("exported:", ", ".join(sorted(seen)), "+ one searchset Bundle")


if __name__ == "__main__":
    main()
