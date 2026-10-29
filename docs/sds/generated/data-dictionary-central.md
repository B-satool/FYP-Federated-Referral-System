## Data dictionary: Central platform database (`central_db`)

### `audit_events` (AuditEvent, `services/central/app/models/audit.py`)

FR-59/FR-60: actor, institution, action, affected record, timestamp, outcome.

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `actor_id` | String(64) | no |  |  |  |
| `actor_name` | String(200) | no |  |  |  |
| `institution_id` | String(50) | yes | indexed |  |  |
| `action` | String(80) | no | indexed |  |  |
| `target_type` | String(60) | no |  |  |  |
| `target_id` | String(100) | no |  |  |  |
| `referral_id` | Integer | yes | indexed |  |  |
| `outcome` | String(20) | no |  |  |  |
| `detail` | JSON | no |  | `dict` |  |
| `created_at` | DateTime(timezone=True) | no | indexed | `utcnow` |  |
| `chain_seq` | Integer | yes | unique |  | Hash chain (spec v4 11.5; lifecycle/audit_chain.py): set once by the sealing job, never changed. A database trigger keeps the table append-only: no delete, no change except sealing an unsealed row. |
| `prev_hash` | String(64) | yes |  |  |  |
| `chain_hash` | String(64) | yes |  |  |  |

### `consents` (Consent, `services/central/app/models/consent.py`)

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `reference` | String(30) | no | unique |  |  |
| `referral_id` | Integer | no | FK → referrals.id, indexed |  |  |
| `patient_cnic` | String(15) | no | indexed |  |  |
| `patient_name` | String(200) | no |  |  |  |
| `purpose` | String(20) | no |  | `'TREAT'` |  |
| `requesting_org` | String(50) | no |  |  |  |
| `requesting_practitioner_id` | String(64) | yes |  |  |  |
| `requesting_practitioner_name` | String(200) | no |  |  |  |
| `destination_org` | String(50) | yes |  |  |  |
| `custodians_requested` | JSON | no |  | `list` | what the staff asked for |
| `categories` | JSON | no |  | `list` |  |
| `sensitive_offered` | JSON | no |  | `list` |  |
| `data_period_start` | String(20) | yes |  |  |  |
| `requested_by_id` | String(64) | no |  |  |  |
| `requested_by_name` | String(200) | no |  |  |  |
| `requested_at` | DateTime(timezone=True) | no |  | `utcnow` |  |
| `status` | String(20) | no | indexed | `'requested'` | requested \| granted \| declined \| revoked \| expired \| withdrawn |
| `custodians_granted` | JSON | no |  | `list` | the patient's answer |
| `sensitive_specific` | JSON | no |  | `list` |  |
| `period_start` | DateTime(timezone=True) | yes |  |  |  |
| `period_end` | DateTime(timezone=True) | yes |  |  |  |
| `document` | JSON | yes |  |  | FHIR Consent shape, signed by the patient |
| `patient_key_id` | String(16) | yes |  |  |  |
| `decided_at` | DateTime(timezone=True) | yes |  |  |  |
| `decline_reason` | Text | yes |  |  |  |
| `revocation` | JSON | yes |  |  | signed by the patient |
| `revoked_at` | DateTime(timezone=True) | yes |  |  |  |

### `record_requests` (RecordRequest, `services/central/app/models/consent.py`)

One request to one institution for a referral's records, and its outcome. A refusal keeps its reason code; an unreachable institution is 'unavailable'. Neither is ever shown as 'no records' (AGENTS.md).

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `referral_id` | Integer | no | FK → referrals.id, indexed |  |  |
| `consent_id` | Integer | no | FK → consents.id, indexed |  |  |
| `custodian` | String(50) | no |  |  |  |
| `request_key` | String(200) | no | unique |  |  |
| `local_patient_id` | String(50) | yes |  |  |  |
| `practitioner_id` | String(64) | no |  |  |  |
| `status` | String(30) | no | indexed |  | sent \| answered \| partial \| refused \| pending_manual_review \| no_records \| unavailable \| failed |
| `refusals` | JSON | no |  | `list` |  |
| `item_count` | Integer | no |  | `0` |  |
| `batch_id` | String(60) | yes |  |  |  |
| `policy_version` | String(60) | yes |  |  |  |
| `message` | Text | no |  | `''` |  |
| `requested_by` | String(200) | no |  |  |  |
| `requested_at` | DateTime(timezone=True) | no |  | `utcnow` |  |
| `answered_at` | DateTime(timezone=True) | yes |  |  |  |

### `encrypted_batches` (EncryptedBatch, `services/central/app/models/encrypted.py`)

