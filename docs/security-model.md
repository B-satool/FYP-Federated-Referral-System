# Security model (architecture spec v4)

How the referral platform protects patient records, what it does not protect against, and which test checks each
claim. The cryptography itself is in [crypto.md](crypto.md); machine-to-machine authentication is in [auth.md](auth.md).

## What is protected

The central platform holds record content only as ciphertext, only while the referral is open. It never holds a data
key or anyone's private key; its own signing key is the only private key it keeps.

| Threat | Protection |
|---|---|
| The platform's database, backups, logs or queues leak | They hold titles, ciphertext and wrapped data keys. Without a doctor's, department's or patient's private key nothing opens. Purge deletes the ciphertext and the wrapped keys, so a backup taken before the purge is unreadable once the wrapped keys have aged out of it. |
| A platform administrator or developer reads the database | Same as above. |
| A staff account, or a compromised staff account | Staff tokens never receive ciphertext or wrapped keys (the endpoints refuse them), and staff responses hold titles, statuses and counts only. |
| A forged key in the directory (a "fake doctor") | Every directory entry is signed by the issuing hospital (or, for a patient, the platform). Browsers and adapters check the signature against keys pinned at onboarding, before encrypting to anyone. A failure is refused and audited. |
| A changed package after approval | The doctor's signature covers each item's plaintext hash. The receiving doctor and the patient check every item they decrypt against it. |
| A replayed or forged records request | Requests to an institution carry a short-lived ES256 assertion (issuer, audience, expiry, single-use `jti`) with the consent reference. The adapter fetches the consent itself and checks the patient's signature. |

## What is not protected (state these limits)

- **A compromised doctor's device, or malware on it,** sees what that doctor decrypts. A doctor can copy or
  photograph what they read.
- **Device keys need no passphrase** (decision 2026-10-30). Anyone who can use the doctor's browser profile and sign in
  as the doctor can read what the doctor can. The key itself cannot be copied out of the browser (it is
  non-extractable). Use personal, locked devices. One device per doctor at a time: a new browser gets a new key and
  the earlier one is revoked.
- **The browser application is served by the platform.** A malicious platform could ship altered client code. The
  application is not signed or integrity-checked independently of the server.
- **Metadata is visible to the platform:** who referred whom, when, the department, the urgency, the reason for
  referral, record titles, and the patient's name, CNIC, date of birth and sex (used to match the patient across
  institutions, D8).
- **The AI relay sees de-identified text in memory** while forwarding it. De-identification can miss identifiers;
  the doctor sees and can edit the text before it is sent, and the relay refuses text that still holds the patient's
  name, CNIC, record number, the reference or an institution's name.
- **Decrypt events are reported by the client** ("which items were opened"). A modified client could skip them.
- **Revoking consent cannot recall** what a doctor has already decrypted on their device.
- **A doctor who leaves a department** can still read what they already downloaded or could decrypt with the old group
  key. New referrals use the rotated key.
