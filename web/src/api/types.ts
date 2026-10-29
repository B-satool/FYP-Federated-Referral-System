export type Me = {
  id: string;
  username: string;
  name: string;
  institution_id: string | null;
  institution_name: string | null;
  institution_kind: "clinic" | "hospital" | "laboratory" | "platform" | null;
  department: string | null;
  department_name: string | null;
  department_kind: "clinical" | "laboratory" | "imaging" | "cardiac" | null;
  roles: string[];
  account_status: string;
  /** role templates the user holds, their home route and menu (from rules/roles/templates.v2.json) */
  templates?: string[];
  home?: string | null;
  menu?: MenuItem[];
  /** from the templates: content (opens records on their own device) | titles_only | none */
  record_visibility?: "content" | "titles_only" | "none";
  /** the role holds encryption keys (doctors, patients) */
  holds_keys?: boolean;
  scopes?: string[];
};

export type MenuItem = { key: string; route: string; label: string; group: string };

export type Department = { name: string; kind: "clinical" | "laboratory" | "imaging" | "cardiac" };
export type Institution = { name: string; kind: "clinic" | "hospital" | "laboratory"; departments: string[] };
export type Practitioner = { name: string; institution: string; department: string; username?: string };
export type RequestKind = "referral" | "test";

export type ReferenceData = {
  institutions: Record<string, Institution>;
  departments: Record<string, Department>;
  /** words in a procedure name -> features to pre-tick */
  procedure_hints: Record<string, string[]>;
  procedure_tags: Record<string, string>;
  urgencies: Record<string, { label: string; detail: string }>;
  urgency_note: string;
  statuses: Record<string, string>;
  test_statuses: Record<string, string>;
  practitioners: Practitioner[];
  test_suggestions: { test: string; category: string; body_area?: string }[];
  diagnostic_categories: Record<string, string>;
  drug_classes: Record<string, string>;
  referral_window_days: number;
  flag_disclaimer: string;
  llm_configured: boolean;
  limits: { max_upload_mb: number; max_pages: number; formats: string[]; language: string };
};

export type PatientIndexEntry = {
  institution_id: string;
  local_patient_id: string;
  given: string;
  family: string;
  name: string;
  birth_date: string;
  sex: string;
  cnic: string | null;
  phone: string | null;
  city: string | null;
};

export type Referral = {
  id: number;
  reference: string;
  /** referral = to a doctor or department; test = tests or scans only */
  kind: RequestKind;
  status: string;
  status_label: string;
  row_version: number;
  /** staff retrieved the records and uploaded the papers; the doctor can now review the packet */
  prepared_by: string | null;
  prepared_at: string | null;
  /** the doctor reviewed the packet's clinical content; staff can send */
  packet_reviewed_by: string | null;
  packet_reviewed_at: string | null;
  /** staff view: the reason, notes, procedure and other clinical content are left out (null) */
  redacted?: boolean;
  patient: { institution_id: string; local_patient_id: string; name: string; birth_date: string | null; sex: string | null; cnic: string | null };
  source_institution: string;
  source_institution_name: string;
  source_department: string | null;
  source_department_name: string | null;
  requesting_doctor_id: string | null;
  requesting_doctor_name: string;
  /** null for a test request */
  destination_institution: string | null;
  destination_name: string | null;
  destination_department: string | null;
  destination_department_name: string | null;
  destination_doctor: string | null;
  reason: string | null;
  consultation_notes: string | null;
  urgency: string;
  urgency_label: string;
  urgency_detail: string | null;
  procedure_status: "planned" | "none" | "unknown";
  planned_procedure: string | null;
  procedure_tags: string[];
  procedure_tag_labels: string[];
  procedure_label: string;
  requested_at: string | null;
  created_by: string;
  amendment_open: boolean;
  current_package_version: number | null;
  submitted_package_version: number | null;
  delivery_status: string;
  meds_checked_by: string | null;
  meds_checked_at: string | null;
  patient_informed_by: string | null;
  patient_informed_at: string | null;
  patient_informed_note: string | null;
  cancel_reason: string | null;
  decline_reason: string | null;
  acknowledged_at: string | null;
  accepted_at: string | null;
  closed_at: string | null;
  closed_by: string | null;
  /** the shared records are held until this time, then removed (null: no limit yet) */
  working_set_expires_at: string | null;
  working_set_purged_at: string | null;
  /** the receiving doctor marked the referral complete */
  receiver_completed_at: string | null;
  receiver_completed_by: string | null;
  created_at: string;
  updated_at: string;
};

