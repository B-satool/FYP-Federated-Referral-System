"""Central seed: medicine names, medication rules and the patients' existing patient links.

Run: python -m app.seed --reset --yes   (wipes central workflow data and uploaded files)

Links are seeded only for places each patient has already been (laboratory, other
hospitals), as confirmed at earlier visits. The link to the hospital a patient is
being referred to is NOT seeded: requesting and approving it is part of the demo.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone

from refcommon.sourcekit import normalize_cnic
from sqlalchemy import text

from .config import settings
from .db import Base, SessionLocal
from .medications import mapping
from .medications.rules import rule_hash
from .models import MedicationRule, MedicineName, PatientLink, PatientLinkEvent

SEED_ACTOR = ("seed-script", "Seed script (synthetic data)")
REVIEWER = ("seed-reviewer", "Dr Nadia Hassan (clinical reviewer, seed approval)")
# keys used in seed-data/patients/*.json -> institution ids
SEED_KEYS = {"drali": ["clinic-ali"], "chughtai": ["lab-b"], "ziauddin": ["zia", "rad-zia"], "akuh": ["aku", "rad-aku"]}
DEST_KEYS = {"aku": "akuh", "zia": "ziauddin"}


def _local_id(p: dict, inst: str) -> str | None:
    return next((p["local_ids"][k] for k in SEED_KEYS[inst] if p["local_ids"].get(k)), None)


def seed_names(db) -> int:
    data = json.loads((settings.repo_root / "rules" / "terminology" / "medicine-names.pk.json").read_text(encoding="utf-8"))
    seen: set[str] = set()
    for e in data["entries"]:
        for kind, names in (("generic", e["generic"]), ("brand", e["brands"])):
            for n in names:
                key = mapping.normalize(n)
                if key and key not in seen:
                    seen.add(key)
                    db.add(MedicineName(name=key, display=n, ingredient=e["ingredient"], drug_class=e["class"], kind=kind,
                                        added_by=SEED_ACTOR[1]))
    return len(seen)


def seed_rules(db) -> int:
    data = json.loads((settings.repo_root / "rules" / "medication" / "seed-rules.json").read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc)
    for x in data["rules"]:
        r = MedicationRule(rule_id=x["rule_id"], version=1, title=x["title"], drug_class=x["drug_class"],
                           procedure_tags=sorted(x["procedure_tags"]), message=x["message"], rationale=x["rationale"],
                           reference=x["reference"], status="approved", content_hash="", created_by=SEED_ACTOR[1],
                           created_by_id=SEED_ACTOR[0], decided_by=REVIEWER[1], decided_by_id=REVIEWER[0],
                           decided_at=now, reference_checked=x["reference"],
                           decision_note="Approved for the synthetic demonstration; a named clinician must re-check.")
        r.content_hash = rule_hash(r)
        db.add(r)
    return len(data["rules"])


def seed_links(db) -> int:
    now = datetime.now(timezone.utc)
    count = 0
    for path in sorted((settings.repo_root / "seed-data" / "patients").glob("*.json")):
        p = json.loads(path.read_text(encoding="utf-8"))
        own = _local_id(p, "drali")
        dest = DEST_KEYS.get(p["referral"]["to_institution"])
        demo = p["demographics"]
        for inst in ("chughtai", "ziauddin", "akuh"):
            other = _local_id(p, inst)
            if not other or inst == dest:
                continue
            link = PatientLink(requester_institution="drali", requester_local_id=own, target_institution=inst,
                               target_local_id=other, patient_name=demo["name"], patient_birth_date=demo["dob"],
                               patient_sex=demo["sex"], patient_cnic=normalize_cnic(demo.get("cnic")),
                               purpose="Seed: patient seen there earlier (synthetic)", status="verified",
                               requested_by=SEED_ACTOR[1], requested_by_id=SEED_ACTOR[0], requested_at=now,
                               decided_by=SEED_ACTOR[1], decided_by_id=SEED_ACTOR[0], decided_at=now,
                               decision_note="Confirmed by that institution's staff at an earlier visit (synthetic)")
            db.add(link)
            db.flush()
            db.add(PatientLinkEvent(link_id=link.id, action="verified", actor=SEED_ACTOR[1], actor_id=SEED_ACTOR[0],
                                    institution_id=inst, note=link.decision_note))
            count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args()
    with SessionLocal() as db:
        if db.query(MedicineName).count() > 0 and not args.reset:
            print("Central already seeded; pass --reset --yes to wipe workflow data and reseed.")
            return
        if args.reset:
            if not args.yes:
                sys.exit("Refusing to reset without --yes")
            names = ", ".join(t.name for t in Base.metadata.sorted_tables)
            db.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
            if settings.storage_root.exists():
                for p in settings.storage_root.iterdir():
                    p.unlink() if p.is_file() else shutil.rmtree(p)
        n_names, n_rules, n_links = seed_names(db), seed_rules(db), seed_links(db)
        db.commit()
        print(f"Central seeded: {n_names} medicine names, {n_rules} approved rules, {n_links} existing patient links")


if __name__ == "__main__":
    main()
