# Architecture and Stage 0 decisions

> **Version 1 document.** Version 2 changed the institutions, roles, linking, retrieval, medicines and sending; see [v2-changes.md](v2-changes.md) for what differs. This page has not been rewritten for v2 yet.

This file records the implementable scope agreed in Stage 0 (Roadmap §7) and the system boundaries (Roadmap §1). Items marked **(provisional)** are reasonable defaults chosen so the prototype could be built. They still require confirmation by the supervisor and a clinical reviewer, as SRS §12 requires.

## 1. System boundaries

| Component | Owns | Talks to |
|---|---|---|
| Clinic A service (`services/clinic`) | `clinic_db`: patients, encounters, conditions, prescriptions, patient-reported medication, document metadata, access grants, audit | Nobody. It answers authorized requests only. |
| Lab B service (`services/lab`) | `lab_db`: patients, results, reports, result revisions, access grants, audit | Nobody |
| Specialist C service (`services/specialist`) | `specialist_db`: patients, prior consultations, received package versions, decisions, flag acknowledgments, clarifications, responses, outbox | Central `/inbound/specialist-events` (service token) |
| Central platform (`services/central`) | `central_db`: users, patient links, referrals, evidence, documents, extraction, medication entries, rule approvals, flags, reviews, briefs, packages, outbox, responses, tasks, audit; plus the protected document volume | Source APIs only (forwarded user token or service token) |
| Worker (same image, `celery -A app.tasks`) | Nothing of its own; job state lives in `central_db` | OCR, LLM provider, specialist inbound API |
| Keycloak | Its own `keycloak` database | — |

There is one PostgreSQL server with **separate databases and separate logins** per owner (`infra/postgres/init`). The central service is configured only with `central_db` credentials. Redis is only the job queue, never a source of truth.

## 2. Identity and authorization

- Browser sign-in uses OIDC authorization code with PKCE (public client `referral-web`). Institution comes from Keycloak group membership; roles are realm roles.
- Every service verifies the JWT signature, issuer and **its own audience**. It then **introspects** the token with Keycloak, cached for 10 s. A disabled account or ended session therefore stops working at the source services within seconds.
- The central platform also checks its own `users.account_status` on every request. Disabling an account blocks access to centrally retained data immediately (FR-05).
- **Source authorization (FR-03, FR-04).** A source allows a request when either:
  - the caller belongs to the source's own institution, filtered by role category (clinic staff do not receive `conditions`); or
  - the source's administrator has granted an access grant for that patient and category (`access_grants` table, managed in each source's admin screen).

  The central platform forwards the user's own token, so the source decides about that user.
- **Service-to-service calls.** Central delivers packages to the specialist with the `central-api` client-credentials token (role `svc_central`). The specialist returns events with the `specialist-api` token (role `svc_specialist`). Browser-supplied identity headers are never trusted.
- **Administrators.** An administrator manages accounts, grants and link corrections, but receives no clinical record access (central `load_referral` requires a clinical role).
- **Rule approval.** Only the `rule_reviewer` role can approve medication rules.

## 3. Stage 0 decisions

