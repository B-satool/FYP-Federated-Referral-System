export type Me = {
  id: string;
  username: string;
  name: string;
  institution_id: string | null;
  institution_name: string | null;
  institution_kind: "clinic" | "laboratory" | "specialist" | "platform" | null;
  roles: string[];
  account_status: string;
};

export type ReferenceData = {
  institutions: Record<string, { name: string; kind: string }>;
  specialties: Record<string, string>;
  procedures: Record<string, string>;
  priorities: string[];
  statuses: Record<string, string>;
  llm_configured: boolean;
  llm_model: string | null;
  limits: { max_upload_mb: number; max_pages: number; formats: string[]; language: string };
};

export type PatientSummary = {
  institution_id: string;
  local_patient_id: string;
  given: string;
  family: string;
  birth_date: string;
  sex: string;
  city?: string;
  synthetic: boolean;
};

export type Retrieval = {
  id: number;
  source_institution: string;
  source_name: string;
  local_patient_id: string;
  link_id: number | null;
  status: "successful" | "empty" | "partial" | "denied" | "unavailable" | "invalid";
  record_count: number;
  new_count: number;
  duplicate_count: number;
  invalid_count: number;
  withheld: string[];
  message: string;
  retryable: boolean;
  attempts: number;
  duration_ms: number;
  requested_by: string;
  requested_at: string;
};

export type SourceOverview = {
  source_institution: string;
  source_name: string;
  linked: boolean;
  local_patient_id: string | null;
  link_id: number | null;
  link_states?: string[];
  latest: Retrieval | null;
  message?: string;
};

export type ChecklistRow = {
  id: string;
  title: string;
  state: "present" | "missing" | "unresolved" | "conflict" | "not_applicable" | "limitation_recorded";
  blocking: boolean;
  override_allowed: boolean;
  open_items: number[];
};

export type Blocker = { type: string; id?: number; message: string; how: string };

export type PackageSummary = {
  version: number;
  approved_by: string;
  approved_at: string;
  content_hash: string;
  superseded: boolean;
  delivery_key: string;
  overrides: { message: string; rationale: string }[];
};

export type Referral = {
  id: number;
  reference: string;
  status: string;
  status_label: string;
  row_version: number;
  patient: { institution_id: string; local_patient_id: string; name: string; birth_date: string | null; sex: string | null };
  source_institution: string;
  source_institution_name: string;
  destination_institution: string;
  destination_name: string;
  specialty: string;
  reason: string;
  priority: string | null;
  planned_procedure: string | null;
  procedure_status: "not_stated" | "known" | "unknown";
  procedure_label: string;
  created_by: string;
  referring_clinician_id: string | null;
  referring_clinician_name: string | null;
  amendment_open: boolean;
  current_package_version: number | null;
  submitted_package_version: number | null;
  delivery_status: string;
  cancel_reason: string | null;
  decline_reason: string | null;
  acknowledged_at: string | null;
  accepted_at: string | null;
  closed_at: string | null;
  closed_by: string | null;
  created_at: string;
  updated_at: string;
};

export type ReferralDetail = Referral & {
  sources: SourceOverview[];
  checklist: ChecklistRow[];
  approval_blockers: Blocker[];
  packages: PackageSummary[];
  verified_links: { institution_id: string; local_patient_id: string; link_id: number }[];
};

export type Evidence = {
  id: number;
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
  superseded_by: number | null;
  author: string | null;
  row_version: number;
  patient_ref: { institution_id: string; local_patient_id: string };
};

export type EvidenceDetail = Evidence & {
  fhir: Record<string, unknown> | null;
  revisions: {
    id: number;
    action: string;
    prior_value: Record<string, unknown> | null;
    new_value: Record<string, unknown> | null;
    prior_state: string | null;
    new_state: string | null;
    editor: string;
    note: string;
    created_at: string;
  }[];
  versions: { id: number; version: string; superseded_by: number | null; display: string; retrieved_at: string }[];
  document: { id: number; filename: string; doc_type: string } | null;
};

