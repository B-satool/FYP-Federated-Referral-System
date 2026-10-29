"""Onboard the participating institutions (spec v4 section 6.1): pin each one's public signing key and the
platform's key, and record the participation agreement.

This is the out-of-band step a real deployment does once per institution when it signs the participation agreement:
the operator reads each institution's public key from the institution itself, compares the fingerprint with the
institution's own administrator (shown below), and writes the pinned registry. Every service and the web client
read the registry from a read-only mount; the platform's API never serves or changes it.

Usage (stack running):  python scripts/onboard_participants.py [--suspend chughtai] [--reset]
Writes infra/participants/participants.json (not committed: keys differ per installation).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "infra" / "participants" / "participants.json"
AGREEMENT = {"version": "PA-1.0", "date": "2026-10-29",
             "purposes": ["TREAT", "ETREAT", "PATRQT"],
             "text": "docs/participation-agreement.md"}
# institution -> (adapter URL as the services see it, URL reachable from this computer)
INSTITUTIONS = {
    "drali": ("http://drali:8000", "http://localhost:8001"),
    "chughtai": ("http://chughtai:8000", "http://localhost:8002"),
    "ziauddin": ("http://ziauddin:8000", "http://localhost:8003"),
    "akuh": ("http://akuh:8000", "http://localhost:8004"),
}
HUB = "http://localhost:8000"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--suspend", action="append", default=[], help="mark an institution suspended")
    ap.add_argument("--reset", action="store_true", help="re-read every key even if already pinned")
    args = ap.parse_args()
    current = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() and not args.reset else {}
    institutions = dict(current.get("institutions", {}))
    for inst, (internal, local) in INSTITUTIONS.items():
        try:
            info = httpx.get(f"{local}/.well-known/refx-participant", timeout=15).json()
        except (httpx.HTTPError, ValueError) as exc:
            print(f"  {inst}: not reachable ({exc}); keeping any earlier entry", file=sys.stderr)
            continue
        prior = institutions.get(inst)
        if prior and prior["signing_key"] != info["signing_key"]:
            print(f"  {inst}: SIGNING KEY CHANGED (was {prior['key_id']}, now {info['key_id']}); re-pinned")
        institutions[inst] = {"name": info["name"], "signing_key": info["signing_key"], "key_id": info["key_id"],
                              "adapter_url": internal, "agreement_version": AGREEMENT["version"],
                              "agreement_date": prior.get("agreement_date", AGREEMENT["date"]) if prior else str(date.today()),
                              "status": "suspended" if inst in args.suspend else "active"}
        print(f"  {inst:9} {info['name']:32} key {info['fingerprint']}  {institutions[inst]['status']}")
    jwks = httpx.get(f"{HUB}/.well-known/jwks.json", timeout=15).json()
    (kid, spki), = jwks["spki"].items()
    print(f"  platform  signing key {' '.join(kid[i:i + 4] for i in range(0, 16, 4))}")
    data = {"version": 1, "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "agreement": AGREEMENT, "platform": {"id": "hub", "signing_key": spki, "key_id": kid},
            "institutions": institutions}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)}. Compare each fingerprint with that institution's administrator.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
