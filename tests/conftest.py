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


def read_env() -> dict[str, str]:
    env = {}
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def compose(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", "compose", *args], cwd=ROOT, capture_output=True, text=True, check=check, timeout=300)


READY_URLS = {"clinic": "http://localhost:8001/ready", "lab": "http://localhost:8002/ready",
              "specialist": "http://localhost:8003/ready", "central": "http://localhost:8000/ready"}


def start_service(name: str) -> None:
    """Start a stopped service and wait until it reports ready."""
    import httpx
    from helpers import wait_for

    compose("start", name)

    def ready():
        try:
            return httpx.get(READY_URLS[name], timeout=3).status_code == 200
        except httpx.HTTPError:
            return False

    wait_for(ready, timeout=90, interval=2, what=f"{name} ready")


@pytest.fixture(scope="session", autouse=True)
def fresh_seed():
    """Start every test session from the deterministic synthetic seed (set SKIP_RESET=1 to keep data)."""
    if os.environ.get("SKIP_RESET") == "1":
        return
    for svc in ("clinic", "lab", "specialist", "central"):
        compose("exec", "-T", svc, "python", "-m", "app.seed", "--reset", "--yes")


@pytest.fixture(scope="session")
def approved_rules():
    """Clinical reviewer approves the draft orthodontics rules (idempotent)."""
    reviewer = central("dr.reviewer")
    rules = ok(reviewer.get("/rules"))["rules"]
    for rule in rules:
        if rule["approval_state"] != "approved":
            ok(reviewer.post(f"/rules/{rule['rule_id']}/versions/{rule['version']}/decision",
                             {"decision": "approve", "reference_checked": rule["reference"][:200] or "Reviewed",
                              "note": "Approved for the synthetic prototype demonstration"}))
    return rules


def new_referral(patient: str, procedure: str | None = "tooth_extraction", user: str = "dr.malik",
                 reason: str = "Crowding and jaw discomfort; orthodontic opinion requested") -> dict:
    body = {"patient_local_id": patient, "reason": reason, "priority": "routine",
            "procedure_status": "known" if procedure else "unknown", "planned_procedure": procedure}
    return ok(central(user).post("/referrals", body), 201)
