# Testing checkpoints (Roadmap T0–T7)

Testing is kept proportionate (Roadmap §15):
- **Every PR:** build, type and lint checks, plus the checks affected by the change.
- **Stage gates:** the shared scenario for that stage.
- **Deployment:** a short smoke check.

Paid model calls happen only at model or prompt changes.

## How to run

```powershell
docker compose up -d --build
python -m venv .venv; .\.venv\Scripts\pip install httpx pytest
.\.venv\Scripts\python -m pytest tests -q          # reseeds every database first (SKIP_RESET=1 to keep data)
docker compose run --rm --no-deps -v ${PWD}/services/central/tests:/srv/tests central python -m pytest tests -q
cd web; npx playwright install chromium; npx playwright test e2e/smoke.spec.ts
```

The integration tests stop and start the `lab` and `clinic` containers to simulate outages, so the Docker CLI must be available.

## Checkpoints

| Gate | What is checked | Where |
|---|---|---|
| **T0** Feasibility | One patient traced clinic → specialist with sample JSON (`contracts/examples`); one OCR sample; one generated brief (with a key) | `scripts/export_contract_examples.py`, `scripts/evaluate_ocr.py`, T6 generation |
| **T1** Foundation & access | Fresh start and seed; allowed vs cross-institution denied at central **and** at each source; unauthenticated and forged tokens rejected; admin has no clinical access; disabled account rejected at central immediately and at sources after the introspection cache; job status visible | `tests/test_t1_foundation.py`, T4 jobs |
| **T2** Federation & identity | Only verified links import evidence; Clinic A/MR-102 ≠ Lab B/MR-102; invalidated link unused; repeat retrieval creates no duplicates; denied ≠ unavailable, other evidence kept, bounded retry and recovery; identity check, verify, invalidate with affected referrals and history; lab correction → new record version; HL7 validation of representative resources | `tests/test_t2_federation.py`, `scripts/fhir-validate.ps1` |
| **T3** Manual journey | create → retrieve → verify → flags → template brief → approval → edit approved (→ draft, v2) → stale save rejected → send → duplicate send ignored → tampered package rejected → acknowledge → flag reviews → accept → response approval enforced → return → clinic receipt / review → task → close; decline and cancel reasons; search and filters; audit coverage | `tests/test_t3_manual_flow.py` |
| **T4** Documents | Digital PDF (embedded text), scanned image (OCR with regions), unreadable sample, rejected file; correction keeps prior value; clinician-only verification; authenticated downloads; dose discrepancy across sources; same test on different dates is not a conflict; manual transcription | `tests/test_t4_documents.py`, `scripts/evaluate_ocr.py` |
| **T5** Medication flags | Table: confirmed, stopped, uncertain, unverified, ambiguous mapping, missing procedure, denied/unavailable source, no match, procedure outside rule, specialty-only rule, deterministic repeat, changed rule version, no rules (unsupported coverage), evaluation failure, no medication-change advice. Integrated: reviewer-only activation, procedure context changes, no duplicate flags, incomplete history coexists, changed flag after submission → amendment, new package version, version-specific specialist review, specialist clarification relay | `services/central/tests/test_evaluator.py`, `tests/test_t5_medication_flags.py` |
| **T6** Full workflow | Missing-information request to Lab B answered in the lab work queue (lab sees only its own ID); checklist missing items and non-overridable fields; clinician-only priority; brief generation (visible failure and manual fallback without a key; real model and citation checks with a key); guardrail unit tests | `tests/test_t6_full_flow.py`, `services/central/tests/test_brief_validation.py` |
| **T7** Stabilization | Three browser smoke journeys; backup → restore into a disposable environment; 10-user load test against the p95 < 2 s target; regression of earlier checks | `web/e2e/smoke.spec.ts`, `scripts/backup.ps1` + `scripts/restore-check.ps1`, `scripts/loadtest.py`, all of the above |

## Latest recorded results

See the release notes section of `docs/release-notes.md` for the results of the v1.0-demo build.
