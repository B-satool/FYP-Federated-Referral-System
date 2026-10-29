# Requirement traceability (SRS → v2 implementation → verification), as of 2026-10-29

Paths are relative to `services/central/app` unless stated. Tests:
- **API:** `tests/test_*.py`, e.g. `v2_flow`, `v2_scenarios`, `v3_lifecycle`, `referral_expiry`, `drap_brands`.
- **U:** unit tests in `services/central/tests`.
- **E2E:** `web/e2e/smoke.spec.ts` and `admin.spec.ts`.

Where v2 differs from the SRS on purpose, the row says so; see [v2-changes.md](v2-changes.md) §3.

## 5.1 Authentication and authorization

| FR | Implementation | Verified by |
|---|---|---|
| FR-01 | Keycloak realm (`infra/keycloak`), groups → institution and department, realm roles; `refcommon/auth.py`; role templates (`rules/roles/templates.v1.json`, `identity/role_templates.py`) | API `test_role_menus`, `test_admin_assigns_a_role_by_template`; E2E admin |
| FR-02 | `security.py` `load_referral` / `require_roles` on every handler; only staff send; **only doctors see or change clinical content** (staff views of the serializers, doctor-only endpoints; AGENTS.md rule 12) | API `v2_flow`; U `test_staff_view.py` |
| FR-03 | `refcommon/sourcekit.py` `decide_access` in each institution service | API `test_grants_are_temporary` |
| FR-04 | Per-patient, per-category grants with expiry; created when an institution confirms a link | API `test_grants_are_temporary`; U `test_grant_*` |
| FR-05 | Central account status, Keycloak disable, token introspection at institutions | Manual (v1 test not ported) |

## 5.2 Patient identity and linking

| FR | Implementation | Verified by |
|---|---|---|
| FR-06 | `(institution_id, local_patient_id)` everywhere | API `v2_flow` |
| FR-07, FR-08 | `identity/` links: the other institution looks the patient up by CNIC and confirms, registers as new (arriving patient only), or rejects | API `test_p5_referral_flow`, `test_p2_every_linked_hospital_and_stopped_medicine` |
| FR-09 | No automatic linking; a newly registered patient is never a records source | API `test_p5_referral_flow` |
| FR-10 | Link invalidation keeps history; affected records invalidated | Manual (v1 test not ported) |

## 5.3 Referral creation and management

| FR | Implementation | Verified by |
|---|---|---|
| FR-11 | `referrals/router.py`: referral or test request | API `v2_flow`; E2E |
| FR-12 | Procedure in the doctor's words plus ticked features; "unknown" allowed; nothing guessed | API `test_procedure_without_features_is_not_checked`; U `test_procedure_not_known_is_never_guessed` |
| FR-13 | `GET /referrals` filters (type, patient, reference, status, destination including test destinations, dates) | E2E (list) |
| FR-14 | Cancel (doctor only) and decline reasons | API `v2_flow`, `test_decline_removes_the_shared_records_straight_away` |
| FR-15 | `mark_clinical_change`, immutable `ReferralPackage`, amendment opens a new version | API `test_selection_manifest_own_copy_and_purge` |

## 5.4 Retrieval and common representation

| FR | Implementation | Verified by |
|---|---|---|
| FR-16 | `integration/retrieval.py`: every linked institution, up to 5, most recent first; history years per specialty | API `test_p2_every_linked_hospital_and_stopped_medicine` |
| FR-17 | `services/provider/app/adapter.py` (FHIR R4 subset) → `integration/importer.py` | API `v2_flow` |
| FR-18, FR-19 | `EvidenceItem.original`, `clinical_time` vs `retrieved_at` | API `v2_scenarios` |
| FR-20 | Unique `(referral, source, type, id, version)`; superseded versions | API `test_selection_manifest_own_copy_and_purge` (refetch after removal) |
| FR-21 | `SourceRetrieval.status`: successful, empty, partial, denied, expired, unavailable, invalid, skipped | API `v2_flow`, `test_grants_are_temporary` |

## 5.5 Document processing

| FR | Implementation | Verified by |
|---|---|---|
| FR-22 | `documents/router.py` type, size and page checks | API `test_uploaded_prescription_merges_with_recorded_medicines` |
| FR-23 | `documents/processing.py`: Tesseract, or Google Cloud Vision for handwriting (`OCR_ENGINE=google_vision`) with Tesseract fallback | API (above); U `test_vision_ocr.py` (live Vision not yet run) |
| FR-24 | Original kept in protected storage; authenticated download; removed with the working set | API `test_selection_manifest_own_copy_and_purge` |
| FR-25 | Fields start proposed and unverified; the doctor checks each against the page | API (above) |
| FR-26 | Document review screen (page image with the line highlighted) | E2E |
| FR-27 | Unreadable detection; nothing guessed | U extraction validator |
| FR-28 | `EvidenceRevision` (editor, prior value) | API (above) |

## 5.6 Medications and laboratory results

| FR | Implementation | Verified by |
|---|---|---|
| FR-29 | MedicationEntry from records, papers and staff entries; one row per ingredient and strength, listing every place | API `test_uploaded_prescription_merges_with_recorded_medicines` |
| FR-30 | Only current medicines come in; stopped ones are never current | API `test_p2_every_linked_hospital_and_stopped_medicine` |
| FR-31, FR-32 | Observation mapping (value, unit, date, place) | API `v2_scenarios` |
| FR-33, FR-34 | `medications/mapping.py`: hand-checked names, DRAP register brands (start of name only), ambiguous names never guessed (pick by company), unmapped kept as written | U `test_register_names.py`, `test_ambiguous_brand_returns_ambiguous`; API `test_drap_brands.py` |