/** GET /referrals rows: a test request lists where its orders go. */
export type ReferralRow = Referral & {
  test_destinations?: { institution_id: string; institution_name: string; department_name: string | null; tests: string[] }[];
};

export type Retrieval = {
  id: number;
  source_institution: string;
  source_name: string;
  institution_kind: string | null;
  last_activity: string | null;
  window_start: string | null;
  local_patient_id: string;
  link_id: number | null;
  status: string;
  record_count: number;
  new_count: number;
  duplicate_count: number;
  invalid_count: number;
  withheld: string[];
  message: string;
  retryable: boolean;
  requested_by: string;
  requested_at: string;
};

export type SourceOverview = {
  institution_id: string;
  name: string;
  kind: string;
  own: boolean;
  destination: boolean;
  linked: boolean;
  local_patient_id?: string;
  link_id?: number | null;
  link_states?: string[];
  pending_link_id?: number | null;
  /** the latest records request to this institution (spec v4: under consent, answered encrypted) */
  latest: RecordRequestOut | null;
};

/** One institution's answer to a records request. A refusal or "could not be reached" is never "no records". */
export type RecordRequestOut = {
  id: number;
  custodian: string;
  custodian_name: string;
  status: "sent" | "answered" | "partial" | "refused" | "pending_manual_review" | "no_records" | "unavailable" | "not_linked" | "failed";
  status_text: string;
  refusals: { reason: string; categories: string[]; message: string }[];
  item_count: number;
  message: string;
  requested_by: string;
  requested_at: string;
  answered_at: string | null;
  policy_version: string | null;
};

export type ConsentSummary = {
  id: number;
  reference: string;
  status: "requested" | "granted" | "declined" | "revoked" | "expired" | "withdrawn";
  custodians_requested: { institution_id: string; name: string }[];
  custodians_granted: { institution_id: string; name: string }[];
  sensitive_specific: string[];
  requested_by: string;
  requested_at: string;
  period_start: string | null;
  period_end: string | null;
  decided_at: string | null;
  decline_reason: string | null;
  revoked_at: string | null;
  signed: boolean;
};

export type ReadinessItem = { key: string; label: string; ok: boolean; detail: string; who: "staff" | "doctor" | "system"; tab: string | null; blocking: boolean };

export type PatientLink = {
  id: number;
  requester_institution: string;
  requester_name: string;
  requester_local_id: string;
  target_institution: string;
  target_name: string;
  target_local_id: string | null;
  patient_name: string;
  patient_birth_date: string | null;
  patient_sex: string | null;
  patient_cnic: string | null;
  referral_id: number | null;
  purpose: string;
  /** records = asking for records (match or "no record here"); intake = arriving with a referral or order (match or register new) */
  kind: "records" | "intake";
  status: "requested" | "verified" | "rejected" | "invalidated";
  requested_by: string;
  requested_at: string;
  decided_by: string | null;
  decided_at: string | null;
  decision_note: string | null;
  registered_new: boolean;
  invalidated_by: string | null;
  invalidated_at: string | null;
  invalidation_reason: string | null;
  events?: { action: string; actor: string; institution_id: string | null; note: string; created_at: string }[];
};

export type LookupCandidate = PatientIndexEntry & { compare: { cnic: boolean; name: boolean; birth_date: boolean; sex: boolean } };

export type ResultValue = { test: string; value: string; unit?: string | null; reference?: string | null; flag?: string | null };

export type Diagnostic = {
  id: number;
  reference: string;
  referral_id: number;
  category: string;
  category_label: string;
  test: string;
  body_area: string | null;
  clinical_question: string;
  urgency: string;
  urgency_label: string;
  destination_institution: string;
  destination_name: string;
  destination_department: string;
  destination_department_name: string;
  status: string;
  requested_by: string;
  sent_by: string | null;
  sent_at: string | null;
  reject_reason: string | null;
  scheduled_for: string | null;
  report: { findings?: string; impression?: string; report_text?: string; values?: ResultValue[]; reported_by?: string; reported_at?: string } | null;
  local_patient_id: string | null;
  /** images or files returned with the report; fetch /diagnostics/{id}/attachments/{n} */
  attachments: { n: number; filename: string; content_type: string; size: number }[];
  seen_by: string | null;
  seen_at: string | null;
  history: { status: string; by: string; at: string; reason?: string; scheduled_for?: string }[];
  created_at: string;
  updated_at?: string;
  referral_reference?: string;
  patient_name?: string;
};

