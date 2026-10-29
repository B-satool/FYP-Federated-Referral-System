# 18. End-to-end encrypted referrals (architecture spec v4)

This section describes the system as built from `docs/e2e-architecture-spec-v4.md` (approved 2026-10-29). Where it
disagrees with an earlier section, this one is current; each earlier section marks what it superseded. Sumaiya B.
built WP0 to WP4 (keys, consent, encrypted retrieval, role screens); WP5 to WP11 were finished on 2026-10-30.

## 18.1 What the platform holds

The central platform holds record content only as ciphertext, only while the referral is open. It never holds a data
key or anyone's private key; its own signing key is the only private key it keeps (AGENTS.md invariant 13). It holds
plaintext metadata: who referred whom, when, the department, the urgency, the reason, record titles, and the patient's
demographics for matching. The threat model and its limits are in `docs/security-model.md`; the cryptography in
`docs/crypto.md`.

## 18.2 Flow

| Step | Who | What happens | Code |
|---|---|---|---|
| 1 | Referring doctor | Fills in the request (reason, notes, procedure) | `referrals/router.py` |
| 2 | Staff, then the patient | Staff request consent; the patient signs it in the patient portal on their phone | `consent/router.py`, `web/src/features/patient/Consent.tsx` |
| 3 | Staff | Records requests to the consented institutions, each with a signed ES256 assertion; each adapter checks the consent and its own policy and answers with titles, ciphertext and wrapped data keys, or a refusal with a reason code | `records/requests.py`, `services/provider/app/release.py`, `policy.py` |
| 4 | Referring doctor | Decrypts on the device; the deterministic floor ticks the defaults; the AI may be asked (de-identified, previewed); enters the medicine list; adds papers (read on the device) | `web/src/features/referrals/Records.tsx`, `MedicinesTab.tsx`, `e2e/Papers.tsx` |
| 5 | Referring doctor | Approves: the device signs the manifest (each item's plaintext and ciphertext hashes) and re-wraps the data keys to the receiving department's group key and the patient's key (notes only if shared) | `web/src/features/e2e/approve.ts`, `sending/packages.py` (`approve`) |
| 6, 7 | Staff, receiving staff | Staff send a titles-only notice; receiving staff acknowledge, confirm the patient (CNIC and name) and assign a doctor | `sending/packages.py` (`send`), `services/provider/app/main.py` |
| 8 | Receiving staff | Optionally add their hospital's own records, encrypted by their adapter to the department's group key | `POST /cases/{id}/own-records`, `POST /e2e/adapter/receiving-batches` |
| 9, 10 | Receiving doctor | Opens the package with the department group key, verifies the signature and every item hash, accepts or declines, may ask for more information | `web/src/features/e2e/ReceivedPackage.tsx`, `GET /e2e/received/{reference}/package` |
| 11 | System, receiving doctor | Reminders 30 days after acceptance, then weekly, then escalation; extend (with a reason, at most 180 days) or close; purge after the grace period | `lifecycle/working_set.py` |
| 12 | Patient | Saves the signed package on the phone; it opens and verifies after the purge | `patient_access.py` (`/copy`), `web/src/features/patient/MyCopy.tsx` |

## 18.3 Keys and the directory

Doctors' and patients' key pairs are created in the browser and kept in IndexedDB, sealed with a passphrase (PBKDF2
600,000 iterations, AES-256-GCM). Only public keys leave the device. Hospitals sign their doctors' and departments'
directory entries; the platform signs patients'. Every client and adapter verifies an entry against the issuer's key
pinned at onboarding (`infra/participants/participants.json`, `scripts/onboard_participants.py`) before encrypting to
it. Department group keys are held by the hospital's adapter and wrapped to each member doctor; a leaver triggers
rotation.

## 18.4 The signed package (spec 5.8)

`refx.package.manifest/v1` (`refcommon.e2e.package_manifest`, mirrored in `web/src/crypto/suite.ts`) lists each item
with `content_hash` (SHA-256 of the plaintext) and `ciphertext_hash`, the recipient department's group key id and
version, the patient's key id, and the signer. The platform checks the signature against the doctor's hospital-signed
key and each ciphertext hash against what it stores, stores the manifest immutably, and supersedes the previous
version. `POST /e2e/verify-manifest` tells any holder whether their copy is the recorded version (or that the referral
was purged).

## 18.5 AI (spec 8, 9.1)

| Use | Input | Output checks | Code |
|---|---|---|---|
| Record suggestions | De-identified on the device (`web/src/features/e2e/deidentify.ts`), shown and editable before sending | Unknown or repeated ids dropped; reasons with treatment or dosing wording withheld | `POST /ai/relay/selection` |
| Flags, Layer 2 | Generic names, the procedure, an age band, the Layer 1 pairs already flagged | Names must be from the input; Layer 1 pairs never repeated; advice and "safe" wording dropped; labelled "AI suggestion, not verified" | `POST /ai/relay/flags` |

The relay (`app/ai_relay.py`) stores nothing and logs no content: the audit entry holds the actor, the referral, the
counts, the payload's SHA-256, the model, the latency and the outcome. It refuses a payload that still contains the
patient's name, CNIC, record number, the referral reference, an institution's name or the date of birth. It runs only
when a doctor clicks.

## 18.6 Medication flags (spec 9)

Layer 1 runs on the device (`web/src/features/e2e/flags.ts`, pure functions) over `GET /med-bundle`: the medicine
names (hand-checked names and the DRAP register, with products listed by company for ambiguous names), the components
of combination products and the DDInter pairs with label quotes. The bundle is versioned by its SHA-256 over canonical
JSON, which the browser recomputes before use. Names are mapped exactly, by strict start-of-name for register brands,
or approximately (one or two letters away, shown as "probable"); ambiguous names wait for the doctor to choose the
product. Unmapped names and ingredients without interaction data are "could not be assessed". Ignore and Research are
logged with a hash of the flag key. There is no drug-procedure table anywhere (T-FLAG-2): `seed-rules.json` and the
drug-procedure label rules were removed; those risks come only from Layer 2. The server's evaluator remains for tests
and test-and-scan orders only.

## 18.7 Papers (spec 10)

Papers are read on the device with Tesseract.js 5.1.1; the engine and the English model are served by this
application (`web/public/ocr`, copied at build), not a CDN. The doctor checks and corrects each medicine against the
image; the image and the reading are encrypted together in one batch. The patient can add papers from the app,
encrypted to the referring doctor's and their own key. The server's plaintext upload path refuses referrals; staff
see "Scanned paper" or "Patient-provided document" and a date.

## 18.8 Lifecycle and purge (spec 7, 11)

Settings: `ACCEPTED_HOLD_DAYS` (30), `REMINDER_INTERVAL_DAYS` (7), `ESCALATE_AFTER_REMINDERS` (3),
`MAX_REFERRAL_DAYS` (180), `CLOSE_GRACE_DAYS` (7), `DECLINE_GRACE_DAYS` (1). Jobs: `close_reminders` hourly,
`purge_working_sets` every 10 minutes. Purge deletes the ciphertext, titles, batches and wrapped keys, writes a
`purge_receipts` row (manifest hash, counts, trigger) and tells the receiving hospital. It is idempotent. See
`docs/data-lifecycle.md`.

## 18.9 Audit (spec 11.5)

Audit entries hold ids, actors, reason codes and hashes; never content, keys or de-identified text. The table is
append-only (a database trigger refuses deletes and changes to sealed entries). The `seal_audit` job (every minute)
chains new entries: `chain_seq`, `prev_hash`, and `chain_hash` = SHA-256 of the previous hash and the entry's canonical
fields. `GET /admin/audit/chain` recomputes the chain. Entries newer than 30 seconds are not yet sealed. Decrypt events
are reported by the client and are best effort.

## 18.10 Tests

The spec's acceptance tests (section 17) and where they run are listed in `docs/security-model.md`. Integration tests:
`tests/test_e2e_*.py` (keys, consent, retrieval, package, AI, flags, patient, lifecycle, audit). Unit tests: `libs/common/tests` (the suite, Python and browser interop, Layer 1 and the
drug-procedure scan) and `services/provider/tests` (policy). Browser journey: `web/e2e/smoke.spec.ts`.
