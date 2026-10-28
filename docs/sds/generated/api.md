## API inventory

Generated from the FastAPI route decorators. *Access checks* lists the authorisation calls made inside each handler (roles, institution scope, service identity, optimistic-concurrency checks). Every endpoint except `/health` and `/ready` also requires a valid Keycloak access token (verified signature, issuer, audience and introspection). Parameters exclude the database session and the caller's identity.

### Central platform API (`central`, port 8000): 97 endpoints

#### audit and reference data

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| GET | `/admin/audit` | Administrators see audit metadata for their institution (no clinical record content). | require_roles(institution_admin, action=admin.audit) | action: str \| None; outcome: str \| None; limit: int | institution_audit (services/central/app/audit_router.py:46) |
| GET | `/me` | Me. | valid access token (any role) |  | me (services/central/app/audit_router.py:68) |
| GET | `/reference-data` | Reference data. | valid access token (any role) |  | reference_data (services/central/app/audit_router.py:82) |
| GET | `/referrals/{referral_id}/audit` | Referral audit. | load_referral(view_audit) | referral_id: int | referral_audit (services/central/app/audit_router.py:40) |

#### documents

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| GET | `/documents/{document_id}` | Get document. | _load_doc → load_referral() | document_id: int | get_document (services/central/app/documents/router.py:113) |
| GET | `/documents/{document_id}/file` | Download. | _load_doc → load_referral() | document_id: int | download (services/central/app/documents/router.py:132) |
| GET | `/documents/{document_id}/pages/{page}` | Page image. | _load_doc → load_referral() | document_id: int; page: int | page_image (services/central/app/documents/router.py:144) |
| POST | `/documents/{document_id}/reprocess` | Reprocess. | _load_doc → load_referral() | document_id: int | reprocess (services/central/app/documents/router.py:154) |
| GET | `/jobs/{job_id}` | Get job. | load_referral(view) | job_id: str | get_job (services/central/app/documents/router.py:167) |
| GET | `/referrals/{referral_id}/documents` | List documents. | load_referral(view) | referral_id: int | list_documents (services/central/app/documents/router.py:99) |
| POST | `/referrals/{referral_id}/documents` | Upload. | ensure_clinical_edit_allowed(); load_referral(upload) | referral_id: int; file: UploadFile; doc_type: str | upload (services/central/app/documents/router.py:47) |
| GET | `/referrals/{referral_id}/jobs` | Referral jobs. | load_referral(view) | referral_id: int | referral_jobs (services/central/app/documents/router.py:179) |

#### evidence

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| GET | `/evidence/{evidence_id}` | Get evidence. | _load → load_referral() | evidence_id: int | get_evidence (services/central/app/evidence_router.py:75) |
| POST | `/evidence/{evidence_id}/correct` | Correct. | _load → load_referral() | evidence_id: int; body: CorrectIn | correct (services/central/app/evidence_router.py:125) |
| POST | `/evidence/{evidence_id}/exclude` | Exclude. | _set_state → _load → load_referral() | evidence_id: int; body: StateIn | exclude (services/central/app/evidence_router.py:177) |
| POST | `/evidence/{evidence_id}/restore` | Restore. | _set_state → _load → load_referral() | evidence_id: int; body: StateIn | restore (services/central/app/evidence_router.py:182) |
| POST | `/evidence/{evidence_id}/select` | Staff finalise the packet: their choice overrides the default and the AI recommendation. | _load → load_referral(); ensure_clinical_edit_allowed() | evidence_id: int; body: SelectIn | select_evidence (services/central/app/evidence_router.py:100) |
| POST | `/evidence/{evidence_id}/unresolve` | Mark unresolved. | _set_state → _load → load_referral() | evidence_id: int; body: StateIn | mark_unresolved (services/central/app/evidence_router.py:172) |
| POST | `/evidence/{evidence_id}/verify` | Checking a field read from a paper against the paper. Staff do this while preparing the referral; a checked medicine joins the current-medicine list. | _load → load_referral() | evidence_id: int; body: VerifyIn | verify (services/central/app/evidence_router.py:192) |
| GET | `/referrals/{referral_id}/evidence` | List evidence. | load_referral(view) | referral_id: int; category: str \| None; include_superseded: bool | list_evidence (services/central/app/evidence_router.py:63) |
| POST | `/referrals/{referral_id}/evidence/manual` | Manual transcription with an optional source reference; works without OCR (FR-58). | ensure_clinical_edit_allowed(); load_referral(edit) | referral_id: int; body: ManualIn | manual_entry (services/central/app/evidence_router.py:219) |

