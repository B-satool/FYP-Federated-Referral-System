# Data sources and external services (spec v4 9.1, 10, 16 O2)

| Source | Used for | Licence or terms | Where |
|---|---|---|---|
| **DDInter 2.0** (https://ddinter.scbdd.com) | Drug-drug interaction pairs with severity and identifiers (342 pairs among the project's ingredients) | CC BY-NC-SA 4.0 (Bioregistry), acceptable for a non-commercial academic prototype. **Re-check at each download.** | `rules/interactions/` |
| **DRAP product register** (team snapshot) | Pakistani brand names mapped to ingredients, with company and registration number (4,996 register names, 21 names registered for different medicines) | Public register; snapshot agreed by the team; rate-limited collection | `rules/terminology/drap/` |
| **Hand-checked medicine names** | Brands and generics checked one by one | Project data | `rules/terminology/medicine-names.pk.json` |
| **US drug labels (openFDA / DailyMed)** | Verbatim quotes shown with interaction flags, and drug-condition label rules | Public domain (US government works) | `rules/labels/` |
| **Tesseract.js 5.1.1 and the English `best_int` model** | Reading scanned papers on the device | Apache 2.0. Served by this application, not a CDN. | `web/package.json`, `web/public/ocr` (copied at build) |
| **An external language model** (the demo uses Groq, `openai/gpt-oss-120b`) | AI record suggestions and Layer 2 flag suggestions, on a doctor's request, de-identified | The provider's API terms. Groq states that API data is not used for training; **confirm the current terms and data location before any use beyond synthetic data.** Data leaves the country (O2). | `.env` (`LLM_*`), `docs/decisions/2026-10-28-cloud-model-privacy.md` |

**The medication bundle** (`GET /med-bundle`) is built from the first four sources. It is versioned by its SHA-256 over
canonical JSON, and the browser checks that hash before computing any flag. Size: about 5,100 names and 342 pairs, a
few hundred kilobytes as JSON. That is small enough for a phone, so it is not split.

**No external OCR service is used**, so no image or text leaves the device (D15). If one is added, it must be called
directly from the device with short-lived credentials, with header masking on, and its terms recorded here.
