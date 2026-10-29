# Release notes

## v4: end-to-end encrypted referrals (branch `e2e-v4/wp5-approval`, 2026-10-30)

Built from `docs/e2e-architecture-spec-v4.md`. Sumaiya B. built WP0 to WP4 (2026-10-29); WP5 to WP11 were finished on
2026-10-30. Status per package: `docs/e2e-mapping.md`. Security claims and their limits: `docs/security-model.md`.

**What is included:**
- **Keys and consent:**
  - device keys for doctors and patients;
  - a hospital-signed key directory with pinned keys;
  - department group keys;
  - patient consent signed in the patient app;
  - each institution's own release policy, with refusal reason codes;
  - signed request assertions between the platform and the institutions.
- **Encryption:**
  - records arrive encrypted for the doctor, who decrypts them on the device;
  - staff see titles only;
  - the doctor signs the package, and the data keys are re-wrapped to the receiving department and the patient;
  - the receiving department's doctor verifies every item against the signature;
  - the receiving hospital can add its own records for its doctors.
- **AI only on a doctor's request:** de-identified on the device, previewed, and relayed without storage or logging.
  Record suggestions, and Layer 2 flag suggestions labelled "not verified".
- **Medication flags on the device** from a hash-checked bundle (DRAP brands, DDInter pairs). Ignore and Research are
  logged. No drug-procedure table.
- **Papers read on the device** (self-hosted Tesseract.js) and encrypted with the reading; the patient can add papers
  from the app.
- **Lifecycle:**
  - a reminder 30 days after acceptance, weekly repeats, escalation;
  - extensions with a reason, up to 180 days;
  - the specialist closes, and the referral is purged a week later by deleting the ciphertext and keys, with a receipt.
- **The patient keeps a verified copy** on the phone after the purge.
- **The audit trail is append-only and hash-chained.**

**Removed:**
- plaintext retrieval at the platform;
- per-patient sharing grants;
- the sender's copy;
- the receiver's stored package;
- server-side AI and OCR on the referral path;
- the hand-written drug-class rules and the drug-procedure label rules.

## v2 (branch `main`, 2026-10-28)

Version 2 rebuilds the prototype around the team's feedback. What changed and why is in `docs/v2-changes.md`, and
each decision is in `docs/decisions/`.

**What is included**
- **Institutions:** four synthetic Karachi institutions (Dr Ali's Clinic, Chughtai Lab, Ziauddin, Aga Khan). Each has
  its own database and its own access decisions, with expiring grants.
- **Referrals and test or scan requests:**
  - separate doctor and staff screens;
  - patient confirmation on arrival;
  - retrieval from every linked institution (up to five);
  - a rule-based packet selection, with an optional AI recommendation;
  - paper reading (Tesseract, or Google Cloud Vision for handwriting);
  - a referral letter with an immutable, hashed version.
- **The receiving doctor** accepts or declines (no written response), can keep the records longer, and marks the
  referral complete. Then the clinic tells the patient, and the doctor or staff close it.
- **Medication flags:**
  - reviewer-approved procedure rules, DDInter interactions and US drug-label warnings, each with its source;
  - about 5,000 DRAP brand names, with ambiguous names chosen by company;
  - AI clash suggestions, labelled "not verified".
- **Data lifecycle:** shared records are removed 72 h after the referral is marked complete (30-day safety limit,
  extendable), straight away on decline, on the platform and at the receiver. The manifest, fingerprint and audit
  stay.
- **Role templates:** administrators assign staff, doctor and other roles in the app.
- **Language models** through Ollama (local or `:cloud`), Anthropic or OpenAI-compatible servers. Input is always
  de-identified, and an external model needs explicit permission.

**Verification (2026-10-28):** unit 130 passed, API 22 passed, browser 3 passed, type check and build clean.
See `docs/testing.md`.

**Known limitations**
1. Synthetic data. The clinical rules, procedure features and brand mappings are not clinically reviewed; the
   DRAP brands are loaded unchecked, by decision.
2. Live model and Vision calls have not run yet: the Ollama account needs credits, and there is no Vision key. The
   platform falls back to the rule-based selection and Tesseract.
3. De-identification uses patterns and can miss unusual text. Page images sent to Vision cannot be de-identified.
   Synthetic data only.
4. Retention numbers are placeholders.
5. Not production-hardened (HTTP on localhost, demo passwords). See `docs/operations.md`.
6. Load test and backup/restore check not re-run on v2.

---

## v1.0-demo (2026-10-02, tag `v1.0-demo`)

First complete demonstration release of the Referral Preparation and Follow-through Platform. It covers SRS FR-01 to FR-72 within the provisional Stage 0 scope (orthodontics, English, synthetic data).

### What is included

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

### Verification summary

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

### Known limitations (v1)

1. **Synthetic data and provisional clinical content.** The specialty, checklist, procedures, medication classes and rule references are provisional. The rules are AI-assisted drafts and need a named clinical reviewer to confirm meaning and references before any real use.
2. **OCR scope.** Tesseract handles typed and printed text. Accuracy was measured only on machine-generated renders, and **no claim is made about handwriting**. A real de-identified evaluation set and agreed thresholds are still needed.
3. **Language model.** Brief drafting and model-based extraction require `ANTHROPIC_API_KEY`. Without it the platform uses the evidence template, the manual editor and the deterministic rule-based extractor. The independent brief fact-checklist comparison (Roadmap T6) still has to be run with a key.
4. **Single specialist destination and single connected clinic patient index.** Clinic X exists only as a separate institution for authorization tests.
5. **Revocation at sources** takes up to about 10 s (the introspection cache). It is immediate at the central platform.
6. **Not production-hardened.** The local stack uses HTTP and `start-dev` Keycloak, with no rate limiting or HA. The hosted checklist is in `docs/operations.md`. Retention periods are placeholders pending institutional policy.
7. **Document storage** is a local volume behind a replaceable interface; no object storage or encryption at rest is configured.
