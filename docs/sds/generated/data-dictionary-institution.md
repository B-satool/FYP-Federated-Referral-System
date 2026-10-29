## Data dictionary: Institution service database (one per institution: `drali_db`, `chughtai_db`, `ziauddin_db`, `akuh_db`)

### `audit_events` (AuditEvent, `services/provider/app/models.py`)

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  | (from AuditMixin) |
| `actor_id` | String(100) | no |  |  | (from AuditMixin) |
| `actor_name` | String(200) | no |  |  | (from AuditMixin) |
| `institution_id` | String(50) | yes |  |  | (from AuditMixin) |
| `action` | String(100) | no | indexed |  | (from AuditMixin) |
| `target_type` | String(60) | no |  |  | (from AuditMixin) |
| `target_id` | String(100) | no |  |  | (from AuditMixin) |
| `outcome` | String(20) | no |  |  | (from AuditMixin) |
| `referral_context` | String(60) | yes |  |  | (from AuditMixin) |
| `detail` | JSON | no |  | `dict` | (from AuditMixin) |
| `created_at` | DateTime(timezone=True) | no | indexed | `utcnow` | (from AuditMixin) |

### `cases` (Case, `services/provider/app/models.py`)

One referral received by this institution, across all sent versions.

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `central_referral_id` | String(40) | no | unique |  |  |
| `sender_institution` | String(50) | no |  |  |  |
| `sender_name` | String(200) | no |  |  |  |
| `department` | String(60) | no | indexed |  |  |
| `requested_doctor` | String(200) | yes |  |  |  |
| `patient_name` | String(200) | no |  |  |  |
| `patient_birth_date` | String(20) | yes |  |  |  |
| `patient_sex` | String(10) | yes |  |  |  |
| `patient_cnic` | String(15) | yes |  |  |  |
| `local_patient_id` | String(30) | yes |  |  | set once staff here confirm the patient (match a record or register them as new) |
| `link_request_id` | Integer | yes |  |  | the central intake link request |
| `urgency` | String(20) | no |  |  |  |
| `status` | String(30) | no |  | `'received'` | received -> acknowledged (staff) -> assigned (staff) -> accepted \| declined (doctor) -> responded -> completed |
| `latest_version` | Integer | no |  |  |  |
| `assigned_doctor` | String(200) | yes |  |  |  |
| `assigned_by` | String(200) | yes |  |  |  |
| `assigned_at` | DateTime(timezone=True) | yes |  |  |  |
| `assign_note` | Text | yes |  |  |  |
| `acknowledged_by` | String(200) | yes |  |  |  |
| `acknowledged_at` | DateTime(timezone=True) | yes |  |  |  |
| `decision` | String(20) | yes |  |  |  |
| `decision_by` | String(200) | yes |  |  |  |
| `decision_at` | DateTime(timezone=True) | yes |  |  |  |
| `decline_reason` | Text | yes |  |  |  |
| `completed_by` | String(200) | yes |  |  | the referred doctor has finished with it; the shared records are then removed after 72 hours |
| `completed_at` | DateTime(timezone=True) | yes |  |  |  |
| `hold_until` | DateTime(timezone=True) | yes |  |  | until when the shared records are kept (mirrors the platform: 30 days after acceptance, extendable) |
| `shared_removed_at` | DateTime(timezone=True) | yes |  |  | when the shared records (packages, forwarded results) were removed here; this institution's own decision, questions and response are kept |
| `received_at` | DateTime(timezone=True) | no |  | `utcnow` |  |
| `updated_at` | DateTime(timezone=True) | no |  | `utcnow` |  |

### `conditions` (Condition, `services/provider/app/models.py`)

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | String(40) | no | PK |  |  |
| `patient_id` | String | no | FK → patients.local_id, indexed |  |  |
| `display` | String(300) | no |  |  |  |
| `snomed` | String(30) | yes |  |  |  |
| `clinical_status` | String(20) | no |  |  |  |
| `onset` | String(10) | yes |  |  | as recorded: YYYY, YYYY-MM or YYYY-MM-DD |
| `sensitive_category` | String(40) | yes |  |  | the category this institution marks sensitive (psychiatric \| hiv_sexual_health \| ...), released only with the patient's specific consent (spec v4 4.2, 6.2) |
| `version` | Integer | no |  | `1` | (from Versioned) |
| `updated_at` | DateTime(timezone=True) | no |  | `utcnow` | (from Versioned) |

