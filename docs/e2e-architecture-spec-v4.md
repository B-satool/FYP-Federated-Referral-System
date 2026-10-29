# Architecture Spec v4 — End-to-End Encrypted Federated Referral Platform

Date: 2026-10-29
Repo: B-satool/FYP-Federated-Referral-System
Base branch: `main` (it already contains the v2 work, the patient accounts and patient view, and the staff view changes). Read `docs/v2-changes.md` first.
Audience: Claude Code, working with the project team.

**Already on `main`:** `docs/v2-changes.md` records that the team has since added role templates and an account-role screen, an AI packet recommendation (where staff, not doctors, currently decide the selection), a data-lifecycle decision note (`decisions/2026-10-27-data-lifecycle-and-v3.md`), and patient accounts with a patient view. Extend these instead of duplicating them. **Where `main` differs from this spec, this spec wins** (for example: doctors, not staff, decide the packet; staff never see content; doctors enter medicines).

This spec replaces and consolidates the earlier drafts (`architecture-spec-v3.md`, `data-lifecycle-and-roles-spec.md`, and the access-grant parts of the medication specs). Where this spec disagrees with them, this spec wins. If `medication-mapping-spec.md` and `medication-flagging-spec-v2.md` are available, reuse their brand-to-generic pipeline, data sources and tests, but follow section 9 here for how flags are produced.

---

## 0. Ground rules for the implementer

1. **Push to GitHub only when the project owner tells you to** (for example, "push to github"). Until then, work on local branches.
2. **The project owner has approved every change listed in section 13 (2026-10-29). Implement them.** Record that approval in `docs/approvals.md`. For any schema, authentication, package or `AGENTS.md` change that is **not** in section 13, ask before doing it.
3. **Synthetic data only.** Never use real patient data. Test canaries must be obviously fake.
4. **Do not claim what was not run.** The notes in `docs/v2-changes.md` say "9 API, 17 unit, 2 browser journeys" tests; this has not been independently run. Run the existing suites yourself before and after each work package and report real results.
5. **No hand-rolled cryptography.** Use vetted libraries only (see section 5.2).
6. Keep `AGENTS.md` invariants that are not listed in section 13 (see section 13 for the list that must change).
7. Each work package (section 14) is a separate branch/commit series with its own tests and docs.

---

## 1. Goal in one paragraph

Hospitals, clinics and labs each keep their own database. A referring doctor starts a referral, the patient consents, the platform fetches the needed records from the other institutions, and a specialist at the receiving hospital reviews. The platform **never holds readable patient records**: records are encrypted for the clinicians who need them, stored only as ciphertext while the referral is open, readable only on a clinician's own device after login, and deleted when the referral closes. Staff handle the process but can never read record content. AI helps in two bounded ways (suggesting which records to include, and suggesting medication flags) using de-identified text, only when a doctor asks.

---

## 2. The final flow (authoritative, from the team)

Numbering is used by the work packages and tests.

