# Source-backed medication flagging

This document records how spec v2 ("Source-backed medication flagging for all departments") was applied on the `v2` branch, what was approved, what was built, and what is still open.

## 1. Approval (spec section 0)

On 2026-10-27 the project lead approved all five gates for the FYP build:
1. the new tables and columns (section 4);
2. replacing per-rule reviewer approval for imported rules with visible sources, an "automatically generated, not clinically reviewed" label, and the clinician's Ignore/Research decision;
3. using fixed extraction offline to build rules, with the app only evaluating stored rules deterministically;
4. using DDInter (CC BY-NC-SA 4.0, non-commercial), openFDA labels and RxNav;
5. the disclaimer near flags.

The approval was given in the development session, not in writing from the supervisor and module owners, as the spec's gate asks. **The supervisor and the module owners still need to confirm it in writing** before this is merged. The disclaimer wording (`FLAG_DISCLAIMER` in `services/central/app/config.py`) is a placeholder for the supervisor to replace.

The same day it was also decided that **only clinical rule reviewers** see the Medication rules and Medicine names screens. Doctors and staff see the flags, not the rule lists.

## 2. How the spec maps onto v2

The spec was written against the v1 code (orthodontics JSON rules, `RuleApproval`, `generation/brief.py` and so on). v2 already had several of the pieces it asks for:
- rules in the database, approved by a reviewer;
- a medicine-name table mapping to ingredient and class;
- `mapped | ambiguous | unmapped` statuses;
- current medicines only;
- procedure features chosen by the doctor;
- a doctor review before sending.

The spec was applied as follows:

| Spec | v2 implementation |
|---|---|
| Ingredient table with RxNorm and ATC codes | `rules/terminology/ingredients.json`, loaded into `ingredients`. It holds the international name used by DDInter and labels (aspirin is acetylsalicylic acid, paracetamol is acetaminophen) and combination parts (co-amoxiclav is amoxicillin and clavulanic acid). Codes come from RxNav via `scripts/build_ingredient_codes.py`. |
| Brand to ingredient | The existing `medicine_names` table (curated Pakistani brands). Salts such as sodium and potassium are removed by the name normaliser. Not taken from DRAP or DrugsInfo Pakistan: neither offers a file, and permission was not obtained. |
| Drug-drug from DDInter | `scripts/import_ddinter.py` writes `rules/interactions/ddinter-subset.csv`: 342 pairs among our ingredients (Major 23, Moderate 163, Minor 17, not graded 139). Each pair is stored once, with DDInter's level unchanged. The coverage report is printed and saved on every import. |
| Drug-condition and drug-procedure from labels | `scripts/extract_label_rules.py` downloads one US label per ingredient (openFDA) and keeps sentences that match a controlled vocabulary (`rules/vocab/label-targets.json`). Every candidate passes `app/medications/label_validation.py`: the quote must be verbatim, the ingredient known, the target in the vocabulary, and the summary free of advice. Result: 115 rules from 35 labels, in `rules/labels/label-rules.json`. |
| Procedure vocabulary | The platform's own procedure features (what the doctor ticks) are the vocabulary, so label rules match the form directly. |
| Condition vocabulary | Fixed word lists map the patient's current recorded conditions to categories (liver impairment, kidney impairment, portal hypertension and so on). Resolved conditions are left out. |
| Evaluator | Still one pure function. It adds `interaction`, `label_warning` and `interactions_not_checked` flags. Every flag carries its source type, name, reference, version and (for labels) the quote, plus `auto_generated`. The rule-set fingerprint is stored on each evaluation and each decision. Nothing is reported as "safe"; no match reads "No matching rule on file". |
| Ignore / Research | Each flag offers **Mark as reviewed**, **Ignore** and **Research**, with an optional note. Each choice is logged with who, when, flag version and rule-set fingerprint. Ignored flags stay visible. |
| Avoiding alert fatigue | The doctor must decide on these flags before sending: approved-rule flags, Major interactions, label rules from a boxed warning or contraindication, and "could not be checked" notices. Other flags are grouped by severity, minor ones are collapsed, and they are for reading. |
| Rules screen | Reviewer-only, with three tabs: approved rules (editable, approval as before), DDInter interactions (read-only, searchable), and drug-label rules (read-only, with quote, label version and extractor version). |
| Existing manual rules | Kept as they were (RULE-001 to RULE-011, reviewer approval still required). Each is shown as "Approved by a clinical reviewer". |

