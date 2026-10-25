# Requirement traceability (SRS → implementation → verification)

> **Version 1 document.** Version 2 changed the institutions, roles, linking, retrieval, medicines and sending; see [v2-changes.md](v2-changes.md) for what differs. This page has not been rewritten for v2 yet.

Paths are relative to `services/central/app` unless stated otherwise. Test IDs: `T1…T6` are `tests/test_t*_*.py`, `U` is `services/central/tests`, `E2E-n` is `web/e2e/smoke.spec.ts` journey *n*.

## 5.1 Authentication and authorization

| FR | Implementation | Verified by |
|---|---|---|
| FR-01 | Keycloak realm (`infra/keycloak`), group → institution, realm roles; `refcommon/auth.py` | T1 `test_me_reports_institution_and_role` |
| FR-02 | `security.py` `load_referral` / `require_roles` on every handler; clinician-only approval and verification | T1, T3 (staff approve → 403), T4 (staff verify → 403) |
| FR-03 | `refcommon/sourcekit.py` `decide_access` in each source service | T1 `test_source_level_authorization`, T2 denied case |
| FR-04 | Role categories (clinic staff without `conditions`) and per-patient, per-category grants | T1 partial bundle; E2E-1 "withheld" message |
| FR-05 | Central account status checked on each request, Keycloak disable + logout, token introspection at sources, evidence `access_revoked` on denial | T1 `test_disabled_account_loses_access_immediately_and_at_sources` |

## 5.2 Patient identity and linking

| FR | Implementation | Verified by |
|---|---|---|
| FR-06 | Institution identifier systems; `(institution_id, local_patient_id)` everywhere | T2 |
| FR-07, FR-08 | `models/identity.py` PatientLink + events; `identity/router.py` propose/check/verify | T2 `test_link_proposal_identity_check_verification_and_invalidation` |
| FR-09 | No automatic linking; Lab B/MR-102 is a different person | T2 `test_only_verified_links_import_evidence_and_same_local_id_stays_separate` |
| FR-10 | `invalidate_link`: evidence invalidated, affected packages listed, review item, amendment | T2 (invalidation), T2 `test_invalidated_link_is_not_used` |

## 5.3 Referral creation and management

| FR | Implementation | Verified by |
|---|---|---|
| FR-11 | `referrals/router.py` create/get/patch | T3, E2E-1 |
| FR-12 | Referral model; `procedure_status` not_stated/known/unknown | T5 procedure tests, E2E-2 (explicitly unknown) |
| FR-13 | `GET /referrals` filters | T3 `test_search_and_filter_referrals` |
| FR-14 | Cancel and decline reasons | T3 `test_specialist_decline_and_clinic_cancel_record_reasons` |
| FR-15 | `mark_clinical_change`, immutable `ReferralPackage`, amendment | T3 (edit approved → draft, v2), T5, E2E-3 |

## 5.4 Retrieval and common representation

| FR | Implementation | Verified by |
|---|---|---|
| FR-16 | `integration/sources.py`, `integration/retrieval.py` (parallel calls to all three) | T2 |
| FR-17 | Source adapters (`services/*/app/adapter.py`) → `integration/importer.py` | T2, `scripts/fhir-validate.ps1` |
| FR-18, FR-19 | `EvidenceItem.original`, `clinical_time` vs `retrieved_at` | T2 (units, dates preserved) |
| FR-20 | Unique `(referral, source, type, id, version)`; superseded versions | T2 repeat retrieval, lab correction |
| FR-21 | `SourceRetrieval.status` six outcomes | T2 denied vs unavailable, partial bundle |

## 5.5 Document processing

| FR | Implementation | Verified by |
|---|---|---|
| FR-22 | `documents/router.py` type/size/page validation (declared vs actual) | T4 rejected file, E2E-2 |
| FR-23 | Tesseract via `documents/processing.py` `extract_document()` | T4 scanned image, `scripts/evaluate_ocr.py` |
| FR-24 | Original kept in protected storage; authenticated download | T4 |
| FR-25 | Fields start `proposed` / `unverified`; clinician-only verify | T4 |
| FR-26 | Document review screen (page image + region highlight) | E2E-2 `document-review` |
| FR-27 | Unreadable detection; nothing guessed; missing stays missing | T4 unreadable, T2 glucose |
| FR-28 | `EvidenceRevision` (editor, prior value) | T4 history assertions |

## 5.6 Medications and laboratory results

| FR | Implementation | Verified by |
|---|---|---|
| FR-29 | MedicationEntry fields from MedicationRequest/Statement/document | T3, contract examples |
| FR-30 | `use_status` separate from prescription status | T3, T5 |
| FR-31, FR-32 | Observation mapping (value, unit, specimen, status, collection time); `dataAbsentReason` | T2 |
| FR-33, FR-34 | `medications/mapping.py` bounded dictionary; suggested → ambiguous; unmapped kept in original form | U table (ambiguous mapping), T3 |

## 5.7 Completeness and discrepancy review

