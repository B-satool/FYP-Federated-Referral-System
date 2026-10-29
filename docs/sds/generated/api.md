## API inventory

Generated from the FastAPI route decorators. *Access checks* lists the authorisation calls made inside each handler (roles, institution scope, service identity, optimistic-concurrency checks). Every endpoint except `/health` and `/ready` also requires a valid Keycloak access token (verified signature, issuer, audience and introspection). Parameters exclude the database session and the caller's identity.

### Central platform API (`central`, port 8000): 122 endpoints

#### AI relay (de-identified, on request)

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| POST | `/ai/relay/flags` | Layer 2: generic names and the procedure only. Adds suggestions; it can never remove or change a Layer 1 flag (those are computed on the device and never sent back). | _referral_for → load_referral() | body: FlagsIn | relay_flags (services/central/app/ai_relay.py:249) |
| POST | `/ai/relay/selection` | Relay selection. | _referral_for → load_referral() | body: SelectionIn | relay_selection (services/central/app/ai_relay.py:130) |

#### audit and reference data

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| GET | `/admin/audit` | Administrators see audit metadata for their institution (no clinical record content). | require_roles(institution_admin, action=admin.audit) | action: str \| None; outcome: str \| None; limit: int | institution_audit (services/central/app/audit_router.py:52) |
| GET | `/admin/audit/chain` | Recompute the audit trail's hash chain (spec v4 11.5): sealed and unsealed counts and the first break, if any. | require_roles(institution_admin, action=admin.audit_chain) |  | audit_chain (services/central/app/audit_router.py:74) |
| GET | `/me` | Me. | valid access token (any role) |  | me (services/central/app/audit_router.py:83) |
| GET | `/reference-data` | Reference data. | valid access token (any role) |  | reference_data (services/central/app/audit_router.py:97) |
| GET | `/referrals/{referral_id}/audit` | Referral audit. | load_referral(view_audit) | referral_id: int | referral_audit (services/central/app/audit_router.py:45) |

#### consent

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| GET | `/e2e/adapter/consents/{reference}` | The signed consent behind a request, for the institution to check itself. Only a custodian named by the patient may read it. | public (no token) | reference: str | adapter_consent (services/central/app/consent/router.py:233) |
| GET | `/patient-access/consents` | My consents. | valid access token (any role) |  | my_consents (services/central/app/consent/router.py:131) |
| POST | `/patient-access/consents/{reference}/decision` | Decide consent. | valid access token (any role) | reference: str; body: DecisionIn | decide_consent (services/central/app/consent/router.py:173) |
| POST | `/patient-access/consents/{reference}/prepare` | The exact document for the patient's choices, for the patient's device to show and sign. | valid access token (any role) | reference: str; body: PrepareIn | prepare_consent (services/central/app/consent/router.py:150) |
| POST | `/patient-access/consents/{reference}/revoke` | Future requests are refused. Records a doctor already opened cannot be recalled (stated in the portal). | valid access token (any role) | reference: str; body: RevokeIn | revoke_consent (services/central/app/consent/router.py:211) |
| GET | `/referrals/{referral_id}/consents` | Referral consents. | load_referral(view, roles=['clinic_staff', 'clinician']) | referral_id: int | referral_consents (services/central/app/consent/router.py:108) |
| POST | `/referrals/{referral_id}/consents` | Staff ask the patient (through the patient portal) for permission to fetch records for this referral. | load_referral(consent_request, roles=('clinic_staff',)) | referral_id: int; body: ConsentRequestIn | request_consent (services/central/app/consent/router.py:75) |

#### documents

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| GET | `/documents/{document_id}` | Get document. | _load_doc → load_referral() | document_id: int | get_document (services/central/app/documents/router.py:120) |
| GET | `/documents/{document_id}/file` | Download. | _load_doc → load_referral() | document_id: int | download (services/central/app/documents/router.py:139) |
| GET | `/documents/{document_id}/pages/{page}` | Page image. | _load_doc → load_referral() | document_id: int; page: int | page_image (services/central/app/documents/router.py:151) |
| POST | `/documents/{document_id}/reprocess` | Reprocess. | _load_doc → load_referral() | document_id: int | reprocess (services/central/app/documents/router.py:161) |
| GET | `/jobs/{job_id}` | Get job. | load_referral(view) | job_id: str | get_job (services/central/app/documents/router.py:174) |
| GET | `/referrals/{referral_id}/documents` | List documents. | load_referral(view) | referral_id: int | list_documents (services/central/app/documents/router.py:103) |
| POST | `/referrals/{referral_id}/documents` | Upload. | ensure_clinical_edit_allowed(); load_referral(upload, roles=('clinician',)) | referral_id: int; file: UploadFile; doc_type: str | upload (services/central/app/documents/router.py:47) |
| GET | `/referrals/{referral_id}/jobs` | Referral jobs. | load_referral(view) | referral_id: int | referral_jobs (services/central/app/documents/router.py:186) |

