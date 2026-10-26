"""Central seed: medicine names, medication rules, imported rule data (ingredients, DDInter
interactions, drug-label rules) and the patients' existing patient links.

Run: python -m app.seed --reset --yes   (wipes central workflow data and uploaded files)

Links are seeded only for places each patient has already been (laboratory, other
hospitals), as confirmed at earlier visits. The link to the hospital a patient is
being referred to is NOT seeded: requesting and approving it is part of the demo.
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from datetime import datetime, timezone

from refcommon.exchange import content_hash
from refcommon.sourcekit import normalize_cnic
from sqlalchemy import text

from .config import settings
from .db import Base, SessionLocal
from .medications import mapping
from .medications.rules import rule_hash
from .models import (AiSuggestion, DrugInteraction, Ingredient, LabelRule, MedicationRule, MedicineName, PatientLink, PatientLinkEvent,
                     RulesetRelease)

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


def seed_imported(db) -> dict:
    """Load the imported rule data (files produced by the scripts in scripts/) and record the release."""
    root = settings.repo_root / "rules"
    report = json.loads((root / "interactions" / "ddinter-import-report.json").read_text(encoding="utf-8"))
    absent = set(report["our_ingredients_not_in_ddinter"])
    ingredients = json.loads((root / "terminology" / "ingredients.json").read_text(encoding="utf-8"))
    for i in ingredients["ingredients"]:
        db.add(Ingredient(name=i["name"], standard=i.get("standard"), label_name=i.get("label_name"),
                          rxnorm_id=i.get("rxnorm_id"), atc_codes=i.get("atc_codes", []), components=i.get("components", []),
                          in_interaction_source=bool(i.get("standard")) and i["name"] not in absent, note=i.get("note")))
    version = f"retrieved {report['imported']}"
    with (root / "interactions" / "ddinter-subset.csv").open(encoding="utf-8") as fh:
        pairs = list(csv.DictReader(fh))
    db.add_all(DrugInteraction(ingredient_a=p["ingredient_a"], ingredient_b=p["ingredient_b"], severity=p["severity"],
                               source="ddinter", source_version=version, source_ref=p["source_ref"]) for p in pairs)
    labels = json.loads((root / "labels" / "label-rules.json").read_text(encoding="utf-8"))
    vocab = json.loads((root / "vocab" / "label-targets.json").read_text(encoding="utf-8"))
    for r in labels["rules"]:
        group = "procedure" if r["kind"] == "drug_procedure" else "condition"
        db.add(LabelRule(rule_key=r["rule_key"], kind=r["kind"], ingredient=r["ingredient"], target=r["target"],
                         target_label=vocab[group].get(r["target"], {}).get("label", r["target"]),
                         severity_hint=r["severity_hint"], summary=r["summary"], quote=r["quote"], section=r["section"],
                         source_type=r["source_type"], source_ref=r["source_ref"], source_name=r["source_name"],
                         source_version=r["source_version"], extractor_version=r["extractor_version"]))
    ai_path = root / "ai" / "suggestions.json"
    ai = json.loads(ai_path.read_text(encoding="utf-8")) if ai_path.exists() else {"suggestions": []}
    db.add_all(AiSuggestion(pair_key=s["pair_key"], ingredient_a=s["ingredient_a"], ingredient_b=s["ingredient_b"], score=s["score"],
                            reason=s["reason"], model_version=ai["model_version"], data_version=ai["data_version"])
               for s in ai["suggestions"])
    counts = {"ingredients": len(ingredients["ingredients"]), "interactions": len(pairs), "label_rules": len(labels["rules"]),
              "ai_suggestions": len(ai["suggestions"])}
    release_hash = content_hash({"ddinter": report["files_sha256"], "labels": labels["content_sha256"],
                                 "ingredients": ingredients, "vocabulary": vocab["version"]})
    db.add(RulesetRelease(hash=release_hash, counts=counts,
                          notes=f"DDInter 2.0 {version}; {labels['version']} ({labels['extractor_version']}); {vocab['version']}"))
    return counts


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
        imported = seed_imported(db)
        db.commit()
        print(f"Central seeded: {n_names} medicine names, {n_rules} approved rules, {n_links} existing patient links, "
              f"{imported['interactions']} DDInter interactions, {imported['label_rules']} drug-label rules, "
              f"{imported['ai_suggestions']} AI suggestions")


if __name__ == "__main__":
    main()