export type Clarification = {
  id: number;
  question: string;
  asked_by: string;
  asked_at: string;
  status: string;
  answer: string | null;
  answered_by: string | null;
  answered_at: string | null;
};

export type ReferralDetail = Referral & {
  sources: SourceOverview[];
  readiness: ReadinessItem[] | null;
  /** signed versions, newest first (spec v4 5.8) */
  packages: SignedVersion[];
  links: PatientLink[];
  diagnostics: Diagnostic[];
  clarifications: Clarification[];
  consent: ConsentSummary | null;
  record_requests: RecordRequestOut[];
  encrypted_item_count: number;
  /** the keys an approval re-wraps to; verified on the device against pinned keys */
  recipient_keys?: { department: import("../crypto/directory").DirectoryRow | null; patient: import("../crypto/directory").DirectoryRow | null };
};

export type SignedVersion = {
  version: number; signed_by: string; signed_at: string; manifest_sha256: string; signer_key_id: string;
  item_count: number; superseded: boolean; sent: boolean;
};

export type Evidence = {
  id: number;
  /** staff view: only the record's title, source, date and packet status */
  redacted?: boolean;
  origin: "source" | "document" | "manual";
  category: string;
  display: string;
  original: Record<string, unknown>;
  current: Record<string, unknown>;
  source_institution: string;
  source_name: string;
  source_record_type: string | null;
  source_record_id: string | null;
  source_record_version: string | null;
  link_id: number | null;
  clinical_time: string | null;
  retrieved_at: string;
  document_id: number | null;
  page: number | null;
  region: { x: number; y: number; w: number; h: number } | null;
  source_text: string | null;
  confidence: Record<string, unknown> | null;
  review_state: string;
  verification_status: string;
  verified_by: string | null;
  verified_at: string | null;
  selected: boolean;
  /** selected by the rule-based default (current conditions, medicines, last 6 months) */
  in_default: boolean;
  selection_source: "default" | "ai" | "staff" | null;
  selected_by: string | null;
  selected_at: string | null;
  ai_recommendation: "include" | "exclude" | "optional" | null;
  ai_relevance: "high" | "medium" | "low" | null;
  ai_reason: string | null;
  superseded_by: number | null;
  author: string | null;
  row_version: number;
};

export type SelectionRun = {
  id: number;
  status: "completed" | "unavailable" | "rejected" | "nothing_to_review";
  provider: string | null;
  model: string | null;
  prompt_version: string;
  prompt_hash: string;
  item_count: number;
  truncated: boolean;
  missing: string[];
  error: string | null;
  created_by: string;
  created_at: string;
};

export type SelectionStatus = {
  run: SelectionRun | null;
  counts: { retrieved: number; selected: number; staff_overrides_of_ai: number };
  llm_configured: boolean;
  prompt_version: string;
};

export type EvidenceDetail = Evidence & {
  fhir: Record<string, unknown> | null;
  revisions: { id: number; action: string; prior_value: unknown; new_value: unknown; prior_state: string | null; new_state: string | null; editor: string; note: string; created_at: string }[];
  versions: { id: number; version: string | null; superseded_by: number | null; display: string; retrieved_at: string }[];
  document: { id: number; filename: string; doc_type: string } | null;
};

export type DocumentSummary = {
  id: number;
  referral_id: number;
  original_filename: string;
  doc_type: string;
  declared_type: string;
  detected_type: string;
  size_bytes: number;
  page_count: number;
  status: string;
  error: string | null;
  uploaded_by: string;
  created_at: string;
  deleted: boolean;
};

export type Job = { id: string; kind: string; status: string; error: string | null; result: Record<string, unknown> | null };

export type DocumentDetail = {
  document: DocumentSummary;
  extraction: {
    id: number;
    status: string;
    error: string | null;
    text_source: string | null;
    ocr_engine: string | null;
    ocr_engine_version: string | null;
    extractor: string | null;
    extractor_version: string | null;
    notes: string[];
    duration_ms: number;
    pages: { page: number; source: string; image_key: string; mean_ocr_confidence: number | null; lines: { text: string; bbox: { x: number; y: number; w: number; h: number } | null }[] }[];
    raw_text: string;
    created_at: string;
  } | null;
  fields: Evidence[];
};