1. **Referral form.** The referring doctor fills in the referral form and records the patient's current medications (asked from the patient). The doctor submits the request to the staff (receptionist).
2. **Consent and papers.** Staff/receptionist asks the patient for consent **through the patient portal of our system**: staff send a consent request, and the patient approves (or declines) it in the portal. The patient may scan any documents they have and add them to the request in the portal (encrypted on the patient's device, section 10).
3. **Records requested.** After the patient has consented, the other institutions are asked for the patient's data, with the reason for the referral. The request is handled by staff at both hospitals (the adapter policy in section 6 can auto-approve or route to a manual queue).
4. **Doctor retrieval.** The doctor clicks a button to retrieve the data. The data is end-to-end encrypted, including in our database. The doctor's screen shows all the data, with AI suggestions, and the doctor can select or deselect records.
5. **Approval.** The doctor approves the selected records. The package goes forward with the doctor's notes, to the staff. **Staff cannot see any records** (titles only).
6. **Patient linking at the receiving hospital.** Staff link the patient to the receiving hospital if a link does not already exist (matching is by ID number and name).
7. **Receiving staff decision.** Staff at the receiving hospital accept the referral, deny it, or create a new patient record; the referral is delivered once the link exists.
8. **Assignment.** The referral goes to the receiving hospital's staff, who cannot see the records. They assign a doctor, send it to that doctor, and add records from their own hospital to the referral.
9. **Specialist review.** The specialist doctor reviews and accepts or declines. The patient and the referring hospital are notified if accepted.
10. **More information.** The specialist can ask the referring doctor for more information. The rest of the care is handled by the receiving hospital (the patient goes to them).
11. **Closing.** Referral data is purged when the referral is closed. A reminder is sent 30 days after the referral was accepted; the specialist can extend or close.
12. **Patient copy.** The patient can see the referral with its records permanently, in their own app, stored locally on their device, even after the referral is closed.
13. **Encryption.** Data is end-to-end encrypted.

---

## 3. Decisions already made by the team

| # | Decision | Notes |
|---|----------|-------|
| D1 | Central platform stores no readable records; ciphertext only, temporarily | Purge on close (section 11) |
| D2 | Receiving hospital does not keep other hospitals' records | Patient app keeps the patient's own copy |
| D3 | Staff see titles only, never content | Enforced server-side by what is sent, not by hiding in the UI |
| D4 | Department-wise group key at the receiving hospital; any verified doctor of that department can hold it; referral goes to one doctor | Joining rules in 5.5 |
| D5 | Hospital signs its doctors' public keys; apps verify the signature | 5.4 |
| D6 | Lost keys: re-fetch from source hospitals and re-wrap to the new key; scans/notes recovered from the patient's copy or the sender's copy | NOT recovered from audit logs; audit logs hold no keys or content (5.7) |
| D7 | Patients have accounts and a smartphone app | 12 |
| D8 | Patient matching across hospitals uses names and ID numbers (plaintext demographics) | Stated limitation in 15 |
| D9 | AI record suggestions: browser decrypts and de-identifies; only de-identified text leaves the device, only when the doctor clicks "suggest"; action is logged; doctor sees what is sent | 8 |
| D10 | Medication flags have two layers: (1) deterministic interaction data via the Pakistani brand mapping; (2) AI suggestions for anything not in the dataset and for drug-to-procedure risks, with NO hardcoded drug-procedure table | 9 |
| D11 | No per-flag human confirmation; flags show source/explanation, an "automatic, not clinically reviewed" tag, and Ignore / Research buttons (logged) | 9.5 |
| D12 | Permission model is three layers: legal participation agreement, per-institution policy in its own FHIR adapter, and per-request signed-token checks (SMART Backend Services / UDAP B2B) | 6 |
| D13 | Handwriting needs a proper OCR approach, measured on synthetic samples | 10 |
| D14 | Staff never read or edit record content, at any step, including intake. They see titles only. Whatever the staff screens did before (gathering records, fixing doses, adding medicines) is removed or reduced to titles-only | 4 |
| D15 | An external OCR/vision service may read scanned papers, but **our servers must never read the image or the extracted text**. The device calls the OCR service directly | 10 |
| D16 | **No sender-side copy.** Neither the platform nor the sending hospital keeps a copy of the referral letter, summary or records beyond the temporary ciphertext window. The patient's local copy is the only persisting copy | 11.4 |

---

## 4. Roles and what each can see

Four roles plus the patient, and a system actor. "Titles" means label, category, date and source institution only (see 4.2).

| Role | Referral metadata (status, dates, who/where, reason) | Record titles | Record content | Doctor notes | AI features |
|------|------|------|------|------|------|
| Referring doctor | yes | yes | yes, for records they retrieved | write/read | yes |
| Referring staff | yes | yes | **no** | **no** (metadata only) | no |
| Receiving staff | yes | yes | **no** | **no** | no |
| Receiving doctor / specialist | yes | yes | yes, if assigned (or member of the department group) | read | yes |
| Source-hospital staff (fulfilling a request) | the request only | n/a | **no** (adapter answers automatically or via manual queue under its own policy) | n/a | no |
| Patient | own referral | yes | yes, own copy | letter only (decision: referral letter and the receiving decision; doctor's private notes are not shown unless the doctor marks them shareable) | no |
| Platform admin | system health only | no | no | no | no |

Notes:
- **Staff never read or edit record content (D14).** The current-medication list is asked by the doctor and entered by the doctor (step 1). Scans are captured by the patient, or on a device under the patient's control, and encrypted at capture to the referring doctor's key (section 10); staff see only a title such as "Patient-provided document, date". Staff handle the process only: consent, patient linking, accept/deny, assignment, notifications. Dose reconciliation, OCR correction and adding medicines are doctor tasks. The existing staff screens that gather records, check scanned papers, fix doses or add medicines must be removed or reduced to titles-only.
- Staff views must be built so the server **never sends content** to staff clients. Hiding fields in the UI is not acceptable and must fail the test T-STAFF-1.

### 4.1 Role templates

Keep the role-template mechanism (six templates were drafted on `feature/grant-expiry`: see `services/central/app/identity/role_templates.py` and `rules/roles/templates.v1.json` on that local branch, if you can access it; otherwise recreate). A template defines: allowed screens, allowed API scopes, record-visibility level (`titles_only` | `content`), and whether the role may hold keys. Templates drive the per-role screens. Adding a template must not require code changes in the screens beyond a registry entry. Template changes are an authorization change (section 13).

### 4.2 What "titles" may contain

A title record has: `item_id`, `kind` (lab, imaging, note, prescription, scan, other), `label` (for example "Complete blood count"), `date`, `source_institution`. It never has values, results, free text or medicine doses.

**Sensitive categories** (psychiatric, HIV/sexual health, and any category the institution marks sensitive): the label itself can reveal the diagnosis. These items show a generic label ("Restricted record") to staff, and the real label only to doctors. Include this in the adapter policy (section 6.2).

---

## 5. End-to-end encryption design

### 5.1 Threat model

Protects against: a stolen or leaked platform database, backups, logs and queue contents; a platform administrator or developer reading the database; platform staff-role users; a compromised staff account.
Does not protect against: a compromised doctor device or malware on it; a doctor who copies or screenshots data; a malicious platform that ships altered client code (the browser app is served by the platform), unless the app is signed/integrity-checked; metadata (who referred whom, when, titles, patient names and IDs for matching). State these limits in the docs.

### 5.2 Primitives (use libraries, not custom code)

- Content encryption: AES-256-GCM, a fresh random 96-bit nonce per encryption, with associated data binding the ciphertext to `referral_id`, `item_id`, `key_version`.
- Key wrapping to recipients: HPKE (RFC 9180) or libsodium sealed boxes (X25519 + XSalsa20-Poly1305/ChaCha20-Poly1305). If WebCrypto-only is required, use ECDH P-256 + HKDF-SHA-256 + AES-256-GCM (ECIES-style).
- Signatures: Ed25519 (libsodium) or ECDSA P-256 (WebCrypto).
- Passphrase-based key backup: Argon2id (preferred) or PBKDF2-HMAC-SHA-256 with high iteration count.
- Browser: WebCrypto API and/or `libsodium-wrappers`. Python side (source adapters, services): `cryptography` and/or `pynacl`.
- Pin library versions. Record the choice in `docs/crypto.md` with the reason.

### 5.3 Keys

| Key | Held by | Purpose |
|-----|---------|---------|
| Doctor encryption keypair | doctor's device (private); platform directory (public, hospital-signed) | receive wrapped data keys |
| Doctor signing keypair | doctor's device | sign approved packages and notes |
| Department group keypair | the group's members (private key wrapped separately to each member's public key and stored as ciphertext); public key in the directory | receiving-side access that survives reassignment |
| Patient keypair | patient's device | patient's local copy |
| Hospital signing key | the hospital (held by its admin / its adapter, in its own key store) | signs doctors' public keys and department keys |
| Referral data key (DEK), one per referral and key version | nobody in plaintext at rest; exists wrapped to each authorized recipient | encrypts record items |
| Hub signing key | the platform (for SMART Backend Services client assertions) | machine-to-machine authentication (section 6.3) |

The doctor's private key never leaves the device unencrypted and is never sent to the platform. In the browser, store it as a non-extractable `CryptoKey` in IndexedDB where possible. Offer an optional encrypted backup file protected by a passphrase (Argon2id). Optional: WebAuthn PRF to unlock the key with a hardware token or biometric.

**Key unlock UX.** Logging in (Keycloak) gets the doctor a session. Decrypting needs the device key, which is unlocked with the doctor's passphrase/biometric on that device. Spell this out on screen: "Your login proves who you are; your device key decrypts the data."

### 5.4 Key directory and fake-key protection

- The platform hosts a directory of public keys. Each entry (doctor or department) is a record signed by the **hospital signing key**: `{subject_id, role, hospital_id, department, public_key, key_version, valid_from, valid_to, hospital_signature}`.
- Every client, and every source adapter that encrypts to a recipient, **verifies the hospital signature** against that hospital's pinned public key before using the key. The hospital's public key is obtained out of band at onboarding (the participation agreement process, section 6.1) and pinned in the client/adapter configuration. A key without a valid signature is rejected and the failure is audited.
- Revocation: signed revocation entries; clients and adapters check them. Key `valid_to` limits exposure.
- Show a short fingerprint of the recipient key to the doctor when approving a package ("Sending to Dr X, Cardiology, Hospital Y, key ab12…").

### 5.5 Department group key (D4)

- Each receiving department has a group keypair. The private key is wrapped to each current member's public key.
- A doctor **joins** only when the hospital (admin role) signs their directory entry for that department and an existing member (or the hospital admin, who holds a member key by policy) wraps the group private key to them. Document who the "hospital admin who can hold a member key" is; this is a deliberate trust point.
- A doctor who **leaves** is revoked in the directory and the group key is **rotated** (`key_version + 1`). New referrals use the new version. A leaver can still read anything they already downloaded or could already decrypt with the old key; say so in the docs.
- The referral is assigned to one doctor (step 8), but the DEK is wrapped to the department group key so reassignment does not break access. The platform still records which individual doctor is assigned, and audits which member opened it.
- The sending doctor wraps the DEK to the receiving department's group public key at approval time (verify the signature first).

### 5.6 Record encryption pipeline

1. **Source adapter** receives a verified request (section 6). It collects the allowed records, builds an item list, and generates the DEK for this retrieval (or reuses the referral DEK for the current key version, to be decided in the spike; default: one DEK per referral).
2. For each record item: encrypt content with the DEK (AES-256-GCM), produce `{item_id, ciphertext, nonce, aad, title_record}`. The title record is plaintext (4.2), and is sent separately so staff can see it.
3. Wrap the DEK to the **requesting doctor's** public key (and the patient's public key, for the patient copy, once the patient is verified). Include the wrapped keys in the response.
4. Send ciphertext + wrapped keys + titles to the hub. The hub stores them as received. **The hub never has a DEK or a private key.**
5. On approval, the sending doctor's browser re-wraps the DEK (or wraps it for the first time, depending on the pipeline) for the receiving department group key and the patient key, signs the package, and uploads the new wrapped keys. See 5.8.
6. Items added later by the receiving hospital's adapter are encrypted to the assigned doctor's department group key (new DEK version if needed) and appended.

