"""Deterministic synthetic seed for Lab B. Run: python -m app.seed --reset --yes

Note the deliberate identifier collision: Lab B / MR-102 is a DIFFERENT person
from Clinic A / MR-102 (FR-09 test case).
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime, timezone

from refcommon.db import make_session_factory

from .models import AccessGrant, Base, Patient, Report, Result


def dt(y, m, d, h=8):
    return datetime(y, m, d, h, 0, tzinfo=timezone.utc)


def seed(db) -> None:
    db.add_all([
        Patient(local_id="LB-5531", given="Ayesha", family="Khan", birth_date=date(1987, 3, 14), sex="F"),
        Patient(local_id="MR-102", given="Bilal", family="Ahmed", birth_date=date(1990, 1, 1), sex="M"),
        Patient(local_id="LB-6002", given="Imran", family="Qureshi", birth_date=date(1981, 5, 5), sex="M"),
        Patient(local_id="LB-7100", given="Fatima", family="Noor", birth_date=date(2009, 6, 21), sex="F"),
    ])
    db.flush()
    db.add_all([
        Report(id="REP-5531-1", patient_id="LB-5531", code="34555-3", name="Coagulation panel",
               collected_at=dt(2026, 9, 5), issued_at=dt(2026, 9, 5, 14), conclusion="INR within target range for anticoagulation"),
        Report(id="REP-5531-0", patient_id="LB-5531", code="34555-3", name="Coagulation panel",
               collected_at=dt(2026, 7, 2), issued_at=dt(2026, 7, 2, 15)),
        Report(id="REP-5531-2", patient_id="LB-5531", code="58410-2", name="Complete blood count",
               collected_at=dt(2026, 9, 5), issued_at=dt(2026, 9, 5, 14)),
        Report(id="REP-102B-1", patient_id="MR-102", code="58410-2", name="Complete blood count",
               collected_at=dt(2026, 8, 1), issued_at=dt(2026, 8, 1, 13)),
        Report(id="REP-6002-1", patient_id="LB-6002", code="58410-2", name="Complete blood count",
               collected_at=dt(2026, 6, 11), issued_at=dt(2026, 6, 11, 13)),
    ])
    db.flush()
    db.add_all([
        Result(id="OBS-5531-1", patient_id="LB-5531", report_id="REP-5531-1", loinc="6301-6", test_name="INR",
               value_num=2.6, unit="{INR}", reference_range="2.0-3.0 (therapeutic)", specimen="Venous blood (citrate)",
               collected_at=dt(2026, 9, 5), resulted_at=dt(2026, 9, 5, 14)),
        Result(id="OBS-5531-0", patient_id="LB-5531", report_id="REP-5531-0", loinc="6301-6", test_name="INR",
               value_num=3.1, unit="{INR}", reference_range="2.0-3.0 (therapeutic)", specimen="Venous blood (citrate)",
               collected_at=dt(2026, 7, 2), resulted_at=dt(2026, 7, 2, 15)),
        Result(id="OBS-5531-2", patient_id="LB-5531", report_id="REP-5531-2", loinc="718-7", test_name="Hemoglobin",
               value_num=12.9, unit="g/dL", reference_range="12.0-15.5", specimen="Venous blood (EDTA)",
               collected_at=dt(2026, 9, 5), resulted_at=dt(2026, 9, 5, 14)),
        Result(id="OBS-5531-3", patient_id="LB-5531", report_id="REP-5531-2", loinc="777-3", test_name="Platelets",
               value_num=245, unit="10*9/L", reference_range="150-400", specimen="Venous blood (EDTA)",
               collected_at=dt(2026, 9, 5), resulted_at=dt(2026, 9, 5, 14)),
        Result(id="OBS-5531-4", patient_id="LB-5531", report_id=None, loinc="2345-7", test_name="Glucose (fasting)",
               value_num=None, value_text=None, unit="mg/dL", reference_range="70-99", specimen="Venous blood",
               collected_at=dt(2026, 9, 5), resulted_at=dt(2026, 9, 5, 14), status="preliminary"),
        Result(id="OBS-102B-1", patient_id="MR-102", report_id="REP-102B-1", loinc="718-7", test_name="Hemoglobin",
               value_num=15.1, unit="g/dL", reference_range="13.5-17.5", specimen="Venous blood (EDTA)",
               collected_at=dt(2026, 8, 1), resulted_at=dt(2026, 8, 1, 13)),
        Result(id="OBS-6002-1", patient_id="LB-6002", report_id="REP-6002-1", loinc="718-7", test_name="Hemoglobin",
               value_num=14.2, unit="g/dL", reference_range="13.5-17.5", specimen="Venous blood (EDTA)",
               collected_at=dt(2026, 6, 11), resulted_at=dt(2026, 6, 11, 13)),
    ])
    db.add_all([
        AccessGrant(grantee_institution="clinic-a", local_patient_id="LB-5531", categories=["demographics", "labs"],
                    basis="Seed: patient consent on lab requisition (synthetic)", granted_by="Seed script"),
        AccessGrant(grantee_institution="clinic-a", local_patient_id="LB-6002", categories=["demographics", "labs"],
                    basis="Seed: patient consent on lab requisition (synthetic)", granted_by="Seed script"),
        AccessGrant(grantee_institution="spec-c", local_patient_id="LB-5531", categories=["labs"],
                    basis="Seed: referral data-sharing agreement (synthetic)", granted_by="Seed script"),
    ])
    # LB-7100 (Fatima Noor) intentionally has NO grant for Clinic A -> denied retrieval demo.


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args()
    _, Session = make_session_factory(os.environ["DATABASE_URL"])
    with Session() as db:
        if db.query(Patient).count() > 0 and not args.reset:
            print("Lab B already has data; pass --reset --yes to replace it.")
            return
        if args.reset:
            if not args.yes:
                sys.exit("Refusing to reset without --yes")
            for table in reversed(Base.metadata.sorted_tables):
                db.execute(table.delete())
            db.flush()
        seed(db)
        db.commit()
        print("Lab B seeded:", db.query(Patient).count(), "patients")


if __name__ == "__main__":
    main()
