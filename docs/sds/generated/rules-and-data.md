## Rules and reference data (`rules/`)

Data files loaded at seed time or read by the services. Large data sets are summarised.

| File | Size | Contents |
|---|---|---|
| `rules/ai/atc-class-names.json` | 55 KB | 0, A, A01, A01A, A01AA, A01AB |
| `rules/ai/ddinter-atc.json` | 57 KB | abacavir: 1, abaloparatide: 1, abametapir (topical): 0, abarelix: 1, abatacept: 1, abciximab: 1 |
| `rules/ai/evaluation.json` | 2 KB | model_version, trained, training_data, known_interactions, drugs, drugs_with_atc |
| `rules/ai/model.json` | 1 KB | model_version, data_version, features: 24, coefficients: 24, intercept, threshold |
| `rules/ai/suggestions.json` | 25 KB | model_version, data_version, threshold, label, suggestions: 66 |
| `rules/interactions/README.md` | 1 KB |  |
| `rules/interactions/ddinter-import-report.json` | 1 KB | imported, files: 8, files_sha256, ddinter_rows, ddinter_drugs, ddinter_drugs_not_mapped_to_our_ingredients |
| `rules/interactions/ddinter-subset.csv` | 28 KB | 342 rows |
| `rules/labels/interaction-quotes.json` | 20 KB | version, extractor_version, content_sha256, status, stats: 4, quotes: 37 |
| `rules/labels/label-rules.json` | 66 KB | version, extractor_version, vocabulary, content_sha256, status, stats: 8 |
| `rules/roles/templates.v2.json` | 7 KB | template_set_id, version, approved, note, screens: 12, scopes: 16 |
| `rules/sources.json` | 3 KB | note, ddinter: 13, openfda_labels: 6, rxnav: 5, brand_names: 4 |
| `rules/terminology/brand-import-template.csv` | 0 KB | 2 rows |
| `rules/terminology/brand-sources.csv` | 965 KB | 5433 rows |
| `rules/terminology/drap/brand-import.csv` | 689 KB | 6122 rows |
| `rules/terminology/drap/details.jsonl` | 588 KB | 1517 rows |
| `rules/terminology/drap/drugs.csv` | 162 KB | 1360 rows |
| `rules/terminology/drap/products.csv` | 11,643 KB | 115006 rows |
| `rules/terminology/ingredients.json` | 8 KB | version, note, ingredients: 44, codes_retrieved |
| `rules/terminology/medicine-names.pk.json` | 123 KB | version, note, entries: 43, register_ambiguous: 21 |
| `rules/vocab/label-targets.json` | 6 KB | version, note, procedure: 7, condition: 8, severity_by_section: 5 |
