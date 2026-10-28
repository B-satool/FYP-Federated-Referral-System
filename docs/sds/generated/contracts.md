## Exchange contracts (`libs/common/refcommon/exchange.py`)

Project API contracts between the central platform and the institution services. They are not standard FHIR resources; a FHIR R4 4.0.1 Bundle travels inside the referral package unchanged.

| Constant | Value |
|---|---|
| `PACKAGE_ENVELOPE_VERSION` | `referral-package/2.0` |
| `ORDER_ENVELOPE_VERSION` | `diagnostic-order/1.0` |
| `EVENT_ENVELOPE_VERSION` | `provider-event/1.0` |
| `CONTRACT_NOTE` | `Project API contract (not a standard FHIR resource)` |

### Provider event types

Events an institution service sends to `POST /inbound/provider-events` (deduplicated by `event_key`):

`acknowledged`, `accepted`, `declined`, `info_requested`, `response_returned`, `completed`, `hold_extended`, `order_accepted`, `order_rejected`, `order_scheduled`, `order_done`, `order_reported`

### Outbox message kinds (central → institution)

| Outbox kind | Institution endpoint |
|---|---|
| `deliver_package` | `/inbound/referrals` |
| `deliver_order` | `/inbound/orders` |
| `forward_result` | `/inbound/results` |
| `clarification_answer` | `/inbound/clarification-answers` |
| `sender_copy` | `/outbound-copies` |
| `expire_shared` | `/inbound/referral-expired` |

### Fields covered by the package SHA-256

Transport fields (delivery key, FHIR bundle timestamp) are excluded so a retry never changes the hash: `referral_id`, `package_version`, `sender_institution`, `sender_department`, `destination_institution`, `destination_department`, `destination_doctor`, `urgency`, `reason`, `procedure_status`, `planned_procedure`, `procedure_label`, `patient`, `requesting_doctor`, `brief_sections`, `medication_flags`, `medication_evaluation`, `evidence`, `limitations`, `diagnostic_requests`, `ai_suggestions`, `selection`, `sent_by`, `sent_by_id`, `sent_at`

### `BriefStatement`


| Field | Type | Default | Note |
|---|---|---|---|
| `id` | str | (required) |  |
| `text` | str | (required) |  |
| `evidence_ids` | list[int] | Field(default_factory=list) |  |
| `author_kind` | Literal['model', 'clinician', 'template'] | 'template' |  |
| `author_name` | str \| None | None |  |
| `edited_by` | str \| None | None |  |
| `verification` | Literal['verified', 'unresolved', 'unverified', 'mixed', 'none'] | 'none' |  |
| `source` | str \| None | None |  |
| `date` | str \| None | None |  |
| `group` | str \| None | None |  |

### `BriefSection`


| Field | Type | Default | Note |
|---|---|---|---|
| `key` | str | (required) |  |
| `title` | str | (required) |  |
| `statements` | list[BriefStatement] | Field(default_factory=list) |  |

### `FlagSnapshot`


| Field | Type | Default | Note |
|---|---|---|---|
| `flag_id` | int | (required) |  |
| `version` | int | (required) |  |
| `kind` | str | (required) |  |
| `title` | str | (required) |  |
| `message` | str | (required) |  |
| `medication` | str \| None | None |  |
| `drug_class` | str \| None | None |  |
| `source_label` | str \| None | None |  |
| `rule_id` | str \| None | None |  |
| `rule_version` | int \| None | None |  |
| `evidence_ids` | list[int] | Field(default_factory=list) |  |
| `acknowledged` | dict[str, Any] \| None | None | {by, at, decision: reviewed\|ignore\|research, note} |
| `severity` | str \| None | None |  |
| `ingredients` | list[str] | Field(default_factory=list) |  |
| `source_type` | str \| None | None |  |
| `source_name` | str \| None | None |  |
| `source_ref` | str \| None | None |  |
| `source_version` | str \| None | None |  |
| `source_quote` | str \| None | None |  |
| `auto_generated` | bool | False |  |