## 5.7 Completeness and discrepancy review

| FR | Implementation | Verified by |
|---|---|---|
| FR-35, FR-36 | **Changed:** one "before sending" list (`sending/readiness.py`), no overrides | API `v2_flow` (blockers) |
| FR-37, FR-38 | Different doses of the same medicine highlighted for the doctor; different dates are not a conflict | API `test_uploaded_prescription_merges_with_recorded_medicines` |
| FR-39 | Questions from the receiving doctor answered by the clinic (`followup/router.py` clarifications) | Manual |
| FR-40 | The doctor resolves dose differences by marking the one not current | API (above) |

## 5.8 Referral brief

| FR | Implementation | Verified by |
|---|---|---|
| FR-41 to FR-46 | **Changed:** the letter is built deterministically from the checked records with their sources (`sending/brief.py`); no model writes it. Unavailable sources are listed as "could not be obtained". | API `v2_flow` (letter sections) |
| FR-47 | **Changed:** the doctor submits, then reviews the packet (papers, medicines, flags, records, letter) and marks it reviewed (`POST /referrals/{id}/packet-reviewed`); a later clinical change clears the review; staff send. Each sent version is hashed and records who requested, reviewed and sent. | API `v2_flow` |

## 5.9 Submission, response and follow-up

| FR | Implementation | Verified by |
|---|---|---|
| FR-48 | Send only when the "before sending" list is complete | API `v2_flow` |
| FR-49 | Delivery, acknowledgment and acceptance stored separately | API `v2_flow` |
| FR-50 | Receiving doctor accepts or declines (reason required) and can ask questions; **no written response** (2026-10-28) | API `v2_flow`, `referral_expiry` |
| FR-51 | **Changed:** no response to approve; "Mark as complete" (manual) ends the receiver's part | API `test_accept_extend_complete_then_expire` |
| FR-52 | Requesting doctor and staff notified of the decision; staff record that the patient was told | API `v2_flow` |
| FR-53 | Follow-up tasks with owner, due date and outcome; doctor or staff close | API `v2_flow`; E2E (doctor closes) |
| FR-54 | `/work-queue` per role | E2E |

## 5.10 Failure handling and audit

| FR | Implementation | Verified by |
|---|---|---|
| FR-55 | Per-source results; other sources kept | API `v2_scenarios` |
| FR-56 | Bounded retries (sources, outbox); visible error states; the purge waits for deliveries | API `test_accept_extend_complete_then_expire` |
| FR-57 | Delivery key and event key deduplication | API `v2_flow` |
| FR-58 | Everything works without a model or a Vision key: rule-based selection and reader, Tesseract | API suite runs without them; U `test_failure_keeps_the_default`, `test_no_key_never_calls_google` |
| FR-59, FR-60 | `AuditEvent` everywhere (including role changes, removals, model calls with destination); institution audit tables | API (audit assertions) |

## 5.11 Referral-specific medication flags

| FR | Implementation | Verified by |
|---|---|---|
| FR-61 | Rules in the database, versioned, approved by a `rule_reviewer`; imported DDInter and drug-label rules marked automatically generated | U `test_flagging.py`; API `test_scenario_flags` |
| FR-62 | Mapping status; ambiguous → the doctor chooses by company | U, API `test_drap_brands.py` |
| FR-63 | Stopped medicines are not current | API `test_p2_every_linked_hospital_and_stopped_medicine` |
| FR-64 | Procedure rules not run when the procedure or its features are unknown | U `test_planned_procedure_without_features_is_not_guessed` |
| FR-65 | Every flag shows medicine, class or ingredients, reason, source, rule or version, quote | U `test_every_flag_has_source_and_tag` |
| FR-66 | Unavailable sources are limitations, never "none" | U `test_unavailable_source_is_a_limitation_not_none` |
| FR-67 | "No rule on file", never "safe" | U `test_no_match_says_no_rule_on_file_never_safe` |
| FR-68 | Flags and AI suggestions (labelled) in the package; the model cannot write flags | U `test_forcing_scores_never_changes_flags` |
| FR-69 | Reviewed / Ignore / Research with reviewer, time and flag version | API `test_imported_flags_show_source_and_decisions_are_logged` |
| FR-70 | Re-evaluation on change; new version and amendment after sending | API `v2_flow` |
| FR-71 | Fixed wording; no advice or urgency | U `test_messages_never_advise_changing_a_medicine`, `test_flag_text_never_advises_changing_medication` |
| FR-72 | Evaluation runs audited; failure distinct from no match | U `test_evaluator.py` |

## Non-functional requirements

| NFR | Where |
|---|---|
| 10.1 Security and privacy | Authorization at central and at each institution; expiring grants; temporary working set with manifest and fingerprint (`data-lifecycle.md`); de-identified model input with explicit permission for external models (`generation/privacy.py`, U `test_privacy.py`); TLS and secrets guidance (`operations.md`); synthetic data |
| 10.2 Reliability | Immutable versions; optimistic concurrency (409); idempotent delivery; the purge waits for deliveries; backup and restore scripts |
| 10.3 Usability | Separate doctor and staff screens; the page image beside each field; status tags with text, not colour alone; clear next steps |
| 10.4 Performance | Async OCR, AI and delivery with job status; 10 s source timeout; `scripts/loadtest.py` (v1 figures; not re-run on v2) |
| 10.5 Maintainability | `LLMProvider`, `extract_document()`, versioned rules, prompts (`PROMPT_VERSION`) and role templates |
| 10.6 Medication-flag reliability | Deterministic evaluator; only approved or source-backed rules; documented coverage |
