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

### `services/provider/migrations`

| Order | Revision | Revises | Change | File |
|---|---|---|---|---|
| 1 | `64628844a0ce` | `(base)` | institution schema | `services/provider/migrations/versions/64628844a0ce_institution_schema.py` |
| 2 | `f90a83a36cf0` | `64628844a0ce` | round two: intake, assignment, report images | `services/provider/migrations/versions/f90a83a36cf0_round_two_intake_assignment_report_.py` |
| 3 | `6608cba6436e` | `f90a83a36cf0` | grant expiry and sent copies | `services/provider/migrations/versions/6608cba6436e_grant_expiry_and_sent_copies.py` |
| 4 | `eb77d5fffde7` | `6608cba6436e` | case completion and hold | `services/provider/migrations/versions/eb77d5fffde7_case_completion_and_hold.py` |
