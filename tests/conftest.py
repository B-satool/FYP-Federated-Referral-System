"""Integration checks run against the running Compose stack (see docs/testing.md).

Prerequisite: docker compose up -d && scripts/reset-and-seed.ps1 -Force
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(__file__))

from helpers import central, ok  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SERVICES = ("drali", "chughtai", "ziauddin", "akuh", "central")


def compose(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", "compose", *args], cwd=ROOT, capture_output=True, text=True, check=check, timeout=300)


@pytest.fixture(scope="session", autouse=True)
def fresh_seed():
    """Start every test session from the deterministic synthetic seed (set SKIP_RESET=1 to keep data)."""
    if os.environ.get("SKIP_RESET") == "1":
        return
    for svc in SERVICES:
        compose("exec", "-T", svc, "python", "-m", "app.seed", "--reset", "--yes")


def find_patient(name: str, user: str = "dr.ali") -> dict:
    hits = ok(central(user).get("/patients/search", params={"q": name}))
    assert hits, f"patient {name} not found"
    return hits[0]


def new_referral(patient_name: str, dest: str, dept: str, procedure: str | None, tags: list[str] | None = None, *,
                 submit: bool = True, reason: str = "Synthetic test referral: please assess and advise on management.",
                 user: str = "dr.ali") -> dict:
    """A referral to a doctor or department; the procedure is written in the doctor's words."""
    p = find_patient(patient_name, user)
    body = {"kind": "referral", "patient_local_id": p["local_patient_id"], "destination_institution": dest,
            "destination_department": dept, "reason": reason, "urgency": "routine",
            "procedure_status": "planned" if procedure else "unknown", "planned_procedure": procedure,
            "procedure_tags": tags or [], "submit": submit}
    return ok(central(user).post("/referrals", body), 201)


def new_test_request(patient_name: str, tests: list[dict], *, user: str = "dr.ali") -> dict:
    p = find_patient(patient_name, user)
    body = {"kind": "test", "patient_local_id": p["local_patient_id"], "reason": "Synthetic test request",
            "diagnostic_requests": tests, "submit": True}
    return ok(central(user).post("/referrals", body), 201)


SURGERY = ["major_surgery", "general_anaesthesia", "prolonged_fasting", "bleeding_risk"]
TINY_PNG = ("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAAAAAA6fptVAAAACklEQVR4nGNgAAAAAgABSK+kcQAAAABJRU5ErkJggg==")