#### end-to-end keys

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| GET | `/.well-known/jwks.json` | The platform's public signing key, pinned by every adapter at onboarding. | public (no token) |  | jwks (services/central/app/keys/router.py:39) |
| POST | `/e2e/adapter/directory` | Receive directory. | public (no token) | body: DirectoryBatch | receive_directory (services/central/app/keys/router.py:63) |
| POST | `/e2e/client-events` | Events only a client can see: a directory signature that failed in the browser, which items a doctor opened (decrypted). Best effort: a modified client could skip them (stated in docs/security-model.md). The detail must hold ids, counts and reason codes only; text values are cut short and never content. | valid access token (any role) | body: ClientEventIn | client_event (services/central/app/keys/router.py:271) |
| GET | `/e2e/directory` | Directory. | has_any(patient) | subject_id: str \| None; hospital_id: str \| None; department: str \| None; subject_type: str \| None; include_revoked: bool | directory (services/central/app/keys/router.py:131) |
| GET | `/e2e/directory/departments/{hospital_id}/{department}` | Department entries. | valid access token (any role) | hospital_id: str; department: str | department_entries (services/central/app/keys/router.py:181) |
| GET | `/e2e/directory/me` | The caller's own entries, and the department group keys wrapped to their current key. | has_any(patient) |  | my_directory (services/central/app/keys/router.py:167) |
| GET | `/e2e/participants` | Onboarded institutions as pinned at this installation (for display; clients use their own pinned copy). | valid access token (any role) |  | participants (services/central/app/keys/router.py:47) |
| POST | `/e2e/patient-keys` | A patient's keys, generated on the patient's device. The platform signs the entry for the signed-in patient (CNIC from the verified token) and revokes the patient's earlier key. | valid access token (any role) | body: PatientKeyIn | register_patient_key (services/central/app/keys/router.py:200) |

#### evidence

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| GET | `/evidence/{evidence_id}` | Get evidence. | _load → load_referral() | evidence_id: int | get_evidence (services/central/app/evidence_router.py:79) |
| POST | `/evidence/{evidence_id}/correct` | Correct. | _load → load_referral() | evidence_id: int; body: CorrectIn | correct (services/central/app/evidence_router.py:131) |
| POST | `/evidence/{evidence_id}/exclude` | Exclude. | _set_state → _load → load_referral() | evidence_id: int; body: StateIn | exclude (services/central/app/evidence_router.py:183) |
| POST | `/evidence/{evidence_id}/restore` | Restore. | _set_state → _load → load_referral() | evidence_id: int; body: StateIn | restore (services/central/app/evidence_router.py:188) |
| POST | `/evidence/{evidence_id}/select` | The doctor finalises the packet: their choice overrides the default and the AI recommendation. | _load → load_referral(); ensure_clinical_edit_allowed() | evidence_id: int; body: SelectIn | select_evidence (services/central/app/evidence_router.py:106) |
| POST | `/evidence/{evidence_id}/unresolve` | Mark unresolved. | _set_state → _load → load_referral() | evidence_id: int; body: StateIn | mark_unresolved (services/central/app/evidence_router.py:178) |
| POST | `/evidence/{evidence_id}/verify` | The doctor checks a field read from a paper against the page image; a checked medicine joins the current-medicine list. | _load → load_referral() | evidence_id: int; body: VerifyIn | verify (services/central/app/evidence_router.py:198) |
| GET | `/referrals/{referral_id}/evidence` | List evidence. | load_referral(view) | referral_id: int; category: str \| None; include_superseded: bool | list_evidence (services/central/app/evidence_router.py:66) |
| POST | `/referrals/{referral_id}/evidence/manual` | Manual transcription by the doctor, with an optional source reference; works without OCR (FR-58). | ensure_clinical_edit_allowed(); load_referral(edit, roles=('clinician',)) | referral_id: int; body: ManualIn | manual_entry (services/central/app/evidence_router.py:225) |

#### health

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| GET | `/health` | Health. | public (no token) |  | health (services/central/app/main.py:49) |
| GET | `/ready` | Ready. | public (no token) |  | ready (services/central/app/main.py:54) |

#### inbound (institution services)

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| POST | `/inbound/provider-events` | Provider event. | require_service(svc_provider) | body: ProviderEvent | provider_event (services/central/app/delivery/inbound.py:28) |

#### medication data bundle

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| GET | `/med-bundle` | The current bundle; clients keep it until the version changes. | valid access token (any role) | response: Response | med_bundle (services/central/app/medications/bundle.py:61) |

