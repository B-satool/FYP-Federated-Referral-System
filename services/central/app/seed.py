"""Central seed: verified/invalidated patient links for the synthetic population.

Run: python -m app.seed --reset --yes   (wipes central workflow data and uploaded files)

The expected-link map lives ONLY here and in tests (controlled seed/test use).
Note Clinic A/MR-102 and Lab B/MR-102 are different people and are never linked.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime, timezone

from .config import settings
from .db import Base, SessionLocal
from .models import PatientLink, PatientLinkEvent

SEED_ACTOR = ("seed-script", "Seed script (synthetic data)")

LINKS = [
    # (a_inst, a_id, b_inst, b_id, status, basis)
    ("clinic-a", "MR-102", "lab-b", "LB-5531", "verified",
     "Seed: name, date of birth and national ID matched on lab requisition form (synthetic)"),
    ("clinic-a", "MR-215", "lab-b", "LB-6002", "invalidated",
     "Seed: originally linked on name only"),
    ("clinic-a", "MR-330", "lab-b", "LB-7100", "verified",
     "Seed: name and date of birth matched on lab requisition form (synthetic)"),
]


def seed(db) -> None:
    now = datetime.now(timezone.utc)
    for a_inst, a_id, b_inst, b_id, status, basis in LINKS:
        link = PatientLink(a_institution=a_inst, a_local_id=a_id, b_institution=b_inst, b_local_id=b_id, status=status,
                           basis=basis, proposed_by=SEED_ACTOR[1], proposed_by_id=SEED_ACTOR[0], proposed_at=now)
        if status in ("verified", "invalidated"):
            link.verified_by, link.verified_by_id, link.verified_at = SEED_ACTOR[1], SEED_ACTOR[0], now
        db.add(link)
        db.flush()
        db.add(PatientLinkEvent(link_id=link.id, action="proposed", actor=SEED_ACTOR[1], actor_id=SEED_ACTOR[0], note=basis))
        if status == "invalidated":
            link.status_key = f"invalidated-{link.id}"
            link.invalidated_by, link.invalidated_at = SEED_ACTOR[1], now
            link.invalidation_reason = "Date of birth differs (1979-11-02 vs 1981-05-05): different person"
            db.add(PatientLinkEvent(link_id=link.id, action="invalidated", actor=SEED_ACTOR[1], actor_id=SEED_ACTOR[0],
                                    note=link.invalidation_reason))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args()
    with SessionLocal() as db:
        if db.query(PatientLink).count() > 0 and not args.reset:
            print("Central already seeded; pass --reset --yes to wipe workflow data and reseed.")
            return
        if args.reset:
            if not args.yes:
                sys.exit("Refusing to reset without --yes")
            names = ", ".join(t.name for t in Base.metadata.sorted_tables)
            db.execute(__import__("sqlalchemy").text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
            if settings.storage_root.exists():
                for p in settings.storage_root.iterdir():
                    p.unlink() if p.is_file() else shutil.rmtree(p)
        seed(db)
        db.commit()
        print("Central seeded:", db.query(PatientLink).count(), "patient links")


if __name__ == "__main__":
    main()