## 3. Data sources

All are recorded in `rules/sources.json`. Files are downloaded by a person; the application never calls these services.

- **DDInter 2.0** (https://ddinter2.scbdd.com/download/; the old ddinter.scbdd.com host no longer resolves):
  - Licence: CC BY-NC-SA 4.0. The terms page also says the absence of an interaction does not mean there is none.
  - Content: the download files give only drug names and a severity level, with no mechanism or management text. So flags show the severity and the source entry, never management advice.
  - Coverage: the download covers ATC groups A, B, D, H, L, P, R and V only. Pairs where neither drug falls in these groups may be missing.
- **openFDA drug labels** (public domain). These are US labels, so Pakistani-only products have none.
- **RxNav** (RxNorm codes, and ATC via RxClass).

## 4. Measured coverage

- DDInter: 1,939 drugs.
  - 39 of our 41 ingredients are present. Gliclazide and hyoscine butylbromide are missing. When a patient takes them, the evaluator shows "interactions not checked", never "none".
- US labels: found for 35 of 41 ingredients.
  - No single-ingredient US label for colecalciferol, clavulanic acid, ferrous fumarate, gliclazide, hyoscine butylbromide or daclatasvir.
  - Of 482 label candidates, 1 was rejected by the verbatim-quote check.
- **Extraction accuracy:** not measured yet.
  - `python scripts/label_rule_audit.py sample 100` has written 100 of the 115 rules to `evaluation/label-rule-audit.csv`.
  - A team member marks each as supported by its quote or not, then runs `python scripts/label_rule_audit.py report`. That number goes in the project report.
  - Known weak spots seen while tuning: very broad words ("surgery", "bleeding") pick up some sentences that are only loosely relevant; long label sentences can mention several topics.

## 5. Tests

- `services/central/tests/test_flagging.py` (22 tests), on the committed imported data:
  - **Golden cases:**
    - P1: alendronate with dental surgery (label, with quote)
    - P2: metformin with contrast (label)
    - P3: aspirin with diclofenac (DDInter)
    - P4: ibuprofen with liver disease (condition)
    - P5: antiplatelets before surgery, with no invented insulin advice
  - **Behaviour:**
    - determinism and pair symmetry
    - unmapped medicines are "could not be checked"; ambiguous names stay ambiguous
    - combination products are checked part by part, and salt variants resolve to one name
    - every flag carries a source; there is no "safe" wording and no advice
    - only serious flags need a decision; an unknown procedure is not guessed
  - **Validator:** rejects a non-verbatim quote, an unknown ingredient, an unknown target and advice wording; accepts every stored rule.
- `tests/test_v2_scenarios.py`: imported flags carry their source; Ignore and Research are logged with the rule-set version; an ignored flag stays listed.
- The browser journey ignores one flag with a note and reviews the rest.

## 6. Not done

- **AI suggestion layer (spec section 8)** is not built. The spec makes it optional and says to build it only after sections 4 to 7 are measured; the accuracy sample is still unmarked.
- **Language-model extraction** is not used: no model key is configured. The fixed patterns are reproducible, and any model output would have to pass the same validator.
- **DRAP / DrugsInfo Pakistan brand data:** needs a file or written permission.
- **Pharmacist sign-off** of the demo flags and the curated brand list.
- **Mechanism and management text** for interactions: DDInter's download does not include it.
- `docs/architecture.md` and the SRS traceability still describe the v1 rule approval (FR-61); the change for imported rules must be reflected there once the supervisor confirms gate 2.

## 7. Refreshing the data

```powershell
python scripts/build_ingredient_codes.py                     # RxNorm and ATC codes
python scripts/import_ddinter.py <folder of DDInter CSVs>     # interaction subset and coverage report
python scripts/extract_label_rules.py download <cache folder>
python scripts/extract_label_rules.py extract <cache folder>  # label rules
python scripts/label_rule_audit.py sample 100                 # new accuracy sample for the new release
docker compose up -d --build central worker; .\scripts\reset-and-seed.ps1 -Force
```

A new medicine added in the app under Medicine names only gets interactions and label rules after its ingredient is added to `ingredients.json` and these scripts are run again.