### `consultation_responses` (ConsultationResponse, `services/provider/app/models.py`)

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `case_id` | Integer | no | FK → cases.id, indexed |  |  |
| `package_version` | Integer | no |  |  |  |
| `content` | JSON | no |  |  |  |
| `status` | String(20) | no |  | `'draft'` | draft \| returned |
| `drafted_by` | String(200) | no |  |  |  |
| `drafted_at` | DateTime(timezone=True) | no |  | `utcnow` |  |
| `row_version` | Integer | no |  | `1` |  |
| `returned_by` | String(200) | yes |  |  |  |
| `returned_by_id` | String(100) | yes |  |  |  |
| `returned_at` | DateTime(timezone=True) | yes |  |  |  |
| `return_key` | String(200) | yes | unique |  |  |

### `doctor_keys` (DoctorKey, `services/provider/app/models.py`)

A doctor's public keys, signed by this hospital once it accepts them (spec v4 5.4). The doctor's private keys stay on the doctor's device.

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `subject_id` | String(64) | no | indexed |  |  |
| `username` | String(100) | no |  |  |  |
| `display_name` | String(200) | no |  |  |  |
| `department` | String(60) | yes | indexed |  |  |
| `enc_key_id` | String(16) | no | indexed |  |  |
| `key_version` | Integer | no |  |  |  |
| `request` | JSON | no |  |  | the doctor's signed registration (proof of possession) |
| `entry` | JSON | yes |  |  | the hospital-signed directory entry |
| `status` | String(20) | no | indexed | `'pending'` | pending (waits for an administrator) \| active \| revoked \| rejected |
| `recovery` | Boolean | no |  | `False` | replaces a key the doctor lost |
| `approved_by` | String(200) | yes |  |  |  |
| `revocation` | JSON | yes |  |  |  |
| `revoked_by` | String(200) | yes |  |  |  |
| `revoked_at` | DateTime(timezone=True) | yes |  |  |  |
| `published_at` | DateTime(timezone=True) | yes |  |  |  |
| `created_at` | DateTime(timezone=True) | no |  | `utcnow` |  |

### `forwarded_results` (ForwardedResult, `services/provider/app/models.py`)

A diagnostic report from another department or institution, attached to a case.

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `forward_key` | String(200) | no | unique |  |  |
| `case_id` | Integer | no | FK → cases.id, indexed |  |  |
| `content` | JSON | no |  |  |  |
| `received_at` | DateTime(timezone=True) | no |  | `utcnow` |  |

### `group_key_wraps` (GroupKeyWrap, `services/provider/app/models.py`)

A department group private key, wrapped to one member doctor's encryption key (ciphertext only).

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `department` | String(60) | no | indexed |  |  |
| `group_version` | Integer | no |  |  |  |
| `member_subject_id` | String(64) | no | indexed |  |  |
| `member_key_id` | String(16) | no |  |  |  |
| `wrapped` | JSON | no |  |  |  |
| `published_at` | DateTime(timezone=True) | yes |  |  |  |
| `created_at` | DateTime(timezone=True) | no |  | `utcnow` |  |

Unique constraints: (department, group_version, member_key_id)

### `imaging_reports` (ImagingReport, `services/provider/app/models.py`)

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | String(40) | no | PK |  |  |
| `patient_id` | String | no | FK → patients.local_id, indexed |  |  |
| `study_date` | Date | no | indexed |  |  |
| `study` | String(200) | no |  |  |  |
| `body_part` | String(100) | yes |  |  |  |
| `findings` | Text | no |  | `''` |  |
| `impression` | Text | no |  | `''` |  |
| `reporter` | String(200) | yes |  |  |  |
| `sensitive_category` | String(40) | yes |  |  | the category this institution marks sensitive (psychiatric \| hiv_sexual_health \| ...), released only with the patient's specific consent (spec v4 4.2, 6.2) |
| `version` | Integer | no |  | `1` | (from Versioned) |
| `updated_at` | DateTime(timezone=True) | no |  | `utcnow` | (from Versioned) |

