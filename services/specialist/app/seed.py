"""Deterministic synthetic seed for Specialist C. Run: python -m app.seed --reset --yes"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime, timezone

from refcommon.db import make_session_factory

from .models import AccessGrant, Base, Patient, PriorConsultation


def seed(db) -> None:
    db.add_all([
        Patient(local_id="SP-7781", given="Ayesha", family="Khan", birth_date=date(1987, 3, 14), sex="F"),
        Patient(local_id="SP-8020", given="Hamza", family="Siddiqui", birth_date=date(1995, 8, 9), sex="M"),
    ])
    db.flush()
    db.add(PriorConsultation(
        id="CONS-7781-1", patient_id="SP-7781", seen_at=datetime(2024, 5, 11, 11, 0, tzinfo=timezone.utc),
        clinician="Dr Faisal Haider", summary="Orthodontic assessment; treatment deferred by patient",
        diagnosis="Class II malocclusion", diagnosis_code="22811000",
    ))
    db.add(PriorConsultation(
        id="CONS-8020-1", patient_id="SP-8020", seen_at=datetime(2023, 2, 7, 10, 0, tzinfo=timezone.utc),
        clinician="Dr Faisal Haider", summary="Review of posterior crossbite; observation advised",
        diagnosis="Posterior crossbite", diagnosis_code="70305005",
    ))
    for pid in ("SP-7781", "SP-8020"):
        db.add(AccessGrant(grantee_institution="clinic-a", local_patient_id=pid,
                           categories=["demographics", "consultations", "conditions"],
                           basis="Seed: prior referral relationship (synthetic)", granted_by="Seed script"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args()
    _, Session = make_session_factory(os.environ["DATABASE_URL"])
    with Session() as db:
        if db.query(Patient).count() > 0 and not args.reset:
            print("Specialist C already has data; pass --reset --yes to replace it.")
            return
        if args.reset:
            if not args.yes:
                sys.exit("Refusing to reset without --yes")
            for table in reversed(Base.metadata.sorted_tables):
                db.execute(table.delete())
            db.flush()
        seed(db)
        db.commit()
        print("Specialist C seeded:", db.query(Patient).count(), "patients")


if __name__ == "__main__":
    main()