#### health

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| GET | `/health` | Health. | public (no token) |  | health (services/central/app/main.py:45) |
| GET | `/ready` | Ready. | public (no token) |  | ready (services/central/app/main.py:50) |

#### inbound (institution services)

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| POST | `/inbound/provider-events` | Provider event. | require_service(svc_provider) | body: ProviderEvent | provider_event (services/central/app/delivery/inbound.py:26) |

#### medications

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| GET | `/drug-classes` | Drug classes. | valid access token (any role) |  | drug_classes (services/central/app/medications/router.py:517) |
| GET | `/medicine-names` | Medicine names. | role rule_reviewer required | q: str | medicine_names (services/central/app/medications/router.py:294) |
| POST | `/medicine-names` | Add name. | require_roles(rule_reviewer, action=medicine_name.add) | body: NameIn | add_name (services/central/app/medications/router.py:315) |
| POST | `/medicine-names/{name_id}/retire` | Retire name. | require_roles(rule_reviewer, action=medicine_name.retire) | name_id: int | retire_name (services/central/app/medications/router.py:335) |
| POST | `/referrals/{referral_id}/ai-suggestions/review` | The doctor marks an AI suggestion Ignore (not relevant for this patient) or Research (needs follow-up). It changes no flag. | load_referral(review_ai_suggestion, roles=('clinician',)) | referral_id: int; body: SuggestionReviewIn | review_suggestion (services/central/app/medications/router.py:70) |
| POST | `/referrals/{referral_id}/flags/{flag_id}/acknowledge` | The doctor records a decision on the flag for this patient: reviewed, ignore or research. Any decision means 'seen'; it is never treatment clearance. Ignored flags stay in the record. | load_referral(acknowledge_flag, roles=('clinician',)) | referral_id: int; flag_id: int; body: AckIn | acknowledge_flag (services/central/app/medications/router.py:264) |
| GET | `/referrals/{referral_id}/medications` | Medications. | load_referral(view) | referral_id: int | medications (services/central/app/medications/router.py:34) |
| POST | `/referrals/{referral_id}/medications/checked` | Staff confirm they asked the patient about every medicine, including over-the-counter ones. | ensure_clinical_edit_allowed(); load_referral(edit) | referral_id: int; body: CheckedIn | medicines_checked (services/central/app/medications/router.py:245) |
| POST | `/referrals/{referral_id}/medications/manual` | Staff add a medicine the patient says they take, e.g. an over-the-counter painkiller. | ensure_clinical_edit_allowed(); load_referral(edit, roles=('clinic_staff',)) | referral_id: int; body: ManualMedIn | add_medicine (services/central/app/medications/router.py:112) |
| POST | `/referrals/{referral_id}/medications/{entry_id}/exclude` | Staff mark a recorded medicine as not current (e.g. an old prescription, or the other side of a dose difference). The record is kept, with who and why. | ensure_clinical_edit_allowed(); load_referral(edit) | referral_id: int; entry_id: int; body: ReasonIn | exclude_medicine (services/central/app/medications/router.py:154) |
| POST | `/referrals/{referral_id}/medications/{entry_id}/mapping` | Doctor or staff resolve a name: choose a medicine from the name list, or, for a DRAP brand name used for different products, the product it is (by the company on the pack). | ensure_clinical_edit_allowed(); load_referral(map_medication) | referral_id: int; entry_id: int; body: MapIn | set_mapping (services/central/app/medications/router.py:206) |
| POST | `/referrals/{referral_id}/medications/{entry_id}/restore` | Restore medicine. | ensure_clinical_edit_allowed(); load_referral(edit) | referral_id: int; entry_id: int | restore_medicine (services/central/app/medications/router.py:172) |
| GET | `/rules` | List rules. | require_roles(rule_reviewer, action=rule.list); role rule_reviewer required |  | list_rules (services/central/app/medications/router.py:361) |
| POST | `/rules` | Reviewers draft a rule. It does nothing until a reviewer approves it. | require_roles(rule_reviewer, action=rule.create) | body: RuleIn | create_rule (services/central/app/medications/router.py:407) |
| GET | `/rules/ai` | The suggestion model's evaluation figures and its stored suggestions (reviewer only). | require_roles(rule_reviewer, action=rule.list) |  | ai_model (services/central/app/medications/router.py:87) |
| GET | `/rules/interactions` | Imported drug-drug interactions (read-only), searchable by ingredient. | require_roles(rule_reviewer, action=rule.list) | q: str | list_interactions (services/central/app/medications/router.py:485) |
| GET | `/rules/label-rules` | Rules read from drug labels by script (read-only), with the sentence each relies on. | require_roles(rule_reviewer, action=rule.list) | q: str; kind: str | list_label_rules (services/central/app/medications/router.py:496) |
| PUT | `/rules/{rule_id}` | An edit is a new draft version; the approved version keeps working until the new one is approved. | require_roles(rule_reviewer, action=rule.edit) | rule_id: str; body: RuleIn | edit_rule (services/central/app/medications/router.py:422) |
| POST | `/rules/{rule_id}/versions/{version}/decision` | Only a clinical rule reviewer may approve, reject or retire a rule version. | require_roles(rule_reviewer, action=rule.decision) | rule_id: str; version: int; body: RuleDecisionIn | decide_rule (services/central/app/medications/router.py:440) |