### `incoming_packages` (IncomingPackage, `services/provider/app/models.py`)

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `case_id` | Integer | no | FK → cases.id, indexed |  |  |
| `version` | Integer | no |  |  |  |
| `delivery_key` | String(200) | no | unique |  |  |
| `envelope` | JSON | no |  |  |  |
| `content_hash` | String(64) | no |  |  |  |
| `received_at` | DateTime(timezone=True) | no |  | `utcnow` |  |

Unique constraints: (case_id, version)

### `info_requests` (InfoRequest, `services/provider/app/models.py`)

'Ask for more information' from the receiving doctor to the referring clinic.

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `case_id` | Integer | no | FK → cases.id, indexed |  |  |
| `package_version` | Integer | no |  |  |  |
| `question` | Text | no |  |  |  |
| `status` | String(20) | no |  | `'open'` | open \| answered |
| `created_by` | String(200) | no |  |  |  |
| `created_at` | DateTime(timezone=True) | no |  | `utcnow` |  |
| `answer` | Text | yes |  |  |  |
| `answered_by` | String(200) | yes |  |  |  |
| `answered_at` | DateTime(timezone=True) | yes |  |  |  |
| `answer_key` | String(200) | yes | unique |  |  |

### `key_store` (KeyStore, `services/provider/app/models.py`)

This institution's own private keys: the hospital signing key and each department's group key. The private part is sealed with the service's key-store secret (AES-256-GCM); it never leaves this service.

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `purpose` | String(80) | no | indexed |  | hospital_signing \| group:<department> |
| `version` | Integer | no |  | `1` |  |
| `public_spki` | Text | no |  |  |  |
| `private_sealed` | JSON | no |  |  |  |
| `entry` | JSON | yes |  |  | the signed directory entry for a department group key (published to the platform) |
| `published_at` | DateTime(timezone=True) | yes |  |  |  |
| `created_at` | DateTime(timezone=True) | no |  | `utcnow` |  |
| `retired_at` | DateTime(timezone=True) | yes |  |  |  |

Unique constraints: (purpose, version)

### `lab_results` (LabResult, `services/provider/app/models.py`)

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | String(40) | no | PK |  |  |
| `patient_id` | String | no | FK → patients.local_id, indexed |  |  |
| `panel` | String(200) | no |  |  |  |
| `collected` | Date | no | indexed |  |  |
| `test` | String(120) | no |  |  |  |
| `loinc` | String(20) | yes |  |  |  |
| `value_num` | Float | yes |  |  |  |
| `value_text` | String(200) | yes |  |  |  |
| `unit` | String(40) | yes |  |  |  |
| `reference_range` | String(60) | yes |  |  |  |
| `abnormal_flag` | String(20) | yes |  |  |  |
| `sensitive_category` | String(40) | yes |  |  | the category this institution marks sensitive (psychiatric \| hiv_sexual_health \| ...), released only with the patient's specific consent (spec v4 4.2, 6.2) |
| `status` | String(20) | no |  | `'final'` |  |
| `note` | Text | yes |  |  |  |
| `version` | Integer | no |  | `1` | (from Versioned) |
| `updated_at` | DateTime(timezone=True) | no |  | `utcnow` | (from Versioned) |

### `medications` (Medication, `services/provider/app/models.py`)

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | String(40) | no | PK |  |  |
| `patient_id` | String | no | FK → patients.local_id, indexed |  |  |
| `name` | String(200) | no |  |  |  |
| `brand_as_written` | String(100) | yes |  |  |  |
| `dose` | String(100) | yes |  |  |  |
| `route` | String(40) | yes |  |  |  |
| `frequency` | String(100) | yes |  |  |  |
| `start_date` | Date | yes |  |  |  |
| `status` | String(20) | no |  |  | active \| stopped \| completed |
| `prescriber` | String(200) | yes |  |  |  |
| `note` | Text | yes |  |  |  |
| `sensitive_category` | String(40) | yes |  |  | the category this institution marks sensitive (psychiatric \| hiv_sexual_health \| ...), released only with the patient's specific consent (spec v4 4.2, 6.2) |
| `version` | Integer | no |  | `1` | (from Versioned) |
| `updated_at` | DateTime(timezone=True) | no |  | `utcnow` | (from Versioned) |

