"""Lightweight 10-user screen/save test against the SRS's proposed target
(ordinary screen loads and saves within 2 s for at least 95% of requests).

Asynchronous OCR/LLM completion is excluded from request latency by design.
Run from the host test venv while the stack is up:
  .venv\\Scripts\\python scripts\\loadtest.py --users 10 --seconds 60
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests"))
from helpers import central, ok  # noqa: E402

USERS = ["staff.a", "dr.malik", "dr.reviewer", "dr.locum"]
PATIENTS = ["MR-102", "MR-215", "MR-330", "MR-418"]


def worker(idx: int, seconds: float, results: list, lock: threading.Lock) -> None:
    user = USERS[idx % len(USERS)]
    api = central(user)
    ref = ok(api.post("/referrals", {"patient_local_id": PATIENTS[idx % len(PATIENTS)], "reason": "Load test referral (synthetic)",
                                     "procedure_status": "unknown"}), 201)
    ok(api.post(f"/referrals/{ref['id']}/retrieve"))  # warm-up, not measured
    deadline = time.time() + seconds
    i = 0
    while time.time() < deadline:
        i += 1
        ops = [
            ("list referrals", lambda: api.get("/referrals")),
            ("open referral", lambda: api.get(f"/referrals/{ref['id']}")),
            ("evidence", lambda: api.get(f"/referrals/{ref['id']}/evidence")),
            ("medications", lambda: api.get(f"/referrals/{ref['id']}/medications")),
            ("work queue", lambda: api.get("/work-queue")),
        ]
        for name, fn in ops:
            t0 = time.perf_counter()
            r = fn()
            dt = time.perf_counter() - t0
            with lock:
                results.append((name, dt, r.status_code))
        current = api.get(f"/referrals/{ref['id']}").json()
        t0 = time.perf_counter()
        r = api.patch(f"/referrals/{ref['id']}", {"expected_version": current["row_version"],
                                                  "reason": f"Load test referral (synthetic) iteration {i}"})
        with lock:
            results.append(("save draft", time.perf_counter() - t0, r.status_code))


def pct(values: list[float], p: float) -> float:
    s = sorted(values)
    return s[min(len(s) - 1, int(round(p / 100 * (len(s) - 1))))]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--users", type=int, default=10)
    ap.add_argument("--seconds", type=float, default=60)
    args = ap.parse_args()
    results: list[tuple[str, float, int]] = []
    lock = threading.Lock()
    threads = [threading.Thread(target=worker, args=(i, args.seconds, results, lock)) for i in range(args.users)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    by_op: dict[str, list[float]] = {}
    errors = sum(1 for _, _, s in results if s >= 400)
    for name, dt, _ in results:
        by_op.setdefault(name, []).append(dt)
    all_dt = [dt for _, dt, _ in results]
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(), "users": args.users, "seconds": args.seconds,
        "requests": len(results), "errors": errors,
        "p50_ms": round(statistics.median(all_dt) * 1000), "p95_ms": round(pct(all_dt, 95) * 1000),
        "max_ms": round(max(all_dt) * 1000), "target_p95_ms": 2000,
        "meets_target": pct(all_dt, 95) < 2.0,
        "by_operation": {k: {"n": len(v), "p50_ms": round(statistics.median(v) * 1000), "p95_ms": round(pct(v, 95) * 1000)}
                         for k, v in sorted(by_op.items())},
    }
    out = Path(__file__).resolve().parent.parent / "evaluation" / "results" / "load-latest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