export type MedicationEntry = {
  id: number;
  evidence_id: number;
  record_kind: string;
  original_name: string;
  brand: string | null;
  strength: string | null;
  dose: string | null;
  route: string | null;
  frequency: string | null;
  start_date: string | null;
  over_the_counter: boolean;
  source_label: string;
  ingredient: string | null;
  drug_class: string | null;
  drug_class_label: string | null;
  mapping_status: string;
  mapping_note: string | null;
  /** a DRAP brand name used for different products: pick the one on the pack (known = in the app's medicine list) */
  mapping_choices?: { ingredient: string; company: string; drap_reg_no: string; strength: string; dosage_form: string; known?: boolean }[] | null;
  duplicate_of: number | null;
  dose_differs: boolean;
  excluded: boolean;
  excluded_by: string | null;
  excluded_reason: string | null;
};

export type FlagDecision = "reviewed" | "ignore" | "research";

/** Where a flag came from, shown beside it. */
export type FlagSource = {
  severity?: string | null;
  ingredients?: string[];
  source_type?: string | null;
  source_name?: string | null;
  source_ref?: string | null;
  source_version?: string | null;
  source_quote?: string | null;
  auto_generated?: boolean;
};

export type Flag = FlagSource & {
  id: number;
  flag_key: string;
  version: number;
  kind: "confirmed" | "interaction" | "label_warning" | "unrecognised_medicine" | "interactions_not_checked" | "procedure_not_checked" | "records_incomplete";
  requires_decision: boolean;
  title: string;
  message: string;
  medication: string | null;
  drug_class: string | null;
  drug_class_label: string | null;
  source_label: string | null;
  rule_id: string | null;
  rule_version: number | null;
  evidence_ids: number[];
  status: string;
  created_at: string;
  acknowledgements: { id: number; side: string; by: string; institution_id: string; flag_version: number; decision: FlagDecision; note: string; created_at: string }[];
};

export type MedicationView = {
  entries: MedicationEntry[];
  excluded: MedicationEntry[];
  meds_checked: { by: string | null; at: string | null; note: string | null };
  evaluation: { id: number; status: string; outcome: string | null; summary_message: string | null; trigger: string; context: Record<string, unknown>; error: string | null; created_at: string } | null;
  flags: Flag[];
  flag_history: Flag[];
  /** possible clashes for pairs with no DDInter entry; never flags */
  ai_suggestions: AiSuggestion[];
  ai_label: string;
  /** staff view: counts only, no medicine names or flags */
  redacted?: boolean;
  medicine_count?: number;
  flag_count?: number;
  flags_awaiting_doctor?: number;
};

export type AiSuggestion = {
  pair_key: string;
  ingredients: string[];
  score: number;
  reason: string;
  model_version: string;
  data_version?: string;
  label?: string;
  review: { decision: "ignore" | "research"; note: string; by: string; at: string } | null;
};

export type BriefStatement = {
  id: string;
  text: string;
  evidence_ids: number[];
  author_kind: string;
  author_name: string | null;
  verification: string;
  /** where it is recorded, when, and grouping (a lab panel) */
  source?: string | null;
  date?: string | null;
  group?: string | null;
};
export type BriefSection = { key: string; title: string; statements: BriefStatement[] };
export type BriefPreview = { sections: BriefSection[]; limitations: string[]; evidence_ids: number[] };

export type ConsultationResponse = {
  id: number;
  package_version: number;
  content: { assessment?: string; plan?: string; instructions_for_clinic?: string; appointment?: string };
  specialist_name: string;
  returned_at: string;
  received_at: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
  review_note: string | null;
};

export type FollowupTask = {
  id: number;
  referral_id: number;
  description: string;
  specified_by: string;
  assignee_name: string | null;
  due_date: string | null;
  status: string;
  outcome: string | null;
  completed_by: string | null;
  completed_at: string | null;
  created_by: string;
  created_at: string;
};

export type ReferralEvent = {
  id: number;
  event_type: string;
  from_status: string | null;
  to_status: string | null;
  actor: string;
  institution_id: string | null;
  institution_name: string | null;
  detail: Record<string, unknown>;
  created_at: string;
};

export type AuditEvent = {
  id: number;
  actor_id: string;
  actor_name: string;
  institution_id: string | null;
  action: string;
  target_type: string;
  target_id: string;
  referral_id: number | null;
  outcome: string;
  detail: Record<string, unknown>;
  created_at: string;
};