### `EvidenceSnapshot`


| Field | Type | Default | Note |
|---|---|---|---|
| `evidence_id` | int | (required) |  |
| `category` | str | (required) |  |
| `display` | str | (required) |  |
| `original` | dict[str, Any] | Field(default_factory=dict) |  |
| `origin` | str | (required) |  |
| `source_institution` | str | (required) |  |
| `source_record_type` | str \| None | None |  |
| `source_record_id` | str \| None | None |  |
| `source_record_version` | str \| None | None |  |
| `clinical_time` | str \| None | None |  |
| `verification_status` | str | (required) |  |
| `document_ref` | dict[str, Any] \| None | None |  |
| `also_recorded_in` | list[str] | Field(default_factory=list) |  |

### `PackageEnvelope`

One sent version of a referral. The requesting doctor authorised the request; staff compiled and sent this exact version (recorded separately).

| Field | Type | Default | Note |
|---|---|---|---|
| `envelope_version` | str | PACKAGE_ENVELOPE_VERSION |  |
| `contract_note` | str | CONTRACT_NOTE |  |
| `delivery_key` | str | (required) |  |
| `referral_id` | str | (required) |  |
| `package_version` | int | (required) |  |
| `sender_institution` | str | (required) |  |
| `sender_department` | str \| None | None |  |
| `destination_institution` | str | (required) |  |
| `destination_department` | str | (required) |  |
| `destination_doctor` | str \| None | None |  |
| `urgency` | str | (required) |  |
| `reason` | str | (required) |  |
| `procedure_status` | str | (required) |  |
| `planned_procedure` | str \| None | None |  |
| `procedure_label` | str \| None | None |  |
| `patient` | dict[str, Any] | (required) |  |
| `requesting_doctor` | dict[str, Any] | (required) |  |
| `brief_sections` | list[BriefSection] | (required) |  |
| `medication_flags` | list[FlagSnapshot] | (required) |  |
| `medication_evaluation` | dict[str, Any] | (required) |  |
| `evidence` | list[EvidenceSnapshot] | (required) |  |
| `limitations` | list[str] | Field(default_factory=list) |  |
| `diagnostic_requests` | list[dict[str, Any]] | Field(default_factory=list) |  |
| `ai_suggestions` | list[dict[str, Any]] | Field(default_factory=list) |  |
| `selection` | dict[str, Any] | Field(default_factory=dict) |  |
| `sent_by` | str | (required) |  |
| `sent_by_id` | str | (required) |  |
| `sent_at` | datetime | (required) |  |
| `content_hash` | str | (required) |  |
| `fhir_bundle` | dict[str, Any] | (required) |  |
| `supersedes_version` | int \| None | None |  |

### `DiagnosticOrder`

A test or scan request sent to a laboratory or imaging department. It is a separate order: it does not depend on the specialist's decision about the referral.

| Field | Type | Default | Note |
|---|---|---|---|
| `envelope_version` | str | ORDER_ENVELOPE_VERSION |  |
| `contract_note` | str | CONTRACT_NOTE |  |
| `order_key` | str | (required) |  |
| `order_ref` | str | (required) |  |
| `referral_id` | str | (required) |  |
| `sender_institution` | str | (required) |  |
| `destination_institution` | str | (required) |  |
| `destination_department` | str | (required) |  |
| `category` | Literal['laboratory', 'imaging', 'cardiac'] | (required) |  |
| `test` | str | (required) |  |
| `body_area` | str \| None | None |  |
| `clinical_question` | str | (required) |  |
| `urgency` | str | (required) |  |
| `patient` | dict[str, Any] | (required) |  |
| `requested_by` | str | (required) |  |
| `requested_at` | datetime | (required) |  |

### `ResultForward`

A returned diagnostic report forwarded to the referral's receiving hospital, so the specialist sees it next to the brief.