#### medications

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| GET | `/drug-classes` | Drug classes. | valid access token (any role) |  | drug_classes (services/central/app/medications/router.py:523) |
| GET | `/medicine-names` | Medicine names. | role rule_reviewer required | q: str | medicine_names (services/central/app/medications/router.py:300) |
| POST | `/medicine-names` | Add name. | require_roles(rule_reviewer, action=medicine_name.add) | body: NameIn | add_name (services/central/app/medications/router.py:321) |
| POST | `/medicine-names/{name_id}/retire` | Retire name. | require_roles(rule_reviewer, action=medicine_name.retire) | name_id: int | retire_name (services/central/app/medications/router.py:341) |
| POST | `/referrals/{referral_id}/ai-suggestions/review` | The doctor marks an AI suggestion Ignore (not relevant for this patient) or Research (needs follow-up). It changes no flag. | load_referral(review_ai_suggestion, roles=('clinician',)) | referral_id: int; body: SuggestionReviewIn | review_suggestion (services/central/app/medications/router.py:79) |
| POST | `/referrals/{referral_id}/flags/{flag_id}/acknowledge` | The doctor records a decision on the flag for this patient: reviewed, ignore or research. Any decision means 'seen'; it is never treatment clearance. Ignored flags stay in the record. | load_referral(acknowledge_flag, roles=('clinician',)) | referral_id: int; flag_id: int; body: AckIn | acknowledge_flag (services/central/app/medications/router.py:273) |
| GET | `/referrals/{referral_id}/medications` | Medications. | load_referral(view) | referral_id: int | medications (services/central/app/medications/router.py:33) |
| POST | `/referrals/{referral_id}/medications/checked` | Staff confirm they asked the patient about every medicine, including over-the-counter ones. | ensure_clinical_edit_allowed(); load_referral(edit, roles=('clinician',)) | referral_id: int; body: CheckedIn | medicines_checked (services/central/app/medications/router.py:254) |
| POST | `/referrals/{referral_id}/medications/manual` | Staff add a medicine the patient says they take, e.g. an over-the-counter painkiller. | ensure_clinical_edit_allowed(); load_referral(edit, roles=('clinician',)) | referral_id: int; body: ManualMedIn | add_medicine (services/central/app/medications/router.py:121) |
| POST | `/referrals/{referral_id}/medications/{entry_id}/exclude` | Staff mark a recorded medicine as not current (e.g. an old prescription, or the other side of a dose difference). The record is kept, with who and why. | ensure_clinical_edit_allowed(); load_referral(edit, roles=('clinician',)) | referral_id: int; entry_id: int; body: ReasonIn | exclude_medicine (services/central/app/medications/router.py:163) |
| POST | `/referrals/{referral_id}/medications/{entry_id}/mapping` | Doctor or staff resolve a name: choose a medicine from the name list, or, for a DRAP brand name used for different products, the product it is (by the company on the pack). | ensure_clinical_edit_allowed(); load_referral(map_medication, roles=('clinician',)) | referral_id: int; entry_id: int; body: MapIn | set_mapping (services/central/app/medications/router.py:215) |
| POST | `/referrals/{referral_id}/medications/{entry_id}/restore` | Restore medicine. | ensure_clinical_edit_allowed(); load_referral(edit, roles=('clinician',)) | referral_id: int; entry_id: int | restore_medicine (services/central/app/medications/router.py:181) |
| GET | `/rules` | List rules. | require_roles(rule_reviewer, action=rule.list); role rule_reviewer required |  | list_rules (services/central/app/medications/router.py:367) |
| POST | `/rules` | Reviewers draft a rule. It does nothing until a reviewer approves it. | require_roles(rule_reviewer, action=rule.create) | body: RuleIn | create_rule (services/central/app/medications/router.py:413) |
| GET | `/rules/ai` | The suggestion model's evaluation figures and its stored suggestions (reviewer only). | require_roles(rule_reviewer, action=rule.list) |  | ai_model (services/central/app/medications/router.py:96) |
| GET | `/rules/interactions` | Imported drug-drug interactions (read-only), searchable by ingredient. | require_roles(rule_reviewer, action=rule.list) | q: str | list_interactions (services/central/app/medications/router.py:491) |
| GET | `/rules/label-rules` | Rules read from drug labels by script (read-only), with the sentence each relies on. | require_roles(rule_reviewer, action=rule.list) | q: str; kind: str | list_label_rules (services/central/app/medications/router.py:502) |
| PUT | `/rules/{rule_id}` | An edit is a new draft version; the approved version keeps working until the new one is approved. | require_roles(rule_reviewer, action=rule.edit) | rule_id: str; body: RuleIn | edit_rule (services/central/app/medications/router.py:428) |
| POST | `/rules/{rule_id}/versions/{version}/decision` | Only a clinical rule reviewer may approve, reject or retire a rule version. | require_roles(rule_reviewer, action=rule.decision) | rule_id: str; version: int; body: RuleDecisionIn | decide_rule (services/central/app/medications/router.py:446) |

#### notifications

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| GET | `/notifications` | List notifications. | _mine() | unread_only: bool | list_notifications (services/central/app/notifications.py:65) |
| POST | `/notifications/read-all` | Mark all read. | _mine() |  | mark_all_read (services/central/app/notifications.py:84) |
| POST | `/notifications/{notification_id}/read` | Mark read. | _mine() | notification_id: int | mark_read (services/central/app/notifications.py:73) |

