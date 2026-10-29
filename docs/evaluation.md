# Evaluation

## Spec v4 research questions (section 15), status on 2026-10-30

| RQ | Question | Status |
|---|---|---|
| RQ1 | Does patient matching find one person across institutions despite spelling variants? | **Planned, not run.** Matching is by CNIC and name, confirmed by staff. A benchmark of synthetic name-variant pairs against `POST /identity/lookup` is still to be built. |
| RQ2 | Can the AI pick what a clinician would include, compared with the fixed floor? | **Planned, not run.** The relay and the floor are built. The gold lists are the seed patients' `expected_retrieval_view`. Running it needs model calls (Groq free tier, about 2 referrals a minute). |
| RQ3 (brand mapping) | How well are Pakistani brand names mapped as people write them? | **Run** (below) |
| RQ3 (handwriting) | How reliably are medicine, dose and frequency read from handwriting? | **Planned, not run.** Tesseract.js runs on the device; no synthetic handwritten set exists yet. The v1 Tesseract figures below are for machine-rendered text only. |
| RQ4 | Does the AI layer rediscover held-out known interactions, and with how many false alarms? | **Planned, not run.** The Layer 2 relay is built. A held-out DDInter set and a curated drug-procedure set (a benchmark only, never loaded at runtime) are still to be built. |
| T-PERF-1 | Time and size to open a typical referral on a device | **Run on a laptop, not on a phone** (below) |

### RQ3: brand mapping (2026-10-30)

`node evaluation/e2e/rq3-brand-mapping.ts <bundle.json>` runs the browser's Layer 1 matcher
(`web/src/features/e2e/flags.ts`) on variants of the 54 hand-checked single-word brands in bundle `177b7e86d7cd`.
Results: `evaluation/results/rq3-brand-mapping-latest.json`.

| Written as | Cases | Mapped exactly | Approximate, right ingredient | Wrong ingredient | Left unmapped |
|---|---|---|---|---|---|
| As on the pack | 54 | 54 | 0 | 0 | 0 |
| Upper case with a strength ("DISPRIN 75mg") | 54 | 54 | 0 | 0 | 0 |
| With "Tab." and form words | 54 | 54 | 0 | 0 | 0 |
| One dropped letter | 54 | 0 | 43 | 1 | 10 |
| Two letters swapped | 54 | 1 | 50 | 0 | 3 |
| One letter doubled | 54 | 0 | 52 | 0 | 2 |
| Two slips | 54 | 0 | 5 | 2 | 47 |

**Reading it:**
- **Approximate matches are never silent.** The screen shows "Spelling close to …: check it is the same medicine",
  and any flag from such a match is tagged "name matched approximately".
- **The 3 wrong-ingredient cases** (out of 378) are why that tag exists.
- **Unmapped names are "could not be assessed",** not "no issues", and can be sent to the AI.
- **The benchmark is synthetic.** It tests typing slips, not real prescriptions or the DRAP register names.

### T-PERF-1: opening a referral on the device (2026-10-30)

`node web/scripts/perf-decrypt.ts`: 30 items (25 records and 5 scans of 1.5 MB) in 4 batches. That is about 10 MB to
download (base64). The median time to unwrap the data keys, decrypt every item and hash it for the manifest check was
**62 ms** (range 57–72 ms over 5 runs). This was the browser crypto code under Node 24 on the team's laptop. A
mid-range phone has not been measured.

---

# OCR, extraction and brief evaluation (v1 and v2)

> **v1 measurements.** These figures are for Tesseract on machine-rendered samples. Handwriting (Google Cloud Vision, `OCR_ENGINE=google_vision`) and the AI packet selection have not been evaluated on real data yet; see [testing.md](testing.md).

## What was evaluated

| Item | Setup |
|---|---|
| OCR engine | Tesseract 5 (LSTM, `--psm 4`) behind `extract_document()`, with grayscale, upscale and autocontrast preprocessing |
| Field extractor | `rules-extractor/1`, deterministic. It proposes only supported medication and laboratory fields. |
| Development set | `evaluation/ocr/dev/`: 3 scanned-style renders (prescription, lab slip, clinic note), with transcriptions and expected fields |
| Held-out set | `evaluation/ocr/heldout/`: 3 different renders with heavier noise and rotation. Run only after the model choice was fixed. |
| Script | `scripts/evaluate_ocr.py` (same code path as production). Results in `evaluation/results/ocr-latest.json`. |

## Baseline results (2026-10-01)

| Split | Docs | Mean CER | Mean WER | Supported-field recall | Field precision | Mean OCR time |
|---|---|---|---|---|---|---|
| dev | 3 | 0.000 | 0.000 | 1.00 | 1.00 | ≈2.0 s |
| held-out | 3 | 0.008 | 0.022 | 1.00 | 1.00 | ≈1.0 s |

Integration checks also covered the four sample documents (T4):
- **Digital PDF:** embedded text used, no OCR needed, all medication fields found.
- **Scanned note:** OCR found Ecosprin, INR 2.6 and Hb 12.9 with line regions.
- **Unreadable image:** classified *unreadable* (fewer than 3 words or mean OCR confidence under 55), with nothing guessed.
- **Mismatched file:** rejected at upload.

## Limits of these results (read before quoting them)

- All samples are **machine-generated, typed renders** with synthetic noise. They show the pipeline works end to end. They **do not** show reliability on real handwriting or real clinic scans. Never cite these numbers as handwriting accuracy.
- The sets are very small (3 + 3). Before quoting any figure, build a larger set from real **de-identified** documents with accurate transcriptions, labelling machine-generated layouts and handwriting separately.
- Numeric acceptance thresholds (CER, field accuracy, correction time) are **not yet agreed**; SRS §11 asks for them to be set after this baseline. Proposed starting points for discussion: field recall ≥ 0.9 on supported fields, *zero* silent guesses (missing stays missing), and correction time measured during the supervisor demo.
- OCR confidence is stored only as tool metadata and is never shown as a clinical probability.

## Brief generation

Generation needs an API key (`ANTHROPIC_API_KEY`), so routine CI never calls the paid model. The guardrails are tested without a model (`services/central/tests/test_brief_validation.py`):
- references outside the supplied evidence are rejected
- record-derived statements must cite evidence
- the schema has no section in which the model could restate medication flags
- the prompt forbids converting "not available" into "no history"
- an unconfigured provider fails visibly

With a key, `tests/test_t6_full_flow.py::test_brief_generation_path` runs the real model and checks that every citation is within the supplied evidence set.

**Fact-checklist comparison (Roadmap T6), still to be run by the team with a key:**
1. For 3–5 held-out referrals, write an independent fact checklist (which facts must appear, which must not).
2. Generate briefs and score unsupported claims, relevant omissions, source accuracy and clinician correction time.
3. Do not use the same model as the only judge of its own output.

Record results in `evaluation/results/briefs-<date>.md`.

## Performance (NFR 10.4)

`scripts/loadtest.py`: 10 concurrent users for 60 s of screen loads and draft saves. OCR and LLM completion are excluded from request latency by design and timed separately as jobs. Results go to `evaluation/results/load-latest.json`; see docs/testing.md for the latest run.
