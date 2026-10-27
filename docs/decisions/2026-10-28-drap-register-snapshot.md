# Decision: local snapshot of the DRAP product register

- **Date:** 2026-10-28
- **Status:** agreed by all three members (reported by the project lead on 2026-10-28). This replaces the "Do not scrape" rule in `scripts/import_brands.py`.

## Why

- The project needs Pakistani brand → ingredient mappings. DDInter covers drug–drug interactions but not Pakistani brands.
- DRAP has not yet answered the formal data request, so the only access is the public search page (`https://eapp.dra.gov.pk/WebProductIndex.php`).
- That page is sometimes down, and the app cannot depend on it at run time.
- We checked DRAP's terms of use and found nothing on automated access. `robots.txt` only disallows `/wp-admin/`.

## What was decided

1. `scripts/scrape_drap.py` builds a snapshot in `rules/terminology/drap/`. The app never calls DRAP.
   - **List.** One generic-name lookup per letter and digit (36 requests) collects every product: brand, generic names, company and registration number.
   - **Details.** Composition, strength, dosage form and route are fetched one page at a time, spaced 2 s apart. By default only products containing our ingredients are fetched.
2. Every snapshot row keeps its DRAP registration number and retrieval date.
   - The register includes veterinary products, and only the detail page says which ones. So `export` drops non-human products and warns about rows whose details are not fetched yet.
   - Brand names are cut to the base brand ("Coagurin 5mg Tablets" → "Coagurin").
   - A DRAP component maps to one of our ingredients only by its name plus salt or form words. It never maps to a combination.
3. **Mappings are not verified by being scraped.** `brand-import.csv` leaves `checked_by` empty. A clinical reviewer checks each row before `import_brands.py --write`. AGENTS.md invariants 3 and 5 are unchanged.
4. When DRAP answers the formal request, its export replaces the snapshot, and the snapshot is kept only for comparison.

## Accepted risk

- The snapshot can go out of date (new registrations, cancellations). Re-run `list` before each import, and record its date.
- The page layout can change without notice. The script then fails or returns empty fields, which shows up in the export counts.
