"""Seed this institution's database from the shared synthetic seed data.

Each instance reads seed-data/patients/*.json and keeps only the record blocks
that belong to its own institution (for example Chughtai Lab keeps the "lab-b"
blocks). Every person and record is fictional.

Run:  python -m app.seed --reset --yes
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

from refcommon.db import make_session_factory
from refcommon.sourcekit import ALL_CATEGORIES, MAX_GRANT_DAYS, grant_expiry, normalize_cnic

from .config import INSTITUTION, INSTITUTION_NAME
from .models import AccessGrant, Base, Condition, ImagingReport, LabResult, Medication, Patient, Surgery, Visit

SEED_DIR = Path(os.environ.get("SEED_DATA_DIR", "/srv/seed-data/patients"))

# Keys used in the seed files for each institution. A hospital's radiology department
# is part of the hospital (same patient record).
SEED_KEYS = {
    "drali": ["clinic-ali"],
    "chughtai": ["lab-b"],
    "ziauddin": ["zia", "rad-zia"],
    "akuh": ["aku", "rad-aku"],
}
DEST_KEYS = {"aku": "akuh", "zia": "ziauddin"}


def _date(value: str | None) -> date | None:
    if not value:
        return None
    parts = [int(x) for x in value.split("-")]
    while len(parts) < 3:
        parts.append(1)
    return date(*parts[:3])


def local_id_for(patient: dict) -> str | None:
    ids = patient.get("local_ids", {})
    for key in SEED_KEYS[INSTITUTION]:
        if ids.get(key):
            return ids[key]
    return None


def seed(db) -> int:
    count = 0
    for path in sorted(SEED_DIR.glob("*.json")):
        p = json.loads(path.read_text(encoding="utf-8"))
        blocks = [p["sources"][k] for k in SEED_KEYS[INSTITUTION] if k in p.get("sources", {})]
        local_id = local_id_for(p)
        if not local_id:
            continue  # the patient has never been registered here
        demo = p["demographics"]
        *given, family = demo["name"].split()
        db.add(Patient(local_id=local_id, cnic=normalize_cnic(demo.get("cnic")), given=" ".join(given), family=family,
                       birth_date=_date(demo["dob"]), sex=demo["sex"], phone=demo.get("phone"), city=demo.get("city"),
                       registered_by="Seed script (synthetic data)"))
        db.flush()
        count += 1
        n = 0

        def rid(kind: str) -> str:
            nonlocal n
            n += 1
            return f"{kind}-{local_id}-{n}"

        for block in blocks:
            for c in block.get("conditions", []):
                db.add(Condition(id=rid("CON"), patient_id=local_id, display=c["display"], snomed=c.get("snomed"),
                                 clinical_status=c.get("status", "active"), onset=c.get("onset")))
            for s in block.get("surgeries", []):
                db.add(Surgery(id=rid("PROC"), patient_id=local_id, procedure=s["procedure"], performed=s.get("date"),
                               location=s.get("where")))
            for v in block.get("visits", []):
                db.add(Visit(id=rid("ENC"), patient_id=local_id, visit_date=_date(v["date"]), setting=v["setting"],
                             clinician=v.get("doctor"), reason=v.get("reason") or "", summary=v.get("summary") or ""))
            for m in block.get("medications", []):
                db.add(Medication(id=rid("RX"), patient_id=local_id, name=m["name"], brand_as_written=m.get("brand_as_written"),
                                  dose=m.get("dose"), route=m.get("route"), frequency=m.get("frequency"),
                                  start_date=_date(m.get("start")), status=m.get("status", "active"),
                                  prescriber=m.get("prescriber"), note=m.get("note")))
            for panel in block.get("labs", []):
                for r in panel.get("results", []):
                    value = r.get("value")
                    numeric = isinstance(value, (int, float)) and not isinstance(value, bool)
                    db.add(LabResult(id=rid("OBS"), patient_id=local_id, panel=panel["panel"], collected=_date(panel["date"]),
                                     test=r["test"], loinc=r.get("loinc"), value_num=float(value) if numeric else None,
                                     value_text=None if numeric or value is None else str(value), unit=r.get("unit") or None,
                                     reference_range=r.get("reference"), abnormal_flag=r.get("flag") or None,
                                     note=panel.get("note")))
            for i in block.get("imaging", []):
                db.add(ImagingReport(id=rid("IMG"), patient_id=local_id, study_date=_date(i["date"]), study=i["study"],
                                     body_part=i.get("body_part"), findings=i.get("findings") or "",
                                     impression=i.get("impression") or "", reporter=i.get("radiologist")))
        # The patient's existing link with the referring clinic (confirmed at an earlier visit) is
        # backed by this institution's own grant, as if its staff had approved it. The link to the
        # hospital the patient is being referred to is not seeded: approving it is part of the demo.
        destination = DEST_KEYS.get(p["referral"]["to_institution"])
        if INSTITUTION != "drali" and INSTITUTION != destination:
            db.add(AccessGrant(grantee_institution="drali", local_patient_id=local_id, categories=list(ALL_CATEGORIES),
                               basis="Seed: patient link confirmed by our staff at an earlier visit (synthetic)",
                               granted_by="Seed script (synthetic data)", expires_at=grant_expiry(MAX_GRANT_DAYS)))
    return count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="delete all rows first")
    parser.add_argument("--yes", action="store_true", help="confirm reset")
    args = parser.parse_args()
    _, Session = make_session_factory(os.environ["DATABASE_URL"])
    with Session() as db:
        if db.query(Patient).count() > 0 and not args.reset:
            print(f"{INSTITUTION_NAME} already has data; pass --reset --yes to replace it.")
            return
        if args.reset:
            if not args.yes:
                sys.exit("Refusing to reset without --yes")
            for table in reversed(Base.metadata.sorted_tables):
                db.execute(table.delete())
            db.flush()
        count = seed(db)
        db.commit()
        print(f"{INSTITUTION_NAME} seeded: {count} patients")


if __name__ == "__main__":
    main()
