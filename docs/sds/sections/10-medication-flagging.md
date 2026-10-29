# 10. Medication flagging design

> **Superseded in part by section 18 (spec v4, 2026-10-30).** Flags are computed on the device from the hash-checked bundle (Layer 1) with AI suggestions (Layer 2); the hand-written drug-class rules and the drug-procedure label rules were removed (section 18.6).

## 10.1 Principles

- Flags come **only** from `evaluate_medications()`, a pure, deterministic function. The same medicines, procedure, conditions and rule set always give the same flags (invariant 5).
- A flag reports a recorded rule, interaction or label statement and its source. It never advises starting, stopping or changing a medicine, never prescribes and never assigns urgency.
- Nothing is reported as "safe". No match means "no matching rule on file".
- Every gap is a flag of its own kind, so missing checks are visible:
  - a medicine that isn't recognised;
  - an ingredient that isn't in the interaction source;
  - a procedure that isn't known;
  - records that are incomplete.
- A doctor's decision on a flag ("reviewed", "ignore", "research") means it was seen. It is never treatment clearance.

## 10.2 Data sources

| Source | Table and file | Status |
|---|---|---|
| Manual drug-class-by-procedure rules | `medication_rules` (seeded from `rules/medication/seed-rules.json`, edited in the app) | Active only when a `rule_reviewer` approves that exact version (content hash recorded) |
| Drug–drug interactions | `drug_interactions` (DDInter 2.0 subset, `rules/interactions/ddinter-subset.csv`, CC BY-NC-SA 4.0) | Imported as loaded; severity is DDInter's own (Major, Moderate, Minor, Unknown) |
| Drug-condition and drug-procedure statements from US drug labels | `label_rules` (`rules/labels/label-rules.json`, made by `scripts/extract_label_rules.py`) | Imported; each keeps the exact quoted sentence, section and source; validated by `label_validation.py` |
| Ingredients | `ingredients` (`rules/terminology/ingredients.json`): international name, label name, RxNorm and ATC codes, combination parts | Reference data |
| Medicine names | `medicine_names` (`rules/terminology/medicine-names.pk.json`): generic names, hand-checked brands, DRAP register brands, ambiguous register names | Reviewer-maintained; register brands loaded by decision 2026-10-28 |
| Rule set fingerprint | `ruleset_releases` | Hash of the approved manual rules, label rules and interaction data in force |

**Interaction explanations.** DDInter's download gives only the pair and its level. `scripts/extract_label_rules.py interactions` adds, for each pair, the shortest sentence from either drug's US label that names the other drug and talks about the combination. The drug-interactions section is preferred, and the sentence is kept verbatim in `rules/labels/interaction-quotes.json`, loaded onto `drug_interactions.label_quote`.
- **Excluded:** drug-class mentions ("calcium channel blockers"), fragments cut at headings, and pairs read and found irrelevant (`REVIEWED_NOT_RELEVANT`).
- **No quote, no explanation:** without a quote nothing is shown. No model writes explanations.

**How label rules are validated.** A rule from a drug label is kept only if:

- the quoted sentence appears verbatim in the cited section;
- the ingredient is one of the project's;
- the target is in the controlled vocabulary (`rules/vocab/label-targets.json`);
- the summary contains no advice to start, stop or change a medicine.

Sentences are matched to targets by fixed word patterns, so the same label always gives the same rules.

## 10.3 Inputs to the evaluator

- **Current medicines:** each entry's mapping status, ingredient(s), drug class, original name, source label and evidence ids. Duplicates are excluded and combination products are expanded into their parts.
- **Procedure:** the status (`planned`, `none`, `unknown`) and tags.
- **Conditions:** from the selected evidence.
- **Rule data:** approved manual rules, interaction pairs and coverage (which ingredients DDInter knows), and label rules.
- **Source outcomes:** the retrieval results, so incomplete records can be reported.

## 10.4 Procedure features

A doctor writes the procedure in their own words and ticks what it involves. Words in the name pre-tick likely features (`PROCEDURE_HINTS` in `config.py`, for example "extraction" ticks oral surgery and bleeding risk), and the doctor can change them. Nothing is guessed silently.

