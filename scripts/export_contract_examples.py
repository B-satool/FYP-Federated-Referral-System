"""Publish real request/response examples for the shared contracts into contracts/examples/.

Run against a stack that has completed at least one referral journey (e.g. after the T3 checks):
  .venv\\Scripts\\python scripts\\export_contract_examples.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
from helpers import central  # noqa: E402

OUT = ROOT / "contracts" / "examples"


def write(name: str, data) -> None:
    (OUT / f"{name}.json").write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    dr = central("dr.malik")
    refs = dr.get("/referrals").json()
    with_pkg = next((r for r in refs if r["submitted_package_version"]), None)
    if with_pkg is None:
        sys.exit("No submitted referral found; run the T3 checks or the demo first.")
    rid = with_pkg["id"]
    detail = dr.get(f"/referrals/{rid}").json()
    write("PatientRef", detail["patient"])
    write("RetrievalResult", dr.get(f"/referrals/{rid}/retrievals").json()[:3])
    evidence = dr.get(f"/referrals/{rid}/evidence").json()
    write("EvidenceItem", [e for e in evidence if e["category"] in ("medication", "lab")][:3])
    meds = dr.get(f"/referrals/{rid}/medications").json()
    write("MedicationEntry", meds["entries"][:3])
    write("MedicationFlag", meds["flags"])
    write("MedicationEvaluation", meds["evaluation"])
    pkg = dr.get(f"/referrals/{rid}/packages/{with_pkg['submitted_package_version']}").json()
    write("ReferralPackage.envelope", pkg["envelope"])
    links = dr.get("/patient-links", params={"institution": "clinic-a", "local_id": with_pkg["patient"]["local_patient_id"]}).json()
    write("PatientLink", links)
    write("ReviewItem", dr.get(f"/referrals/{rid}/review-items").json()[:3])
    write("Clarification", dr.get(f"/referrals/{rid}/clarifications").json()[:2])
    write("ConsultationResponse", dr.get(f"/referrals/{rid}/responses").json())
    write("ReferralEvent", dr.get(f"/referrals/{rid}/events").json())
    jobs = dr.get(f"/referrals/{rid}/jobs").json()
    if jobs:
        write("Job", jobs[0])
    print("wrote examples for", with_pkg["reference"], "to", OUT)


if __name__ == "__main__":
    main()