### `order_attachments` (OrderAttachment, `services/provider/app/models.py`)

An image or file returned with a report (scan images, ECG trace, report PDF).

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `order_id` | Integer | no | FK → orders.id, indexed |  |  |
| `filename` | String(200) | no |  |  |  |
| `content_type` | String(100) | no |  |  |  |
| `data` | LargeBinary | no |  |  |  |
| `uploaded_by` | String(200) | no |  |  |  |
| `created_at` | DateTime(timezone=True) | no |  | `utcnow` |  |

### `orders` (Order, `services/provider/app/models.py`)

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `order_key` | String(200) | no | unique |  |  |
| `order_ref` | String(40) | no | indexed |  |  |
| `central_referral_id` | String(40) | no |  |  |  |
| `sender_institution` | String(50) | no |  |  |  |
| `sender_name` | String(200) | no |  |  |  |
| `department` | String(60) | no | indexed |  |  |
| `category` | String(20) | no |  |  |  |
| `test` | String(200) | no |  |  |  |
| `body_area` | String(100) | yes |  |  |  |
| `clinical_question` | Text | no |  |  |  |
| `urgency` | String(20) | no |  |  |  |
| `patient_name` | String(200) | no |  |  |  |
| `patient_birth_date` | String(20) | yes |  |  |  |
| `patient_sex` | String(10) | yes |  |  |  |
| `patient_cnic` | String(15) | yes |  |  |  |
| `local_patient_id` | String(30) | yes |  |  |  |
| `link_request_id` | Integer | yes |  |  |  |
| `requested_by` | String(200) | no |  |  |  |
| `status` | String(20) | no |  | `'requested'` | requested \| accepted \| rejected \| scheduled \| done \| reported |
| `reject_reason` | Text | yes |  |  |  |
| `scheduled_for` | DateTime(timezone=True) | yes |  |  |  |
| `report_text` | Text | yes |  |  |  |
| `findings` | Text | yes |  |  |  |
| `impression` | Text | yes |  |  |  |
| `values` | JSON | no |  | `list` |  |
| `reported_by` | String(200) | yes |  |  |  |
| `reported_at` | DateTime(timezone=True) | yes |  |  |  |
| `history` | JSON | no |  | `list` |  |
| `received_at` | DateTime(timezone=True) | no |  | `utcnow` |  |
| `updated_at` | DateTime(timezone=True) | no |  | `utcnow` |  |

### `outbox` (Outbox, `services/provider/app/models.py`)

Events for the central platform, written in the same transaction as the change.

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `event_key` | String(200) | no | unique |  |  |
| `event_type` | String(40) | no |  |  |  |
| `case_id` | Integer | yes | FK → cases.id, indexed |  |  |
| `order_id` | Integer | yes | FK → orders.id, indexed |  |  |
| `payload` | JSON | no |  |  |  |
| `status` | String(20) | no |  | `'pending'` |  |
| `attempts` | Integer | no |  | `0` |  |
| `last_error` | Text | yes |  |  |  |
| `next_attempt_at` | DateTime(timezone=True) | no |  | `utcnow` |  |
| `created_at` | DateTime(timezone=True) | no |  | `utcnow` |  |
| `sent_at` | DateTime(timezone=True) | yes |  |  |  |

### `patients` (Patient, `services/provider/app/models.py`)

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `local_id` | String(30) | no | PK |  |  |
| `cnic` | String(15) | yes | indexed |  | 13 digits, no dashes |
| `given` | String(100) | no |  |  |  |
| `family` | String(100) | no |  |  |  |
| `birth_date` | Date | no |  |  |  |
| `sex` | String(10) | no |  |  |  |
| `phone` | String(30) | yes |  |  |  |
| `city` | String(60) | yes |  |  |  |
| `registered_by` | String(200) | yes |  |  |  |
| `synthetic` | Boolean | no |  | `True` |  |
| `version` | Integer | no |  | `1` | (from Versioned) |
| `updated_at` | DateTime(timezone=True) | no |  | `utcnow` | (from Versioned) |