- **Lost keys:** records from institutions are fetched again for the new key. Items that existed only on the platform
  (the doctor's notes, the medicine list, papers, flag decisions) are recoverable only from the patient's copy.
- **If the patient loses their phone,** their copy is lost; the institutions still hold the originals.

## Deliberate trust points

| Trust point | Why |
|---|---|
| Each hospital's adapter holds its departments' group keys | The hospital is the data controller for its patients' care. Its own system can read referrals sent to its departments. |
| Patient key entries are signed by the platform | A patient has no hospital. A malicious platform could register a false patient key; the patient's own copy would then not open for them, which they would notice. |
| An external AI model receives de-identified text when a doctor asks | O2: an external API is used only for the synthetic demo, with `LLM_EXTERNAL_ALLOWED=true`; production should use a model on the team's own server. |

## Wording to use (spec v4 8.5, 10)

- "Records are stored encrypted and decrypted only on the clinician's device. When the doctor requests AI help,
  de-identified text passes through our server to the model and is not stored."
- "Our servers never read scanned papers. Papers are read on the device." (No external OCR service is used.)

Do not say the platform "never sees the data" or "never decrypts anything": the relay exposure and the metadata are
real.

## Acceptance tests (spec v4 section 17)

| Test | What it checks | Where | Status (2026-10-30) |
|---|---|---|---|
| T-DB-1 | A database dump holds no canary plaintext, no data key, no doctor private key | `tests/test_e2e_retrieval.py` | Passes |
| T-STAFF-1 | Staff responses hold titles only; staff tokens cannot fetch ciphertext | `test_e2e_retrieval.py`, `test_e2e_package.py`, browser journey | Passes |
| T-DOC-1 | The doctor decrypts; another department or hospital cannot | `test_e2e_retrieval.py`, `test_e2e_package.py` | Passes |
| T-DIR-1 | A missing or invalid hospital signature is refused and audited | `tests/test_e2e_keys.py` | Passes |
| T-GROUP-1 | Join, leave, rotation; a leaver cannot open new items | `test_e2e_keys.py` | Passes |
| T-TOKEN-1 | Bad signature, audience, expiry, replay, non-participant, purpose, consent link | `test_e2e_consent.py`, `services/provider/tests` | Passes |
| T-CONSENT-1 | Staff cannot create or approve a consent; only the patient's signature grants it | `test_e2e_consent.py` | Passes |
| T-POLICY-1 | Sensitive category without specific consent is refused; manual review returns pending | `test_e2e_consent.py`, `services/provider/tests/test_policy.py` | Passes |
| T-REFUSAL-1 | Refused or unavailable is shown as such, never "no records" | `test_e2e_consent.py`; UI `SourceOutcomes` | Passes |
| T-APPROVE-1 | The signature verifies; a change breaks it; a new version needs its own signature | `test_e2e_package.py` | Passes |
| T-AI-1 | Identifiers refused; no payload text in the audit trail; nothing runs without a click; the floor works without a model | `test_e2e_ai.py` | Passes |
| T-AI-2 | Unknown item ids are dropped | `ai_relay.py`; unit `test_selection.py` | Passes |
| T-FLAG-1 | A known pair flags from brand names; an unmapped brand is "could not be assessed" | `libs/common/tests/test_browser_flags.py`, `test_e2e_flags.py` | Passes |
| T-FLAG-2 | Layer 2 is schema-checked and labelled; it never repeats or removes Layer 1; no drug-procedure table | `test_e2e_flags.py`, `test_browser_flags.py` | Passes |
| T-FLAG-3 | Ignore and Research are audited (with a hash, not names) | `test_e2e_flags.py` | Passes |
| T-LIFE-1 | Reminder at 30 days, escalation, extension with a reason (capped), close, grace, purge with a receipt, idempotent | `test_e2e_lifecycle.py` | Passes |
| T-LIFE-2 | After purge, the patient's copy still opens and verifies | `test_e2e_patient.py`, browser journey | Passes |
| T-REC-1 | Lost key: new key, records fetched again; platform-only items unrecoverable | `test_e2e_retrieval.py` | Passes |
| T-OCR-1 | Papers never reach the server in plaintext; staff see a title only | `test_e2e_patient.py` (the plaintext upload path refuses referrals) | Passes. There is no external OCR provider, so header masking is not needed. |
| T-NOCOPY-1 | After purge nothing holds the content; nothing is written back to the sending hospital | `test_e2e_lifecycle.py` | Passes |
| T-AUDIT-1 | Audit entries hold no content, keys or de-identified text; the table is append-only; the hash chain verifies and finds an altered entry | `tests/test_e2e_audit.py`, plus `test_e2e_ai.py` and `test_e2e_flags.py` for content | Passes. Entries are sealed into the chain about a minute after they are written. |
| T-PERF-1 | Time and size to open a typical referral | `web/scripts/perf-decrypt.ts` | Measured: 30 items with 5 scans of 1.5 MB, about 10 MB to download, median 62 ms to unwrap, decrypt and hash (Node 24 on the team laptop). **Not measured on a phone.** |
