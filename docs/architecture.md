# Architecture (version 2, as of 2026-10-29)

> **The full, versioned design is the [Software Design Specification](sds/SDS.md).** This page is a shorter overview.

How the platform is built and the rules it keeps. Why things changed since v1 is in [v2-changes.md](v2-changes.md),
and each decision is recorded in [decisions/](decisions/). Items marked **(provisional)** are defaults chosen so the
prototype could be built. The supervisor and a clinical reviewer still have to confirm them.

## 1. System boundaries

| Component | Owns | Talks to |
|---|---|---|
| **Institution service** (`services/provider`), run four times: Dr Ali's Clinic `drali`, Chughtai Lab `chughtai`, Ziauddin `ziauddin`, Aga Khan `akuh` | Its own database (`<id>_db`): patients and their records (visits, conditions, surgery, medicines, labs, imaging), access grants, incoming referrals (`cases`), orders and results, its copy of what it sent (`sent_copies`), audit | Answers authorized requests. Sends events (acknowledged, accepted, declined, completed, hold extended, order updates) to central `/inbound/provider-events` with its service token. |
| **Central platform** (`services/central`) | `central_db`: users, patient links, referrals, retrieved records (`evidence_items`), papers and OCR, medicine list, rules and medicine names, flags and reviews, packet selection, sent packages and manifests, outbox, notifications, tasks, audit; the protected file store | Institution APIs only, with the user's own token or its service token. **Never an institution's database.** |
| **Worker** (same image, `celery -A app.tasks`) | Nothing of its own; job state lives in `central_db` | Delivers the outbox every 5 s; runs OCR, the AI selection, the purge (every 10 min) and grant close-out (every minute) |
| **Web app** (`web/`) | Nothing (one React app for every role) | Central and the user's own institution service |
| **Keycloak** | Its `keycloak` database: accounts, roles, institution and department groups | — |
| **Outside services (optional)** | — | A language model through Ollama (local, or `:cloud` models on ollama.com) or Anthropic; Google Cloud Vision for handwriting. Only when configured, and see §6. |

There is one PostgreSQL server with **separate databases and logins** per owner (`infra/postgres/init`). Central has
only `central_db` credentials. Redis is only the job queue.

## 2. Identity and authorization

- **Sign-in:** OIDC authorization code with PKCE (client `referral-web`). Institution and department come from
  Keycloak groups; roles are realm roles.
- **Token checks:** every service verifies the JWT and its own audience, then introspects the token, cached for 10 s.
  A disabled account stops working within seconds. Central also checks its own `users.account_status`.
- **Roles:**
  - `clinician`: referring or receiving doctor. **The only role that sees clinical content** (AGENTS.md rule 12,
    [decision](decisions/2026-10-29-doctor-only-clinical-content.md)).
  - `clinic_staff`: retrieves records, uploads papers, sends, tells the patient, closes; takes referrals in. Sees
    titles, sources, dates, statuses and counts only, never values, diagnoses, medicines, flags, papers or the letter.
    This is enforced by the serializers' staff views and doctor-only endpoints.
  - `diagnostics_staff`: laboratory, radiology and ECG.
  - `institution_admin`: accounts, roles, record sharing and audit, but no clinical records.
  - `rule_reviewer`: medication rules and medicine names.
- **Role templates** (`rules/roles/templates.v1.json`): named bundles of these roles, each with a home screen and a
  menu.
  - Admins apply a template on **Accounts and roles**. The platform changes the user's Keycloak roles; this needs
    `view-realm` and `manage-users` on central's service account.
  - It never changes the admin's own account, another institution's account or a service role, and it is audited.
  - The menu only hides screens. Every API still checks the role itself.
- **Source authorization:** each institution decides for itself.
  - Its own staff are allowed by role.
  - Anyone else needs an **access grant** for that patient and category. A grant is created when that institution's
    staff confirm a patient link.
  - Grants **expire**: 14 days by default, 30 at most. Administrators can extend them, and they are revoked at every
    institution when the referral finishes.
  - Central forwards the user's own token, so the institution decides about that user. Identity headers sent by a
    browser are never trusted.
- **Service calls:** central → institutions with `svc_central`, institutions → central with `svc_provider`.