#### patient access

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| GET | `/patient-access/places` | The institutions on the network. The patient's device asks each one directly whether it holds records for them; the platform does not keep that list. | require_patient → deny(patient, self, Only a patient account can use the patient view); require_patient → deny(patient, self, This patient account has no CNIC, so nothing can be matched to it); require_patient → role patient required |  | places (services/central/app/patient_access.py:220) |
| GET | `/patient-access/referrals` | Every referral and test request for this patient, at any institution, newest first. Drafts the doctor has not submitted are left out. | require_patient → deny(patient, self, Only a patient account can use the patient view); require_patient → deny(patient, self, This patient account has no CNIC, so nothing can be matched to it); require_patient → role patient required |  | my_referrals (services/central/app/patient_access.py:114) |
| GET | `/patient-access/referrals/{reference}/copy` | The patient's own copy (spec v4 11.3): the signed manifest, the items, and the data keys wrapped to the patient's key. The app decrypts it on the phone, checks it against the signature and keeps it there, even after the referral is purged here. Items the doctor did not share with the patient have no wrap for them. | _own_referral → deny(referral, Not your referral); _own_referral → require_patient → deny(patient, self, Only a patient account can use the patient view); _own_referral → require_patient → deny(patient, self, This patient account has no CNIC, so nothing can be matched to it); _own_referral → require_patient → role patient required | reference: str | my_copy (services/central/app/patient_access.py:144) |
| POST | `/patient-access/referrals/{reference}/papers` | Papers the patient adds in the app (spec v4 step 2, 10): encrypted on the phone to the referring doctor's key and the patient's own key. The platform checks only the shape; staff see "Patient-provided document" and a date. | _own_referral → deny(referral, Not your referral); _own_referral → require_patient → deny(patient, self, Only a patient account can use the patient view); _own_referral → require_patient → deny(patient, self, This patient account has no CNIC, so nothing can be matched to it); _own_referral → require_patient → role patient required | reference: str; body: PatientBatchIn | add_papers (services/central/app/patient_access.py:169) |