**Large files.** Scans/images are encrypted in chunks (for example, 1 MB chunks each with its own nonce and chunk index in the associated data) so the browser can stream. Store ciphertext in object storage or a bytea column per the existing pattern; do not log it.

### 5.7 Lost keys and recovery (D6)

- Audit logs record who did what, when and which item ids. They hold no keys and no content, and must not be changed to hold either. They cannot be used to recover lost data.
- Recovery: (a) the doctor generates a new keypair; the hospital signs the new public key and revokes the old; (b) the platform re-requests the records from the source institutions under a fresh consent/grant check (section 6), and the adapters re-encrypt to the new key; (c) items that exist only inside the platform (patient scans, doctor notes, the medicine list entered by the doctor, flag acknowledgements) are restored only from the patient's local copy (section 11.3), because there is no sender-side copy (D16); if the patient has no copy they are lost, and the UI says so.
- A recovery attempt is audited and notifies the hospital admin.
- Optional hospital-held key escrow is **not** part of this spec. It is listed in the open decisions (section 16).

### 5.8 Approval and signing

On approval the doctor's browser builds a **package manifest**: ordered list of `{item_id, content_hash (hash of plaintext), ciphertext_hash, kind, title}`, the doctor's notes (encrypted like items), the recipient department and key version, a timestamp, and the referral ID. The doctor signs the manifest with their signing key. The platform stores the signed manifest (no plaintext). Packages are immutable and versioned: any change is a new version with a new signature. This answers "what exactly was approved?" without holding plaintext: the signature covers the plaintext hashes; the original content can be re-verified by anyone who holds the decrypted copy.

### 5.9 Purge by crypto-shredding

On close: delete all ciphertext **and** all wrapped DEKs/group-key wrappers for the referral. Ensure the delete also reaches object storage, caches, queues and replicas. Because backups cannot be edited, backups hold ciphertext without keys, which is unreadable once wrapped keys are deleted (confirm wrapped keys are not stored in the same backup set past the retention window; see 11.2). The signed manifest and audit trail remain (metadata only).

---

## 6. Permission model (replaces per-patient sharing grants)

### 6.1 Layer 1 — Participation agreement (legal, signed once per institution)

This is a document, not code. The system must **enforce or record** the clauses below at onboarding and at runtime:

| Clause | System behaviour |
|--------|------------------|
| Allowed purposes: referral and treatment, emergency, patient's own access | The token's `purpose` claim must be one of the allowed values; others are refused |
| Duty to respond to referral requests with valid consent unless an exception applies | Requests are logged; unanswered requests surface in an overdue list |
| Allowed refusals: law prohibits it; record is too sensitive and specific consent was not given; request is incomplete or invalid | The adapter returns a **structured refusal with one of these reason codes** (section 6.2), never an empty list |
| Security duties: encryption, audit logs, breach reporting (draft data protection bill is said to require 72 hours; **verify this against the actual bill before citing it**) | Encryption per section 5; audit per section 11.5; a breach-report procedure documented in `docs/` |
| Liability: who is responsible if data is misused after it is shared | Documentation only; legal text is a team/supervisor deliverable |
| Retention: the receiver deletes data when the referral packet expires | Purge per section 11 |