| Tag | Meaning |
|---|---|
| `oral_surgery` | Oral or dental surgery |
| `major_surgery` | Major or elective surgery |
| `minor_surgery` | Minor surgery |
| `general_anaesthesia` | General anaesthesia |
| `prolonged_fasting` | Fasting before and after the procedure |
| `iodinated_contrast` | Iodinated contrast media |
| `arterial_access` | Arterial puncture |
| `gi_endoscopy` | Gastrointestinal endoscopy |
| `sedation` | Sedation |
| `bleeding_risk` | Procedure with bleeding risk |

A manual rule matches a drug class against these tags, so one rule covers every procedure with the tag. Drug classes are listed in `DRUG_CLASSES` (`config.py`): anticoagulant, antiplatelet, NSAID, biguanide, sulfonylurea, SGLT2 inhibitor, insulin, bisphosphonate, systemic corticosteroid, statin, beta blocker, ACE inhibitor, ARB, calcium channel blocker, PPI, analgesic, opioid, antibiotic, antiviral, antispasmodic, iron, calcium and vitamin D, thyroid hormone, bronchodilator.

## 10.5 Flag kinds

| Kind | Raised when | Needs the doctor's decision before sending |
|---|---|---|
| `confirmed` | An approved manual rule's drug class matches a current medicine and the planned procedure has a matching tag | Yes |
| `interaction` | Two current ingredients form a DDInter pair. If a US drug label has a sentence naming both, it is shown verbatim as the flag's source quote, with the label and section | Only for Major |
| `label_warning` | A label rule's ingredient is current and its target matches a condition or procedure feature | Only for severity hint "high" |
| `unrecognised_medicine` | A medicine's name is unmapped or ambiguous (including DRAP names registered for different medicines) | Yes |
| `procedure_not_checked` | The procedure is unknown, or planned without features, and a current medicine has procedure rules | Yes |
| `interactions_not_checked` | A current ingredient is not covered by the interaction source | Yes |
| `records_incomplete` | A source was denied, expired, unavailable, invalid, partial or skipped | Yes |

When nothing matches, the evaluation summary says so in neutral words. If no rule data is loaded at all, the outcome is `no_rules`, never "no problems".

## 10.6 Versioning, decisions and the package

- **Evaluation runs.** Every evaluation is an `evaluation_runs` row: trigger, outcome, input hash, rule versions, rule-set hash and number of changed flags.
- **Flag versions.** A flag whose content changes is superseded and a new version is inserted. A decision (`flag_reviews`) is bound to one flag version and the rule-set hash. A new version needs a new decision.
- **In the package.** The package carries every active flag as a `FlagSnapshot` with its source (type, name, reference, version, quote), its severity, whether it was auto-generated, and the doctor's decision and note. The evaluation summary and the AI suggestions travel beside the flags.
- **At the receiving side.** The specialist sees the flags as structured items, not as text restated in the letter.

## 10.7 Rule maintenance

| Action | Who | Endpoint |
|---|---|---|
| Create a manual rule or a new version | Rule reviewer | `POST /rules`, `PUT /rules/{rule_id}` |
| Approve or reject a version (reference checked, note) | Rule reviewer | `POST /rules/{rule_id}/versions/{version}/decision` |
| Inspect interactions, label rules, AI model figures | Rule reviewer | `GET /rules/interactions`, `/rules/label-rules`, `/rules/ai` |
| Add or retire a medicine name | Rule reviewer | `POST /medicine-names`, `POST /medicine-names/{id}/retire` |
| Import DDInter, label rules, brand names | Developer, offline | `scripts/import_ddinter.py`, `extract_label_rules.py`, `import_brands.py`, `scrape_drap.py` |

The DRAP register snapshot (`rules/terminology/drap/`) comes from the public DRAP product search:

- **Products:** all 115,006 products, with structured details for 1,500 of them.
- **Brand mappings:** 5,398 brands loaded as register mappings; 21 ambiguous names held as options.
- **Veterinary products** are excluded wherever DRAP's detail page says so.

Decisions 2026-10-28 ("DRAP register snapshot", "DRAP brands loaded") record the method and the accepted risk.