## 3. The flows

### Referral (`REF-…`)
1. **Request:** the doctor fills in the form: destination hospital and department (optionally a doctor), reason (the
   headline), consultation notes, urgency, and the procedure in their own words with the features it involves
   (surgery, anaesthesia, contrast, bleeding risk …).
2. **Linking:** staff ask other institutions to confirm the patient (records request). Linking is never done on
   matching names or IDs, and only `verified` links are used.
3. **Retrieval** (`integration/retrieval.py`):
   - It asks every linked institution: up to `MAX_RETRIEVAL_SOURCES` (5), most recently visited first. The rest are
     listed as skipped.
   - Visits, results and imaging go back the years set for the specialty (`SPECIALTY_HISTORY_YEARS`). Conditions and
     current medicines come whatever their date.
   - Unavailable, denied or expired sources are shown as such, never as "no history".
4. **Packet selection** (`selection/selection.py`):
   - A rule-based default ticks current conditions, previous surgery, current medicines, staff-added items, and the
     last 6 months of visits, results and imaging.
   - A model, if configured, may recommend adding records, with a reason. It never removes a default item, and
     records it leaves out are listed under "Not included".
   - **The doctor decides** while reviewing the packet. Every choice is recorded. Staff see the records by title only.
5. **Papers** (`documents/processing.py`): staff upload them. OCR uses Tesseract (printed text) or Google Cloud Vision
   (also handwriting). Medicine and lab fields are proposed, and **the doctor** checks each against the page image.
6. **Medicines and flags:** see §4.
7. **Ready → doctor's packet review → send:**
   - Staff mark it ready.
   - The doctor checks the papers, confirms the medicines with the patient, decides every flag (Reviewed, Ignore or
     Research), reviews the ticked records and the letter, and marks the **packet reviewed**. A later clinical change
     clears the review.
   - Staff send.
   - The package (`sending/packages.py`) gets a SHA-256 fingerprint and a manifest. It is delivered to the receiving
     institution, and a copy goes to the sending clinic's own system.
8. **Receiving side:**
   - Intake staff acknowledge it, confirm the patient on arrival (match or register as new) and assign a doctor. They
     see who, from where, the urgency and the record titles only; the assigned doctor sees the referral.
   - The doctor **accepts or declines** (with a reason) and can ask questions. There is **no written response**
     ([decision](decisions/2026-10-28-no-specialist-response.md)).
   - The requesting doctor and staff are notified.
   - The receiving doctor presses **Mark as complete** when finished. It is never automatic.
9. **Follow-through:** staff record that the patient was told; follow-up tasks are optional; the **doctor or staff**
   close it.

### Test or scan request (`TST-…`)
1. The doctor lists tests, each sent by staff as an order to a laboratory, radiology or ECG department.
2. The department confirms the patient, then accepts or rejects, schedules and reports. A report needs values, or
   findings, an impression and images.
3. Results come back to the doctor. Staff tell the patient and close it.

### Status model (`referrals/state.py`)
`draft → requested → submitted → acknowledged → accepted → (followup_pending) → closed`, with `declined` and
`cancelled` ending a referral, and `submitted → response_returned → closed` for test requests (results back). Every
change carries `expected_version` (a stale save gets 409). A clinical change after sending opens an **amendment**:
a new version is sent and the earlier one stays unchanged.

## 4. Medicines and flags (`medications/`)

- **Names → ingredients** (`mapping.py`):
  - **Hand-checked names** (`rules/terminology/medicine-names.pk.json`, `brands`) match anywhere in what was written.
  - **DRAP register brands** (`register_brands`, about 5,000) match only at the **start** of the written name. Short
    names and ordinary words are not loaded, and the hand-checked list wins.
  - Names DRAP uses for two medicines (e.g. Glare) are never guessed: the doctor picks the product by company.
  - An unrecognised medicine is flagged and never treated as safe.
- **Flags** come only from the deterministic evaluator (`evaluator.py`):
  - reviewer-approved procedure rules (drug class × procedure feature);
  - DDInter drug–drug interactions;
  - warnings read from US drug labels, with the quote.
  - Each flag shows its source. "Reviewed" means seen, not cleared, and no flag advises changing a medicine.