export type Job = {
  id: string;
  kind: string;
  status: "queued" | "running" | "completed" | "failed";
  referral_id: number | null;
  document_id: number | null;
  result: Record<string, unknown> | null;
  error: string | null;
  created_by: string;
  created_at: string;
  finished_at: string | null;
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

export type OcrLine = { i: number; page: number; text: string; bbox: { x: number; y: number; w: number; h: number } | null; ocr_confidence: number | null };

export type DocumentDetail = {
  document: DocumentSummary;
  extraction: null | {
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
    pages: { page: number; source: string; image_key: string; mean_ocr_confidence: number | null; lines: OcrLine[] }[];
    raw_text: string;
  };
  fields: Evidence[];
  jobs: Job[];
};

export type MedicationEntry = {
  id: number;
  evidence_id: number;
  record_kind: string;
  original_name: string;
  strength: string | null;
  dose: string | null;
  route: string | null;
  frequency: string | null;
  start_date: string | null;
  end_date: string | null;
  source_status: string | null;
  source_label: string;
  ingredient: string | null;
  ingredient_code: string | null;
  drug_class: string | null;
  class_code: string | null;
  mapping_source: string | null;
  mapping_version: string | null;
  mapping_status: string;
  mapping_note: string | null;
  use_status: string;
  use_verified_by: string | null;
  use_verified_at: string | null;
  use_note: string | null;
};

export type FlagReview = {
  id: number;
  side: "referring" | "specialist";
  action: "reviewed" | "request_clarification";
  reviewer: string;
  institution_id: string;
  flag_version: number;
  package_version: number | null;
  clarification_id: number | null;
  note: string;
  created_at: string;
};

export type MedicationFlag = {
  id: number;
  flag_key: string;
  version: number;
  kind: "confirmed" | "possible_use" | "procedure_context_required" | "ambiguous_mapping" | "history_incomplete";
  title: string;
  message: string;
  medication: string | null;
  drug_class: string | null;
  current_use_status: string | null;
  source_label: string | null;
  rule_id: string | null;
  rule_version: number | null;
  evidence_ids: number[];
  status: string;
  created_at: string;
  superseded_at: string | null;
  reviews: FlagReview[];
};

export type MedicationsResponse = {
  entries: MedicationEntry[];
  evaluation: null | {
    id: number;
    status: string;
    outcome: string | null;
    summary_message: string | null;
    trigger: string;
    rule_versions: Record<string, number>;
    mapping_version: string | null;
    context: Record<string, unknown>;
    error: string | null;
    changed_flags: number;
    created_at: string;
  };
  flags: MedicationFlag[];
  flag_history: MedicationFlag[];
};

export type ReviewItem = {
  id: number;
  item_key: string;
  kind: "missing" | "unresolved" | "discrepancy" | "link_invalidated";
  checklist_item_id: string | null;
  title: string;
  detail: string;
  evidence_ids: number[];
  blocking: boolean;
  override_allowed: boolean;
  clinical: boolean;
  status: string;
  resolution: string | null;
  resolved_by: string | null;
  resolved_at: string | null;
  created_at: string;
};

export type Clarification = {
  id: number;
  referral_id: number;
  referral_reference?: string;
  patient_name?: string | null;
  patient_ref_at_assignee?: string | null;
  overdue?: boolean;
  review_item_id: number | null;
  flag_id: number | null;
  origin: "clinic" | "specialist";
  question: string;
  assignee_institution: string;
  assignee_institution_name: string;
  assignee_role: string | null;
  status: string;
  due_date: string | null;
  created_by: string;
  created_at: string;
  response_text: string | null;
  response_document_ids: number[];
  answered_by: string | null;
  answered_at: string | null;
  resolved_by: string | null;
  resolved_at: string | null;
  resolution_note: string | null;
  package_version: number | null;
};

export type BriefStatement = {
  id: string;
  text: string;
  evidence_ids: number[];
  author_kind: "model" | "clinician" | "template";
  author_name: string | null;
  edited_by: string | null;
  verification: string;
};

export type BriefSection = { key: string; title: string; statements: BriefStatement[] };

export type Brief = {
  id: number;
  version: number;
  kind: string;
  sections: BriefSection[];
  limitations: string[];
  evidence_ids: number[];
  model: string | null;
  prompt_version: string | null;
  based_on_version: number | null;
  created_by: string;
  created_at: string;
};

export type BriefResponse = {
  latest: Brief | null;
  versions: { version: number; kind: string; model: string | null; created_by: string; created_at: string }[];
  llm_configured: boolean;
  llm_model: string | null;
  section_titles: Record<string, string>;
};

export type ConsultationResponse = {
  id: number;
  package_version: number;
  content: Record<string, string>;
  specialist_name: string;
  approved_at: string;
  received_at: string;
  receipt_recorded_by: string | null;
  receipt_recorded_at: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  review_note: string | null;
};

export type FollowupTask = {
  id: number;
  referral_id: number;
  referral_reference?: string;
  overdue?: boolean;
  description: string;
  specified_by: string;
  assignee_name: string | null;
  assignee_role: string | null;
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

export type PatientLink = {
  id: number;
  a_institution: string;
  a_local_id: string;
  b_institution: string;
  b_local_id: string;
  status: string;
  basis: string;
  match_check: Record<string, unknown> | null;
  proposed_by: string;
  proposed_at: string;
  verified_by: string | null;
  verified_at: string | null;
  invalidated_by: string | null;
  invalidated_at: string | null;
  invalidation_reason: string | null;
  events?: { action: string; actor: string; note: string; detail: Record<string, unknown>; created_at: string }[];
};
