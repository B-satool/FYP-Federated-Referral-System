# Data inventory: where clinical content lives and for how long

Spec v3, work package A, step 1. "Working set" means the content is removed when the working set ends (`lifecycle/working_set.py`): 72 hours after the specialist's answer is returned or the referral ends, and at most 60 days after the first retrieval. Removal waits until every package, order and the clinic's own copy has been delivered.

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
| `consultation_responses`, `clarifications` | answer, questions | Specialist's reply | Working set | Receiving institution; sending clinic copy |
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
| `cases` / package versions (receiving institution) | The referral it received | The receiving hospital's record and retention policy |
| Orders and results (laboratory, radiology) | Orders received and results reported | The institution's own record |
