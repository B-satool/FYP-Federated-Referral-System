## Database migrations (Alembic, applied at service start: `alembic upgrade head`)

### `services/central/migrations`

| Order | Revision | Revises | Change | File |
|---|---|---|---|---|
| 1 | `f768a09d90d4` | `(base)` | v2 schema | `services/central/migrations/versions/f768a09d90d4_v2_schema.py` |
| 2 | `3cb2af44a7f8` | `f768a09d90d4` | round two: request kinds, staff checkpoint, intake links, result images | `services/central/migrations/versions/3cb2af44a7f8_round_two_request_kinds_staff_.py` |
| 3 | `f476d3248be7` | `3cb2af44a7f8` | source-backed flagging: ingredients, interactions, label rules, decisions | `services/central/migrations/versions/f476d3248be7_source_backed_flagging_ingredients_.py` |
| 4 | `76763a476e7c` | `f476d3248be7` | ai suggestions and reviews | `services/central/migrations/versions/76763a476e7c_ai_suggestions_and_reviews.py` |
| 5 | `97915d386e71` | `76763a476e7c` | data lifecycle and packet selection | `services/central/migrations/versions/97915d386e71_data_lifecycle_and_packet_selection.py` |
| 6 | `50cb02ecd52d` | `97915d386e71` | receiver completion | `services/central/migrations/versions/50cb02ecd52d_receiver_completion.py` |
| 7 | `fec095fdc2b0` | `50cb02ecd52d` | ambiguous brand choices | `services/central/migrations/versions/fec095fdc2b0_ambiguous_brand_choices.py` |
| 8 | `a1c3e5f7b9d2` | `fec095fdc2b0` | consultation notes and the doctor's packet review | `services/central/migrations/versions/a1c3e5f7b9d2_consultation_notes_and_packet_review.py` |
| 9 | `c3e5a7b9d1f2` | `a1c3e5f7b9d2` | end-to-end key directory, group-key wraps, platform key, seen assertions (spec v4 WP1, approval A1) | `services/central/migrations/versions/c3e5a7b9d1f2_e2e_key_directory.py` |
| 10 | `d4f6b8c0e2a3` | `c3e5a7b9d1f2` | consent, records requests and encrypted referral content (spec v4 WP2/WP3, approvals A1, A3 and A4) | `services/central/migrations/versions/d4f6b8c0e2a3_consent_and_encrypted_records.py` |
| 11 | `e5a7c9d1f3b4` | `d4f6b8c0e2a3` | close reminders and escalation (spec v4 WP9, approval A1) | `services/central/migrations/versions/e5a7c9d1f3b4_close_reminders.py` |
| 12 | `f6b8d0e2a4c5` | `e5a7c9d1f3b4` | audit hash chain and append-only trigger (spec v4 11.5, WP11) | `services/central/migrations/versions/f6b8d0e2a4c5_audit_hash_chain.py` |

### `services/provider/migrations`

| Order | Revision | Revises | Change | File |
|---|---|---|---|---|
| 1 | `64628844a0ce` | `(base)` | institution schema | `services/provider/migrations/versions/64628844a0ce_institution_schema.py` |
| 2 | `f90a83a36cf0` | `64628844a0ce` | round two: intake, assignment, report images | `services/provider/migrations/versions/f90a83a36cf0_round_two_intake_assignment_report_.py` |
| 3 | `6608cba6436e` | `f90a83a36cf0` | grant expiry and sent copies | `services/provider/migrations/versions/6608cba6436e_grant_expiry_and_sent_copies.py` |
| 4 | `eb77d5fffde7` | `6608cba6436e` | case completion and hold | `services/provider/migrations/versions/eb77d5fffde7_case_completion_and_hold.py` |
| 5 | `b2d4f6a8c0e1` | `eb77d5fffde7` | end-to-end keys: key store, doctors' signed keys, group-key wraps, seen assertions (spec v4 WP1, approval A1) | `services/provider/migrations/versions/b2d4f6a8c0e1_e2e_keys.py` |
| 6 | `c4e6a8b0d2f3` | `b2d4f6a8c0e1` | records requests under consent and policy; sensitive-category markers (spec v4 WP2, approvals A1 and A3) | `services/provider/migrations/versions/c4e6a8b0d2f3_consent_policy_requests.py` |
| 7 | `d5f7b9c1e3a4` | `c4e6a8b0d2f3` | remove per-patient sharing grants: consent and this institution's policy replace them (spec v4 6.2, approval A3) | `services/provider/migrations/versions/d5f7b9c1e3a4_drop_sharing_grants.py` |