Items encrypted under one data key: one institution's answer to one request, one upload by a doctor or the patient, or the receiving hospital's added records.

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `referral_id` | Integer | no | FK → referrals.id, indexed |  |  |
| `batch_id` | String(60) | no | unique |  |  |
| `origin` | String(20) | no |  |  | custodian (a source institution's answer) \| doctor (the referring doctor's own items) \| patient (patient's scans) \| receiving (records the receiving hospital added) |
| `source_institution` | String(50) | yes |  |  |  |
| `record_request_id` | Integer | yes |  |  |  |
| `created_by` | String(200) | no |  |  |  |
| `created_at` | DateTime(timezone=True) | no |  | `utcnow` |  |

### `encrypted_items` (EncryptedItem, `services/central/app/models/encrypted.py`)

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `referral_id` | Integer | no | FK → referrals.id, indexed |  |  |
| `batch_id` | String(60) | no | indexed |  |  |
| `item_id` | String(120) | no |  |  |  |
| `kind` | String(20) | no |  |  | lab \| imaging \| note \| prescription \| scan \| other |
| `category` | String(30) | yes |  |  |  |
| `label` | String(300) | no |  |  |  |
| `item_date` | String(30) | yes |  |  |  |
| `source_institution` | String(50) | yes |  |  |  |
| `sensitive` | Boolean | no |  | `False` |  |
| `sealed` | JSON | no |  |  | {"nonce", "ciphertext"} or {"chunks": [{"nonce", "ciphertext"}, ...]} for large files |
| `size` | BigInteger | no |  | `0` |  |
| `ciphertext_sha256` | String(64) | no |  |  |  |
| `created_at` | DateTime(timezone=True) | no |  | `utcnow` |  |

Unique constraints: (batch_id, item_id)

### `package_manifests` (PackageManifest, `services/central/app/models/encrypted.py`)

A doctor-signed package version (spec v4 5.8): the ordered item list with plaintext and ciphertext hashes, the recipient department key, the referral. Immutable; a change is a new version and signature.

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `referral_id` | Integer | no | FK → referrals.id, indexed |  |  |
| `version` | Integer | no |  |  |  |
| `manifest` | JSON | no |  |  | signed by the doctor (signature inside) |
| `manifest_sha256` | String(64) | no |  |  |  |
| `signer_subject` | String(64) | no |  |  |  |
| `signer_key_id` | String(16) | no |  |  |  |
| `item_count` | Integer | no |  |  |  |
| `superseded` | Boolean | no |  | `False` |  |
| `created_at` | DateTime(timezone=True) | no |  | `utcnow` |  |

Unique constraints: (referral_id, version)

### `purge_receipts` (PurgeReceipt, `services/central/app/models/encrypted.py`)

What remains after a referral's content is crypto-shredded (spec v4 11.2).

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `referral_id` | Integer | no | FK → referrals.id, unique |  |  |
| `purged_at` | DateTime(timezone=True) | no |  | `utcnow` |  |
| `items_count` | Integer | no |  |  |  |
| `wrapped_keys_count` | Integer | no |  |  |  |
| `manifest_hash` | String(64) | yes |  |  |  |
| `trigger` | String(40) | no |  |  |  |
| `detail` | JSON | no |  | `dict` |  |
| `note` | Text | no |  | `''` |  |

### `wrapped_keys` (WrappedKey, `services/central/app/models/encrypted.py`)

A batch's data key, wrapped to one recipient key (doctor, patient or department group).

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `referral_id` | Integer | no | FK → referrals.id, indexed |  |  |
| `batch_id` | String(60) | no | indexed |  |  |
| `recipient_type` | String(20) | no |  |  | doctor \| patient \| department |
| `recipient_subject` | String(100) | no | indexed |  |  |
| `recipient_key_id` | String(16) | no | indexed |  |  |
| `key_version` | Integer | yes |  |  |  |
| `wrapped` | JSON | no |  |  |  |
| `created_by` | String(200) | no |  |  |  |
| `created_at` | DateTime(timezone=True) | no |  | `utcnow` |  |

Unique constraints: (batch_id, recipient_key_id)

### `documents` (Document, `services/central/app/models/evidence.py`)

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `referral_id` | Integer | no | FK → referrals.id, indexed |  |  |
| `patient_institution` | String(50) | no |  |  |  |
| `patient_local_id` | String(50) | no |  |  |  |
| `uploaded_by` | String(200) | no |  |  |  |
| `uploaded_by_id` | String(64) | no |  |  |  |
| `original_filename` | String(255) | no |  |  |  |
| `declared_type` | String(100) | no |  |  |  |
| `detected_type` | String(100) | no |  |  |  |
| `size_bytes` | Integer | no |  |  |  |
| `sha256` | String(64) | no |  |  |  |
| `storage_key` | String(200) | no |  |  |  |
| `doc_type` | String(40) | no |  |  |  |
| `page_count` | Integer | no |  | `0` |  |
| `status` | String(20) | no |  | `'uploaded'` | uploaded \| queued \| processing \| extracted \| failed |
| `error` | Text | yes |  |  |  |
| `created_at` | DateTime(timezone=True) | no |  | `utcnow` |  |
| `deleted_at` | DateTime(timezone=True) | yes |  |  |  |

### `evidence_items` (EvidenceItem, `services/central/app/models/evidence.py`)

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `referral_id` | Integer | no | FK → referrals.id, indexed |  |  |
| `patient_institution` | String(50) | no |  |  |  |
| `patient_local_id` | String(50) | no |  |  |  |
| `origin` | String(20) | no |  |  | source \| document \| manual |
| `source_institution` | String(50) | no |  |  |  |
| `source_record_type` | String(40) | yes |  |  |  |
| `source_record_id` | String(80) | yes |  |  |  |
| `source_record_version` | String(20) | yes |  |  |  |
| `link_id` | Integer | yes |  |  |  |
| `category` | String(30) | no | indexed |  |  |
| `display` | Text | no |  |  |  |
| `original` | JSON | no |  | `dict` |  |
| `current` | JSON | no |  | `dict` |  |
| `fhir` | JSON | yes |  |  |  |
| `clinical_time` | DateTime(timezone=True) | yes |  |  |  |
| `retrieved_at` | DateTime(timezone=True) | no |  | `utcnow` |  |
| `document_id` | Integer | yes | FK → documents.id |  |  |
| `page` | Integer | yes |  |  |  |
| `region` | JSON | yes |  |  |  |
| `source_text` | Text | yes |  |  |  |
| `confidence` | JSON | yes |  |  |  |
| `review_state` | String(20) | no |  |  | imported \| proposed \| corrected \| unresolved \| excluded \| manual |
| `verification_status` | String(20) | no |  |  | source_record \| unverified \| verified \| invalidated |
| `verified_by` | String(200) | yes |  |  |  |
| `verified_at` | DateTime(timezone=True) | yes |  |  |  |
| `selected` | Boolean | no |  | `False` |  |
| `in_default` | Boolean | no |  | `False` | packet selection (spec v3 B): rule-based default, AI recommendation, staff decision |
| `selection_source` | String(10) | yes |  |  | default \| ai \| staff |
| `selected_by` | String(200) | yes |  |  |  |
| `selected_at` | DateTime(timezone=True) | yes |  |  |  |
| `ai_recommendation` | String(10) | yes |  |  | include \| exclude \| optional |
| `ai_relevance` | String(10) | yes |  |  | high \| medium \| low |
| `ai_reason` | Text | yes |  |  |  |
| `ai_run_id` | Integer | yes |  |  |  |
| `superseded_by` | Integer | yes |  |  |  |
| `author` | String(200) | yes |  |  |  |
| `row_version` | Integer | no |  | `1` |  |
| `created_at` | DateTime(timezone=True) | no |  | `utcnow` |  |
| `updated_at` | DateTime(timezone=True) | no |  | `utcnow` |  |

Unique constraints: (referral_id, source_institution, source_record_type, source_record_id, source_record_version) `uq_evidence_source_version`

### `evidence_revisions` (EvidenceRevision, `services/central/app/models/evidence.py`)

Append-only history; raw extraction is never overwritten (FR-28).

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `evidence_id` | Integer | no | FK → evidence_items.id, indexed |  |  |
| `action` | String(30) | no |  |  |  |
| `prior_value` | JSON | yes |  |  |  |
| `new_value` | JSON | yes |  |  |  |
| `prior_state` | String(20) | yes |  |  |  |
| `new_state` | String(20) | yes |  |  |  |
| `editor` | String(200) | no |  |  |  |
| `editor_id` | String(64) | no |  |  |  |
| `note` | Text | no |  | `''` |  |
| `created_at` | DateTime(timezone=True) | no |  | `utcnow` |  |

### `extraction_runs` (ExtractionRun, `services/central/app/models/evidence.py`)

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `document_id` | Integer | no | FK → documents.id, indexed |  |  |
| `job_id` | String(40) | yes |  |  |  |
| `text_source` | String(20) | yes |  |  | embedded \| ocr \| mixed |
| `ocr_engine` | String(60) | yes |  |  |  |
| `ocr_engine_version` | String(40) | yes |  |  |  |
| `extractor` | String(80) | yes |  |  |  |
| `extractor_version` | String(40) | yes |  |  |  |
| `raw_text` | Text | no |  | `''` |  |
| `pages` | JSON | no |  | `list` |  |
| `status` | String(20) | no |  | `'running'` |  |
| `error` | Text | yes |  |  |  |
| `notes` | JSON | no |  | `list` |  |
| `duration_ms` | Integer | no |  | `0` |  |
| `created_at` | DateTime(timezone=True) | no |  | `utcnow` |  |

### `jobs` (Job, `services/central/app/models/evidence.py`)

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | String(40) | no | PK |  |  |
| `kind` | String(40) | no |  |  |  |
| `status` | String(20) | no |  | `'queued'` | queued \| running \| completed \| failed |
| `referral_id` | Integer | yes | FK → referrals.id, indexed |  |  |
| `document_id` | Integer | yes | FK → documents.id |  |  |
| `params` | JSON | no |  | `dict` |  |
| `result` | JSON | yes |  |  |  |
| `error` | Text | yes |  |  |  |
| `attempts` | Integer | no |  | `0` |  |
| `created_by` | String(200) | no |  |  |  |
| `created_by_id` | String(64) | no |  |  |  |
| `institution_id` | String(50) | yes |  |  |  |
| `created_at` | DateTime(timezone=True) | no |  | `utcnow` |  |
| `started_at` | DateTime(timezone=True) | yes |  |  |  |
| `finished_at` | DateTime(timezone=True) | yes |  |  |  |

### `selection_runs` (SelectionRun, `services/central/app/models/evidence.py`)

One AI packet-selection attempt: which model and prompt, and whether its answer was used.

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `referral_id` | Integer | no | FK → referrals.id, indexed |  |  |
| `status` | String(20) | no |  |  | completed \| unavailable (no model / API error) \| rejected (answer failed checks) \| nothing_to_review \| discarded (the working set was removed before the answer arrived) |
| `provider` | String(40) | yes |  |  |  |
| `model` | String(80) | yes |  |  |  |
| `prompt_version` | String(40) | no |  |  |  |
| `prompt_hash` | String(64) | no |  |  |  |
| `item_count` | Integer | no |  | `0` |  |
| `truncated` | Boolean | no |  | `False` |  |
| `missing` | JSON | no |  | `list` |  |
| `error` | Text | yes |  |  |  |
| `created_by` | String(200) | no |  |  |  |
| `created_at` | DateTime(timezone=True) | no |  | `utcnow` |  |

### `source_retrievals` (SourceRetrieval, `services/central/app/models/evidence.py`)

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `referral_id` | Integer | no | FK → referrals.id, indexed |  |  |
| `source_institution` | String(50) | no |  |  |  |
| `local_patient_id` | String(50) | no |  |  |  |
| `link_id` | Integer | yes |  |  |  |
| `institution_kind` | String(20) | yes |  |  |  |
| `last_activity` | String(20) | yes |  |  |  |
| `window_start` | String(20) | yes |  |  |  |
| `status` | String(20) | no |  |  | successful \| empty \| partial \| denied \| unavailable \| invalid \| skipped (not the most recent of its kind) |
| `record_count` | Integer | no |  | `0` |  |
| `new_count` | Integer | no |  | `0` |  |
| `duplicate_count` | Integer | no |  | `0` |  |
| `invalid_count` | Integer | no |  | `0` |  |
| `withheld` | JSON | no |  | `list` |  |
| `message` | Text | no |  | `''` |  |
| `retryable` | Boolean | no |  | `False` |  |
| `attempts` | Integer | no |  | `1` |  |
| `duration_ms` | Integer | no |  | `0` |  |
| `requested_by` | String(200) | no |  |  |  |
| `requested_at` | DateTime(timezone=True) | no |  | `utcnow` |  |

### `patient_link_events` (PatientLinkEvent, `services/central/app/models/identity.py`)

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `link_id` | Integer | no | FK → patient_links.id, indexed |  |  |
| `action` | String(30) | no |  |  |  |
| `actor` | String(200) | no |  |  |  |
| `actor_id` | String(64) | no |  |  |  |
| `institution_id` | String(50) | yes |  |  |  |
| `note` | Text | no |  | `''` |  |
| `detail` | JSON | no |  | `dict` |  |
| `created_at` | DateTime(timezone=True) | no |  | `utcnow` |  |

### `patient_links` (PatientLink, `services/central/app/models/identity.py`)

A request from one institution to another to confirm which of the other's patient records is the same person. It becomes verified only when staff at the OTHER institution check it and approve it. Records are never linked on matching IDs or names.

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `requester_institution` | String(50) | no | indexed |  |  |
| `requester_local_id` | String(50) | no | indexed |  |  |
| `target_institution` | String(50) | no | indexed |  |  |
| `target_local_id` | String(50) | yes | indexed |  |  |
| `patient_name` | String(200) | no |  |  | Identity details sent with the request (from the requester's own record) |
| `patient_birth_date` | String(20) | yes |  |  |  |
| `patient_sex` | String(10) | yes |  |  |  |
| `patient_cnic` | String(15) | yes |  |  |  |
| `referral_id` | Integer | yes | FK → referrals.id |  |  |
| `purpose` | Text | no |  | `''` |  |
| `kind` | String(20) | no |  | `'records'` | records = asking a place the patient visited for their records (it matches a record or says it has none); intake = sent with a referral or test order, so the receiver matches the patient or registers them as new |
| `status` | String(20) | no | indexed | `'requested'` | requested \| verified \| rejected \| invalidated |
| `status_key` | String(40) | no |  | `'current'` | lets a rejected/invalidated pair be requested again without violating uniqueness |
| `requested_by` | String(200) | no |  |  |  |
| `requested_by_id` | String(64) | no |  |  |  |
| `requested_at` | DateTime(timezone=True) | no |  | `utcnow` |  |
| `decided_by` | String(200) | yes |  |  |  |
| `decided_by_id` | String(64) | yes |  |  |  |
| `decided_at` | DateTime(timezone=True) | yes |  |  |  |
| `decision_note` | Text | yes |  |  |  |
| `match_check` | JSON | yes |  |  |  |
| `registered_new` | Boolean | no |  | `False` |  |
| `invalidated_by` | String(200) | yes |  |  |  |
| `invalidated_at` | DateTime(timezone=True) | yes |  |  |  |
| `invalidation_reason` | Text | yes |  |  |  |

Unique constraints: (requester_institution, requester_local_id, target_institution, status_key)

### `users` (User, `services/central/app/models/identity.py`)

Central reference to a Keycloak account. account_status is checked on every request.

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | String(64) | no | PK |  | Keycloak subject |
| `username` | String(100) | no | indexed |  |  |
| `display_name` | String(200) | no |  |  |  |
| `institution_id` | String(50) | yes | indexed |  |  |
| `department` | String(60) | yes |  |  |  |
| `roles` | JSON | no |  | `list` |  |
| `account_status` | String(20) | no |  | `'active'` |  |
| `status_changed_by` | String(200) | yes |  |  |  |
| `status_changed_at` | DateTime(timezone=True) | yes |  |  |  |
| `last_seen_at` | DateTime(timezone=True) | no |  | `utcnow` |  |

### `group_key_wraps` (GroupKeyWrap, `services/central/app/models/keys.py`)

A department group private key wrapped to one member doctor's encryption key (ciphertext).

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `hospital_id` | String(50) | no |  |  |  |
| `department` | String(60) | no |  |  |  |
| `group_version` | Integer | no |  |  |  |
| `member_subject_id` | String(64) | no | indexed |  |  |
| `member_key_id` | String(16) | no | indexed |  |  |
| `wrapped` | JSON | no |  |  |  |
| `created_at` | DateTime(timezone=True) | no |  | `utcnow` |  |

Unique constraints: (hospital_id, department, group_version, member_key_id)

### `key_directory` (DirectoryEntry, `services/central/app/models/keys.py`)

A doctor's, department's or patient's public keys, signed by the issuing hospital (or, for a patient, the platform). Stored exactly as signed; clients and adapters verify the signature against pinned keys.

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `subject_id` | String(100) | no | indexed |  |  |
| `subject_type` | String(20) | no | indexed |  | doctor \| department \| patient |
| `hospital_id` | String(50) | yes | indexed |  |  |
| `department` | String(60) | yes | indexed |  |  |
| `enc_key_id` | String(16) | no | unique |  |  |
| `key_version` | Integer | no |  |  |  |
| `issued_by` | String(50) | no |  |  |  |
| `entry` | JSON | no |  |  |  |
| `revocation` | JSON | yes |  |  |  |
| `revoked_at` | DateTime(timezone=True) | yes |  |  |  |
| `created_at` | DateTime(timezone=True) | no |  | `utcnow` |  |

### `platform_keys` (PlatformKey, `services/central/app/models/keys.py`)

The platform's own signing key (request assertions to adapters, patient key entries). Sealed with the platform's key-store secret.

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `kid` | String(16) | no | PK |  |  |
| `public_spki` | Text | no |  |  |  |
| `private_sealed` | JSON | no |  |  |  |
| `created_at` | DateTime(timezone=True) | no |  | `utcnow` |  |
| `retired_at` | DateTime(timezone=True) | yes |  |  |  |

### `seen_assertions` (SeenAssertion, `services/central/app/models/keys.py`)

Adapter request assertions already accepted (jti), until they expire: a replay is refused.

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `jti` | String(80) | no | PK |  |  |
| `issuer` | String(50) | no |  |  |  |
| `expires_at` | DateTime(timezone=True) | no | indexed |  |  |

### `ai_suggestions` (AiSuggestion, `services/central/app/models/medications.py`)

A possible clash between two ingredients that have no entry in the interaction source, scored offline by a small model. A suggestion is never a flag: it cannot add, remove or change a flag, never blocks sending and is not included in the sent referral.

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `pair_key` | String(210) | no | PK |  | "a\|b" with a < b |
| `ingredient_a` | String(100) | no | indexed |  |  |
| `ingredient_b` | String(100) | no | indexed |  |  |
| `score` | Float | no |  |  |  |
| `reason` | Text | no |  |  |  |
| `model_version` | String(60) | no |  |  |  |
| `data_version` | String(200) | no |  |  |  |

### `drug_interactions` (DrugInteraction, `services/central/app/models/medications.py`)

A drug-drug interaction pair from an imported source (stored once, ingredient_a < ingredient_b). The severity is the source's own level, unchanged.

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `ingredient_a` | String(100) | no | indexed |  |  |
| `ingredient_b` | String(100) | no | indexed |  |  |
| `severity` | String(20) | no |  |  | Major \| Moderate \| Minor \| Unknown |
| `source` | String(40) | no |  |  | ddinter |
| `source_version` | String(80) | no |  |  |  |
| `source_ref` | String(80) | no |  |  |  |
| `label_quote` | Text | yes |  |  | Why, in the source's own words: a sentence quoted verbatim from a US drug label's interaction section that names the other ingredient (rules/labels/interaction-quotes.json). Empty when none exists. |
| `label_source` | String(200) | yes |  |  |  |
| `label_section` | String(60) | yes |  |  |  |

Unique constraints: (ingredient_a, ingredient_b, source)

### `evaluation_runs` (EvaluationRun, `services/central/app/models/medications.py`)

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `referral_id` | Integer | no | FK → referrals.id, indexed |  |  |
| `trigger` | String(160) | no |  |  |  |
| `status` | String(20) | no |  |  | completed \| failed |
| `outcome` | String(30) | yes |  |  | flags \| no_match \| no_rules |
| `summary_message` | Text | yes |  |  |  |
| `context` | JSON | no |  | `dict` |  |
| `rule_versions` | JSON | no |  | `dict` |  |
| `input_hash` | String(64) | no |  |  |  |
| `ruleset_hash` | String(64) | yes |  |  |  |
| `error` | Text | yes |  |  |  |
| `changed_flags` | Integer | no |  | `0` |  |
| `triggered_by` | String(200) | no |  |  |  |
| `created_at` | DateTime(timezone=True) | no |  | `utcnow` |  |

### `flag_reviews` (FlagReview, `services/central/app/models/medications.py`)

A doctor's decision on one flag version for this patient: reviewed, ignore (not relevant for this patient) or research (needs follow-up). Any decision means the flag has been seen; it is never treatment clearance. Ignored flags stay visible in the record.

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `referral_id` | Integer | no | FK → referrals.id, indexed |  |  |
| `flag_id` | Integer | no | FK → medication_flags.id, indexed |  |  |
| `flag_version` | Integer | no |  |  |  |
| `side` | String(20) | no |  | `'referring'` |  |
| `reviewer` | String(200) | no |  |  |  |
| `reviewer_id` | String(64) | no |  |  |  |
| `institution_id` | String(50) | no |  |  |  |
| `package_version` | Integer | yes |  |  |  |
| `decision` | String(20) | no |  | `'reviewed'` | reviewed \| ignore \| research |
| `ruleset_hash` | String(64) | yes |  |  |  |
| `note` | Text | no |  | `''` |  |
| `created_at` | DateTime(timezone=True) | no |  | `utcnow` |  |

### `ingredients` (Ingredient, `services/central/app/models/medications.py`)

An ingredient as named in this project, with its international name (used by DDInter and drug labels), RxNorm and ATC codes, and the parts of a combination product.

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `name` | String(100) | no | PK |  |  |
| `standard` | String(100) | yes |  |  |  |
| `label_name` | String(100) | yes |  |  |  |
| `rxnorm_id` | String(20) | yes |  |  |  |
| `atc_codes` | JSON | no |  | `list` |  |
| `components` | JSON | no |  | `list` |  |
| `in_interaction_source` | Boolean | no |  | `False` |  |
| `note` | Text | yes |  |  |  |

### `label_rules` (LabelRule, `services/central/app/models/medications.py`)

A drug-condition or drug-procedure rule read from a drug label by script, with the exact sentence it relies on. Imported rules are labelled automatically generated, not clinically reviewed.

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `rule_key` | String(200) | no | unique |  |  |
| `kind` | String(20) | no |  |  | drug_condition \| drug_procedure |
| `ingredient` | String(100) | no | indexed |  |  |
| `target` | String(60) | no |  |  |  |
| `target_label` | String(120) | no |  |  |  |
| `severity_hint` | String(20) | no |  |  | high \| moderate \| low (display only) |
| `summary` | Text | no |  |  |  |
| `quote` | Text | no |  |  |  |
| `section` | String(40) | no |  |  |  |
| `source_type` | String(40) | no |  | `'drug_label'` |  |
| `source_ref` | String(80) | no |  |  |  |
| `source_name` | String(200) | no |  |  |  |
| `source_version` | String(80) | no |  |  |  |
| `extractor_version` | String(40) | no |  |  |  |
| `status` | String(20) | no |  | `'auto_extracted'` | auto_extracted \| withdrawn |

### `medication_entries` (MedicationEntry, `services/central/app/models/medications.py`)

One current medicine as recorded by one source. Entries for the same medicine and strength from different sources form a group shown once (duplicate_of points at the entry that represents the group).

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `referral_id` | Integer | no | FK → referrals.id, indexed |  |  |
| `evidence_id` | Integer | no | FK → evidence_items.id |  |  |
| `record_kind` | String(20) | no |  |  | prescription \| document \| manual |
| `original_name` | String(200) | no |  |  |  |
| `brand` | String(100) | yes |  |  |  |
| `strength` | String(60) | yes |  |  |  |
| `dose` | String(120) | yes |  |  |  |
| `route` | String(40) | yes |  |  |  |
| `frequency` | String(100) | yes |  |  |  |
| `start_date` | String(20) | yes |  |  |  |
| `over_the_counter` | Boolean | no |  | `False` |  |
| `source_label` | String(300) | no |  |  |  |
| `ingredient` | String(100) | yes |  |  |  |
| `ingredients` | JSON | no |  | `list` | every ingredient checked for this medicine (several for a combination product) |
| `drug_class` | String(60) | yes |  |  |  |
| `mapping_status` | String(20) | no |  |  | mapped \| ambiguous \| unmapped \| staff_mapped |
| `mapping_choices` | JSON | yes |  |  | ambiguous DRAP brand: the products it could be, for staff or the doctor to pick from by company |
| `mapping_note` | Text | yes |  |  |  |
| `duplicate_of` | Integer | yes |  |  |  |
| `dose_differs` | Boolean | no |  | `False` |  |
| `excluded` | Boolean | no |  | `False` |  |
| `excluded_by` | String(200) | yes |  |  |  |
| `excluded_reason` | Text | yes |  |  |  |
| `created_at` | DateTime(timezone=True) | no |  | `utcnow` |  |
| `updated_at` | DateTime(timezone=True) | no |  | `utcnow` |  |

Unique constraints: (referral_id, evidence_id)

### `medication_flags` (MedicationFlag, `services/central/app/models/medications.py`)

A flag version. A material change supersedes the row and creates version+1.

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `referral_id` | Integer | no | FK → referrals.id, indexed |  |  |
| `flag_key` | String(200) | no |  |  |  |
| `version` | Integer | no |  | `1` |  |
| `kind` | String(40) | no |  |  | confirmed (approved manual rule) \| interaction \| label_warning \| unrecognised_medicine \| interactions_not_checked \| procedure_not_checked \| records_incomplete |
| `severity` | String(20) | yes |  |  | the source's level, unchanged |
| `ingredients` | JSON | no |  | `list` |  |
| `source_type` | String(40) | yes |  |  | manual_rule \| ddinter \| drug_label |
| `source_name` | String(200) | yes |  |  |  |
| `source_ref` | Text | yes |  |  |  |
| `source_version` | String(80) | yes |  |  |  |
| `source_quote` | Text | yes |  |  |  |
| `auto_generated` | Boolean | no |  | `False` |  |
| `requires_decision` | Boolean | no |  | `True` | the doctor must record a decision before sending (approved rules, Major interactions, high label warnings, gaps) |
| `title` | String(300) | no |  |  |  |
| `message` | Text | no |  |  |  |
| `medication` | String(300) | yes |  |  |  |
| `drug_class` | String(60) | yes |  |  |  |
| `source_label` | String(500) | yes |  |  |  |
| `rule_id` | String(60) | yes |  |  |  |
| `rule_version` | Integer | yes |  |  |  |
| `medication_entry_id` | Integer | yes |  |  |  |
| `evidence_ids` | JSON | no |  | `list` |  |
| `content_hash` | String(64) | no |  |  |  |
| `status` | String(20) | no |  | `'active'` | active \| superseded \| withdrawn |
| `run_id` | Integer | no | FK → evaluation_runs.id |  |  |
| `created_at` | DateTime(timezone=True) | no |  | `utcnow` |  |
| `superseded_at` | DateTime(timezone=True) | yes |  |  |  |

Unique constraints: (referral_id, flag_key, version)

### `medication_rules` (MedicationRule, `services/central/app/models/medications.py`)

One version of a drug-against-procedure rule. Edited in the app; a new or changed rule is a draft until a clinical reviewer approves that exact version.

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `rule_id` | String(60) | no | indexed |  |  |
| `version` | Integer | no |  |  |  |
| `title` | String(300) | no |  |  |  |
| `drug_class` | String(60) | no |  |  |  |
| `procedure_tags` | JSON | no |  | `list` |  |
| `message` | Text | no |  |  |  |
| `rationale` | Text | no |  | `''` |  |
| `reference` | Text | no |  | `''` |  |
| `status` | String(20) | no | indexed | `'draft'` | draft \| approved \| rejected \| retired \| superseded |
| `content_hash` | String(64) | no |  |  |  |
| `created_by` | String(200) | no |  |  |  |
| `created_by_id` | String(64) | no |  |  |  |
| `created_at` | DateTime(timezone=True) | no |  | `utcnow` |  |
| `decided_by` | String(200) | yes |  |  |  |
| `decided_by_id` | String(64) | yes |  |  |  |
| `decided_at` | DateTime(timezone=True) | yes |  |  |  |
| `reference_checked` | Text | yes |  |  |  |
| `decision_note` | Text | yes |  |  |  |

Unique constraints: (rule_id, version)

### `medicine_names` (MedicineName, `services/central/app/models/medications.py`)

A medicine name (brand or generic, as written in Pakistan) mapped to its ingredient and drug class. Maintained in the app by clinical reviewers.

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `name` | String(120) | no | unique |  | normalised lowercase |
| `display` | String(120) | no |  |  |  |
| `ingredient` | String(100) | no |  |  |  |
| `drug_class` | String(60) | no |  |  |  |
| `kind` | String(20) | no |  | `'generic'` | generic \| brand \| register_brand \| register_ambiguous (DRAP) |
| `status` | String(20) | no |  | `'active'` | active \| retired |
| `options` | JSON | yes |  |  | register_ambiguous only: the products behind the name (ingredient, company, DRAP number, strength, form) |
| `added_by` | String(200) | no |  |  |  |
| `created_at` | DateTime(timezone=True) | no |  | `utcnow` |  |

### `ruleset_releases` (RulesetRelease, `services/central/app/models/medications.py`)

The exact rule set in force: approved manual rules, label rules and interaction data, by hash.

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `hash` | String(64) | no | unique |  |  |
| `notes` | Text | no |  | `''` |  |
| `counts` | JSON | no |  | `dict` |  |
| `created_at` | DateTime(timezone=True) | no |  | `utcnow` |  |

### `suggestion_reviews` (SuggestionReview, `services/central/app/models/medications.py`)

A doctor's decision on one AI suggestion for one patient: ignore or research (logged).

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `referral_id` | Integer | no | FK → referrals.id, indexed |  |  |
| `pair_key` | String(210) | no |  |  |  |
| `decision` | String(20) | no |  |  | ignore \| research |
| `note` | Text | no |  | `''` |  |
| `score` | Float | no |  |  |  |
| `model_version` | String(60) | no |  |  |  |
| `data_version` | String(200) | no |  |  |  |
| `reviewer` | String(200) | no |  |  |  |
| `reviewer_id` | String(64) | no |  |  |  |
| `created_at` | DateTime(timezone=True) | no |  | `utcnow` |  |

### `briefs` (Brief, `services/central/app/models/referrals.py`)

The referral summary built from the verified records when a version is sent. Immutable.

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `referral_id` | Integer | no | FK → referrals.id, indexed |  |  |
| `version` | Integer | no |  |  |  |
| `kind` | String(20) | no |  | `'template'` |  |
| `sections` | JSON | no |  |  |  |
| `limitations` | JSON | no |  | `list` |  |
| `evidence_ids` | JSON | no |  | `list` |  |
| `created_by` | String(200) | no |  |  |  |
| `created_at` | DateTime(timezone=True) | no |  | `utcnow` |  |

Unique constraints: (referral_id, version)

### `clarifications` (Clarification, `services/central/app/models/referrals.py`)

A request for more information from the receiving doctor, answered by the referring clinic.

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `referral_id` | Integer | no | FK → referrals.id, indexed |  |  |
| `provider_clarification_id` | Integer | yes |  |  |  |
| `package_version` | Integer | yes |  |  |  |
| `question` | Text | no |  |  |  |
| `asked_by` | String(200) | no |  |  |  |
| `asked_at` | DateTime(timezone=True) | no |  | `utcnow` |  |
| `status` | String(20) | no | indexed | `'open'` | open \| answered |
| `answer` | Text | yes |  |  |  |
| `answered_by` | String(200) | yes |  |  |  |
| `answered_at` | DateTime(timezone=True) | yes |  |  |  |

### `consultation_responses` (ConsultationResponse, `services/central/app/models/referrals.py`)

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `referral_id` | Integer | no | FK → referrals.id, indexed |  |  |
| `remote_key` | String(200) | no | unique |  |  |
| `package_version` | Integer | no |  |  |  |
| `content` | JSON | no |  |  |  |
| `specialist_name` | String(200) | no |  |  |  |
| `returned_at` | DateTime(timezone=True) | no |  |  |  |
| `received_at` | DateTime(timezone=True) | no |  | `utcnow` |  |
| `reviewed_by` | String(200) | yes |  |  |  |
| `reviewed_by_id` | String(64) | yes |  |  |  |
| `reviewed_at` | DateTime(timezone=True) | yes |  |  |  |
| `review_note` | Text | yes |  |  |  |
| `fhir_task` | JSON | yes |  |  |  |

### `diagnostic_requests` (DiagnosticRequest, `services/central/app/models/referrals.py`)

A test, scan or equipment request added to a referral. It is a separate order with its own status; it does not wait for the specialist's decision.

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `reference` | String(30) | no | unique |  |  |
| `referral_id` | Integer | no | FK → referrals.id, indexed |  |  |
| `category` | String(20) | no |  |  | laboratory \| imaging \| cardiac |
| `test` | String(200) | no |  |  |  |
| `body_area` | String(100) | yes |  |  |  |
| `clinical_question` | Text | no |  |  |  |
| `urgency` | String(20) | no |  | `'routine'` |  |
| `destination_institution` | String(50) | no | indexed |  |  |
| `destination_department` | String(60) | no |  |  |  |
| `status` | String(20) | no | indexed | `'draft'` | draft (in the referral, not sent yet) \| requested \| accepted \| rejected \| scheduled \| done \| reported \| cancelled |
| `requested_by` | String(200) | no |  |  |  |
| `requested_by_id` | String(64) | no |  |  |  |
| `sent_by` | String(200) | yes |  |  |  |
| `sent_at` | DateTime(timezone=True) | yes |  |  |  |
| `reject_reason` | Text | yes |  |  |  |
| `scheduled_for` | DateTime(timezone=True) | yes |  |  |  |
| `report` | JSON | yes |  |  |  |
| `attachments` | JSON | no |  | `list` | Images or report files returned with the result: [{"n", "filename", "content_type", "storage_key", "size"}] |
| `local_patient_id` | String(50) | yes |  |  | at the destination, once confirmed |
| `seen_by` | String(200) | yes |  |  |  |
| `seen_at` | DateTime(timezone=True) | yes |  |  |  |
| `history` | JSON | no |  | `list` |  |
| `created_at` | DateTime(timezone=True) | no |  | `utcnow` |  |
| `updated_at` | DateTime(timezone=True) | no |  | `utcnow` |  |

### `followup_tasks` (FollowupTask, `services/central/app/models/referrals.py`)

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `referral_id` | Integer | no | FK → referrals.id, indexed |  |  |
| `description` | Text | no |  |  |  |
| `specified_by` | String(200) | no |  |  |  |
| `assignee_name` | String(200) | yes |  |  |  |
| `due_date` | Date | yes |  |  |  |
| `status` | String(20) | no |  | `'open'` | open \| completed \| not_completed |
| `outcome` | Text | yes |  |  |  |
| `completed_by` | String(200) | yes |  |  |  |
| `completed_at` | DateTime(timezone=True) | yes |  |  |  |
| `created_by` | String(200) | no |  |  |  |
| `created_at` | DateTime(timezone=True) | no |  | `utcnow` |  |

### `inbound_messages` (InboundMessage, `services/central/app/models/referrals.py`)

Deduplicates incoming events from the institution services.

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `message_key` | String(200) | no | unique |  |  |
| `message_type` | String(40) | no |  |  |  |
| `referral_id` | Integer | yes | FK → referrals.id |  |  |
| `payload` | JSON | no |  |  |  |
| `received_at` | DateTime(timezone=True) | no |  | `utcnow` |  |

### `notifications` (Notification, `services/central/app/models/referrals.py`)

Something a person should act on or know about. Either addressed to one user, or to a role at an institution (for example the referral desk staff).

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `recipient_id` | String(64) | yes | indexed |  |  |
| `institution_id` | String(50) | no | indexed |  |  |
| `role` | String(40) | yes |  |  |  |
| `referral_id` | Integer | yes | FK → referrals.id |  |  |
| `kind` | String(40) | no |  |  |  |
| `title` | String(300) | no |  |  |  |
| `body` | Text | no |  | `''` |  |
| `link` | String(200) | yes |  |  |  |
| `created_at` | DateTime(timezone=True) | no | indexed | `utcnow` |  |
| `read_at` | DateTime(timezone=True) | yes |  |  |  |
| `read_by` | String(200) | yes |  |  |  |

### `outbox` (Outbox, `services/central/app/models/referrals.py`)

Written in the same transaction that decides to send; a worker delivers it.

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `referral_id` | Integer | no | FK → referrals.id, indexed |  |  |
| `kind` | String(40) | no |  |  | deliver_package \| deliver_order \| forward_result \| clarification_answer |
| `target_institution` | String(50) | no |  |  |  |
| `message_key` | String(200) | no | unique |  |  |
| `payload` | JSON | no |  |  |  |
| `status` | String(20) | no |  | `'pending'` | pending \| sent \| failed |
| `attempts` | Integer | no |  | `0` |  |
| `last_error` | Text | yes |  |  |  |
| `next_attempt_at` | DateTime(timezone=True) | no |  | `utcnow` |  |
| `created_at` | DateTime(timezone=True) | no |  | `utcnow` |  |
| `sent_at` | DateTime(timezone=True) | yes |  |  |  |
| `remote_result` | JSON | yes |  |  |  |

### `referral_events` (ReferralEvent, `services/central/app/models/referrals.py`)

Ordered timeline: status changes, deliveries and receiving-side activity.

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `referral_id` | Integer | no | FK → referrals.id, indexed |  |  |
| `event_type` | String(50) | no |  |  |  |
| `from_status` | String(30) | yes |  |  |  |
| `to_status` | String(30) | yes |  |  |  |
| `actor` | String(200) | no |  |  |  |
| `institution_id` | String(50) | yes |  |  |  |
| `detail` | JSON | no |  | `dict` |  |
| `created_at` | DateTime(timezone=True) | no |  | `utcnow` |  |

### `referral_packages` (ReferralPackage, `services/central/app/models/referrals.py`)

One sent version. Never updated after insert except the supersession marker.

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `referral_id` | Integer | no | FK → referrals.id, indexed |  |  |
| `version` | Integer | no |  |  |  |
| `brief_id` | Integer | no | FK → briefs.id |  |  |
| `envelope` | JSON | no |  |  |  |
| `content_hash` | String(64) | no |  |  |  |
| `delivery_key` | String(200) | no | unique |  |  |
| `sent_by` | String(200) | no |  |  |  |
| `sent_by_id` | String(64) | no |  |  |  |
| `sent_at` | DateTime(timezone=True) | no |  |  |  |
| `superseded` | Boolean | no |  | `False` |  |
| `manifest` | JSON | yes |  |  | Reference list of what the package contained (no clinical values); survives the content purge. |
| `content_purged_at` | DateTime(timezone=True) | yes |  |  |  |

Unique constraints: (referral_id, version)

### `referrals` (Referral, `services/central/app/models/referrals.py`)

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `reference` | String(30) | no | unique |  |  |
| `patient_institution` | String(50) | no | indexed |  | The patient as recorded at the referring institution |
| `patient_local_id` | String(50) | no | indexed |  |  |
| `patient_name` | String(200) | no |  |  |  |
| `patient_birth_date` | String(20) | yes |  |  |  |
| `patient_sex` | String(10) | yes |  |  |  |
| `patient_cnic` | String(15) | yes |  |  |  |
| `source_institution` | String(50) | no | indexed |  | Referring from |
| `source_department` | String(60) | yes |  |  |  |
| `requesting_doctor_id` | String(64) | yes | indexed |  |  |
| `requesting_doctor_name` | String(200) | no |  |  |  |
| `created_by_id` | String(64) | no |  |  |  |
| `created_by_name` | String(200) | no |  |  |  |
| `kind` | String(20) | no | indexed | `'referral'` | referral = to a doctor or department; test = a test or scan only (its orders carry the destinations) |
| `destination_institution` | String(50) | yes | indexed |  | Referring to (referrals only) |
| `destination_department` | String(60) | yes |  |  |  |
| `destination_doctor` | String(200) | yes |  |  |  |
| `reason` | Text | no |  | `''` | Clinical |
| `consultation_notes` | Text | no |  | `''` | the doctor's consultation notes under the reason: symptoms, history, examination (clinical content) |
| `urgency` | String(20) | no |  | `'routine'` |  |
| `procedure_status` | String(20) | no |  | `'unknown'` | planned \| none \| unknown |
| `planned_procedure` | String(300) | yes |  |  | in the doctor's words |
| `procedure_tags` | JSON | no |  | `list` | what the procedure involves |
| `status` | String(30) | no | indexed | `'draft'` | Workflow |
| `row_version` | Integer | no |  | `1` |  |
| `requested_at` | DateTime(timezone=True) | yes |  |  |  |
| `prepared_by` | String(200) | yes |  |  | Staff checkpoint: records, papers and medicines gathered; the doctor can now review the flags |
| `prepared_at` | DateTime(timezone=True) | yes |  |  |  |
| `packet_reviewed_by` | String(200) | yes |  |  | Doctor checkpoint: the doctor reviewed the records, papers, medicines and flags that go in the packet. Staff never see that content (decision 2026-10-29). A later clinical change clears it. |
| `packet_reviewed_at` | DateTime(timezone=True) | yes |  |  |  |
| `amendment_open` | Boolean | no |  | `False` |  |
| `current_package_version` | Integer | yes |  |  |  |
| `submitted_package_version` | Integer | yes |  |  |  |
| `delivery_status` | String(20) | no |  | `'none'` |  |
| `meds_checked_by` | String(200) | yes |  |  | Staff checkpoint: patient asked about all medicines, including over-the-counter ones |
| `meds_checked_at` | DateTime(timezone=True) | yes |  |  |  |
| `meds_checked_note` | Text | yes |  |  |  |
| `patient_informed_by` | String(200) | yes |  |  | Follow-through |
| `patient_informed_at` | DateTime(timezone=True) | yes |  |  |  |
| `patient_informed_note` | Text | yes |  |  |  |
| `cancel_reason` | Text | yes |  |  |  |
| `decline_reason` | Text | yes |  |  |  |
| `closed_at` | DateTime(timezone=True) | yes |  |  |  |
| `closed_by` | String(200) | yes |  |  |  |
| `acknowledged_at` | DateTime(timezone=True) | yes |  |  |  |
| `accepted_at` | DateTime(timezone=True) | yes |  |  |  |
| `working_set_expires_at` | DateTime(timezone=True) | yes | indexed |  | Temporary working set: retrieved records and everything derived from them are held only until working_set_expires_at, then their clinical content is removed (identifiers, status, audit, manifest and fingerprint stay). See lifecycle/working_set.py. |
| `working_set_purged_at` | DateTime(timezone=True) | yes |  |  |  |
| `receiver_completed_at` | DateTime(timezone=True) | yes |  |  | the specialist closed the referral (spec v4 step 11): purged after the grace period |
| `receiver_completed_by` | String(200) | yes |  |  |  |
| `close_reminder_due_at` | DateTime(timezone=True) | yes | indexed |  | spec v4 7: the close reminder (30 days after acceptance, or the end of an extension), weekly repeats, escalation to the receiving department's staff; never a silent auto-close |
| `reminders_sent` | Integer | no |  | `0` |  |
| `last_reminder_at` | DateTime(timezone=True) | yes |  |  |  |
| `escalated_at` | DateTime(timezone=True) | yes |  |  |  |
| `created_at` | DateTime(timezone=True) | no | indexed | `utcnow` |  |
| `updated_at` | DateTime(timezone=True) | no |  | `utcnow` |  |
