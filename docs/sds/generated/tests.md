## Automated tests

116 tests in 22 files.

### `services/central/tests/test_ai_suggestions.py` (unit (no services), 4)

| Test | What it checks |
|---|---|
| `test_pair_in_interaction_table_is_never_a_suggestion` |  |
| `test_forcing_scores_never_changes_flags` |  |
| `test_suggestions_only_for_current_medicines_and_carry_versions` |  |
| `test_committed_suggestions_exclude_ddinter_pairs_and_are_labelled` |  |

### `services/central/tests/test_evaluator.py` (unit (no services), 11)

| Test | What it checks |
|---|---|
| `test_seed_scenarios` |  |
| `test_procedure_not_known_is_never_guessed` |  |
| `test_planned_procedure_without_features_is_not_guessed` |  |
| `test_name_hints_cover_the_seed_procedures` | Words in the procedure name pre-tick the features the seed scenarios need. |
| `test_consultation_only_has_no_procedure_flags` |  |
| `test_unrecognised_medicine_is_reported_not_ignored` |  |
| `test_unavailable_source_is_a_limitation_not_none` |  |
| `test_no_rules_is_not_a_negative_result` |  |
| `test_one_flag_per_medicine_and_rule_however_many_sources` |  |
| `test_deterministic` |  |
| `test_messages_never_advise_changing_a_medicine` |  |

### `services/central/tests/test_flagging.py` (unit (no services), 19)

| Test | What it checks |
|---|---|
| `test_p1_alendronate_dental_label_flag_with_quote` |  |
| `test_p2_metformin_contrast_label_flag` |  |
| `test_p3_aspirin_and_diclofenac_interaction` |  |
| `test_p4_ibuprofen_with_liver_disease_condition_flag` |  |
| `test_p5_antiplatelets_before_surgery_and_no_invented_insulin_advice` |  |
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
| `test_procedure_unknown_does_not_guess_label_rules` |  |
| `test_validator_rejects` |  |
| `test_validator_accepts_and_every_stored_label_rule_passes` |  |

### `services/central/tests/test_grant_closeout.py` (unit (no services), 2)

| Test | What it checks |
|---|---|
| `test_calls_every_source_with_the_referral_reference` |  |
| `test_one_failing_source_is_reported_and_others_still_run` |  |

### `services/central/tests/test_lifecycle.py` (unit (no services), 15)

| Test | What it checks |
|---|---|
| `test_grant_states` |  |
| `test_grant_duration_bounds` |  |
| `test_grant_expiry_default_and_max` |  |
| `test_no_limit_until_accepted_then_safety_limit` |  |
| `test_receiver_extends_and_completes` |  |
| `test_decline_removes_now_and_cancel_after_grace` |  |
| `test_test_requests_end_after_results` |  |
| `test_working_set_restarts_after_purge` |  |
| `test_manifest_holds_references_not_values` |  |
| `test_purged_envelope_keeps_identity_only` |  |
| `test_verify_copy` |  |
| `test_every_template_is_valid` |  |
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
| `test_staff_referral_view_hides_reason_notes_and_procedure` |  |
| `test_staff_test_view_hides_question_and_result` |  |
| `test_consultation_notes_are_hashed_without_changing_older_packages` |  |
| `test_interaction_flag_quotes_the_label_when_a_sentence_exists` |  |

### `services/central/tests/test_vision_ocr.py` (unit (no services), 3)

| Test | What it checks |
|---|---|
| `test_handwriting_is_read_line_by_line_with_boxes` |  |
| `test_vision_failure_falls_back_to_tesseract_and_says_so` |  |
| `test_no_key_never_calls_google` |  |

### `tests/test_drap_brands.py` (integration (full stack), 1)

| Test | What it checks |
|---|---|
| `test_register_brand_and_choosing_an_ambiguous_one_by_company` |  |

### `tests/test_patient_access.py` (integration (full stack), 3)

| Test | What it checks |
|---|---|
| `test_patient_sees_own_referrals_only` |  |
| `test_patient_reads_own_records_from_each_institution` |  |
| `test_patient_endpoints_refuse_everyone_else_and_staff_endpoints_refuse_patients` |  |

### `tests/test_referral_expiry.py` (integration (full stack), 2)

| Test | What it checks |
|---|---|
| `test_accept_extend_complete_then_expire` |  |
| `test_decline_removes_the_shared_records_straight_away` |  |

### `tests/test_v2_flow.py` (integration (full stack), 2)

| Test | What it checks |
|---|---|
| `test_p5_referral_flow` |  |
| `test_p3_test_request_flow` | P3 (Abdul Rehman Gondal): MRI knee at AKUH radiology (never seen there) and blood tests at Chughtai Lab (known there). |

### `tests/test_v2_scenarios.py` (integration (full stack), 5)

| Test | What it checks |
|---|---|
| `test_scenario_flags` |  |
| `test_imported_flags_show_source_and_decisions_are_logged` | P3: DDInter interactions and drug-label flags carry their source; Ignore and Research are logged with the rule-set version, and an ignored flag stays in the record. |
| `test_procedure_without_features_is_not_checked` | A procedure written without saying what it involves: procedure rules are not run, and say so. |
| `test_p2_every_linked_hospital_and_stopped_medicine` | P2 was seen at AKUH (Aug 2026) and at Ziauddin radiology (Oct 2026): both are read, so his history is not cut to the last hospital visited. Diclofenac was stopped and must not appear as a current medicine. |
| `test_uploaded_prescription_merges_with_recorded_medicines` | P5's cardiology prescription (photo) lists the same medicines as the clinic record: after staff check the read fields, each medicine is shown once. |

### `tests/test_v3_lifecycle.py` (integration (full stack), 5)

| Test | What it checks |
|---|---|
| `test_grants_are_temporary` |  |
| `test_role_menus` |  |
| `test_admin_assigns_a_role_by_template` | An institution administrator turns a lab account into front-desk staff and back. The change is made in Keycloak, so it applies on the user's next sign-in, and it is audited. |
| `test_selection_manifest_own_copy_and_purge` |  |
| `test_default_selection_matches_seed_expected_view` | The rule-based default (no model) selects exactly the visits from the last 6 months listed in the seed's expected_retrieval_view; older visits are retrieved but start unselected. |

### `web/e2e/admin.spec.ts` (browser end-to-end (Playwright), 1)

| Test | What it checks |
|---|---|
| `administrator changes a role with a template; the menu follows on the next sign-in` |  |

### `web/e2e/smoke.spec.ts` (browser end-to-end (Playwright), 2)

| Test | What it checks |
|---|---|
| `referral: doctor requests, staff prepare, doctor reviews flags, staff send, hospital accepts and completes, doctor closes` |  |
| `test request: MRI at Aga Khan radiology with images, result back to the doctor` |  |
