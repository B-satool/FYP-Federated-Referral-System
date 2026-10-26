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

## 6. AI suggestion layer (spec section 8)

Built on 2026-10-27, at the project lead's request. It is offline and small, and it cannot touch flags.

**How suggestions are made**
- **Model:** logistic regression (`scripts/train_ai_suggestions.py`). For a pair of drugs, the features are:
  - whether they share an ATC group;
  - how often each drug's ATC class-mates have recorded DDInter interactions with the other drug;
  - how many interactions each drug has;
  - which ATC main groups are involved.
- **ATC classes:** from RxNav, keeping only classes a drug has on its own. RxNav marks these as term type IN; MIN means the class came from a combination product, and those are dropped. Combination, topical, eye, ear, mouth and skin classes are also left out.
- **Training:** the positives are the 160,235 known DDInter pairs. Pairs absent from DDInter are unlabelled, not negatives: a random sample of them is used as background.
- **Output:** the app never runs the model. The script scores every pair among our ingredients that has no DDInter entry, and writes those at or above 0.8 to `rules/ai/suggestions.json` (66 pairs). Each has the two ingredient names, a score, a one-line reason naming the ATC class and example class-mates, and the model and data versions.

**How it is measured**
- 20% of known interactions are held out.
- The class-mate features for the evaluation come from the training interactions only.
- Full figures are in `rules/ai/evaluation.json` and on the reviewer's AI suggestions tab.

| Threshold | Held-out interactions found | Major | Moderate | Minor | Suggestions per 100 random pairs not in DDInter |
|---|---|---|---|---|---|
| 0.5 | about 87% | 90% | 87% | 80% | about 10 |
| 0.8 (used) | 73% | 80% | 74% | 68% | 3.4 |
| 0.9 | about 63% | 72% | 64% | 57% | about 2 |

**Caveats (also stored with the evaluation)**
- A pair not in DDInter is not proven harmless, since DDInter is incomplete.
- The model can only generalise DDInter's class patterns.
- Class-mates can behave differently. For example, cimetidine and esomeprazole share ATC group A02B, but only cimetidine strongly inhibits liver enzymes; this is why esomeprazole gets many suggestions.
- Random pairs are easier than the pairs a doctor actually sees.
- None of these figures is clinical accuracy.

**In the app**
- Doctors see an **AI suggestions** section, separate from the flags and labelled "AI suggestion, not verified", for pairs among the current medicines with no DDInter entry. A pair that DDInter covers is never suggested, whatever its score.
- The doctor can mark each suggestion **Ignore** or **Research**, the same choices as for flags. The review is stored with the score and the model and data versions, and audited.
- Suggestions never block sending and never remove or downgrade a flag. Since spec v3 (work package D, see `docs/decisions/2026-10-27-data-lifecycle-and-v3.md`), they **are sent in the package**, in their own `ai_suggestions` field and letter section labelled "AI suggestion, not verified", with the doctor's decision. They are part of the package fingerprint. When there is nothing to show, the letter says "No rule or suggestion on file".
- The evaluator has no input from the model. Unit tests force every score to 0 and to 1 and check that the flags are identical.

## 7. Pakistani brand data

DrugsInfo Pakistan (drugsinfo.pk) says it imports brand, composition, pack and DRAP registration data from DRAP's registry. Its site has a search but no download, no published terms page, and its robots.txt disallows `/api/`. DRAP's own search page offers no export and restricts use of its list. So neither site is scraped. To bring real Pakistani brand data in:

1. **Ask for a file.** Use the contact page at drugsinfo.pk/contact (or the supervisor's or faculty contact with DRAP). Ask for an export of brand name, generic composition with strengths, dosage form, company and DRAP registration number, for non-commercial academic use, and keep their written permission.
2. **Or build the file by hand** for the brands you need (for example those in the seed patients' prescriptions), reading DrugsInfo or DRAP search results or the packs. Use `rules/terminology/brand-import-template.csv`.
3. **Import it:**
   - Run `python scripts/import_brands.py <file.csv>` to see the report: brands added, combination products recognised by their parts, unknown ingredients, and brand names that would become ambiguous.
   - Then run it again with `--write`.
   - Each imported brand's source, DRAP number and checker are kept in `rules/terminology/brand-sources.csv`.
   - New ingredients then need the code, DDInter and label scripts to be run again (section 9) before they are checked.

## 8. Not done

- **Language-model extraction** is not used: no model key is configured. The fixed patterns are reproducible, and any model output would have to pass the same validator.
- **DRAP / DrugsInfo Pakistan brand data:** needs a file or written permission (section 7).
- **Pharmacist sign-off** of the demo flags and the curated brand list.
- **Mechanism and management text** for interactions: DDInter's download does not include it.
- `docs/architecture.md` and the SRS traceability still describe the v1 rule approval (FR-61); the change for imported rules must be reflected there once the supervisor confirms gate 2.

## 9. Refreshing the data

```powershell
python scripts/build_ingredient_codes.py                     # RxNorm and ATC codes
python scripts/import_ddinter.py <folder of DDInter CSVs>     # interaction subset and coverage report
python scripts/extract_label_rules.py download <cache folder>
python scripts/extract_label_rules.py extract <cache folder>  # label rules
python scripts/label_rule_audit.py sample 100                 # new accuracy sample for the new release
python scripts/train_ai_suggestions.py codes <folder of DDInter CSVs>   # ATC classes for DDInter drugs (needs scikit-learn for train)
python scripts/train_ai_suggestions.py train <folder of DDInter CSVs>   # model, evaluation, suggestions
docker compose up -d --build central worker; .\scripts\reset-and-seed.ps1 -Force
```

A new medicine added in the app under Medicine names only gets interactions and label rules after its ingredient is added to `ingredients.json` and these scripts are run again.
