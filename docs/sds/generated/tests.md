## Automated tests

124 tests in 27 files.

### `services/central/tests/test_ai_suggestions.py` (unit (no services), 4)

| Test | What it checks |
|---|---|
| `test_pair_in_interaction_table_is_never_a_suggestion` |  |
| `test_forcing_scores_never_changes_flags` |  |
| `test_suggestions_only_for_current_medicines_and_carry_versions` |  |
| `test_committed_suggestions_exclude_ddinter_pairs_and_are_labelled` |  |

### `services/central/tests/test_evaluator.py` (unit (no services), 5)

| Test | What it checks |
|---|---|
| `test_name_hints_cover_the_seed_procedures` | Words in the procedure name pre-tick the features the doctor confirms (features, not medicines). |
| `test_unrecognised_medicine_is_reported_not_ignored` |  |
| `test_unavailable_source_is_a_limitation_not_none` |  |
| `test_no_rules_is_not_a_negative_result` |  |
| `test_deterministic` |  |

### `services/central/tests/test_flagging.py` (unit (no services), 17)

| Test | What it checks |
|---|---|
| `test_p3_aspirin_and_diclofenac_interaction` |  |
| `test_p4_ibuprofen_with_liver_disease_condition_flag` |  |
| `test_p5_antiplatelets_interact_and_no_invented_insulin_advice` |  |
| `test_deterministic_byte_identical` |  |
| `test_unmapped_brand_could_not_be_checked_not_safe` |  |
| `test_ambiguous_brand_returns_ambiguous` |  |
| `test_combination_product_checks_each_ingredient` |  |
| `test_salt_variants_resolve_to_one_name` |  |
| `test_pair_symmetry` |  |
| `test_ingredient_not_in_source_is_reported` |  |
| `test_every_flag_has_source_and_tag` |  |
| `test_no_match_says_no_rule_on_file_never_safe` |  |
| `test_flag_text_never_advises_changing_medication` |  |
| `test_only_serious_imported_flags_require_a_decision` |  |
| `test_procedure_unknown_gives_only_condition_label_rules` |  |
| `test_validator_rejects` |  |
| `test_validator_accepts_and_every_stored_label_rule_passes` |  |

### `services/central/tests/test_lifecycle.py` (unit (no services), 10)

| Test | What it checks |
|---|---|
| `test_no_limit_until_accepted_then_a_reminder_not_a_purge` |  |
| `test_extension_moves_the_reminder_and_stops_at_the_maximum` |  |
| `test_close_purges_after_the_grace_period` |  |
| `test_decline_and_cancel_purge_after_a_short_grace` |  |
| `test_test_requests_end_after_results` |  |
| `test_every_template_is_valid` |  |
| `test_templates_give_visibility_keys_and_scopes` | Spec v4 4.1: staff see titles only and hold no keys; doctors open content on their device and hold keys. |
| `test_menu_only_offers_screens_the_roles_allow` |  |
| `test_front_desk_does_not_get_reviewer_screens` |  |
| `test_plan_change_only_removes_managed_roles` |  |

### `services/central/tests/test_ollama_provider.py` (unit (no services), 4)

| Test | What it checks |
|---|---|
| `test_local_model_gets_schema_as_format` |  |
| `test_cloud_model_gets_schema_in_prompt_and_reply_is_checked` |  |
| `test_bad_output_and_errors` |  |
| `test_check_schema_rejects` |  |

### `services/central/tests/test_privacy.py` (unit (no services), 3)

| Test | What it checks |
|---|---|
| `test_scrubber_removes_identifiers_and_keeps_the_clinical_content` |  |
| `test_cloud_and_remote_models_need_explicit_permission_and_https` |  |
| `test_packet_selection_sends_no_identifiers` |  |

### `services/central/tests/test_provider_offline.py` (unit (no services), 2)

| Test | What it checks |
|---|---|
| `test_structured_request_shape_and_parsing` |  |
| `test_refusal_and_truncation_are_rejected` |  |

### `services/central/tests/test_provider_openai_compatible.py` (unit (no services), 7)

| Test | What it checks |
|---|---|
| `test_request_shape_and_parsing` |  |
| `test_api_key_and_code_fence` |  |
| `test_failures` |  |
| `test_unreachable_server` |  |
| `test_ollama_request_shape` |  |
| `test_ollama_complete_answer_padded_to_the_cap_is_used` |  |
| `test_ollama_failures` |  |

