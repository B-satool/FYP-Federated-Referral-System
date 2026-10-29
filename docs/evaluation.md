# OCR, extraction and brief evaluation

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