| Field | Type | Default | Note |
|---|---|---|---|
| `contract_note` | str | CONTRACT_NOTE |  |
| `forward_key` | str | (required) |  |
| `referral_id` | str | (required) |  |
| `order_ref` | str | (required) |  |
| `test` | str | (required) |  |
| `performed_by_institution` | str | (required) |  |
| `report_text` | str | '' |  |
| `values` | list[dict[str, Any]] | Field(default_factory=list) |  |
| `reported_by` | str | (required) |  |
| `reported_at` | datetime | (required) |  |

### `ProviderEvent`


| Field | Type | Default | Note |
|---|---|---|---|
| `envelope_version` | str | EVENT_ENVELOPE_VERSION |  |
| `contract_note` | str | CONTRACT_NOTE |  |
| `event_key` | str | (required) |  |
| `referral_id` | str | (required) |  |
| `order_ref` | str \| None | None |  |
| `package_version` | int \| None | None |  |
| `type` | ProviderEventType | (required) |  |
| `actor_id` | str | (required) |  |
| `actor_name` | str | (required) |  |
| `institution_id` | str | (required) |  |
| `occurred_at` | datetime | (required) |  |
| `data` | dict[str, Any] | Field(default_factory=dict) |  |

### `ClarificationAnswer`


| Field | Type | Default | Note |
|---|---|---|---|
| `contract_note` | str | CONTRACT_NOTE |  |
| `answer_key` | str | (required) |  |
| `referral_id` | str | (required) |  |
| `provider_clarification_id` | int | (required) |  |
| `answer` | str | (required) |  |
| `answered_by` | str | (required) |  |
| `answered_at` | datetime | (required) |  |

## Request bodies (API input models)

### `CancelIn` (services/central/app/diagnostics/router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `reason` | str | Field(min_length=3) |  |

### `SelectIn` (services/central/app/evidence_router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `selected` | bool | (required) |  |

### `CorrectIn` (services/central/app/evidence_router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `fields` | dict[str, Any] | (required) |  |
| `note` | str | '' |  |
| `expected_row_version` | int | (required) |  |

### `StateIn` (services/central/app/evidence_router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `note` | str | '' |  |

### `VerifyIn` (services/central/app/evidence_router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `note` | str | '' |  |
| `expected_row_version` | int | (required) |  |

### `ManualIn` (services/central/app/evidence_router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `category` | Literal['medication', 'lab', 'condition', 'note'] | (required) |  |
| `fields` | dict[str, Any] | (required) |  |
| `document_id` | int \| None | None |  |
| `page` | int \| None | None |  |
| `note` | str | '' |  |

### `ReviewIn` (services/central/app/followup/router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `note` | str | '' |  |

### `AnswerIn` (services/central/app/followup/router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `answer` | str | Field(min_length=2) |  |

### `InformedIn` (services/central/app/followup/router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `note` | str | Field(min_length=3) |  |

### `TaskIn` (services/central/app/followup/router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `description` | str | Field(min_length=3) |  |
| `assignee_name` | str \| None | None |  |
| `due_date` | date \| None | None |  |

### `TaskOutcomeIn` (services/central/app/followup/router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `status` | Literal['completed', 'not_completed'] | (required) |  |
| `outcome` | str | Field(min_length=2) |  |

### `CloseIn` (services/central/app/followup/router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `expected_version` | int | (required) |  |

### `LinkIn` (services/central/app/identity/router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `local_id` | str | (required) |  |
| `target_institution` | str | (required) |  |
| `purpose` | str | Field(min_length=5) |  |

### `ApproveIn` (services/central/app/identity/router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `local_patient_id` | str \| None | None |  |
| `register_new` | bool | False |  |
| `note` | str | Field(min_length=3) |  |

### `DecisionIn` (services/central/app/identity/router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `note` | str | Field(min_length=3) |  |

### `StatusIn` (services/central/app/identity/router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `reason` | str | Field(min_length=3) |  |