At onboarding, record the institution's id, name, its pinned public signing key (for D5), its adapter base URL, and the agreement version/date. Participation can be suspended (the hub refuses to call or accept that institution).

### 6.2 Layer 2 — Each institution's own policy (in its adapter)

Each institution configures rules in its **own FHIR adapter** (its `provider` service), under its own control. The platform cannot override them. A policy file per institution (JSON/YAML, versioned, audited changes) supports at least:

- `auto_approve_with_valid_consent: true|false`
- `excluded_categories`: list (default includes psychiatric notes, HIV and sexual-health records) released **only if** the consent names the category specifically
- `manual_review: {categories | request_types | always}` → requests go to the institution's staff queue
- `respond_within_consent_window_only: true` → answer only inside the consent's date range
- `allowed_record_types_from_consent: true` → answer only with the record types the consent covers
- `sensitive_title_masking: true` → masks titles of sensitive categories (4.2)

Adapter behaviour, in order: verify the token (6.3) → check consent (valid, not expired, covers the category and the requested recipient and purpose) → apply policy → return records **or** a structured refusal:

```
refusal.reason in {
  "prohibited_by_law",
  "sensitive_category_no_specific_consent",
  "request_incomplete_or_invalid",
  "consent_expired_or_out_of_range",
  "pending_manual_review"
}
```

"Unavailable" and "none found" must stay distinct from "refused" in the response and in the UI (AGENTS.md: unavailable is not "none").

This layer **replaces the per-patient, per-category sharing grants** from earlier work. The old `expires_at` grant expiry maps onto the consent's date range. If code from `feature/grant-expiry` is reused, adapt it rather than keeping two models side by side.

### 6.3 Layer 3 — Per-request technical checks (FHIR)