#### notifications

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| GET | `/notifications` | List notifications. | _mine() | unread_only: bool | list_notifications (services/central/app/notifications.py:56) |
| POST | `/notifications/read-all` | Mark all read. | _mine() |  | mark_all_read (services/central/app/notifications.py:75) |
| POST | `/notifications/{notification_id}/read` | Mark read. | _mine() | notification_id: int | mark_read (services/central/app/notifications.py:64) |

#### patient links

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| GET | `/admin/role-templates` | Templates this institution's administrator may apply. | require_roles(institution_admin, action=admin.role_templates) |  | list_role_templates (services/central/app/identity/router.py:412) |
| GET | `/admin/users` | List users. | require_roles(institution_admin, action=admin.users) |  | list_users (services/central/app/identity/router.py:320) |
| POST | `/admin/users/{user_id}/apply-template` | Replace the user's template-managed realm roles with the template's (never service roles, never oneself). | require_roles(institution_admin, action=admin.apply_template) | user_id: str; body: ApplyTemplateIn | apply_role_template (services/central/app/identity/router.py:419) |
| POST | `/admin/users/{user_id}/disable` | Disable user. | _set_status → require_roles(institution_admin, action=admin.user_status) | user_id: str; body: StatusIn | disable_user (services/central/app/identity/router.py:375) |
| POST | `/admin/users/{user_id}/enable` | Enable user. | _set_status → require_roles(institution_admin, action=admin.user_status) | user_id: str; body: StatusIn | enable_user (services/central/app/identity/router.py:380) |
| GET | `/institutions` | Institutions. | valid access token (any role) |  | institutions (services/central/app/identity/router.py:385) |
| GET | `/patient-links` | Links of one of your own patient records (all states, with history). | require_roles(clinic_staff, clinician, institution_admin, diagnostics_staff, action=patient_link.view) | institution: str \| None; local_id: str \| None | list_links (services/central/app/identity/router.py:81) |
| POST | `/patient-links` | Ask another institution to confirm their record of one of your patients. | require_roles(clinic_staff, clinician, action=patient_link.request) | body: LinkIn | request_link (services/central/app/identity/router.py:127) |
| GET | `/patient-links/incoming` | Requests from other institutions for your staff to check. | require_roles(clinic_staff, clinician, institution_admin, diagnostics_staff, action=patient_link.incoming) | status: str | incoming (services/central/app/identity/router.py:102) |
| GET | `/patient-links/outgoing` | Outgoing. | require_roles(clinic_staff, clinician, institution_admin, diagnostics_staff, action=patient_link.outgoing) | status: str | outgoing (services/central/app/identity/router.py:112) |
| POST | `/patient-links/{link_id}/approve` | Only staff at the target institution approve. Approval records the basis and shares the patient's referral-relevant records with the requesting institution. | require_roles(clinic_staff, institution_admin, diagnostics_staff, action=patient_link.approve) | link_id: int; body: ApproveIn | approve_link (services/central/app/identity/router.py:161) |
| POST | `/patient-links/{link_id}/invalidate` | Stops future use. History is kept, and referrals that used it are flagged for review. | require_roles(clinician, institution_admin, clinic_staff, action=patient_link.invalidate) | link_id: int; body: DecisionIn | invalidate_link (services/central/app/identity/router.py:256) |
| POST | `/patient-links/{link_id}/lookup` | Target staff search their own patient index for the person in the request. | require_roles(clinic_staff, institution_admin, diagnostics_staff, action=patient_link.lookup) | link_id: int | lookup (services/central/app/identity/router.py:138) |
| POST | `/patient-links/{link_id}/reject` | Reject link. | require_roles(clinic_staff, institution_admin, diagnostics_staff, action=patient_link.reject) | link_id: int; body: DecisionIn | reject_link (services/central/app/identity/router.py:236) |
| GET | `/patients/search` | Search your own institution's patient index (name, local ID or CNIC). | require_roles(clinic_staff, clinician, institution_admin, diagnostics_staff, action=patients.search) | q: str | search_patients (services/central/app/identity/router.py:295) |

