# Data inventory: where clinical content lives and for how long

Spec v3, work package A, step 1, updated 2026-10-28. "Working set" means the content is removed when the working set ends (`lifecycle/working_set.py`, [decision](decisions/2026-10-28-referral-expiry.md)): 72 hours after the receiving doctor marks the referral complete, straight away if declined, 72 hours after a cancel, and at the latest 30 days after acceptance unless the receiving doctor extends it. Test requests end 72 hours after the results are back. Removal waits until everything sent has been delivered.

## Central platform (`central_db`)

| Table / store | Clinical content | Purpose | Lifetime | Who else holds a copy |
| --- | --- | --- | --- | --- |
| `evidence_items` | display, original, current, FHIR, OCR text and region, AI reason | Retrieved records, papers and entries for one referral | Working set. After that, the row keeps only its ids, category and the record version number. | Source institution (every version) |
| `evidence_revisions` | prior and new values, note | Correction history | Working set (values cleared, the row stays) | — |
| `documents`, `extraction_runs`, file store | uploaded file, page images, extracted text | Papers brought by the patient | Working set; the files are deleted | Patient (the paper) |
| `medication_entries` | names, brand, dose, route, frequency | Merged current-medicine list | Working set | Sources |
| `medication_flags`, `flag_reviews`, `suggestion_reviews` | flag text, quotes, notes | Flags and decisions | Working set (text cleared; flag id, rule, source and decision stay) | Package (receiver, sender copy) |
| `briefs` | brief sections | Letter text | Working set | Package |
| `referral_packages.envelope` | full sent package | What was sent | Working set. Afterwards only ids, hash and sender stay, plus `manifest` (references only). | Receiving institution; sending clinic (`sent_copies`) |
| `outbox.payload`, `inbound_messages.payload` | package, response, order | Delivery | Working set | Receiver / sender |
| `clarifications` | questions and answers | Questions from the receiving doctor | Working set | Receiving institution |
| `consultation_responses` | a written response | Only responses sent before 2026-10-28 (the response step was removed) | Working set | Receiving institution; sending clinic copy |
| `diagnostic_requests` (report, attachments) | results, images | Test results | Working set | Laboratory or radiology |
| `referrals.reason` | reason text | Request | Working set | Package |
| `selection_runs` | model, prompt version and hash, "missing" phrases | AI recommendation record | Kept (no record values) | — |
| `audit_events`, `referral_events` | actions, ids | Accountability | Kept, append-only | Each institution keeps its own audit |
| `patient_links`, `users` | identity | Linking, accounts | Kept | Institutions |

## Institutions (each in its own database)

| Table | Content | Lifetime |
| --- | --- | --- |
| Patient records (visits, labs, imaging, medicines, conditions) | The institution's own record | The institution's own policy (never changed by the platform) |
| `access_grants` | Who may read which categories, and for which referral | Expire (14 days by default, at most 30) and are revoked when the referral finishes |
| `sent_copies` (sending clinic) | The clinic's copy of each package it sent and each response it received | The clinic's own record |
| `cases` (receiving institution) | Its intake, decision, questions, completion and hold dates | The receiving hospital's own record and retention policy |
| `incoming_packages`, `forwarded_results` (receiving institution) | Its copy of the shared records | Removed when the referral expires (`POST /inbound/referral-expired`); the fingerprint stays |
| Orders and results (laboratory, radiology) | Orders received and results reported | The institution's own record |

## What leaves this computer (only when configured)

| Where | What | Safeguard |
| --- | --- | --- |
| A language model outside this computer (`gemma4:cloud` via Ollama, Anthropic) | De-identified record text for the packet selection, and de-identified OCR lines for paper reading | Only with `LLM_EXTERNAL_ALLOWED=true` and over https; no name, CNIC, record numbers, birth date, doctors' or institutions' names; audited (`generation/privacy.py`) |
| Google Cloud Vision | The page image of an uploaded paper | Only with `OCR_ENGINE=google_vision` and a key; the image cannot be de-identified, so synthetic papers only |
