# Architecture spec v4: mapping onto the code (WP0)

How each work package of `e2e-architecture-spec-v4.md` lands in this repository: what is added, changed or removed, and the defaults taken for the open decisions.

## Baseline before v4 (measured 2026-10-29, not copied from earlier notes)

| Suite | Result | Notes |
|---|---|---|
| Central unit tests (`services/central/tests`) | 136 passed | After merging `feature/patient-view` |
| Integration tests (`tests/`) | 21 passed, 4 failed (25 tests, 8 min 22 s, run on 2026-10-29 against the running stack) | Every failure is from the local setup, not the code. **3 tests in `test_patient_access.py`:** the local Keycloak realm has no patient accounts, and the running images predate the patient-view merge. **`test_admin_assigns_a_role_by_template`:** the realm's central service account lacks `view-realm`. Refresh the realm with `scripts/refresh-keycloak-realm.ps1 -Force`. |
| Browser journeys (`web/e2e`) | Not run before v4 | Playwright 1.63 and Chromium are installed |

## Status (2026-10-30)

| WP | Status | Checked by |
|---|---|---|
| WP0 to WP4 | Done (Sumaiya, 2026-10-29) | `tests/test_e2e_keys.py`, `test_e2e_consent.py`, `test_e2e_retrieval.py`, `libs/common/tests`, `services/provider/tests` |
| WP5 Approval | Done: the doctor signs on the device; the data keys are re-wrapped to the department and the patient; staff send a titles-only notice; the department's doctors open and verify it (`GET /e2e/received/{reference}/package`) | `tests/test_e2e_package.py`, browser journey |
| WP6 AI suggestions | Done: the browser de-identifier, the "What is sent to the AI" preview, the relay (`POST /ai/relay/selection`) with no content logging, an identifier safety net, and unknown ids dropped | `tests/test_e2e_ai.py` |
| WP7 Flags | Done: the hash-checked bundle (`GET /med-bundle`), the browser Layer 1 library, the Layer 2 relay (`POST /ai/relay/flags`), and Ignore/Research audited by hash. The drug-procedure rules were removed. | `libs/common/tests/test_browser_flags.py`, `tests/test_e2e_flags.py` |
| WP8 Scans | Done: Tesseract.js runs on the device (self-hosted); the doctor corrects each medicine; the image and the reading are encrypted together; the server's plaintext upload refuses referrals | `tests/test_e2e_patient.py` |
| WP9 Lifecycle | Done: reminders, escalation, capped extension, the specialist closes, grace period, crypto-shred with a receipt | `tests/test_e2e_lifecycle.py`, unit `test_lifecycle.py` |
| WP10 Patient app | Done: the patient adds papers, saves a copy on the phone, and opens and verifies it after the purge | `tests/test_e2e_patient.py`, browser journey |
| WP11 Evaluation and docs | Done, except as listed below. Written: `security-model.md`, `data-lifecycle.md`, `data-sources.md`, the AGENTS.md invariants, `evaluation.md` (RQ3 brand mapping and T-PERF-1 run; RQ1, RQ2, RQ4 and handwriting planned) and the SDS. | |

**Also built:**
- **The receiving hospital adds its own records** (step 8, 5.6 step 6): `POST /cases/{id}/own-records` at its adapter, then `POST /e2e/adapter/receiving-batches`. They are encrypted to the department's group key and the referring side gets no key or titles. Checked in `tests/test_e2e_package.py`.
- **The append-only, hash-chained audit trail** (11.5): `lifecycle/audit_chain.py`, `GET /admin/audit/chain`, and a trigger. Checked in `tests/test_e2e_audit.py`.

**Not done:**
- RQ1, RQ2, RQ4 and the handwriting benchmark (planned, not run);
- T-PERF-1 on a phone.

## Where each package lands