#### referrals

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| GET | `/referrals` | List referrals. | require_roles(clinic_staff, clinician, action=referral.search); role clinician required | patient: str \| None; reference: str \| None; status: str \| None; destination: str \| None; kind: str \| None; mine: bool; date_from: date \| None; date_to: date \| None; limit: int | list_referrals (services/central/app/referrals/router.py:178) |
| POST | `/referrals` | Only a doctor applies for a referral or a test. | require_roles(clinician, action=referral.create) | body: ReferralForm | create_referral (services/central/app/referrals/router.py:142) |
| GET | `/referrals/{referral_id}` | Get referral. | load_referral(view); role clinician required | referral_id: int | get_referral (services/central/app/referrals/router.py:252) |
| PATCH | `/referrals/{referral_id}` | Doctors edit their request. After it was sent, a clinical change opens an amendment. | check_version(); load_referral(edit) | referral_id: int; body: ReferralUpdate | update_referral (services/central/app/referrals/router.py:286) |
| POST | `/referrals/{referral_id}/cancel` | Only a doctor withdraws a request; staff cannot stop it. | check_version(); load_referral(cancel) | referral_id: int; body: CancelIn | cancel (services/central/app/referrals/router.py:423) |
| GET | `/referrals/{referral_id}/events` | Events. | load_referral(view) | referral_id: int | events (services/central/app/referrals/router.py:434) |
| POST | `/referrals/{referral_id}/links` | Staff ask another institution (where the patient has been) to confirm the patient. | load_referral(link) | referral_id: int; body: LinkRequestIn | request_referral_link (services/central/app/referrals/router.py:349) |
| POST | `/referrals/{referral_id}/recommend` | Staff ask for the AI recommendation again (for example after adding papers). | load_referral(prepare, roles=('clinic_staff',)) | referral_id: int | recommend_selection (services/central/app/referrals/router.py:397) |
| GET | `/referrals/{referral_id}/retrievals` | Retrieval history. | load_referral(view) | referral_id: int | retrieval_history (services/central/app/referrals/router.py:411) |
| POST | `/referrals/{referral_id}/retrieve` | Retrieve records. | load_referral(retrieve) | referral_id: int | retrieve_records (services/central/app/referrals/router.py:363) |
| GET | `/referrals/{referral_id}/selection` | Selection status. | load_referral(view) | referral_id: int | selection_status (services/central/app/referrals/router.py:389) |
| POST | `/referrals/{referral_id}/submit` | Submit request. | check_version(); load_referral(submit_request) | referral_id: int; body: VersionIn | submit_request (services/central/app/referrals/router.py:330) |

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
| GET | `/referrals/{referral_id}/brief-preview` | What the specialist will receive if the referral is sent now. | load_referral(view) | referral_id: int | brief_preview (services/central/app/sending/router.py:36) |
| GET | `/referrals/{referral_id}/delivery` | Delivery. | load_referral(view) | referral_id: int | delivery (services/central/app/sending/router.py:93) |
| GET | `/referrals/{referral_id}/packages/{version}` | Get package. | load_referral(view) | referral_id: int; version: int | get_package (services/central/app/sending/router.py:102) |
| POST | `/referrals/{referral_id}/packages/{version}/verify` | Compare a copy of the package (held by the sender or the receiver) with the fingerprint kept at sending. | load_referral(view) | referral_id: int; version: int; body: VerifyCopyIn | verify_package_copy (services/central/app/sending/router.py:124) |
| POST | `/referrals/{referral_id}/packages/{version}/verify-own-copy` | Fetch this clinic's own stored copy (from its own system, with the user's token) and check it. | load_referral(view) | referral_id: int; version: int | verify_own_copy (services/central/app/sending/router.py:136) |
| POST | `/referrals/{referral_id}/prepared` | Staff have gathered the records, papers and medicines; the doctor can now review the flags. | check_version(); load_referral(prepare) | referral_id: int; body: SendIn | mark_prepared (services/central/app/sending/router.py:47) |
| GET | `/referrals/{referral_id}/readiness` | Get readiness. | load_referral(view) | referral_id: int | get_readiness (services/central/app/sending/router.py:30) |
| POST | `/referrals/{referral_id}/retry-delivery` | Retry reuses the same delivery key, so the receiver never gets a duplicate. | load_referral(send) | referral_id: int | retry_delivery (services/central/app/sending/router.py:83) |
| POST | `/referrals/{referral_id}/send` | Staff send the referral once every check is done. | check_version(); load_referral(send) | referral_id: int; body: SendIn | send (services/central/app/sending/router.py:72) |

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