| FR | Implementation | Verified by |
|---|---|---|
| FR-35, FR-36 | `reviews/checklist.py` + `rules/checklists/orthodontics.v1.json` | T6 `test_checklist_reports_missing_items_and_override_rules` |
| FR-37 | D-MED-DOSE / D-LAB-SAME-TIME with both sources and dates | T4 discrepancy assertions |
| FR-38 | Different dates are never a conflict | T4 (INR 2.6 vs 3.1) |
| FR-39 | Clarification model and lifecycle; lab answers via work queue | T6 `test_missing_information_request_answered_by_lab_and_resolved` |
| FR-40 | Clinical items resolved by clinicians with rationale | T4 discrepancy resolution |

## 5.8 Referral brief

| FR | Implementation | Verified by |
|---|---|---|
| FR-41 | `generation/brief.py` + `provider.py` (Claude, structured output) | T6 `test_brief_generation_path` (live when key present) |
| FR-42 | Sections: reason, history, medications, results, outstanding | U |
| FR-43 | `validate_output` requires and allowlists evidence IDs | U `test_reference_outside_supplied_evidence_is_rejected` |
| FR-44 | Clinician-authored and edited statements record their author | T3 |
| FR-45 | Statement verification labels; limitations section | U |
| FR-46 | Unavailable sources passed as limitations; prompt forbids "no history" | U `test_prompt_states_the_boundaries` |
| FR-47 | Clinician-only `approve` | T3 |

## 5.9 Submission, response and follow-up

| FR | Implementation | Verified by |
|---|---|---|
| FR-48 | `schedule_send` only for an approved, non-superseded version | T3 (unapproved submit → 409) |
| FR-49 | `delivery_status`, `acknowledged_at`, `accepted_at` stored separately | T3, E2E-1 |
| FR-50 | Specialist decision and clarification endpoints | T3, T5 |
| FR-51 | Specialist service enforces approval before return | T3 (return before approve → 409) |
| FR-52 | `record-receipt` and clinician `review` are separate | T3 |
| FR-53 | Follow-up tasks with owner, due date and outcome | T3, E2E-1 |
| FR-54 | `/work-queue` | T3, T6 |

## 5.10 Failure handling and audit

| FR | Implementation | Verified by |
|---|---|---|
| FR-55 | Per-source results; other sources kept | T2 lab outage |
| FR-56 | Bounded retries (sources, outbox), visible error states | T2 attempts ≥ 2, outbox status |
| FR-57 | Delivery key and event key deduplication | T3 duplicate send and response |
| FR-58 | Evidence template, manual editor, manual transcription, rules extractor | T4, T6, E2E-2 |
| FR-59, FR-60 | `AuditEvent` everywhere; source audit tables | T3 audit assertions, E2E-1 |

## 5.11 Referral-specific medication flags

| FR | Implementation | Verified by |
|---|---|---|
| FR-61 | Versioned rule file + `RuleApproval` (reviewer, reference, hash) | T5 `test_rules_require_clinical_reviewer_and_drafts_do_not_flag` |
| FR-62 | Mapping status; ambiguous → clarification prompt | U |
| FR-63 | Historical/stopped → no flag; uncertain → prompt | U, T3 (stopped alendronate) |
| FR-64 | Procedure rules unevaluated when unknown; specialty-only prompts | U, T5 |
| FR-65 | Flag shows medication/class, reason, source, use status, rule/version | U `test_flag_content_is_traceable`, T3 |
| FR-66 | "Possible medication use—please confirm"; "Medication history incomplete" (coexisting) | U, T5 |
| FR-67 | No-match message states coverage limits | U, T3 |
| FR-68 | Structured flags in package and specialist view; model cannot write them | U schema test, T3 envelope |
| FR-69 | Reviewed / Request clarification with reviewer, time, flag version, request link | T3, T5 |
| FR-70 | Re-evaluation on use/mapping/specialty/procedure/rule change; new versions; amendment | T5 `test_changed_flag_after_submission_needs_new_version_and_review`, E2E-3 |
| FR-71 | Fixed wording; test that no flag advises changes or urgency | U `test_flags_never_advise_medication_change_or_urgency` |
| FR-72 | Evaluation runs audited; failure distinct from no-match; manual review override | U `test_evaluation_failure_raises_distinctly`, approval override path |

## Non-functional requirements

| NFR | Where |
|---|---|
| 10.1 Security & privacy | Authorization at central and sources; TLS and secrets guidance (operations.md); authenticated document endpoints; retention; synthetic data |
| 10.2 Reliability | Drafts preserved on failures; immutable versions; optimistic concurrency (409); ordered event timeline; backup and restore check |
| 10.3 Usability | Original page beside fields; status tags with icon and text (not colour alone); skip link and focus outlines; clear next actions |
| 10.4 Performance | `scripts/loadtest.py` (10 users, p95 target 2 s); 10 s source timeout; async OCR/LLM with job status |
| 10.5 Maintainability | `LLMProvider` and `extract_document()` interfaces; versioned rules, checklist, mapping, prompts (`PROMPT_VERSION`) |
| 10.6 Medication-flag reliability | Deterministic evaluator; no duplicate visible flags; only approved rules; documented coverage |