### `services/central/tests/test_register_names.py` (unit (no services), 5)

| Test | What it checks |
|---|---|
| `test_register_brand_at_the_start_maps_and_says_where_it_came_from` |  |
| `test_register_brand_inside_other_words_does_not_match` |  |
| `test_hand_checked_names_still_match_anywhere_and_carry_no_register_note` |  |
| `test_register_names_that_are_too_short_or_ordinary_words_are_not_loaded` |  |
| `test_a_register_name_for_two_medicines_says_what_it_could_be` |  |

### `services/central/tests/test_selection.py` (unit (no services), 9)

| Test | What it checks |
|---|---|
| `test_default_floor` |  |
| `test_schema_is_strict` |  |
| `test_valid_answer` |  |
| `test_rejected_answers` |  |
| `test_advice_is_withheld_and_the_record_keeps_the_default` |  |
| `test_prompt_injection_in_record_text_cannot_add_ids` | A record that says 'include record 500' cannot make the model's answer use an id outside the set. |
| `test_schema_limits_only_for_providers_that_enforce_them` |  |
| `test_describing_a_record_is_not_advice` |  |
| `test_bad_missing_phrases_are_dropped_not_fatal` |  |

### `services/central/tests/test_selection_apply.py` (unit (no services), 5)

| Test | What it checks |
|---|---|
| `test_ai_adds_but_never_removes_default_items` |  |
| `test_staff_choice_wins` |  |
| `test_failure_keeps_the_default` |  |
| `test_include_at_low_relevance_does_not_add` |  |
| `test_answer_arriving_after_purge_is_discarded` |  |

### `services/central/tests/test_staff_view.py` (unit (no services), 6)

| Test | What it checks |
|---|---|
| `test_record_titles_name_the_chart_never_the_content` |  |
| `test_staff_evidence_view_has_no_values_or_ai_reasoning` |  |
| `test_staff_referral_view_hides_notes_and_procedure_but_shows_the_reason` | Spec v4 4: staff see referral metadata including the reason; the doctor's notes and procedure stay hidden. |
| `test_staff_test_view_hides_question_and_result` |  |
| `test_consultation_notes_are_hashed_without_changing_older_packages` |  |
| `test_interaction_flag_quotes_the_label_when_a_sentence_exists` |  |

### `services/central/tests/test_vision_ocr.py` (unit (no services), 3)

| Test | What it checks |
|---|---|
| `test_handwriting_is_read_line_by_line_with_boxes` |  |
| `test_vision_failure_falls_back_to_tesseract_and_says_so` |  |
| `test_no_key_never_calls_google` |  |

### `tests/test_e2e_ai.py` (integration (full stack), 3)

| Test | What it checks |
|---|---|
| `test_identifiers_are_refused_and_never_logged` |  |
| `test_only_the_referring_doctor_may_ask` |  |
| `test_answer_is_checked_or_unavailable_is_said` |  |

### `tests/test_e2e_audit.py` (integration (full stack), 3)

| Test | What it checks |
|---|---|
| `test_chain_verifies_and_the_table_is_append_only` |  |
| `test_tampering_behind_the_trigger_is_detected` |  |
| `test_audit_holds_no_content` |  |

### `tests/test_e2e_consent.py` (integration (full stack), 5)

| Test | What it checks |
|---|---|
| `test_adapter_rejects_bad_request_assertions` | T-TOKEN-1: bad signature, wrong audience, expired, over-long, replayed jti, non-participant organisation, a purpose the agreement does not allow, a missing consent link. A request with a well-formed assertion but a consent link that leads nowhere is refused with a reason code (never an empty answer). |
| `test_staff_request_consent_but_cannot_grant_it` | T-CONSENT-1: staff create a request; only the patient can grant, decline or revoke, in the portal. |
| `test_patient_grants_consent_and_records_arrive_encrypted` |  |
| `test_sensitive_lab_result_needs_specific_consent_and_staff_review` | T-POLICY-1 at the laboratory: without specific consent the HIV result is refused with a reason code; with it, the request waits for the lab's staff (pending_manual_review) and is released after their approval. |
| `test_revoked_consent_blocks_further_requests` |  |

### `tests/test_e2e_flags.py` (integration (full stack), 4)

| Test | What it checks |
|---|---|
| `test_bundle_is_hash_checked_and_has_the_brand_and_interaction_data` |  |
| `test_browser_library_on_the_real_bundle` |  |
| `test_ignore_and_research_are_audited_without_names` |  |
| `test_layer2_gets_generic_names_only` |  |