### Institution service API (`drali` 8001, `chughtai` 8002, `ziauddin` 8003, `akuh` 8004): 42 endpoints

#### fhir

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| GET | `/fhir/patients/{local_id}/records` | Referral profile, kept to what a referral needs: conditions, surgeries, current medications only, and visits, results and imaging since the window start (latest result per test). Returned as a FHIR searchset Bundle. | decide_access(); forbid() | local_id: str; categories: str \| None; since: str \| None | patient_records (services/provider/app/main.py:366) |

#### grant close-out

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| POST | `/grants/revoke-by-referral` | Revoke by referral. | forbid(Only the central platform service can close grants by referral); role svc_central required | body: RevokeByReferralIn | revoke_by_referral (libs/common/refcommon/sourcekit.py:302) |

#### health

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| GET | `/health` | Health. | public (no token) |  | health (libs/common/refcommon/sourcekit.py:339) |
| GET | `/ready` | Ready. | public (no token) |  | ready (libs/common/refcommon/sourcekit.py:343) |

#### identity

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| POST | `/identity/lookup` | Own staff look up who a link request refers to. Candidates are shown to a person, with each field compared; nothing is linked automatically. | require_own(clinic_staff, clinician, institution_admin, diagnostics_staff, what=look up a patient for a link request) | body: LookupIn | identity_lookup (services/provider/app/main.py:232) |
| POST | `/identity/register` | Register a patient who is new to this institution (first referral or test here). | require_own(clinic_staff, institution_admin, diagnostics_staff, what=register a new patient) | body: RegisterIn | register_patient (services/provider/app/main.py:270) |