### `ApplyTemplateIn` (services/central/app/identity/router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `template_id` | str | (required) |  |
| `reason` | str | Field(min_length=3) |  |

### `SuggestionReviewIn` (services/central/app/medications/router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `pair_key` | str | (required) |  |
| `decision` | Literal['ignore', 'research'] | (required) |  |
| `note` | str | '' |  |

### `ManualMedIn` (services/central/app/medications/router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `name` | str | Field(min_length=2) |  |
| `strength` | str \| None | None |  |
| `dose` | str \| None | None |  |
| `frequency` | str \| None | None |  |
| `route` | str \| None | None |  |
| `over_the_counter` | bool | False |  |
| `note` | str | '' |  |

### `ReasonIn` (services/central/app/medications/router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `reason` | str | Field(min_length=3) |  |

### `MapIn` (services/central/app/medications/router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `ingredient` | str | (required) |  |
| `company` | str \| None | None |  |
| `drap_reg_no` | str \| None | None |  |

### `CheckedIn` (services/central/app/medications/router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `note` | str | '' |  |

### `AckIn` (services/central/app/medications/router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `flag_version` | int | (required) |  |
| `decision` | Literal['reviewed', 'ignore', 'research'] | 'reviewed' |  |
| `note` | str | '' |  |

### `NameIn` (services/central/app/medications/router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `display` | str | Field(min_length=2) |  |
| `ingredient` | str | Field(min_length=2) |  |
| `drug_class` | str | Field(min_length=2) |  |
| `kind` | Literal['generic', 'brand'] | 'brand' |  |

### `RuleIn` (services/central/app/medications/router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `title` | str | Field(min_length=5) |  |
| `drug_class` | str | (required) |  |
| `procedure_tags` | list[str] | Field(min_length=1) |  |
| `message` | str | Field(min_length=10) |  |
| `rationale` | str | '' |  |
| `reference` | str | '' |  |

### `RuleDecisionIn` (services/central/app/medications/router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `decision` | Literal['approve', 'reject', 'retire'] | (required) |  |
| `reference_checked` | str | Field(min_length=5) |  |
| `note` | str | '' |  |

### `DiagnosticIn` (services/central/app/referrals/router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `category` | str | (required) |  |
| `test` | str | Field(min_length=2) |  |
| `body_area` | str \| None | None |  |
| `clinical_question` | str | Field(min_length=3) |  |
| `urgency` | str | 'routine' |  |
| `destination_institution` | str | (required) |  |
| `destination_department` | str | (required) |  |

### `ReferralForm` (services/central/app/referrals/router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `patient_local_id` | str | (required) |  |
| `kind` | str | 'referral' |  |
| `source_department` | str \| None | None |  |
| `destination_institution` | str \| None | None |  |
| `destination_department` | str \| None | None |  |
| `destination_doctor` | str \| None | None |  |
| `reason` | str | '' |  |
| `urgency` | str | 'routine' |  |
| `procedure_status` | str | 'unknown' |  |
| `planned_procedure` | str \| None | None |  |
| `procedure_tags` | list[str] | Field(default_factory=list) |  |
| `diagnostic_requests` | list[DiagnosticIn] | Field(default_factory=list) |  |
| `submit` | bool | False |  |

### `VersionIn` (services/central/app/referrals/router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `expected_version` | int | (required) |  |

### `LinkRequestIn` (services/central/app/referrals/router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `target_institution` | str | (required) |  |

### `CancelIn` (services/central/app/referrals/router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `expected_version` | int | (required) |  |
| `reason` | str | Field(min_length=3) |  |

### `SendIn` (services/central/app/sending/router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `expected_version` | int | (required) |  |

### `VerifyCopyIn` (services/central/app/sending/router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `package` | dict | (required) |  |

### `LookupIn` (services/provider/app/main.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `cnic` | str \| None | None |  |
| `name` | str \| None | None |  |
| `birth_date` | str \| None | None |  |
| `sex` | str \| None | None |  |

