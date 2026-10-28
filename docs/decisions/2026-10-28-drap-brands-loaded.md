# Decision: load the DRAP register brand names as verified mappings

- **Date:** 2026-10-28
- **Status:** decided by the project lead on 2026-10-28, against the reviewer step in
  [2026-10-28-drap-register-snapshot.md](2026-10-28-drap-register-snapshot.md) (decision 3) and the "verified
  mappings" wording of AGENTS.md invariant 5. Module owners and the clinical reviewer should be told.
- **Why:** with only the 99 hand-entered names, most Pakistani brands showed as "Medicine not recognised" and were
  not checked against DDInter. No pharmacist was available to check about 6,000 rows one by one.

## What was loaded

`python scripts/import_brands.py <copy of brand-import.csv> --register --write`

- In the copy, every row's `checked_by` reads "NOT CHECKED - loaded as verified by project lead decision
  2026-10-28", so the ledger (`rules/terminology/brand-sources.csv`) does not claim a check that never happened.
- **5,398 brands** whose ingredient is one of the app's ingredients were added, each to that ingredient's
  `register_brands` list in `rules/terminology/medicine-names.pk.json`. They are kept separate from the
  hand-checked `brands`. Five ingredients that were known only inside combinations got their own entries:
  colecalciferol and calcium carbonate (calcium / vitamin D), amoxicillin (antibiotic), and sofosbuvir and
  daclatasvir (antiviral).
- **Not loaded:**
  - 645 combination products whose combination is not in the app yet. Procedure rules match one drug class per
    medicine, so a two-drug product could miss a rule without anyone noticing. As "not recognised" it is visible.
  - 21 names that DRAP lists for **two different medicines** (for example, Glare is both gliclazide and
    ibuprofen). These are recorded in `register_ambiguous`. A medicine written with such a name is reported as
    "registered in Pakistan for different medicines: … Check the pack or ask the patient", on the medicine and
    on its flag. It is never guessed.

## Safeguards in matching (`app/medications/mapping.py`, `app/seed.py`)

Register names are matched more strictly than hand-checked ones:

- They match only where the written name **starts** with the brand ("Coagurin 5mg tablets"), never inside other
  words. A register brand called "Vitamin" otherwise turned "Calcium with vitamin D3" into an ambiguous medicine.
- Names with fewer than 3 letters ("D", "M", or "A-81-E" once numbers are stripped), ordinary words ("vitamin",
  "calcium", "plus" …) and words of generic names are not loaded.
- The hand-checked list always wins.
- A medicine mapped only through a register name carries the note "Brand from the DRAP product register".

## Accepted risk

A wrong row in the DRAP register, or a wrong match by `scripts/scrape_drap.py`, now gives a wrong ingredient. The
medicine is then checked against the wrong interactions and rules, and nobody has reviewed it. The note on the
medicine shows the source, so staff and doctors can question it.