#### inbound (central platform)

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| POST | `/inbound/clarification-answers` | Receive answer. | _require_central() | body: ClarificationAnswer | receive_answer (services/provider/app/main.py:585) |
| POST | `/inbound/orders` | Receive order. | _require_central() | body: DiagnosticOrder | receive_order (services/provider/app/main.py:486) |
| POST | `/inbound/referral-expired` | The referral's time is up: remove this institution's copy of the shared records (the packages and the results forwarded with them). Its own decision, questions and response are its record and are kept. | _require_central() | body: ExpiredIn | referral_expired (services/provider/app/main.py:464) |
| POST | `/inbound/referrals` | Idempotent receipt of a sent referral version (keyed by delivery key). | _require_central() | raw: dict | receive_package (services/provider/app/main.py:419) |
| POST | `/inbound/results` | Receive result. | _require_central() | body: ResultForward | receive_result (services/provider/app/main.py:514) |
| POST | `/outbound-copies` | Store our own copy of a referral we sent, or of the response to it (idempotent by key). | _require_central() | body: SentCopyIn | receive_sent_copy (services/provider/app/main.py:537) |

#### incoming referrals

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| GET | `/cases` | List cases. | _visible → _is_intake → has_any(clinic_staff, institution_admin); _visible → role clinician required; require_own(clinician, clinic_staff, institution_admin, what=see incoming referrals) |  | list_cases (services/provider/app/main.py:645) |
| GET | `/cases/{case_id}` | Get case. | _get_case(); require_own(clinician, clinic_staff, institution_admin, what=see incoming referrals) | case_id: int | get_case (services/provider/app/main.py:693) |
| POST | `/cases/{case_id}/acknowledge` | Staff confirm the referral has been received here. | _get_case(); require_own(clinic_staff, institution_admin, what=acknowledge a referral) | case_id: int | acknowledge (services/provider/app/main.py:652) |
| POST | `/cases/{case_id}/assign` | Staff send the referral to the doctor who will see the patient (can be changed until they decide). | _get_case(); require_own(clinic_staff, institution_admin, what=assign a referral) | case_id: int; body: AssignIn | assign (services/provider/app/main.py:673) |

#### intake

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| POST | `/intake/patient` | Staff here confirmed who an arriving patient is (through the central link request): the incoming referral and test orders for that request now point at this record. | require_own(clinic_staff, institution_admin, diagnostics_staff, what=confirm an arriving patient) | body: IntakeIn | intake_patient (services/provider/app/main.py:568) |

#### laboratory and imaging

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| GET | `/orders` | List orders. | _require_diagnostics() |  | list_orders (services/provider/app/main.py:928) |
| GET | `/orders/{order_id}` | Get order. | _get_order(); _require_diagnostics() | order_id: int | get_order (services/provider/app/main.py:935) |
| POST | `/orders/{order_id}/accept` | Accept order. | _get_order(); _require_diagnostics() | order_id: int | accept_order (services/provider/app/main.py:952) |
| GET | `/orders/{order_id}/attachments/{attachment_id}` | Order attachment. | _get_order(); _require_diagnostics() | order_id: int; attachment_id: int | order_attachment (services/provider/app/main.py:941) |
| POST | `/orders/{order_id}/done` | Order done. | _get_order(); _require_diagnostics() | order_id: int | order_done (services/provider/app/main.py:992) |
| POST | `/orders/{order_id}/reject` | A rejection always carries a reason (wrong test, preparation needed, no capacity). | _get_order(); _require_diagnostics() | order_id: int; body: RejectIn | reject_order (services/provider/app/main.py:967) |
| POST | `/orders/{order_id}/report` | Return the report (with images for scans). It is also filed in this institution's own records. | _get_order(); _require_diagnostics() | order_id: int; body: ReportIn | report_order (services/provider/app/main.py:1052) |
| POST | `/orders/{order_id}/schedule` | Schedule order. | _get_order(); _require_diagnostics() | order_id: int; body: ScheduleIn | schedule_order (services/provider/app/main.py:982) |