### `record_requests` (RecordRequest, `services/provider/app/models.py`)

A request from the platform for a referral's records, checked against the patient's consent and this institution's own policy. Answered at once, refused with a reason code, or queued for this institution's staff (pending_manual_review). Only the decision and counts are kept here; the records stay in their own tables.

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `request_key` | String(200) | no | unique |  |  |
| `referral_ref` | String(40) | no | indexed |  |  |
| `requesting_org` | String(50) | no |  |  |  |
| `practitioner_id` | String(64) | no |  |  |  |
| `practitioner_name` | String(200) | yes |  |  |  |
| `purpose` | String(20) | no |  |  |  |
| `consent_ref` | String(60) | no |  |  |  |
| `local_patient_id` | String(50) | yes |  |  |  |
| `categories` | JSON | no |  | `list` |  |
| `since` | String(20) | yes |  |  |  |
| `reason_text` | Text | yes |  |  | the referral reason (administrative) |
| `sensitive` | JSON | no |  | `list` | sensitive categories the request asks for |
| `practitioner_entry` | JSON | yes |  |  | the requesting doctor's signed key |
| `patient_entry` | JSON | yes |  |  | the patient's platform-signed key |
| `status` | String(30) | no | indexed |  | answered \| partial \| refused \| pending_manual_review \| declined |
| `refusals` | JSON | no |  | `list` |  |
| `policy_version` | String(40) | no |  |  |  |
| `item_count` | Integer | no |  | `0` |  |
| `decided_by` | String(200) | yes |  |  |  |
| `decided_at` | DateTime(timezone=True) | yes |  |  |  |
| `delivered_at` | DateTime(timezone=True) | yes |  |  |  |
| `delivery_error` | Text | yes |  |  |  |
| `created_at` | DateTime(timezone=True) | no |  | `utcnow` |  |

### `seen_assertions` (SeenAssertion, `services/provider/app/models.py`)

Request assertions already accepted (jti), kept until they expire, so a replay is refused.

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `jti` | String(80) | no | PK |  |  |
| `issuer` | String(50) | no |  |  |  |
| `expires_at` | DateTime(timezone=True) | no | indexed |  |  |

### `sent_copies` (SentCopy, `services/provider/app/models.py`)

This institution's own copy of a referral it sent (and the response it received). Delivered by the central platform, whose working copy is temporary; this copy is the sender's lasting record.

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `copy_key` | String(220) | no | unique |  |  |
| `central_referral_id` | String(40) | no | indexed |  |  |
| `kind` | String(20) | no |  |  | package \| response |
| `version` | Integer | no |  | `0` |  |
| `content` | JSON | no |  |  |  |
| `received_at` | DateTime(timezone=True) | no |  | `utcnow` |  |

### `surgeries` (Surgery, `services/provider/app/models.py`)

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | String(40) | no | PK |  |  |
| `patient_id` | String | no | FK → patients.local_id, indexed |  |  |
| `procedure` | String(300) | no |  |  |  |
| `performed` | String(10) | yes |  |  |  |
| `location` | String(200) | yes |  |  |  |
| `version` | Integer | no |  | `1` | (from Versioned) |
| `updated_at` | DateTime(timezone=True) | no |  | `utcnow` | (from Versioned) |

### `visits` (Visit, `services/provider/app/models.py`)

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | String(40) | no | PK |  |  |
| `patient_id` | String | no | FK → patients.local_id, indexed |  |  |
| `visit_date` | Date | no | indexed |  |  |
| `setting` | String(200) | no |  |  |  |
| `clinician` | String(200) | yes |  |  |  |
| `reason` | Text | no |  | `''` |  |
| `summary` | Text | no |  | `''` |  |
| `sensitive_category` | String(40) | yes |  |  | the category this institution marks sensitive (psychiatric \| hiv_sexual_health \| ...), released only with the patient's specific consent (spec v4 4.2, 6.2) |
| `version` | Integer | no |  | `1` | (from Versioned) |
| `updated_at` | DateTime(timezone=True) | no |  | `utcnow` | (from Versioned) |