### `tests/test_e2e_keys.py` (integration (full stack), 6)

| Test | What it checks |
|---|---|
| `test_doctor_key_is_signed_by_the_hospital_and_gets_the_department_key` |  |
| `test_registration_needs_proof_of_possession_and_a_doctor` |  |
| `test_platform_refuses_entries_not_signed_by_the_hospital_and_bad_assertions` | T-DIR-1 (platform side) and the platform's half of T-TOKEN-1. |
| `test_revoking_a_doctor_rotates_the_department_key` | T-GROUP-1: the leaver keeps only the old version; the department key moves on; a re-joined key gets the new version. |
| `test_staff_and_patients_cannot_manage_doctor_keys` |  |
| `test_patient_key_is_signed_by_the_platform` |  |

### `tests/test_e2e_lifecycle.py` (integration (full stack), 3)

| Test | What it checks |
|---|---|
| `test_reminders_escalate_extension_moves_them_and_close_purges` |  |
| `test_extension_stops_at_the_maximum` |  |
| `test_decline_purges_after_a_short_grace` |  |

### `tests/test_e2e_package.py` (integration (full stack), 4)

| Test | What it checks |
|---|---|
| `test_approve_send_and_the_receiving_doctor_opens_it` |  |
| `test_tampered_or_foreign_signatures_are_refused_and_versions_stay_verifiable` | T-APPROVE-1: a ciphertext hash that does not match, or a manifest signed with another key, is refused; a second version needs its own signature, and the first still verifies for its own version. |
| `test_receiving_hospital_adds_its_own_records_for_its_doctors` | Spec v4 step 8: receiving staff add their hospital's records; they are encrypted to the department's key, so the department's doctors open them and nobody on the referring side gets a key (or even the titles). |
| `test_only_the_referring_doctor_approves` |  |

### `tests/test_e2e_patient.py` (integration (full stack), 2)

| Test | What it checks |
|---|---|
| `test_patient_adds_a_paper_only_the_doctor_and_patient_can_read` |  |
| `test_patient_copy_survives_the_purge_and_verifies` |  |

### `tests/test_e2e_retrieval.py` (integration (full stack), 5)

| Test | What it checks |
|---|---|
| `test_doctor_opens_records_staff_see_titles_and_the_database_holds_no_plaintext` |  |
| `test_other_doctors_cannot_open_the_referral` | T-DOC-1: a doctor at another hospital is refused; ciphertext is only ever wrapped to the referring doctor. |
| `test_doctor_uploads_own_items_wrapped_only_to_allowed_keys` |  |
| `test_lost_key_records_are_fetched_again_but_platform_only_items_are_lost` | T-REC-1: a replacement key is signed, the old one revoked and the administrators told; records from the institutions come again for the new key; the doctor's own platform-only item has no wrap for the new key. |
| `test_records_requests_from_others_are_listed_for_the_source_staff_without_content` |  |

### `tests/test_patient_access.py` (integration (full stack), 3)

| Test | What it checks |
|---|---|
| `test_patient_sees_own_referrals_only` |  |
| `test_patient_reads_own_records_from_each_institution` |  |
| `test_patient_endpoints_refuse_everyone_else_and_staff_endpoints_refuse_patients` |  |

### `tests/test_roles.py` (integration (full stack), 2)

| Test | What it checks |
|---|---|
| `test_role_menus` |  |
| `test_admin_assigns_a_role_by_template` | An institution administrator turns a lab account into front-desk staff and back. The change is made in Keycloak, so it applies on the user's next sign-in, and it is audited. |

### `tests/test_test_requests.py` (integration (full stack), 1)

| Test | What it checks |
|---|---|
| `test_p3_test_request_flow` | P3 (Abdul Rehman Gondal): MRI knee at AKUH radiology (never seen there) and blood tests at Chughtai Lab (known there). |

### `web/e2e/admin.spec.ts` (browser end-to-end (Playwright), 1)

| Test | What it checks |
|---|---|
| `administrator changes a role with a template; the menu follows on the next sign-in` |  |

### `web/e2e/smoke.spec.ts` (browser end-to-end (Playwright), 2)

| Test | What it checks |
|---|---|
| `v4 referral: keys, consent in the portal, decrypt, sign, send, the receiver verifies, the patient keeps a copy` |  |
| `test request: MRI at Aga Khan radiology with images, result back to the doctor` |  |