- Machine-to-machine authentication between the hub and each adapter uses **SMART Backend Services** (OAuth2 client credentials with a signed JWT client assertion, `private_key_jwt`, public keys published as a JWKS for the hub). If the team prefers, use its **UDAP B2B** extension (the `hl7-b2b` claim carries organisation, user, purpose and consent references; TEFCA's FHIR exchange uses it). Record which one you chose and why in `docs/auth.md`. SMART Backend Services is simpler; UDAP B2B maps more directly to the "which organisation, which doctor, what purpose, which consent" claim set.
- The signed token or request assertion states: **which organisation** and **which doctor** is asking, **the purpose** (`PurposeOfUse` code), and **a link to the patient's consent** (FHIR `Consent` resource id/URL), plus the referral id and a short expiry (minutes).
- The adapter verifies: signature against the hub's registered key, `aud`/`iss`/`exp`/`jti` (reject replay by remembering `jti`), that the organisation is a participant in good standing (6.1), and the consent link (6.4).
- Keycloak stays for **user login** to the web apps. The machine-to-machine layer is new. This is an authentication change (section 13).

### 6.4 Consent

- Consent is a record of the patient's permission. Staff at the referring hospital **request** it, and the **patient grants it in the patient portal**, signed with the patient's key (section 12). Staff cannot create or edit a consent on the patient's behalf. Model it as a FHIR `Consent`-shaped record: `{patient_ref, purpose, recipient_org(s), categories, sensitive_categories_specific[], period{start,end}, status, evidence{method: "patient_portal", requested_by_staff_id, patient_signature, timestamp}}`.
- The consent record is administrative data, not clinical content; the platform may store it. It must be retrievable by the adapter through the link in the token (the adapter checks it, not trusting the hub's claim alone).
- Revocation: patient can revoke; future requests are refused. Already-delivered ciphertext is handled by purge (section 11) and the limits are documented: revoking consent cannot recall what a doctor has already decrypted on their device.

### 6.5 Patient linking

Linking maps one person across institutions (ID number, name, date of birth, phone). It does not grant access: access comes from consent + adapter policy + token. Matching uses plaintext demographics visible to staff and the platform (D8). A match is created or confirmed by staff, and is audited. A wrong link is a safety risk: show the matched fields to staff and require confirmation, and log the decision. Linking measurements belong to RQ1 (section 15).

---

## 7. Referral state machine

States (extend the existing ones; do not break existing transitions without a migration plan):

```
DRAFT → SUBMITTED (doctor → staff)
SUBMITTED → AWAITING_CONSENT → CONSENTED
CONSENTED → RECORDS_REQUESTED → RECORDS_READY (ciphertext available) | PARTIAL (some refused/pending)
RECORDS_READY → DOCTOR_REVIEW → APPROVED (signed package v1)
APPROVED → SENT_TO_STAFF → PATIENT_LINK_PENDING → LINKED
LINKED → RECEIVING_STAFF_REVIEW → ACCEPTED_BY_STAFF | DENIED_BY_STAFF | NEW_PATIENT_CREATED
ACCEPTED_BY_STAFF → ASSIGNED (doctor chosen; receiving-side records added)
ASSIGNED → SPECIALIST_REVIEW → ACCEPTED | DECLINED
ACCEPTED → (notify patient + referring hospital) → ACTIVE
ACTIVE → INFO_REQUESTED ↔ ACTIVE
ACTIVE → CLOSE_REMINDER_DUE (day 30 after ACCEPTED) → EXTENDED | CLOSED
CLOSED → PURGING → PURGED
```

Rules:
- The reminder is created 30 days after the `ACCEPTED` timestamp. The specialist can **extend** (a further period, default 30 days, a reason required) or **close**. Extensions are audited and limited (maximum total, configurable; default 180 days).
- If the reminder is ignored: re-remind weekly, and after a configurable period escalate to the receiving department staff. **Do not auto-close silently** (open decision O4). Declined/denied referrals purge after a short grace period.
- Every state change is an audited event with actor and timestamp. Transitions are idempotent (AGENTS.md) and guarded by role.
- Denial and decline carry a reason visible to the referring doctor and to the patient.

---

## 8. AI record suggestions (D9)

### 8.1 Purpose

Help the referring (or receiving) doctor choose which records belong in the package. The doctor always decides: select/deselect, and the result is a signed package.

### 8.2 Two tiers

1. **Deterministic floor, runs in the browser, always on:** conditions related to the referral reason, surgeries, consultations in the last 6 months, current medicines, allergies, and the most recent relevant labs/imaging. Defined by rule files shipped with the client. If the model is unavailable or the doctor does not click "suggest", the floor still works.
2. **AI ranking, only when the doctor clicks "Suggest":** the browser decrypts the items, **de-identifies** them, shows the doctor exactly what will be sent, and on confirmation sends the de-identified text to the model through the platform relay. The model returns a ranking with short reasons, citing item ids. A "Not included" list is shown with reasons.

### 8.3 De-identification (in the browser)

Remove or replace: names, ID numbers, phone numbers, addresses, hospital and clinic names, doctor names, exact dates of birth (keep age), MRNs. Replace with stable placeholders ("[PATIENT]", "[DOCTOR_1]"). Use a documented ruleset plus pattern matching and a name list from the patient's own demographics (so their name is found inside free text). Show the doctor a preview, allow edits, and say plainly that automatic de-identification can miss things. Never send the encryption keys, the ciphertext, or the identifiers.

### 8.4 Relay

- The browser cannot hold the model API key, so the request goes through a **platform relay endpoint**. The relay sees the de-identified text in memory while forwarding it.
- **Do not log request or response content.** Log metadata only: actor, referral id, item ids, counts, hash of the payload, model name, latency, outcome.
- The relay does not store the text, does not put it in queues that persist, and returns the model response to the browser.
- The model client is behind an interface so the provider can be swapped: external API (needs a decision about data leaving the country: O2), or a model on the team's own server (preferred for production), or off.
- The model never receives identifiers, and never creates or hides records. Output is a suggestion; the item ids it cites are validated against the real list; unknown ids are dropped.

### 8.5 The wording the app and defence must use

"Records are stored encrypted and decrypted only on the clinician's device. When the doctor requests AI help, de-identified text passes through our server to the model and is not stored."

Do **not** say the platform "never sees the data" or "never decrypts anything". The relay exposure is real and must be stated.

### 8.6 Audit and UI

- Log the click (who, when, which referral, which item ids, payload hash, provider).
- A "What is sent to the AI" panel is mandatory before sending.
- The result is labelled "AI suggestion, unverified".

---

## 9. Medication flags (D10, D11)

### 9.1 Two layers

**Layer 1 — Deterministic interaction check (data-backed).**
- Inputs: the current medicines (brand or generic names as entered/scanned).
- Step A: map brand → generic ingredient(s) using the **Pakistani brand-to-generic mapping dataset** (build per `medication-mapping-spec.md` if available: a DRAP-listed brand name → ingredient(s) with strength/form, normalised to RxNorm/ATC where possible; document sources and licences). Matching is fuzzy (spelling variants common in Pakistan) and returns a confidence; unmapped names are passed to Layer 2, never silently dropped.
- Step B: check ingredient pairs against an open interaction dataset (DDInter is the candidate: licence CC BY-NC-SA 4.0 per Bioregistry, which is acceptable for a non-commercial academic prototype; re-check the licence at download time and record it in `docs/data-sources.md`). RxNav's interaction API was discontinued; do not depend on it.
- Output per flag: the pair, severity, the source sentence/identifier from the dataset, and the dataset version.
- **Runs in the browser** over a downloaded, versioned and hash-checked data bundle (no medicines leave the device for this layer). If the bundle is too large for mobile, split by first letter of the generic name or use a compact index; document the size.

**Layer 2 — AI suggestions (not data-backed).**
- Covers: (a) medicines with no mapping or no pair in Layer 1's dataset; (b) **drug-to-procedure risks** (for example, a medicine and a planned procedure such as surgery, contrast imaging, or a dental extraction). **There must be no hardcoded drug-procedure table** and no seed-data-specific rules anywhere in the code or the rule files.
- Inputs: **generic drug names and procedure names only** (plus optionally age band and a coarse indication). No names, no IDs, no free text. This is a much smaller privacy exposure than 8.
- The browser sends these through the same relay pattern as 8.4 (no content logging; metadata only).
- Output (validated against a JSON schema; invalid output is discarded): `{drug, other_drug_or_procedure, concern, severity_estimate, reason, confidence, evidence_hint}`. `evidence_hint` may cite a drug-label section if a label retrieval step is added (optional: attach the relevant text from public labels such as DailyMed/openFDA when available).
- All Layer 2 flags are labelled **"AI suggestion, not verified"**.
- The AI layer can add flags and can mark a medicine "could not be assessed". It **does not remove or downgrade Layer 1 flags**.
- Brand names that Layer 1 could not map may be sent to the AI as raw strings **only if the team accepts that** (they are not patient-identifying but they are health information); the default is to send the string alone, without any other context.

### 9.2 Not-assessed and failure handling

If the model is unavailable, show "AI check not available", never "no issues". If a medicine could not be mapped and the AI did not return, show "could not be assessed" for that medicine. (AGENTS.md: unavailable is not "none".)

### 9.3 Where the code lives

A new shared flag library (pure functions, versioned) used by the browser client. The server may keep a copy of the library for tests and for non-E2E demo mode, but the production path decrypts and evaluates only on the client. Keep the library free of I/O so it can be tested without a network.

### 9.4 Evaluation (RQ3, RQ4 in section 15)

- Layer 1: precision/recall of brand→ingredient mapping on a synthetic list of Pakistani brand names with known answers; interaction detection against held-out known pairs.
- Layer 2: for a synthetic list of known drug–drug pairs held out from any retrieval context, measure recall and false alarms per 100 suggestions; for drug–procedure, build a small expert-curated test set (clearly labelled as a synthetic benchmark, reviewed by a pharmacist/clinician if available) and report agreement. Do **not** use this test set as a runtime table.
- Report the results honestly; if not run, the docs must say "planned, not run".

### 9.5 UI

Each flag shows: the medicines involved, the explanation, the source or "AI suggestion, not verified" tag, the tag "automatically generated, not clinically reviewed", and two buttons: **Ignore** and **Research** (Research opens the dataset/label source or a search link). Both clicks are logged (actor, flag id, action, time). No confirmation step. The decision to ignore is the doctor's.

---

## 10. Scanned papers, handwriting and OCR (D13, D15)

- **Capture.** Scans are captured by the patient (patient app) or on a reception scanner under the patient's control. The image is encrypted on the capture device directly to the referring doctor's key (and the patient's). Staff never open it; they see a title only.
- **Rule:** our servers must never read the image or the extracted text. An **external OCR or vision service may** read it (team decision), but only on a path that does not pass through our servers: the capture device calls the OCR provider **directly**. A relay through our server is **not allowed** for OCR, because the relay would hold the image in memory.
- **Credentials.** The provider's key cannot sit in the app. Use short-lived, narrowly scoped credentials minted for the device if the chosen provider supports them (not verified: check the provider's documentation before choosing), or a per-device credential. If no suitable provider supports this, use the fallback: an OCR service run by each hospital inside its own adapter (the hospital, not the platform, reads the image), or on-device OCR.
- **Result.** The extracted text returns to the device, is encrypted together with the scan, and never reaches our servers in plaintext. Only metadata is logged (client-reported): who, when, which item id, provider, outcome.
- **Provider exposure.** The provider sees plaintext, and prescriptions often carry the patient's name. Mitigations: (a) on-device masking of the header area (name, ID number, phone) before upload, on by default, and shown to the user; masking is imperfect, so say so; (b) provider terms with no retention and no training on the data, recorded in `docs/data-sources.md`; (c) synthetic data only during development.
- **Corrections.** The doctor sees the extracted medicine, dose and frequency next to the image and corrects them. Staff cannot. Run a name check of the extracted medicine against the brand list.
- **Engines to evaluate, in order:** (1) a vision-capable cloud model called directly from the device; (2) a hospital-run OCR in its adapter; (3) an on-device handwriting model (for example a TrOCR-style open model via ONNX/WebGPU); (4) manual entry with brand-name autocomplete. Printed text can use Tesseract on the device. Tesseract on handwriting is reported weak (about 50 to 65% in the team's earlier reading); measure it yourself.
- **Measurement (RQ3):** medicine-name, dose and frequency accuracy per field on synthetic handwritten prescriptions, several engines compared.
- **Claim wording:** "Our servers never read scanned papers. When an external OCR service is used, it processes the image directly from the device."

---

## 11. Data lifecycle

### 11.1 What is stored where

| Data | Central platform | Source/receiving institution DB | Patient app |
|------|------------------|---------------------------------|-------------|
| Referral metadata, state, reason, timestamps | yes, kept | the institution's own referral record | summary |
| Titles | yes during the referral; kept as metadata after (decision O6) | n/a | yes |
| Record content (ciphertext) | **only while the referral is open** | the original stays in the source hospital's own DB (never copied into other hospitals) | yes, permanent, local |
| Wrapped keys | only while the referral is open | n/a | patient's own |
| Signed package manifest | kept (no plaintext) | n/a | yes |
| Consent record | kept | adapter holds its checked copy | yes |
| Audit trail | kept (metadata only) | each institution's own audit | n/a |

### 11.2 Purge

- Trigger: `CLOSED` (specialist closes), declined/denied (after grace), or the maximum total duration reached (after the escalation path in section 7).
- Steps (idempotent, resumable): mark `PURGING` → ensure the patient copy was offered (11.3) → delete ciphertext, wrapped keys and group-key wrappers → delete object-storage objects and any caches/queue entries → write a purge receipt `{referral_id, purged_at, items_count, manifest_hash}` → `PURGED`. A scheduled job retries failures and raises an alert if anything remains.
- Grace period before purge (default 7 days after close, configurable) to let the patient app and the doctors finish.
- Backups: document the backup retention window. Wrapped keys must age out of backups on the same schedule or be kept in a store excluded from backups.
- Verification endpoint: given a stored copy, verify it against the signed manifest hashes (so a recipient can prove what was sent), and report `PURGED` for purged referrals.

### 11.3 Patient copy

- The patient app downloads the referral bundle (titles, ciphertext, the DEK wrapped to the patient's key, the signed manifest, the letter) and keeps it locally, encrypted with the patient's key, with the app's own local storage protection.
- The purge does not wait forever for a patient who never opens the app. After the grace period it purges regardless, and the app shows "this copy is only on your device".
- If the patient loses the phone, the copy is lost (the source hospitals still hold the originals and the patient may ask them). State this in the app and docs. A patient backup passphrase/export is optional (O3).

### 11.4 No sender-side copy (D16)

The platform keeps **no** copy of the referral letter, the doctor's notes, the summary or any record content after the temporary ciphertext window, and it does **not** write anything back into the sending hospital's database. The only persisting copy of a referral's content is the patient's local copy (11.3). The sending doctor's ordinary clinical records in the hospital's own systems exist independently of this platform and are not written by it. Likewise, the receiving specialist's own clinical notes about the patient live in the receiving hospital's own systems once the patient is under care; that is outside this platform. Consequence, to be stated in the docs: lost keys cannot be recovered for platform-only items unless the patient's copy exists (5.7).

### 11.5 Audit

Audit every: login, key creation/rotation/revocation, directory signature failure, consent create/revoke, token issue/verify, request/response/refusal (with reason code), retrieval click, decrypt event (client reports "opened item ids" through an authenticated call), AI suggest click, flag Ignore/Research click, approval/signature, state change, reminder, extension, close, purge receipt, recovery attempt. Audit entries hold ids, actors, reason codes and hashes; never content, never keys, never de-identified text. Audit is append-only; protect with a hash chain.

Note: the decrypt event is client-reported, so it is best-effort, not a guarantee (a modified client could skip it). State that.

---

## 12. Patient portal and app

The patient portal (already started on `main` as patient accounts and a patient view) is where the patient receives and answers consent requests from staff, adds scans, and keeps the local copy. Consent is only valid if given there.

- Patient registration/verification (ID number plus a one-time code or staff-assisted verification at the hospital; decide O5).
- Patient keypair created on the device; the public key is registered in the directory.
- Features: view referral status and the notification when accepted; receive consent requests from staff and approve, decline or revoke them (signed with the patient's key); view and keep the referral and its records locally (even after close); add scanned papers to a request; export.
- Platforms: choose one stack with the team (React Native/Expo or a PWA with IndexedDB). A PWA reuses the web crypto code. Decide in the spike.
- Notifications: patient and referring hospital are notified when the referral is accepted; reminders for consent.

---

## 13. Changes in this spec (approved by the project owner, 2026-10-29)

The project owner has approved all items below. Implement them, and record the approval in `docs/approvals.md`.

| # | Change | Why it needs approval | Module owner |
|---|--------|----------------------|--------------|
| A1 | New tables/columns: key directory, wrapped keys, package manifest signature, consent, adapter policy, purge receipt, reminder/extension, role templates, patient accounts | Schema change | data/central owner |
| A2 | Machine-to-machine auth (SMART Backend Services / UDAP B2B), hospital-signed key directory, role templates, patient login | Authentication/authorization change | auth owner |
| A3 | Replace per-patient sharing grants with consent + adapter policy | Replaces a core access mechanism; touches "each source authorizes access independently" (it still does, via its adapter) | provider/adapters owner |
| A4 | Package format: now encrypted items + signed manifest; central stores no plaintext | Package change | approvals owner |
| A5 | AGENTS.md invariant "central platform never touches source DBs": unchanged (still true). New invariant needed: "central never stores readable record content and never holds a DEK or private key" | Invariant addition | all |
| A6 | AGENTS.md invariant "Flags only from deterministic `evaluate_medications()`; the LLM never creates or suppresses flags" → changed to "Layer 1 deterministic flags come from the data-backed evaluator; Layer 2 AI suggestions are allowed, are labelled unverified, and cannot remove or downgrade a Layer 1 flag" | Invariant change requested by the team | rules/medication owner |
| A7 | AGENTS.md invariant "AI output is a draft and cites evidence IDs" → keep; add "AI receives only de-identified text and only on a doctor's request; no content logging" | Invariant addition | all |
| A8 | AGENTS.md invariant "Never overwrite original data" and "A clinician approves immutable versioned packages": keep; the signature is by the doctor's key | Clarification | approvals owner |
| A9 | Purge of package content and wrapped keys (retention change from "kept" to "purged on close") | Retention/behavioural change | approvals owner |
| A10 | Evaluating flags in the browser rather than on the server | Architecture change for the flags module | rules/medication owner |
| A11 | Doctor/staff/patient clients now hold keys | Client architecture change | web owner |

Record the approval (who, date) in `docs/approvals.md`. Anything not in this table still needs a question to the owner first.

---

## 14. Work packages and build order

Dependencies in brackets. Each package ends with tests, docs updates, and a short report listing what was actually run.

**WP0 — Read, map, spike (no approvals needed).** Read `AGENTS.md`, `docs/v2-changes.md`, the `provider` and `central` services, and the existing patient view and patient accounts (reuse them for section 12 instead of rebuilding). Map each package below onto the real modules and write the mapping to `docs/e2e-mapping.md`. Run the existing test suites and record the real results. Spike: browser crypto with libsodium/WebCrypto (encrypt/wrap/sign) and the HPKE/sealed-box decision. Output: a one-page crypto decision in `docs/crypto.md`.

**WP1 — Key foundation [WP0, A1, A2].** Key directory with hospital-signed entries; hospital signing key handling; client key generation and unlock; department group keys with join/leave/rotate; recovery flow; revocation. Library of crypto helpers used by client and adapters.

**WP2 — Consent, adapter policy, token [WP0, A1–A3].** Consent model and APIs (consent requested by staff, granted by the patient in the portal; this needs the existing patient accounts plus patient key creation, so build the patient key and consent screens of WP10 as part of this package); adapter policy engine with structured refusals; SMART Backend Services (or UDAP B2B) between hub and adapters; participation records and pinned keys.

**WP3 — Encrypted retrieval pipeline [WP1, WP2, A4].** Source adapter builds title + ciphertext + wrapped keys; hub stores them; doctor retrieval button; staff API returns titles only; chunked encryption for scans.

**WP4 — Role-based screens [WP1, WP3, A11].** Role templates drive screens; staff and doctor and patient views; staff titles-only views; remove or reduce the existing staff gather/dose/medicine screens to titles-only (D14).

**WP5 — Approval and signed package [WP3, WP4, A4].** Package manifest, doctor signing, re-wrapping to the receiving department group and patient, immutability and versioning, verification endpoint.

**WP6 — AI record suggestions [WP3, A7].** Browser de-identifier, preview panel, relay endpoint with no content logging, model client interface, ranking prompt and output schema, evidence-id validation, "Not included" list, fallback without a model. Evaluation harness for RQ2.

**WP7 — Medication flags [WP0, A6, A10].** Brand mapping dataset and fuzzy matcher; interaction data bundle build and versioning; browser evaluator; Layer 2 AI suggestions (drug–drug gaps and drug–procedure) via the relay; flag UI with Ignore/Research; evaluation harness for RQ3/RQ4. **No hardcoded drug-procedure table.**

**WP8 — Scans and OCR [WP3].** Client-side OCR for printed text; handwriting evaluation harness and best on-device option; doctor correction flow (staff cannot correct); RQ evaluation.

**WP9 — Lifecycle [WP3, WP5, A9].** State machine updates, 30-day reminder, extend/close with reasons, purge job with receipt and retries, grace period, declined/denied purge, scheduled jobs.

**WP10 — Patient app [WP1, WP5, WP9, A2].** Patient accounts, key creation, consent screens, local encrypted copy, notifications.

**WP11 — Evaluation and documentation [all].** Run the four measurements, write `docs/security-model.md` (including the limits in 5.1 and 15), update `docs/operations.md`, update `AGENTS.md` per approvals, update the defence deck's claims to match what was built (do not claim measurements that were not run).

Suggested order: WP0 → WP1 → WP2 → WP3 → WP4 → WP5 → WP9 → WP6 / WP7 / WP8 (parallel) → WP10 → WP11.

---

## 15. Evaluation (the "computer science" part)

Besides the distributed-systems and security design (separate institution databases, signed access checks, hospital-signed key directory, envelope encryption, delivery outbox with retries and idempotency, hashing/signing of sent versions), four measurable questions:

| RQ | Question | Baseline | Data | Metric |
|----|----------|----------|------|--------|
| RQ1 | Does patient matching find one person across institutions despite spelling variants? | exact match on ID number | synthetic pairs with known answers (Pakistani name spelling variants) | precision, recall |
| RQ2 | Can AI pick what a clinician would include for the package, compared with the fixed floor? | deterministic floor | synthetic cases with a clinician-style gold list | items found, irrelevant items added |
| RQ3 | How reliably are medicine, dose and frequency read from handwriting? Also brand mapping accuracy. | Tesseract | synthetic handwritten prescriptions; synthetic brand list | accuracy per field, several engines compared |
| RQ4 | Does the AI layer rediscover known interactions held out from its context, and how many false alarms? | Layer 1 dataset | held-out known drug pairs; curated drug–procedure test set | recall, false alarms per 100 suggestions |

Also report security tests (section 17). State clearly anything not yet run.

Documented limits to carry into the defence: metadata and demographics are visible to the platform; a compromised doctor device or a malicious platform shipping altered client code defeats E2E; de-identification can miss identifiers; AI suggestions are unverified; the ignored-flag choice is the doctor's; synthetic data only; medication rules and brand mappings are not clinically reviewed; the draft-law claim in 6.1 must be verified.

---

## 16. Open decisions (defaults in brackets; flag to the team if you must pick)

- **O1** (closed) No sender-side copy (D16).
- **O2** AI provider (record suggestions and flags, via relay): external API (data leaves the country) vs self-hosted model [default: abstraction with an external API only for the prototype demo with synthetic data; self-hosted for production]. OCR provider is separate and is called directly from the device (section 10).
- **O3** Patient backup/export of the local copy [default: optional passphrase-protected export].
- **O4** Reminder ignored: weekly reminders, then escalate to department staff; no silent auto-close [default as stated].
- **O5** Patient verification method [default: ID number + one-time code, with staff-assisted verification at the hospital].
- **O6** After purge, keep titles in the platform? [default: keep only the manifest hash and counts, drop titles to reduce exposure].
- **O7** Hospital admin key escrow for lost doctor keys [default: not included; recovery is by re-fetch (5.7)].
- **O8** UDAP B2B vs SMART Backend Services [default: SMART Backend Services, with the claim set of 6.3].
- **O9** (closed) Staff never read or edit content (D14); no intake exception.
- **O10** Maximum total referral lifetime [default 180 days].

---

## 17. Acceptance tests (minimum)

Use canary strings (for example `CANARY-9F3A-NOT-A-REAL-PATIENT`) in test records.

- **T-DB-1** After a full retrieval, dumping the central database and object storage and scanning all bytes finds **no** canary plaintext, no DEK, no private key.
- **T-STAFF-1** Staff API responses (referring and receiving) contain titles only; scanning the full HTTP response bodies and browser network log for canaries finds none. A staff token cannot call the decrypt-key endpoints.
- **T-DOC-1** Doctor with a valid signed key and assignment decrypts and sees content; a doctor in another department cannot; a revoked doctor cannot decrypt new referrals.
- **T-DIR-1** A directory entry with a missing or invalid hospital signature is rejected by the client and by the adapter, and audited.
- **T-GROUP-1** Join, leave and rotation: new referrals use the new key version; leaver cannot decrypt new items.
- **T-TOKEN-1** Adapter rejects: bad signature, wrong audience, expired token, replayed `jti`, non-participant organisation, a purpose not allowed, a missing or expired consent link.
- **T-CONSENT-1** A staff account cannot create, edit or approve a consent for a patient; the consent exists only after the patient approves it in the portal with a valid signature; declined or expired consent blocks the records request.
- **T-POLICY-1** Sensitive category requested without specific consent returns the structured refusal `sensitive_category_no_specific_consent`; with it, returns the items. Manual-review rule returns `pending_manual_review`.
- **T-REFUSAL-1** A refusal or unavailable source is displayed as such, never as "no records".
- **T-APPROVE-1** Package signature verifies; changing any item breaks verification; the new version needs a new signature; the old one stays valid for its own version.
- **T-AI-1** The AI request payload contains no identifier from the patient demographics (test with the patient's name inside a free-text note); the preview shows what is sent; the relay logs contain no payload text; the AI path is skipped with no click; with the model off, the floor still works.
- **T-AI-2** Item ids returned by the model that are not in the list are dropped.
- **T-FLAG-1** Layer 1: a known pair maps and flags using brand names; an unmapped brand yields "could not be assessed", not "no flag".
- **T-FLAG-2** Layer 2: output is schema-validated; invalid JSON is discarded; the model unavailable shows "AI check not available"; AI cannot remove a Layer 1 flag. A source scan shows **no hardcoded drug–procedure table** (grep for static drug/procedure pair lists in the repo and tests excluded from the benchmark folder).
- **T-FLAG-3** Ignore/Research clicks are audited.
- **T-LIFE-1** Reminder fires 30 days after acceptance; extend requires a reason; close triggers the purge after the grace period; purge removes ciphertext and wrapped keys, writes a receipt, and is idempotent when re-run.
- **T-LIFE-2** After purge the patient's local copy (in a test client) still opens and verifies against the manifest.
- **T-REC-1** Lost-key recovery: new key, re-fetch from sources works; items that existed only on the platform are reported as unrecoverable unless the patient's copy exists.
- **T-OCR-1** The OCR path never sends the image or text to our servers (inspect server access logs and request bodies for canaries); the device calls the provider directly; staff see only a title for scans; the header-masking step runs before upload.
- **T-NOCOPY-1** After purge, no table, object store or sending-hospital database contains the referral letter, notes or summary text; the platform made no write-back to the sending hospital.
- **T-AUDIT-1** Audit entries contain no content, keys or de-identified text; the hash chain verifies.
- **T-PERF-1** Report the time and size to decrypt a typical referral (for example 30 items including 5 scans) in the browser on a mid-range phone/laptop.

---

## 18. Deliverables per work package

Code on a local branch; migrations (only after approval); tests; docs (`docs/crypto.md`, `docs/auth.md`, `docs/security-model.md`, `docs/data-lifecycle.md`, `docs/data-sources.md`, `docs/approvals.md`, `docs/e2e-mapping.md`, and `AGENTS.md` updates once approved); a short report stating exactly which tests were run and their results, what is not done, and what is awaiting approval.

Push to GitHub only when the project owner says so.