#### patient links

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| GET | `/admin/role-templates` | Templates this institution's administrator may apply. | require_roles(institution_admin, action=admin.role_templates) |  | list_role_templates (services/central/app/identity/router.py:407) |
| GET | `/admin/users` | List users. | require_roles(institution_admin, action=admin.users) |  | list_users (services/central/app/identity/router.py:315) |
| POST | `/admin/users/{user_id}/apply-template` | Replace the user's template-managed realm roles with the template's (never service roles, never oneself). | require_roles(institution_admin, action=admin.apply_template) | user_id: str; body: ApplyTemplateIn | apply_role_template (services/central/app/identity/router.py:414) |
| POST | `/admin/users/{user_id}/disable` | Disable user. | _set_status → require_roles(institution_admin, action=admin.user_status) | user_id: str; body: StatusIn | disable_user (services/central/app/identity/router.py:370) |
| POST | `/admin/users/{user_id}/enable` | Enable user. | _set_status → require_roles(institution_admin, action=admin.user_status) | user_id: str; body: StatusIn | enable_user (services/central/app/identity/router.py:375) |
| GET | `/institutions` | Institutions. | valid access token (any role) |  | institutions (services/central/app/identity/router.py:380) |
| GET | `/patient-links` | Links of one of your own patient records (all states, with history). | require_roles(clinic_staff, clinician, institution_admin, diagnostics_staff, action=patient_link.view) | institution: str \| None; local_id: str \| None | list_links (services/central/app/identity/router.py:81) |
| POST | `/patient-links` | Ask another institution to confirm their record of one of your patients. | require_roles(clinic_staff, clinician, action=patient_link.request) | body: LinkIn | request_link (services/central/app/identity/router.py:127) |
| GET | `/patient-links/incoming` | Requests from other institutions for your staff to check. | require_roles(clinic_staff, clinician, institution_admin, diagnostics_staff, action=patient_link.incoming) | status: str | incoming (services/central/app/identity/router.py:102) |
| GET | `/patient-links/outgoing` | Outgoing. | require_roles(clinic_staff, clinician, institution_admin, diagnostics_staff, action=patient_link.outgoing) | status: str | outgoing (services/central/app/identity/router.py:112) |
| POST | `/patient-links/{link_id}/approve` | Only staff at the target institution approve, after comparing the identity details. A link says who the patient is there; it does not release any record (that needs the patient's consent). | require_roles(clinic_staff, institution_admin, diagnostics_staff, action=patient_link.approve) | link_id: int; body: ApproveIn | approve_link (services/central/app/identity/router.py:161) |
| POST | `/patient-links/{link_id}/invalidate` | Stops future use. History is kept, and referrals that used it are flagged for review. | require_roles(clinician, institution_admin, clinic_staff, action=patient_link.invalidate) | link_id: int; body: DecisionIn | invalidate_link (services/central/app/identity/router.py:251) |
| POST | `/patient-links/{link_id}/lookup` | Target staff search their own patient index for the person in the request. | require_roles(clinic_staff, institution_admin, diagnostics_staff, action=patient_link.lookup) | link_id: int | lookup (services/central/app/identity/router.py:138) |
| POST | `/patient-links/{link_id}/reject` | Reject link. | require_roles(clinic_staff, institution_admin, diagnostics_staff, action=patient_link.reject) | link_id: int; body: DecisionIn | reject_link (services/central/app/identity/router.py:231) |
| GET | `/patients/search` | Search your own institution's patient index (name, local ID or CNIC). | require_roles(clinic_staff, clinician, institution_admin, diagnostics_staff, action=patients.search) | q: str | search_patients (services/central/app/identity/router.py:290) |

#### records (encrypted)

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| POST | `/e2e/adapter/receiving-batches` | The receiving hospital adds its own records for its doctors (spec v4 step 8, 5.6 step 6): a batch from its adapter (signed request), encrypted to its own department's group key, so only that department's doctors open it. The referring side never gets a wrap for it. | public (no token) | body: ReceivingBatchIn | receiving_batch (services/central/app/records/router.py:187) |
| POST | `/e2e/adapter/record-responses` | An institution's answer after its staff reviewed a request (signed request from that institution). | public (no token) | body: AdapterAnswer | adapter_answer (services/central/app/records/router.py:89) |
| GET | `/e2e/received/{reference}/package` | The receiving department's doctors fetch the sent package (ciphertext and the data keys wrapped to the department group key) and open it on their device. The receiving hospital's system keeps no copy (D2). | department_member → role clinician required | reference: str | received_package (services/central/app/records/router.py:221) |
| GET | `/referrals/{referral_id}/encrypted` | Titles, ciphertext and the data keys wrapped to the caller's own keys. Decryption happens on the device. | require_referring_doctor → load_referral(roles=('clinician',)) | referral_id: int | encrypted_items (services/central/app/records/router.py:112) |
| POST | `/referrals/{referral_id}/encrypted-batches` | The doctor's own items (consultation notes, the medicine list asked from the patient, scans), encrypted on the doctor's device. The platform checks only the shape: who the keys are wrapped to and the size. | require_referring_doctor → load_referral(roles=('clinician',)) | referral_id: int; body: BatchIn | upload_batch (services/central/app/records/router.py:274) |
| GET | `/referrals/{referral_id}/record-requests` | List record requests. | load_referral(view, roles=['clinic_staff', 'clinician']) | referral_id: int | list_record_requests (services/central/app/records/router.py:62) |
| POST | `/referrals/{referral_id}/record-requests` | Send the records requests the patient's consent allows (staff or the referring doctor). | load_referral(records_request, roles=['clinic_staff', 'clinician']) | referral_id: int | request_records (services/central/app/records/router.py:48) |
| GET | `/referrals/{referral_id}/titles` | What every role at the referring institution may see of the records: titles only. | load_referral(view, roles=['clinic_staff', 'clinician']) | referral_id: int | referral_titles (services/central/app/records/router.py:70) |

#### referrals

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| GET | `/referrals` | List referrals. | require_roles(clinic_staff, clinician, action=referral.search); role clinician required | patient: str \| None; reference: str \| None; status: str \| None; destination: str \| None; kind: str \| None; mine: bool; date_from: date \| None; date_to: date \| None; limit: int | list_referrals (services/central/app/referrals/router.py:181) |
| POST | `/referrals` | Only a doctor applies for a referral or a test. | require_roles(clinician, action=referral.create) | body: ReferralForm | create_referral (services/central/app/referrals/router.py:144) |
| GET | `/referrals/{referral_id}` | Get referral. | load_referral(view); role clinician required | referral_id: int | get_referral (services/central/app/referrals/router.py:257) |
| PATCH | `/referrals/{referral_id}` | Doctors edit their request. After it was sent, a clinical change opens an amendment. | check_version(); load_referral(edit) | referral_id: int; body: ReferralUpdate | update_referral (services/central/app/referrals/router.py:320) |
| POST | `/referrals/{referral_id}/cancel` | Only a doctor withdraws a request; staff cannot stop it. | check_version(); load_referral(cancel) | referral_id: int; body: CancelIn | cancel (services/central/app/referrals/router.py:402) |
| GET | `/referrals/{referral_id}/events` | Events. | load_referral(view) | referral_id: int | events (services/central/app/referrals/router.py:413) |
| POST | `/referrals/{referral_id}/links` | Staff ask another institution (where the patient has been) to confirm the patient. | load_referral(link) | referral_id: int; body: LinkRequestIn | request_referral_link (services/central/app/referrals/router.py:383) |
| POST | `/referrals/{referral_id}/submit` | Submit request. | check_version(); load_referral(submit_request) | referral_id: int; body: VersionIn | submit_request (services/central/app/referrals/router.py:364) |

#### response and follow-through

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| POST | `/clarifications/{clarification_id}/answer` | Answer the receiving doctor's request for more information; the answer is sent back. | load_referral(answer_info_request) | clarification_id: int; body: AnswerIn | answer (services/central/app/followup/router.py:58) |
| POST | `/referrals/{referral_id}/close` | Closure means the workflow is complete, not a statement about the patient's condition. | check_version(); load_referral(close) | referral_id: int; body: CloseIn | close (services/central/app/followup/router.py:149) |
| POST | `/referrals/{referral_id}/patient-informed` | Staff record that the patient was told the outcome and what happens next. | load_referral(inform_patient) | referral_id: int; body: InformedIn | patient_informed (services/central/app/followup/router.py:84) |
| GET | `/referrals/{referral_id}/responses` | Responses. | load_referral(view) | referral_id: int | responses (services/central/app/followup/router.py:27) |
| GET | `/referrals/{referral_id}/tasks` | Tasks. | load_referral(view) | referral_id: int | tasks (services/central/app/followup/router.py:104) |
| POST | `/referrals/{referral_id}/tasks` | Tasks such as a repeat test or making sure the patient attends. | load_referral(followup) | referral_id: int; body: TaskIn | add_task (services/central/app/followup/router.py:110) |
| POST | `/responses/{response_id}/review` | The referring doctor records that the outcome has been seen. | load_referral(review_response) | response_id: int; body: ReviewIn | review_response (services/central/app/followup/router.py:38) |
| POST | `/tasks/{task_id}/outcome` | Task outcome. | load_referral(followup) | task_id: int; body: TaskOutcomeIn | task_outcome (services/central/app/followup/router.py:131) |

#### sending

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| POST | `/e2e/verify-manifest` | Given a stored copy of a signed manifest (the receiver's, or the patient's), say whether it is the version the platform recorded, whether its signature verifies against the signer's key, and whether the referral was purged (then only the manifest hash remains). The holder checks the item hashes against its decrypted copy. | valid access token (any role) | body: VerifyIn | verify_manifest (services/central/app/sending/router.py:100) |
| GET | `/referrals/{referral_id}/delivery` | Delivery. | load_referral(view) | referral_id: int | delivery (services/central/app/sending/router.py:86) |
| GET | `/referrals/{referral_id}/packages` | Every approved version. Staff see who signed what and when; the manifest itself (item hashes) for doctors. | load_referral(view, roles=['clinic_staff', 'clinician']) | referral_id: int | list_packages (services/central/app/sending/router.py:49) |
| POST | `/referrals/{referral_id}/packages` | The referring doctor approves: a manifest signed on their device, and the data keys re-wrapped to the receiving department's group key and the patient's key. | load_referral(approve) | referral_id: int; body: ApproveIn | approve_package (services/central/app/sending/router.py:35) |
| GET | `/referrals/{referral_id}/readiness` | Get readiness. | load_referral(view) | referral_id: int | get_readiness (services/central/app/sending/router.py:24) |
| POST | `/referrals/{referral_id}/retry-delivery` | Retry reuses the same delivery key, so the receiver never gets a duplicate. | load_referral(send) | referral_id: int | retry_delivery (services/central/app/sending/router.py:76) |
| POST | `/referrals/{referral_id}/send` | Staff send the approved version to the receiving hospital. | check_version(); load_referral(send) | referral_id: int; body: SendIn | send (services/central/app/sending/router.py:63) |

#### tests and scans

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| GET | `/diagnostics/{dx_id}/attachments/{n}` | An image or file returned with the report. | _load → load_referral() | dx_id: int; n: int | attachment (services/central/app/diagnostics/router.py:148) |
| POST | `/diagnostics/{dx_id}/cancel` | The doctor withdraws a test that has not been sent (or was rejected). | _load → load_referral() | dx_id: int; body: CancelIn | cancel_request (services/central/app/diagnostics/router.py:118) |
| POST | `/diagnostics/{dx_id}/seen` | The requesting doctor records that they have seen the result. | _load → load_referral() | dx_id: int | mark_seen (services/central/app/diagnostics/router.py:132) |
| POST | `/diagnostics/{dx_id}/send` | Staff check the request and send the order, with the patient's identity details. | _load → load_referral() | dx_id: int | send_request (services/central/app/diagnostics/router.py:79) |
| GET | `/referrals/{referral_id}/diagnostics` | List requests. | load_referral(view) | referral_id: int | list_requests (services/central/app/diagnostics/router.py:57) |
| POST | `/referrals/{referral_id}/diagnostics` | The doctor adds a test to their test request (before it is sent). | load_referral(add_diagnostic) | referral_id: int; body: DiagnosticIn | add_request (services/central/app/diagnostics/router.py:64) |

#### work queue

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| GET | `/work-queue` | Work queue. | require_roles(clinician, clinic_staff, action=work_queue); role clinic_staff required; role clinician required |  | work_queue (services/central/app/workqueue.py:27) |

### Institution service API (`drali` 8001, `chughtai` 8002, `ziauddin` 8003, `akuh` 8004): 39 endpoints

#### fhir

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| GET | `/fhir/patients/{local_id}/records` | Referral profile, kept to what a referral needs: conditions, surgeries, current medications only, and visits, results and imaging since the window start (latest result per test). Returned as a FHIR searchset Bundle. | decide_access(); forbid() | local_id: str; categories: str \| None; since: str \| None | patient_records (services/provider/app/main.py:325) |

#### health

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| GET | `/health` | Health. | public (no token) |  | health (libs/common/refcommon/sourcekit.py:137) |
| GET | `/ready` | Ready. | public (no token) |  | ready (libs/common/refcommon/sourcekit.py:141) |

#### identity

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| POST | `/identity/lookup` | Own staff look up who a link request refers to. Candidates are shown to a person, with each field compared; nothing is linked automatically. | require_own(clinic_staff, clinician, institution_admin, diagnostics_staff, what=look up a patient for a link request) | body: LookupIn | identity_lookup (services/provider/app/main.py:229) |
| POST | `/identity/register` | Register a patient who is new to this institution (first referral or test here). | require_own(clinic_staff, institution_admin, diagnostics_staff, what=register a new patient) | body: RegisterIn | register_patient (services/provider/app/main.py:267) |

#### inbound (central platform)

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| POST | `/inbound/clarification-answers` | Receive answer. | _require_central() | body: ClarificationAnswer | receive_answer (services/provider/app/main.py:632) |
| POST | `/inbound/orders` | Receive order. | _require_central() | body: DiagnosticOrder | receive_order (services/provider/app/main.py:531) |
| POST | `/inbound/referral-expired` | The referral's time is up: remove this institution's copy of the shared records (the packages and the results forwarded with them). Its own decision, questions and response are its record and are kept. | _require_central() | body: ExpiredIn | referral_expired (services/provider/app/main.py:509) |
| POST | `/inbound/referrals` | Idempotent receipt of a sent referral version (keyed by delivery key): a notice with record titles and the signed manifest's hash, never record content (spec v4, D2). | _require_central() | raw: dict | receive_package (services/provider/app/main.py:462) |
| POST | `/inbound/results` | Receive result. | _require_central() | body: ResultForward | receive_result (services/provider/app/main.py:559) |
| POST | `/outbound-copies` | Store our own copy of a referral we sent, or of the response to it (idempotent by key). | _require_central() | body: SentCopyIn | receive_sent_copy (services/provider/app/main.py:582) |

#### incoming referrals

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| GET | `/cases` | List cases. | _visible → _is_intake → has_any(clinic_staff, institution_admin); _visible → role clinician required; require_own(clinician, clinic_staff, institution_admin, what=see incoming referrals) |  | list_cases (services/provider/app/main.py:692) |
| GET | `/cases/{case_id}` | Get case. | _get_case(); require_own(clinician, clinic_staff, institution_admin, what=see incoming referrals); role clinician required | case_id: int | get_case (services/provider/app/main.py:784) |
| POST | `/cases/{case_id}/acknowledge` | Staff confirm the referral has been received here. | _get_case(); require_own(clinic_staff, institution_admin, what=acknowledge a referral) | case_id: int | acknowledge (services/provider/app/main.py:699) |
| POST | `/cases/{case_id}/assign` | Staff send the referral to the doctor who will see the patient (can be changed until they decide). | _get_case(); require_own(clinic_staff, institution_admin, what=assign a referral) | case_id: int; body: AssignIn | assign (services/provider/app/main.py:720) |
| POST | `/cases/{case_id}/own-records` | Staff add this hospital's own records for the patient to the referral (spec v4 step 8). This system collects them and encrypts them to the receiving department's group key, so only its doctors open them; staff never see the content. Sensitive categories are left out. The referring side gets no key for them. | _get_case(); require_own(clinic_staff, institution_admin, what=add this hospital's records) | case_id: int | add_own_records (services/provider/app/main.py:740) |

#### intake

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| POST | `/intake/patient` | Staff here confirmed who an arriving patient is (through the central link request): the incoming referral and test orders for that request now point at this record. | require_own(clinic_staff, institution_admin, diagnostics_staff, what=confirm an arriving patient) | body: IntakeIn | intake_patient (services/provider/app/main.py:615) |

#### laboratory and imaging

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| GET | `/orders` | List orders. | _require_diagnostics() |  | list_orders (services/provider/app/main.py:1038) |
| GET | `/orders/{order_id}` | Get order. | _get_order(); _require_diagnostics() | order_id: int | get_order (services/provider/app/main.py:1045) |
| POST | `/orders/{order_id}/accept` | Accept order. | _get_order(); _require_diagnostics() | order_id: int | accept_order (services/provider/app/main.py:1062) |
| GET | `/orders/{order_id}/attachments/{attachment_id}` | Order attachment. | _get_order(); _require_diagnostics() | order_id: int; attachment_id: int | order_attachment (services/provider/app/main.py:1051) |
| POST | `/orders/{order_id}/done` | Order done. | _get_order(); _require_diagnostics() | order_id: int | order_done (services/provider/app/main.py:1102) |
| POST | `/orders/{order_id}/reject` | A rejection always carries a reason (wrong test, preparation needed, no capacity). | _get_order(); _require_diagnostics() | order_id: int; body: RejectIn | reject_order (services/provider/app/main.py:1077) |
| POST | `/orders/{order_id}/report` | Return the report (with images for scans). It is also filed in this institution's own records. | _get_order(); _require_diagnostics() | order_id: int; body: ReportIn | report_order (services/provider/app/main.py:1162) |
| POST | `/orders/{order_id}/schedule` | Schedule order. | _get_order(); _require_diagnostics() | order_id: int; body: ScheduleIn | schedule_order (services/provider/app/main.py:1092) |

#### patient access

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| GET | `/patient-access/records` | The patient's whole record at this institution: no referral window and stopped medicines included. | _own_patient_records → forbid(Only a patient account can read its own records here); _own_patient_records → forbid(This patient account has no CNIC, so no record can be matched to it); _own_patient_records → role patient required |  | patient_history (services/provider/app/main.py:419) |
| GET | `/patient-access/summary` | Whether this institution holds records for the signed-in patient, and how many of each kind. | _own_patient_records → forbid(Only a patient account can read its own records here); _own_patient_records → forbid(This patient account has no CNIC, so no record can be matched to it); _own_patient_records → role patient required |  | patient_summary (services/provider/app/main.py:401) |

#### patients

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| GET | `/patients` | Own patient index (name, local ID or CNIC). | require_own(clinic_staff, clinician, institution_admin, diagnostics_staff, what=search the patient index) | q: str | search_patients (services/provider/app/main.py:192) |
| GET | `/patients/{local_id}` | Get patient. | require_own(clinic_staff, clinician, institution_admin, diagnostics_staff, what=view patient details) | local_id: str | get_patient (services/provider/app/main.py:212) |

#### receiving doctor

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| POST | `/cases/{case_id}/complete` | The specialist closes the referral (spec v4 step 11). The encrypted referral is purged a week later; the patient keeps their own copy. | _get_case(); _require_doctor → require_own(clinician, what=act on incoming referrals) | case_id: int | complete_case (services/provider/app/main.py:955) |
| POST | `/cases/{case_id}/decision` | Decide. | _get_case(); _require_doctor → require_own(clinician, what=act on incoming referrals) | case_id: int; body: DecisionIn | decide (services/provider/app/main.py:829) |
| POST | `/cases/{case_id}/extend-hold` | The specialist keeps the referral open longer: another 30 days, with a reason, at most MAX_REFERRAL_DAYS after accepting (spec v4 7). The close reminder moves to the new date. | _get_case(); _require_doctor → require_own(clinician, what=act on incoming referrals) | case_id: int; body: ExtendHoldIn | extend_hold (services/provider/app/main.py:976) |
| POST | `/cases/{case_id}/info-requests` | Request info. | _get_case(); _require_doctor → require_own(clinician, what=act on incoming referrals) | case_id: int; body: InfoIn | request_info (services/provider/app/main.py:858) |
| PUT | `/cases/{case_id}/response` | Save response. | _get_case(); _require_doctor → require_own(clinician, what=act on incoming referrals) | case_id: int; body: ResponseIn | save_response (services/provider/app/main.py:894) |
| POST | `/cases/{case_id}/response/send` | The receiving doctor signs off and returns the response in one step. | _get_case(); _require_doctor → require_own(clinician, what=act on incoming referrals) | case_id: int; body: SendIn | send_response (services/provider/app/main.py:922) |
| POST | `/outbox/{item_id}/retry` | Retry outbox. | require_own(clinician, diagnostics_staff, institution_admin, what=retry delivery) | item_id: int | retry_outbox (services/provider/app/main.py:1200) |

#### records

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| GET | `/outbound-copies` | Our own copies for one referral (doctors and staff here). | require_own(clinician, clinic_staff, what=read our copies of sent referrals); role clinician required | referral_id: str | list_sent_copies (services/provider/app/main.py:598) |
| GET | `/patients/{local_id}/activity` | When the patient was last seen here (visit, test or scan). Used to choose the most recently visited institution of each kind. | decide_access(); forbid() | local_id: str | patient_activity (services/provider/app/main.py:307) |

#### source administration

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| GET | `/admin/audit` | List audit. | forbid(Only this institution's administrators can read its audit trail); role institution_admin required | limit: int | list_audit (libs/common/refcommon/sourcekit.py:102) |