- **AI suggestions:** an offline model suggests possible clashes for pairs DDInter doesn't cover. They are labelled
  "AI suggestion, not verified", never flags, and are sent in the package with the doctor's decision.

Details and coverage figures are in [medication-flagging.md](medication-flagging.md).

## 5. Data lifecycle ([data-lifecycle.md](data-lifecycle.md), [data-inventory.md](data-inventory.md))

| When | Shared records (**provisional numbers**) |
|---|---|
| Sent, not yet accepted | Kept, no limit |
| Accepted | Safety limit `ACCEPTED_HOLD_DAYS` (30); the receiving doctor can extend it by 30 days, with a reason |
| Marked complete | Removed `WORKING_SET_GRACE_HOURS` (72) later |
| Declined | Removed straight away |
| Cancelled | Removed 72 hours later |
| Test request | Removed 72 hours after the results are back or it ends |

- Removal clears the content **on the platform and at the receiving institution**. The receiver keeps its own
  decision and questions.
- What stays: the reference, status, audit, the package manifest and its fingerprint. The screens say "no longer
  held", never "none".
- Removal waits until everything sent has been delivered.

## 6. Language models and privacy ([decision](decisions/2026-10-28-cloud-model-privacy.md))

- **Providers** sit behind `LLMProvider` (`generation/provider.py`), chosen with `LLM_PROVIDER`:
  - `ollama`: a local model (e.g. `medgemma:4b`) or a `:cloud` model such as `gemma4:cloud`;
  - `anthropic`: `claude-opus-5-5`;
  - `openai_compatible`: e.g. vLLM or Kimi.
- **What the model does:** recommends records for the packet, and reads fields from papers when
  `EXTRACTION_MODE=auto`. Its output is checked in code; anything that fails is discarded, and the rule-based
  result stands. The model has no tools.
- **Privacy** (`generation/privacy.py`):
  - Input is always de-identified: no name, CNIC, record numbers or date of birth (age and sex instead); doctors' and
    institutions' names removed; dates as days before the referral.
  - A model outside this computer is used only with `LLM_EXTERNAL_ALLOWED=true`, and only over https.
  - Each call is audited with its destination; content is never logged.
- **Handwriting OCR:** `OCR_ENGINE=google_vision` sends page images to Google, and these cannot be de-identified
  ([decision](decisions/2026-10-28-handwriting-ocr.md)).
- **Synthetic data only.** Everything works without a model or a Vision key (FR-58).

## 7. Invariants (AGENTS.md)

- **Sent means received:** "Submitted" is set only when the receiving institution confirms receipt. Retries reuse the
  delivery key, and inbound events are deduplicated by event key.
- **Immutable packages:** the SHA-256 and manifest never change. A copy can be checked against them at any time
  (`POST /referrals/{id}/packages/{v}/verify`).
- **Never overwrite original data:** corrections create revisions, and source records keep every version.
- **Unavailable is never "none":** an unavailable, denied, expired or not-retrieved source never becomes "no history"
  or "safe".
- **Audit:** every access, retrieval, link change, correction, decision, delivery, role change, removal and model call
  is recorded with actor, institution, action, target, time and outcome.
- **Only doctors see clinical content** (rule 12): staff and administrators get titles, statuses and counts; the
  doctor reviews the packet before staff send.

## 8. Module ownership (three members)

| Member | Owns |
|---|---|
| Member 1: workflow and UX | `services/central/app/{referrals,followup,sending,selection,workqueue.py,audit_router.py}`, `web/src/features/{referrals,incoming,workqueue}`, shared components |
| Member 2: federation and platform | `services/provider`, `libs/common`, `services/central/app/{integration,identity,delivery,lifecycle}`, `infra/`, `scripts/` (seed, backup, deployment), `web/src/features/{identity,admin,orders}` |
| Member 3: documents and medication rules | `services/central/app/{documents,medications,generation,diagnostics,tasks.py}`, `rules/`, `evaluation/`, `web/src/features/{documents,rules}` |

Changes to shared contracts (`libs/common/refcommon/exchange.py`, `contracts/`), schemas and authentication need the
consuming member's approval (AGENTS.md). The changes made on 2026-10-27/28 are listed for review in the decision
records.