#### patients

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| GET | `/patients` | Own patient index (name, local ID or CNIC). | require_own(clinic_staff, clinician, institution_admin, diagnostics_staff, what=search the patient index) | q: str | search_patients (services/provider/app/main.py:195) |
| GET | `/patients/{local_id}` | Get patient. | require_own(clinic_staff, clinician, institution_admin, diagnostics_staff, what=view patient details) | local_id: str | get_patient (services/provider/app/main.py:215) |

#### receiving doctor

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| POST | `/cases/{case_id}/complete` | The referred doctor has finished with the referral. The shared records are removed 72 hours later. | _get_case(); _require_doctor → require_own(clinician, what=act on incoming referrals) | case_id: int | complete_case (services/provider/app/main.py:850) |
| POST | `/cases/{case_id}/decision` | Decide. | _get_case(); _require_doctor → require_own(clinician, what=act on incoming referrals) | case_id: int; body: DecisionIn | decide (services/provider/app/main.py:724) |
| POST | `/cases/{case_id}/extend-hold` | The referred doctor needs the shared records for longer: kept for another 30 days from now. | _get_case(); _require_doctor → require_own(clinician, what=act on incoming referrals) | case_id: int; body: ExtendHoldIn | extend_hold (services/provider/app/main.py:870) |
| POST | `/cases/{case_id}/info-requests` | Request info. | _get_case(); _require_doctor → require_own(clinician, what=act on incoming referrals) | case_id: int; body: InfoIn | request_info (services/provider/app/main.py:753) |
| PUT | `/cases/{case_id}/response` | Save response. | _get_case(); _require_doctor → require_own(clinician, what=act on incoming referrals) | case_id: int; body: ResponseIn | save_response (services/provider/app/main.py:789) |
| POST | `/cases/{case_id}/response/send` | The receiving doctor signs off and returns the response in one step. | _get_case(); _require_doctor → require_own(clinician, what=act on incoming referrals) | case_id: int; body: SendIn | send_response (services/provider/app/main.py:817) |
| POST | `/outbox/{item_id}/retry` | Retry outbox. | require_own(clinician, diagnostics_staff, institution_admin, what=retry delivery) | item_id: int | retry_outbox (services/provider/app/main.py:1090) |

#### records

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| GET | `/outbound-copies` | Our own copies for one referral (doctors and staff here). | require_own(clinician, clinic_staff, what=read our copies of sent referrals) | referral_id: str | list_sent_copies (services/provider/app/main.py:553) |
| GET | `/patients/{local_id}/activity` | When the patient was last seen here (visit, test or scan). Used to choose the most recently visited institution of each kind. | decide_access(); forbid() | local_id: str | patient_activity (services/provider/app/main.py:348) |

#### sharing

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| POST | `/sharing/grants` | Created when this institution's own staff approve a patient-link request: the requesting institution may then read this patient's referral-relevant records. | require_own(clinic_staff, institution_admin, what=share patient records) | body: ShareIn | share_records (services/provider/app/main.py:301) |

#### source administration

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| GET | `/admin/audit` | List audit. | require_admin() | limit: int | list_audit (libs/common/refcommon/sourcekit.py:280) |
| GET | `/admin/grants` | List grants. | require_admin() |  | list_grants (libs/common/refcommon/sourcekit.py:222) |
| POST | `/admin/grants` | Create grant. | require_admin() | body: GrantIn | create_grant (libs/common/refcommon/sourcekit.py:227) |
| POST | `/admin/grants/{grant_id}/extend` | Only this source's administrator can extend. Counted from now, capped at MAX_GRANT_DAYS. | require_admin() | grant_id: int; body: ExtendIn | extend_grant (libs/common/refcommon/sourcekit.py:248) |
| POST | `/admin/grants/{grant_id}/revoke` | Revoke grant. | require_admin() | grant_id: int | revoke_grant (libs/common/refcommon/sourcekit.py:267) |