| Decision (SRS §12) | Choice |
|---|---|
| Specialty | **Orthodontics** (single specialty), destination Specialist C **(provisional)** |
| Procedure contexts | orthodontic assessment, fixed appliance, tooth extraction, mini-implant placement, orthognathic surgery. The procedure may be **explicitly unknown**; "not stated" blocks submission. |
| Medication classes covered by rules | anticoagulant, antiplatelet, bisphosphonate, systemic corticosteroid **(provisional)** |
| Rule files | `rules/medication/orthodontics.v1.json`. Shipped as **drafts**. A rule is active only after a `rule_reviewer` approves that exact version in-app; the approval stores reviewer, reference checked and content hash. Editing the file invalidates the approval. **The listed references must be confirmed by the clinical reviewer.** |
| Clinical rule reviewer | Role `rule_reviewer` (demo account `dr.reviewer`). A named clinician must be identified before any real use. |
| Mapping source | Local reviewed dictionary `rules/terminology/medication-dictionary.v1.json` (RxNorm RxCUI and ATC codes recorded as identifiers). Entries marked `suggested` are never treated as verified mappings. |
| Checklist | `rules/checklists/orthodontics.v1.json`. Required and non-overridable: reason, clinician-selected priority, procedure stated or unknown, referring clinician. Blocking but overridable by a clinician with rationale: documented history, medication use verified, document/manual fields verified, discrepancies reviewed. Non-blocking limitations: source outages. **(provisional)** |
| Supported discrepancy types | Same ingredient with a different dose instruction in current records; same lab test on the same collection date with different values. Values that differ across dates are never flagged. |
| Documents | English; PDF, PNG and JPEG; up to 10 MB and 10 pages; types prescription, laboratory report, referral/clinic note **(provisional)** |
| OCR / HTR | **Tesseract 5 (LSTM)** behind `extract_document()`. Embedded text is used for digital PDFs. It was chosen over TrOCR because TrOCR needs a separate line-segmentation step and more memory than the 4 GB demo budget allows. The interface allows replacement (Azure Read or TrOCR). |
| Field extraction | The language model with a strict JSON schema and line-ID allowlist when configured, otherwise the deterministic `rules-extractor/1`. Both propose only supported medication and laboratory fields. |
| Language model | `claude-opus-5-5` via the Anthropic SDK behind `LLMProvider`, using structured JSON-schema output with server-side refusal fallback. Optional: everything works without it (FR-58). |
| FHIR | R4 **4.0.1**, limited subset (docs/fhir-subset.md). Custom project endpoints return FHIR content; package and event envelopes are labelled *project API contract*. |
| Patient-link verification | A clinician or institution administrator verifies a proposed link and records the basis. An optional source-side identity check returns field-match booleans only. Identical local IDs never link automatically. |
| Retention | Uploaded document copies, page images and extraction text are deleted `DOCUMENT_RETENTION_DAYS` (default 365) after referral closure by the hourly `retention_sweep`. Approved package snapshots and audit history are retained. **(provisional; needs institutional policy before hosted use)** |
| Dataset | A hand-built synthetic population with partitioned histories across the three sources. Synthea was not used, to keep setup offline and small; the seed scripts are the single source of truth. The expected-link map exists only in `services/central/app/seed.py` and the tests. |
| Quality thresholds | Baseline measured (docs/evaluation.md); numeric acceptance thresholds still to be agreed with the supervisor. |

## 4. Status model and invariants

Referral status (SRS §6) is enforced on the server in `services/central/app/referrals/state.py`:

`draft → awaiting_information ⇄ awaiting_approval → approved → submitted → acknowledged → accepted → response_returned → followup_pending → closed`, with `declined` and `cancelled` as terminal states that record reasons.

Invariants:
- **Submitted means received.** "Submitted" is set only when the specialist service confirms receipt. Delivery, human acknowledgment and acceptance are stored separately.
- **Edits after approval.** Any clinical edit after approval returns an unsent approved version to draft. After submission it opens an **amendment** (`amendment_open`), so a new package version must be approved and sent while the submitted version stays untouched (FR-15, FR-70).
- **Concurrent edits.** Every edit carries `expected_version` (optimistic concurrency) and is rejected with 409 if stale.
- **Immutable packages.** A package stores a SHA-256 over the approved content. The specialist recomputes it and rejects any mismatch.
- **Idempotent delivery.** The delivery key is `sender:referral:version`. Retries reuse it, and the specialist returns the original result for repeats. Inbound events are deduplicated by event key.
- **Separate statuses.** Clarification requests and delivery errors have their own statuses and never erase referral progress.

## 5. Module ownership (three members)

| Member | Owns |
|---|---|
| Member 1 – workflow & UX | `services/central/app/referrals`, `approvals`, `reviews/router.py`, `generation/router.py`, `audit_router.py`, `web/src/features/{referrals,brief,reviews,specialist,workqueue}`, shared components |
| Member 2 – federation & platform | `services/{clinic,lab,specialist}`, `libs/common`, `services/central/app/{integration,identity,delivery}`, `infra/`, `scripts/` (seed, backup, FHIR), `web/src/features/{identity,lab,admin}` |
| Member 3 – documents & medication rules | `services/central/app/{documents,medications,reviews/checklist.py,generation/brief.py,generation/provider.py,tasks.py}`, `rules/`, `evaluation/`, `web/src/features/{documents,medications,rules}` |

Contract changes (`libs/common/refcommon/exchange.py`, `contracts/`) need approval from the consuming member (see AGENTS.md).