### `RegisterIn` (services/provider/app/main.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `cnic` | str | (required) |  |
| `given` | str | (required) |  |
| `family` | str | (required) |  |
| `birth_date` | date | (required) |  |
| `sex` | str | (required) |  |
| `phone` | str \| None | None |  |
| `city` | str \| None | None |  |

### `ShareIn` (services/provider/app/main.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `grantee_institution` | str | (required) |  |
| `local_patient_id` | str | (required) |  |
| `basis` | str | Field(min_length=5) |  |
| `duration_days` | int | DEFAULT_GRANT_DAYS |  |
| `referral_ref` | str \| None | None |  |

### `ExpiredIn` (services/provider/app/main.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `expire_key` | str | (required) |  |
| `referral_id` | str | (required) |  |
| `expired_at` | datetime | (required) |  |

### `SentCopyIn` (services/provider/app/main.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `copy_key` | str | (required) |  |
| `referral_id` | str | (required) |  |
| `kind` | Literal['package', 'response'] | (required) |  |
| `version` | int | 0 |  |
| `content` | dict | (required) |  |

### `IntakeIn` (services/provider/app/main.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `referral_id` | str | (required) |  |
| `local_patient_id` | str | (required) |  |

### `AssignIn` (services/provider/app/main.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `doctor` | str | Field(min_length=3) |  |
| `note` | str | '' |  |

### `DecisionIn` (services/provider/app/main.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `decision` | Literal['accept', 'decline'] | (required) |  |
| `reason` | str \| None | None |  |

### `InfoIn` (services/provider/app/main.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `question` | str | Field(min_length=3) |  |

### `ResponseIn` (services/provider/app/main.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `assessment` | str | '' |  |
| `plan` | str | '' |  |
| `instructions_for_clinic` | str | '' |  |
| `appointment` | str | '' |  |
| `expected_row_version` | int \| None | None |  |

### `SendIn` (services/provider/app/main.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `expected_row_version` | int | (required) |  |

### `ExtendHoldIn` (services/provider/app/main.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `reason` | str | Field(min_length=3) |  |

### `RejectIn` (services/provider/app/main.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `reason` | str | Field(min_length=3) |  |

### `ScheduleIn` (services/provider/app/main.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `scheduled_for` | datetime | (required) |  |

### `ValueIn` (services/provider/app/main.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `test` | str | (required) |  |
| `value` | str | (required) |  |
| `unit` | str \| None | None |  |
| `reference` | str \| None | None |  |
| `flag` | str \| None | None |  |

### `AttachmentIn` (services/provider/app/main.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `filename` | str | Field(min_length=1, max_length=200) |  |
| `content_type` | str | (required) |  |
| `data` | str | (required) | base64 |

### `ReportIn` (services/provider/app/main.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `findings` | str | '' |  |
| `impression` | str | '' |  |
| `values` | list[ValueIn] | Field(default_factory=list) |  |
| `attachments` | list[AttachmentIn] | Field(default_factory=list, max_length=6) |  |

### `Decision` (libs/common/refcommon/sourcekit.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `allowed` | set[str] | (required) |  |
| `denied` | set[str] | (required) |  |
| `reason` | str | (required) |  |
| `expired` | bool | False |  |

### `GrantIn` (libs/common/refcommon/sourcekit.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `grantee_institution` | str | (required) |  |
| `local_patient_id` | str | (required) |  |
| `categories` | list[str] | (required) |  |
| `basis` | str | '' |  |
| `duration_days` | int | DEFAULT_GRANT_DAYS |  |
| `referral_ref` | str \| None | None |  |

### `ExtendIn` (libs/common/refcommon/sourcekit.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `days` | int | (required) |  |
| `reason` | str | (required) |  |

### `RevokeByReferralIn` (libs/common/refcommon/sourcekit.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `referral_ref` | str | (required) |  |
| `reason` | str | 'referral finished' |  |
