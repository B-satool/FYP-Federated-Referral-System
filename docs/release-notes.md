# Release notes — v1.0-demo

First complete demonstration release of the Referral Preparation and Follow-through Platform. It covers SRS FR-01 to FR-72 within the provisional Stage 0 scope (orthodontics, English, synthetic data).

## What is included

- Three independent example systems (Clinic A, Lab B, Specialist C). Each has its own PostgreSQL database, FHIR R4 adapter and its own access decisions (role categories and access grants).
- Central modular platform covering:
  - verified patient links with identity checks, invalidation and impact analysis
  - parallel retrieval with six distinguishable outcomes, deduplication and versioned evidence
  - document upload, OCR, extraction review and correction history
  - medication mapping and deterministic, clinician-approved, versioned medication flags with re-evaluation and amendment
  - specialty checklist and discrepancy review
  - clarification requests with their own lifecycle
  - AI-assisted or template/manual brief with source references
  - clinician approval of immutable, hashed package versions
  - idempotent outbox delivery and specialist acknowledgment, decision, flag review and response
  - follow-up tasks, work queues, closure and audit
- One React application with role-specific screens for clinic staff, clinicians, rule reviewers, lab staff, specialists and administrators.
- Keycloak OIDC (code + PKCE). Token introspection at every service gives fast revocation.
- Operations: Compose stack, health/readiness checks, reset-and-seed, backup and disposable-environment restore check, retention sweep, load test, HL7 validation script, CI workflow.

## Verification summary

See `docs/testing.md`. Results of this build:

| Check | Result (2026-10-01/02) |
|---|---|
| T1–T6 API integration checks (`tests/`, fresh seed) | **29 passed, 1 skipped.** The skip is live-LLM brief generation (no API key in this environment); before skipping, that test confirms the visible failure and manual fallback. |
| Evaluator rule table, AI guardrails, offline provider checks (`services/central/tests`) | **37 passed** |
| Browser smoke journeys (`web/e2e/smoke.spec.ts`): normal end-to-end referral; denied source with unreadable document and manual fallback; changed medication flag requiring renewed review | **3 passed** (2.2 min) |
| Backup → restore into a disposable environment (`scripts/restore-check.ps1`) | **Passed.** Approved package REF-2026-00019 v2 restored; 4 documents reopened, 0 checksum mismatches. |
| 10-user load test inside the Compose network (keep-alive, 60 s, screen loads + draft saves) | **3,168 requests, 0 errors, p50 37 ms, p95 90 ms** (target p95 < 2,000 ms). Draft save p95 124 ms. |
| OCR evaluation (dev / held-out) | CER 0.000 / 0.008, field recall 1.00 / 1.00 (machine-generated renders only) |
| HL7 FHIR validator 6.3.4 (R4 4.0.1), offline (`-tx n/a`), on 10 resource types plus a searchset Bundle and an approved package Bundle | **No structural or reference errors.** 4 errors are the MIME code `application/pdf`, which cannot be resolved without a terminology server. 38 warnings are best-practice recommendations only (resource narrative dom-6, Observation.performer). LOINC and SNOMED codes are reported as "not checked" offline. Report: `contracts/fhir-samples/validation-report.html` (regenerate with `scripts/fhir-validate.ps1`). |

Measured from the Windows host through Docker Desktop's port proxy with a new connection per request, latency was about 2 s and some connections were reset. That is an artefact of the local proxy, not of the services; browsers use keep-alive and were unaffected in the smoke journeys.

## Known limitations (state these in the demonstration)

1. **Synthetic data and provisional clinical content.** The specialty, checklist, procedures, medication classes and rule references are provisional. The rules are AI-assisted drafts and need a named clinical reviewer to confirm meaning and references before any real use.
2. **OCR scope.** Tesseract handles typed and printed text. Accuracy was measured only on machine-generated renders, and **no claim is made about handwriting**. A real de-identified evaluation set and agreed thresholds are still needed.
3. **Language model.** Brief drafting and model-based extraction require `ANTHROPIC_API_KEY`. Without it the platform uses the evidence template, the manual editor and the deterministic rule-based extractor. The independent brief fact-checklist comparison (Roadmap T6) still has to be run with a key.
4. **Single specialist destination and single connected clinic patient index.** Clinic X exists only as a separate institution for authorization tests.
5. **Revocation at sources** takes up to about 10 s (the introspection cache). It is immediate at the central platform.
6. **Not production-hardened.** The local stack uses HTTP and `start-dev` Keycloak, with no rate limiting or HA. The hosted checklist is in `docs/operations.md`. Retention periods are placeholders pending institutional policy.
7. **Document storage** is a local volume behind a replaceable interface; no object storage or encryption at rest is configured.
