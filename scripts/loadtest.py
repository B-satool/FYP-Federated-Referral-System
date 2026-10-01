"""Lightweight 10-user screen/save test against the SRS's proposed target
(ordinary screen loads and saves within 2 s for at least 95% of requests).

Each virtual user keeps a persistent HTTP connection (as a browser does) and works on its own
referral. Asynchronous OCR/LLM completion is excluded from request latency by design.

Recommended (inside the Compose network, so the Windows/macOS Docker port proxy is not measured):
  docker compose run --rm --no-deps -v ${PWD}:/repo -e CENTRAL_URL=http://central:8000 \
      -e KEYCLOAK_URL=http://keycloak:8080 central python /repo/scripts/loadtest.py --users 10 --seconds 60
From the host: .venv\\Scripts\\python scripts\\loadtest.py
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

CENTRAL = os.environ.get("CENTRAL_URL", "http://localhost:8000")
KEYCLOAK = os.environ.get("KEYCLOAK_URL", "http://localhost:8080")
PASSWORD = os.environ.get("DEMO_USER_PASSWORD", "demo1234")
USERS = ["staff.a", "dr.malik", "dr.reviewer"]
PATIENTS = ["MR-102", "MR-215", "MR-330", "MR-418"]


def get_token(user: str) -> str:
    r = httpx.post(f"{KEYCLOAK}/realms/referral/protocol/openid-connect/token",
                   data={"grant_type": "password", "client_id": "dev-cli", "username": user, "password": PASSWORD}, timeout=20)
    r.raise_for_status()
    return r.json()["access_token"]


def worker(idx: int, seconds: float, results: list, errors: list, lock: threading.Lock) -> None:
    user = USERS[idx % len(USERS)]
    client = httpx.Client(base_url=CENTRAL, headers={"Authorization": f"Bearer {get_token(user)}"}, timeout=30)
    ref = client.post("/referrals", json={"patient_local_id": PATIENTS[idx % len(PATIENTS)], "procedure_status": "unknown",
                                          "reason": "Load test referral (synthetic)"}).json()
    client.post(f"/referrals/{ref['id']}/retrieve")  # warm-up, not measured
    ops = [
        ("list referrals", lambda: client.get("/referrals")),
        ("open referral", lambda: client.get(f"/referrals/{ref['id']}")),
        ("evidence", lambda: client.get(f"/referrals/{ref['id']}/evidence")),
        ("medications", lambda: client.get(f"/referrals/{ref['id']}/medications")),
        ("work queue", lambda: client.get("/work-queue")),
    ]
    deadline = time.time() + seconds
    i = 0
    while time.time() < deadline:
        i += 1
        for name, fn in ops:
            t0 = time.perf_counter()
            try:
                status = fn().status_code
            except httpx.HTTPError as exc:
                status = 599
                with lock:
                    errors.append(f"{name}: {exc}")
            with lock:
                results.append((name, time.perf_counter() - t0, status))
        version = client.get(f"/referrals/{ref['id']}").json()["row_version"]
        t0 = time.perf_counter()
        status = client.patch(f"/referrals/{ref['id']}", json={"expected_version": version,
                                                               "reason": f"Load test referral (synthetic) iteration {i}"}).status_code
        with lock:
            results.append(("save draft", time.perf_counter() - t0, status))
    client.close()


def pct(values: list[float], p: float) -> float:
    s = sorted(values)
    return s[min(len(s) - 1, int(round(p / 100 * (len(s) - 1))))]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--users", type=int, default=10)
    ap.add_argument("--seconds", type=float, default=60)
    args = ap.parse_args()
    results: list[tuple[str, float, int]] = []
    errors: list[str] = []
    lock = threading.Lock()
    threads = [threading.Thread(target=worker, args=(i, args.seconds, results, errors, lock)) for i in range(args.users)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    by_op: dict[str, list[float]] = {}
    for name, dt, _ in results:
        by_op.setdefault(name, []).append(dt)
    all_dt = [dt for _, dt, _ in results]
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(), "target": CENTRAL, "users": args.users,
        "seconds": args.seconds, "requests": len(results),
        "http_errors": sum(1 for _, _, s in results if s >= 400), "transport_errors": errors[:10],
        "throughput_rps": round(len(results) / args.seconds, 1),
        "p50_ms": round(statistics.median(all_dt) * 1000), "p95_ms": round(pct(all_dt, 95) * 1000),
        "max_ms": round(max(all_dt) * 1000), "target_p95_ms": 2000, "meets_target": pct(all_dt, 95) < 2.0,
        "by_operation": {k: {"n": len(v), "p50_ms": round(statistics.median(v) * 1000), "p95_ms": round(pct(v, 95) * 1000)}
                         for k, v in sorted(by_op.items())},
    }
    out = Path(os.environ.get("REPO", Path(__file__).resolve().parent.parent)) / "evaluation" / "results" / "load-latest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