| WP | Spec | Code |
|---|---|---|
| WP1 Keys | 5.3–5.5, 5.7 | **Platform:** `central/app/keys/` (key directory, wrapped keys, platform signing key, JWKS). **Adapter:** `provider/app/keys.py` (hospital signing key, department group keys, signing doctor entries). **Shared:** `libs/common/refcommon/e2e.py` (suite `refx-p256-v1`, used by adapters, platform and tests). **Browser:** `web/src/crypto/` (WebCrypto port and key store). |
| WP2 Consent, policy, tokens | 6 | **Platform:** `central/app/consent/` (FHIR `Consent`-shaped record, staff request, patient signature), `central/app/m2m.py` (ES256 request assertions, JWKS). **Adapter:** `provider/app/policy.py` and `provider/policies/<institution>.json` (policy engine, structured refusals), `provider/app/m2m.py` (assertion verification, `jti` replay store, participants). **Removed:** per-patient sharing grants (`/sharing/grants`, admin grant screens, grant close-out job). Consent plus policy replace them (A3). |
| WP3 Encrypted retrieval | 5.6 | **Adapter:** `POST /e2e/record-requests` returns title records, ciphertext and wrapped DEKs, or a structured refusal; a manual-review queue pushes later. **Platform:** `encrypted_items` and `wrapped_keys` tables, ciphertext only. **Removed from the referral path:** the plaintext `evidence_items` import. |
| WP4 Screens | 4 | Role templates gain `record_visibility` and `holds_keys`. **Doctor:** decrypts in the browser (`web/src/features/e2e/`). **Staff:** titles only, and the server sends nothing else. |
| WP5 Approval | 5.8 | The browser builds and signs the package manifest, re-wraps DEKs to the receiving department's group key and the patient key, and uploads them (`POST /e2e/referrals/{id}/approve`). **Platform:** `package_manifests`, immutable and versioned. **Removed:** the plaintext `PackageEnvelope` for referrals, the sender's copy (`sent_copies`, D16) and the receiver's stored copy (D2). The receiver gets a notification with titles, and its doctors read ciphertext from the platform. |
| WP6 AI record suggestions | 8 | **Browser:** de-identification and the "What is sent to the AI" preview. **Platform:** relay `POST /ai/relay/selection`, no content logging. Reuses `LLMProvider`, the schema and `selection.validate`. |
| WP7 Medication flags | 9 | **Browser:** the evaluator (Layer 1: brand mapping plus DDInter pairs with label quotes, from a versioned, hashed bundle `GET /med-bundle`). **Platform:** relay `POST /ai/relay/flags` for Layer 2 (drug-drug gaps and drug-procedure). **Removed:** the manual drug-class-by-procedure rules (`rules/medication/seed-rules.json`, the rule approval screens) and the drug-procedure label rules. The spec forbids a hardcoded drug-procedure table. |
| WP8 Scans and OCR | 10 | Scans are encrypted on the capture device (the patient portal or the doctor's browser) to the doctor's and patient's keys. **OCR:** on-device only (Tesseract.js loaded in the browser) or manual entry by the doctor. **Removed from the referral path:** server-side OCR. The platform never reads the image or text. |
| WP9 Lifecycle | 7, 11 | The spec's states are a computed `stage` over the existing status column (mapping below). **Added:** a reminder 30 days after acceptance, then weekly, escalating to receiving staff; no silent auto-close. Extension: +30 days with a reason, at most 180 days in total. The specialist closes, then a 7-day grace, then purge by crypto-shredding with a receipt. Declined: purge after 1 day. |
| WP10 Patient app | 12 | Extends the existing patient view (`web/src/features/patient/PatientApp.tsx`, a PWA-style screen). **Added:** patient key creation, consent approval with signature (choose all or some places), adding scans, and a local encrypted copy (IndexedDB) that survives purge. |
| WP11 Evaluation and docs | 15, 17 | `evaluation/e2e/` harnesses, the `docs/security-model.md` limits, `AGENTS.md` invariants, and a new SDS version |

## The spec's states mapped onto the stored status

| Spec state | Stored |
|---|---|
| DRAFT | `status=draft` |
| SUBMITTED, AWAITING_CONSENT | `status=requested`, consent `requested` |
| CONSENTED, RECORDS_REQUESTED | `requested`, consent `granted`, record requests sent |
| RECORDS_READY / PARTIAL | every request answered (`partial` if any refused or pending) |
| DOCTOR_REVIEW | the doctor opened the decrypted records |
| APPROVED, SENT_TO_STAFF | `requested`, a signed manifest exists (`approved_version`) |
| PATIENT_LINK_PENDING, LINKED | the intake link at the receiving hospital |
| RECEIVING_STAFF_REVIEW, ACCEPTED_BY_STAFF, DENIED_BY_STAFF | `submitted`, then `acknowledged` (staff accepted) or `declined` with `denied_by_staff` |
| ASSIGNED, SPECIALIST_REVIEW | `acknowledged` with an assigned doctor |
| ACCEPTED, ACTIVE, INFO_REQUESTED | `accepted` (open clarifications show INFO_REQUESTED) |
| CLOSE_REMINDER_DUE, EXTENDED | `accepted` plus `reminder_due_at`, `extended_until` |
| CLOSED, PURGING, PURGED | `closed`, then `working_set_purged_at` with a purge receipt |

## Out of scope for v4 (stated in the SDS)

- **Test and scan orders** (`kind=test`) keep the existing order flow. The laboratory performs the test and keeps its own record. Encrypting orders is future work.
- **Clarification questions and answers** stay as doctor-only text on the platform.

## Defaults taken for the open decisions (spec section 16)

O2 external API for the synthetic demo; O3 passphrase-protected export; O4 weekly reminders then escalation; O5 ID number plus staff-assisted verification; O6 keep only manifest hash and counts after purge; O7 no escrow; O8 SMART Backend Services with the 6.3 claim set; O10 180 days.
