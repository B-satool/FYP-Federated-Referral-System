"""Deterministic synthetic seed for Clinic A.

All people and records are fictional and generated for this project
(labelled synthetic). Run:  python -m app.seed --reset --yes
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime, timezone

from refcommon.db import make_session_factory

from .models import (
    AccessGrant,
    AuditEvent,
    Base,
    Condition,
    Encounter,
    Patient,
    Prescription,
    ReportedMedication,
    SourceDocument,
)

SNOMED = "http://snomed.info/sct"


def dt(y, m, d, h=10):
    return datetime(y, m, d, h, 0, tzinfo=timezone.utc)


def seed(db) -> None:
    db.add_all([
        Patient(local_id="MR-102", given="Ayesha", family="Khan", birth_date=date(1987, 3, 14), sex="F", phone="0300-0000102", city="Lahore"),
        Patient(local_id="MR-215", given="Imran", family="Qureshi", birth_date=date(1979, 11, 2), sex="M", phone="0300-0000215", city="Lahore"),
        Patient(local_id="MR-330", given="Fatima", family="Noor", birth_date=date(2009, 6, 21), sex="F", phone="0300-0000330", city="Lahore"),
        Patient(local_id="MR-418", given="Hamza", family="Siddiqui", birth_date=date(1995, 8, 9), sex="M", phone="0300-0000418", city="Lahore"),
    ])
    db.flush()
    db.add_all([
        # Ayesha Khan - main demonstration patient
        Encounter(id="ENC-102-1", patient_id="MR-102", start=dt(2026, 8, 20), type_text="General practice consultation",
                  reason_text="Crowded lower incisors and jaw discomfort; patient asks about orthodontic treatment", practitioner="Dr Sana Malik"),
        Encounter(id="ENC-102-2", patient_id="MR-102", start=dt(2026, 9, 10), type_text="Follow-up consultation",
                  reason_text="Discussed orthodontic referral; anticoagulation reviewed", practitioner="Dr Sana Malik"),
        Condition(id="CON-102-1", patient_id="MR-102", code_system=SNOMED, code="49436004", display="Atrial fibrillation",
                  clinical_status="active", onset=date(2021, 5, 18), recorded=date(2021, 5, 20)),
        Condition(id="CON-102-2", patient_id="MR-102", code_system=SNOMED, code="312894000", display="Osteopenia",
                  clinical_status="active", onset=date(2019, 1, 10), recorded=date(2019, 1, 15)),
        Prescription(id="RX-102-1", patient_id="MR-102", medication_text="Warfarin 5 mg tablet", strength="5 mg",
                     dose_value=5, dose_unit="mg", dose_text="5 mg once daily", route="oral", frequency="once daily",
                     start_date=date(2021, 6, 1), status="active", prescriber="Dr Sana Malik",
                     note="Dose adjusted by cardiology per INR"),
        Prescription(id="RX-102-2", patient_id="MR-102", medication_text="Alendronate 70 mg tablet", strength="70 mg",
                     dose_value=70, dose_unit="mg", dose_text="70 mg once weekly", route="oral", frequency="once weekly",
                     start_date=date(2019, 2, 1), end_date=date(2023, 2, 1), status="stopped", prescriber="Dr Sana Malik",
                     note="Stopped after 4-year course"),
        Prescription(id="RX-102-3", patient_id="MR-102", medication_text="Atorvastatin 20 mg tablet", strength="20 mg",
                     dose_value=20, dose_unit="mg", dose_text="20 mg at night", route="oral", frequency="once daily",
                     start_date=date(2022, 3, 1), status="active", prescriber="Dr Sana Malik"),
        ReportedMedication(id="MS-102-1", patient_id="MR-102", medication_text="Ecosprin 75", dose_text="75 mg daily (patient report)",
                           status="unknown", reported_on=date(2026, 9, 10), recorded_by="Hina Raza",
                           note="Patient unsure whether still taking"),
        ReportedMedication(id="MS-102-2", patient_id="MR-102", medication_text="Calcium D sachet", dose_text="1 sachet daily",
                           status="active", reported_on=date(2026, 9, 10), recorded_by="Hina Raza"),
        SourceDocument(id="DOC-102-1", patient_id="MR-102", doc_type="Referral letter (paper)", title="Cardiology letter 2025",
                       doc_date=date(2025, 11, 3), author="Cardiology outpatient"),

        # Imran Qureshi - has an INVALIDATED link to a different Lab B patient
        Encounter(id="ENC-215-1", patient_id="MR-215", start=dt(2026, 9, 2), type_text="General practice consultation",
                  reason_text="Malocclusion review request", practitioner="Dr Sana Malik"),
        Condition(id="CON-215-1", patient_id="MR-215", code_system=SNOMED, code="128053003", display="Deep venous thrombosis",
                  clinical_status="resolved", onset=date(2025, 1, 4), recorded=date(2025, 1, 5)),
        Prescription(id="RX-215-1", patient_id="MR-215", medication_text="Xarelto 20 mg tablet", strength="20 mg",
                     dose_value=20, dose_unit="mg", dose_text="20 mg once daily with food", route="oral", frequency="once daily",
                     start_date=date(2025, 1, 6), status="active", prescriber="Dr Sana Malik"),

        # Fatima Noor - adolescent, planned procedure often unknown at referral
        Encounter(id="ENC-330-1", patient_id="MR-330", start=dt(2026, 9, 15), type_text="General practice consultation",
                  reason_text="Overjet and difficulty biting; parents request orthodontic assessment", practitioner="Dr Sana Malik"),
        Condition(id="CON-330-1", patient_id="MR-330", code_system=SNOMED, code="195967001", display="Asthma",
                  clinical_status="active", onset=date(2016, 4, 1), recorded=date(2016, 4, 3)),
        Prescription(id="RX-330-1", patient_id="MR-330", medication_text="Prednisolone 5 mg tablet", strength="5 mg",
                     dose_value=20, dose_unit="mg", dose_text="20 mg once daily for 5 days", route="oral", frequency="once daily",
                     start_date=date(2026, 9, 28), end_date=date(2026, 10, 3), status="active", prescriber="Dr Sana Malik",
                     note="Short course for asthma exacerbation"),

        # Hamza Siddiqui - no relevant medications (no-match path)
        Encounter(id="ENC-418-1", patient_id="MR-418", start=dt(2026, 9, 20), type_text="General practice consultation",
                  reason_text="Crossbite; requests orthodontic opinion", practitioner="Dr Sana Malik"),
        Prescription(id="RX-418-1", patient_id="MR-418", medication_text="Metformin 500 mg tablet", strength="500 mg",
                     dose_value=500, dose_unit="mg", dose_text="500 mg twice daily", route="oral", frequency="twice daily",
                     start_date=date(2024, 6, 1), status="active", prescriber="Dr Sana Malik"),
    ])
    # Specialist C may consult Clinic A records only for patients it has been referred.
    db.add(AccessGrant(grantee_institution="spec-c", local_patient_id="MR-102",
                       categories=["demographics", "medications", "conditions"],
                       basis="Seed: referral data-sharing agreement (synthetic)", granted_by="Seed script"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="drop all Clinic A rows first")
    parser.add_argument("--yes", action="store_true", help="confirm reset")
    args = parser.parse_args()
    _, Session = make_session_factory(os.environ["DATABASE_URL"])
    with Session() as db:
        has_data = db.query(Patient).count() > 0
        if has_data and not args.reset:
            print("Clinic A already has data; pass --reset --yes to replace it.")
            return
        if args.reset:
            if not args.yes:
                sys.exit("Refusing to reset without --yes")
            for table in reversed(Base.metadata.sorted_tables):
                if table.name == "alembic_version":
                    continue
                db.execute(table.delete())
            db.flush()
        seed(db)
        db.commit()
        print("Clinic A seeded:", db.query(Patient).count(), "patients")


if __name__ == "__main__":
    main()
