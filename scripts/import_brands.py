"""Import Pakistani brand names from a CSV file into the curated medicine name list.

  python scripts/import_brands.py <file.csv>            # report what would change
  python scripts/import_brands.py <file.csv> --write    # update the rules files
  python scripts/import_brands.py <file.csv> --register --write [--human-only]
      # register names (the DRAP snapshot): kept apart from the hand-checked brands, in each entry's
      # "register_brands", and matched more strictly (see app/medications/mapping.py). Products whose DRAP
      # page says they are not for human use (veterinary) are always left out; --human-only also leaves out
      # products whose page has not been fetched yet (python scripts/scrape_drap.py details).

Use a file you are allowed to use: an export DRAP or DrugsInfo Pakistan sends you, rows you type in
from the pack or the DRAP search page yourself, or rules/terminology/drap/brand-import.csv from
scripts/scrape_drap.py (docs/decisions/2026-10-28-drap-register-snapshot.md). Do not scrape DrugsInfo.
Fill checked_by for every row before --write.

Columns (see rules/terminology/brand-import-template.csv):
  brand_name, ingredients (generic names separated by ';'), strength, dosage_form, drug_class (needed
  only for a new ingredient or a combination), company, drap_reg_no, source, retrieved_on, checked_by

* A brand with one known ingredient is added to that ingredient's brand list.
* A combination product (several ingredients) becomes a combination entry whose parts are checked
  one by one for interactions and label rules.
* An ingredient this project does not know yet is reported and skipped unless drug_class is given;
  new ingredients then need scripts/build_ingredient_codes.py, import_ddinter.py and
  extract_label_rules.py to be run again before they are checked.
* The same brand name mapping to different ingredients is reported as a conflict and not imported
  (it would make the name ambiguous).
Every imported brand keeps its source, DRAP registration number and checker in brand-sources.csv.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAMES = ROOT / "rules" / "terminology" / "medicine-names.pk.json"
INGREDIENTS = ROOT / "rules" / "terminology" / "ingredients.json"
LEDGER = ROOT / "rules" / "terminology" / "brand-sources.csv"
FIELDS = ["brand_name", "ingredients", "strength", "dosage_form", "drug_class", "company", "drap_reg_no", "source", "retrieved_on", "checked_by"]


DETAILS = ROOT / "rules" / "terminology" / "drap" / "details.jsonl"


def used_for() -> dict[str, str]:
    """DRAP registration number -> "Human", "Veterinary", ... (from the fetched product pages)."""
    if not DETAILS.exists():
        return {}
    out = {}
    for line in DETAILS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            d = json.loads(line)
            out[d.get("registration_no", "")] = (d.get("used_for") or "").strip()
    return out


def main(path: Path, write: bool, register: bool = False, human_only: bool = False) -> None:
    field = "register_brands" if register else "brands"
    use = used_for()
    names = json.loads(NAMES.read_text(encoding="utf-8"))
    ings = json.loads(INGREDIENTS.read_text(encoding="utf-8"))
    by_ing = {e["ingredient"]: e for e in names["entries"]}
    known = {i["name"] for i in ings["ingredients"]}
    brand_owner = {b.lower(): e["ingredient"] for e in names["entries"]
                   for b in e.get("brands", []) + e.get("register_brands", [])}
    added, skipped, conflicts, ledger = [], [], [], []
    with path.open(encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    not_human = unchecked = 0
    kept = []
    for row in rows:
        regs = [x.strip() for x in (row.get("drap_reg_no") or "").split(";") if x.strip()]
        kinds = {use.get(x, "") for x in regs} - {""}
        if kinds and kinds != {"Human"}:
            not_human += 1  # veterinary (or otherwise not for people)
            continue
        if human_only and not kinds:
            unchecked += 1
            continue
        kept.append(row)
    rows_in = len(rows)
    rows = kept
    for row in rows:
        brand = row["brand_name"].strip()
        parts = [p.strip().lower() for p in row["ingredients"].split(";") if p.strip()]
        if not brand or not parts:
            skipped.append(f"{brand or '(no name)'}: brand name and ingredients are required")
            continue
        combos = {tuple(sorted(i["components"])): i["name"] for i in ings["ingredients"] if i.get("components")}
        ingredient = parts[0] if len(parts) == 1 else combos.get(tuple(sorted(parts)), "/".join(sorted(parts)))
        cls = (row.get("drug_class") or "").strip()
        missing = [p for p in parts if p not in known]
        if missing and not cls:
            skipped.append(f"{brand}: unknown ingredient(s) {', '.join(missing)}; add a drug_class to create them")
            continue
        owner = brand_owner.get(brand.lower())
        if owner and owner != ingredient:
            conflicts.append(f"{brand}: already mapped to {owner}, file says {ingredient}")
            continue
        entry = by_ing.get(ingredient)
        if entry is None:
            if not cls and len(parts) > 1:
                skipped.append(f"{brand}: a combination needs drug_class")
                continue
            if not cls and parts[0] not in by_ing:
                # known only as part of a combination (e.g. colecalciferol): no class to file it under
                skipped.append(f"{brand}: {ingredient} has no medicine-name entry yet; add a drug_class to create it")
                continue
            entry = {"ingredient": ingredient, "class": cls or by_ing[parts[0]]["class"], "generic": [ingredient], "brands": []}
            names["entries"].append(entry)
            by_ing[ingredient] = entry
        for p in missing:
            ings["ingredients"].append({"name": p, "standard": p, "note": f"Added from {path.name}; run the code and data scripts."})
            known.add(p)
        if len(parts) > 1 and ingredient not in known:
            ings["ingredients"].append({"name": ingredient, "components": sorted(parts)})
            known.add(ingredient)
        if brand not in entry.setdefault(field, []) and brand not in entry["brands"]:
            entry[field].append(brand)
            brand_owner[brand.lower()] = ingredient
            added.append(f"{brand} -> {ingredient}")
        ledger.append({k: (row.get(k) or "").strip() for k in FIELDS})
    if register:
        # a register name used for two different medicines is ambiguous: drop it everywhere it was added
        clash = {c.split(":")[0].lower() for c in conflicts}
        for e in names["entries"]:
            if e.get(field):
                e[field] = [b for b in e[field] if b.lower() not in clash]
        # keep them as known-ambiguous names, so staff are told what the name could mean
        # one option per medicine and company, so staff can pick by the company on the pack
        options: dict[str, dict[tuple[str, str], dict]] = {}
        for row in rows:
            brand = row["brand_name"].strip()
            if brand.lower() in clash:
                parts = sorted(p.strip().lower() for p in row["ingredients"].split(";") if p.strip())
                ingredient = parts[0] if len(parts) == 1 else "/".join(parts)
                company = (row.get("company") or "").strip()
                options.setdefault(brand, {}).setdefault((ingredient, company.lower()), {
                    "ingredient": ingredient, "company": company, "drap_reg_no": (row.get("drap_reg_no") or "").strip(),
                    "strength": (row.get("strength") or "").strip(), "dosage_form": (row.get("dosage_form") or "").strip()})
        names["register_ambiguous"] = [
            {"brand": b, "options": sorted(o.values(), key=lambda x: (x["ingredient"], x["company"]))}
            for b, o in sorted(options.items()) if len({i for i, _ in o}) > 1]
        added = [a for a in added if a.split(" -> ")[0].lower() not in clash]
        ledger = [row for row in ledger if row["brand_name"].lower() not in clash]
    print(f"{rows_in} rows: {not_human} not for human use (veterinary) left out"
          + (f", {unchecked} not yet checked left out (--human-only)" if human_only else "") + ". "
          + f"Of the rest: {len(added)} brands to add, {len(skipped)} skipped, {len(conflicts)} conflicts"
          + (" (dropped: a register name for two different medicines is ambiguous)" if register and conflicts else ""))
    for line in added:
        print("  add", line)
    for line in skipped + conflicts:
        print("  !", line)
    if not write:
        print("Nothing written (pass --write).")
        return
    NAMES.write_text(json.dumps(names, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    INGREDIENTS.write_text(json.dumps(ings, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    new = not LEDGER.exists()
    with LEDGER.open("a", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerows(ledger)
    print("Written. Reseed to load: scripts/reset-and-seed.ps1 -Force")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(Path(sys.argv[1]), "--write" in sys.argv[2:], "--register" in sys.argv[2:], "--human-only" in sys.argv[2:])