export type Notification = { id: number; kind: string; title: string; body: string; link: string | null; referral_id: number | null; created_at: string; read_at: string | null; personal: boolean };

export type WorkQueue = {
  role: "doctor" | "staff";
  notifications: Notification[];
  drafts?: Referral[];
  flags_to_acknowledge?: (Referral & { unacknowledged: number })[];
  responses_to_review?: (Referral & { specialist_name: string; received_at: string })[];
  results_to_see?: Diagnostic[];
  in_progress?: Referral[];
  to_prepare?: (Referral & { done: number; total: number; next_step: ReadinessItem | null; ready: boolean })[];
  link_requests?: { id: number; patient_name: string; requester: string; requested_at: string; purpose: string }[];
  tests_to_send?: Diagnostic[];
  delivery_problems?: Referral[];
  follow_up?: (Referral & { patient_informed: boolean; open_tasks: number })[];
  info_requests: { id: number; referral_id: number; referral_reference: string; patient_name: string; question: string; asked_by: string; asked_at: string }[];
};

export type Rule = {
  id: number;
  rule_id: string;
  version: number;
  title: string;
  drug_class: string;
  drug_class_label: string;
  procedure_tags: string[];
  procedure_tag_labels: string[];
  message: string;
  rationale: string;
  reference: string;
  status: "draft" | "approved" | "rejected" | "retired" | "superseded";
  content_hash: string;
  intact: boolean;
  created_by: string;
  created_at: string;
  decided_by: string | null;
  decided_at: string | null;
  reference_checked: string | null;
  decision_note: string | null;
  matching_procedures: string[];
};

export type RulesView = {
  rules: { rule_id: string; versions: Rule[] }[];
  drug_classes: Record<string, string>;
  procedure_tags: Record<string, string>;
  can_approve: boolean;
  can_edit: boolean;
};

export type MedicineNamesView = {
  classes: Record<string, string>;
  names: { id: number; display: string; ingredient: string; drug_class: string; kind: string; added_by: string }[];
  ingredients: string[];
  can_edit: boolean;
};

// ---- institution systems (receiving hospital and diagnostics departments)
export type Case = {
  id: number;
  central_referral_id: string;
  sender_institution: string;
  sender_name: string;
  department: string;
  requested_doctor: string | null;
  patient_name: string;
  patient_birth_date: string | null;
  patient_sex: string | null;
  patient_cnic: string | null;
  /** set once staff here confirm the patient */
  local_patient_id: string | null;
  /** central intake link request to confirm the patient (null if already known here) */
  link_request_id: number | null;
  urgency: string;
  /** received -> acknowledged -> assigned -> accepted | declined -> responded */
  status: string;
  latest_version: number;
  acknowledged_by: string | null;
  acknowledged_at: string | null;
  assigned_doctor: string | null;
  assigned_by: string | null;
  assigned_at: string | null;
  assign_note: string | null;
  decision: string | null;
  decision_by: string | null;
  decision_at: string | null;
  decline_reason: string | null;
  /** the referred doctor has finished; the shared records are removed 72 hours later */
  completed_by: string | null;
  completed_at: string | null;
  /** until when the shared records are kept (30 days after acceptance, extendable; 72 hours after completion) */
  hold_until: string | null;
  /** set once the shared records were removed here (the decision, questions and response are kept) */
  shared_removed_at: string | null;
  received_at: string;
  updated_at: string;
  open_info_requests: number;
};

export type PackageEnvelope = {
  referral_id: string;
  package_version: number;
  sender_institution: string;
  sender_department: string | null;
  destination_department: string;
  destination_doctor: string | null;
  urgency: string;
  reason: string;
  procedure_status: string;
  procedure_label: string | null;
  patient: {
    name: string;
    birth_date: string | null;
    sex: string | null;
    cnic?: string | null;
    sender_name?: string;
    identifier?: { institution_id: string; local_patient_id: string };
    local_patient_id?: string | null;
    link_request_id?: number | null;
  };
  requesting_doctor: { name: string; institution: string; department: string | null; requested_at: string | null };
  brief_sections: BriefSection[];
  medication_flags: LetterFlag[];
  medication_evaluation: { status: string; outcome: string | null; summary: string | null };
  limitations: string[];
  /** labelled "AI suggestion, not verified"; never flags */
  ai_suggestions?: (Omit<AiSuggestion, "review"> & { decision?: AiSuggestion["review"] })[];
  selection?: Record<string, unknown>;
  sent_by: string;
  sent_at: string;
  content_hash: string;
  /** set once the working set has ended: only identifiers and the fingerprint remain */
  purged?: boolean;
  note?: string;
};

export type PackageView = {
  version: number;
  sent_by: string;
  sent_at: string;
  content_hash: string;
  superseded: boolean;
  /** null in the staff view */
  envelope: PackageEnvelope | null;
  manifest: Record<string, unknown> | null;
  redacted?: boolean;
  content_purged_at: string | null;
};

export type CopyCheck = { package_version: number; content_hash: string; result: "match" | "mismatch" | "unusable_copy" | "no_copy"; message: string; copy?: PackageEnvelope | null };

export type AccessGrant = {
  id: number;
  grantee_institution: string;
  local_patient_id: string;
  categories: string[];
  status: string;
  basis: string;
  granted_by: string;
  created_at: string;
  revoked_by: string | null;
  revoked_at: string | null;
  expires_at: string | null;
  referral_ref: string | null;
  state: "active" | "expired" | "revoked" | "legacy_no_expiry";
};

export type RoleTemplate = { template_id: string; name: string; description: string; roles: string[]; institution_kinds: string[]; default_grant_days?: number; home: string; menu: string[] };

export type LetterFlag = FlagSource & {
  flag_id: number;
  version: number;
  kind: string;
  title: string;
  message: string;
  medication: string | null;
  source_label: string | null;
  rule_id: string | null;
  acknowledged: { by: string; at: string; decision?: FlagDecision; note?: string } | null;
};

export type RecordTitle = { title: string; kind?: string; category: string; source_institution: string | null; date: string | null };

/** What the receiving hospital's system holds for a sent version (spec v4, D2): administrative data, record titles and
 * the signed manifest's hash. The content is opened from the platform on the doctor's device. */
export type ReferralNotice = {
  referral_id: string;
  package_version: number;
  sender_institution: string;
  sender_name: string;
  destination_department: string;
  destination_doctor: string | null;
  urgency: string;
  reason: string;
  patient: { name: string; birth_date: string | null; sex: string | null; cnic?: string | null; local_patient_id?: string | null; link_request_id?: number | null };
  requesting_doctor: { name: string; id?: string; institution: string; department: string | null };
  titles: { item_id: string; kind: string; category: string | null; label: string; date: string | null; source_institution: string | null; sensitive: boolean }[];
  manifest_sha256: string;
  signed_by: { subject_id: string; sig_key_id: string };
  sent_by: string;
  sent_at: string;
  purged?: boolean;
  note?: string;
};

export type CaseDetail = {
  case: Case;
  /** intake staff view: the notice's titles only */
  redacted?: boolean;
  packages: { version: number; received_at: string; content_hash: string; envelope: ReferralNotice | null; record_titles: RecordTitle[] }[];
  info_requests: { id: number; package_version: number; question: string | null; status: string; created_by: string; created_at: string; answer: string | null; answered_by: string | null; answered_at: string | null }[];
  responses: { id: number; package_version: number; content: ConsultationResponse["content"]; status: string; drafted_by: string; row_version: number; returned_by: string | null; returned_at: string | null }[];
  results: { id: number; received_at: string; purged?: boolean; order_ref: string; test: string; performed_by_institution: string; report_text: string; values: { test: string; value: string; unit?: string; reference?: string; flag?: string }[]; reported_by: string; reported_at: string }[];
};

export type Order = {
  id: number;
  order_ref: string;
  central_referral_id: string;
  sender_institution: string;
  sender_name: string;
  department: string;
  category: string;
  test: string;
  body_area: string | null;
  clinical_question: string;
  urgency: string;
  patient_name: string;
  patient_birth_date: string | null;
  patient_sex: string | null;
  patient_cnic: string | null;
  local_patient_id: string | null;
  /** central intake link request to confirm the patient (null if already known here) */
  link_request_id: number | null;
  requested_by: string;
  status: string;
  reject_reason: string | null;
  scheduled_for: string | null;
  report_text: string | null;
  findings: string | null;
  impression: string | null;
  values: ResultValue[];
  reported_by: string | null;
  reported_at: string | null;
  history: { status: string; by: string; at: string; reason?: string; scheduled_for?: string }[];
  /** only on GET /orders/{id}; fetch /orders/{id}/attachments/{attachment id} */
  attachments: { id: number; filename: string; content_type: string; size: number }[];
  received_at: string;
  updated_at: string;
};
