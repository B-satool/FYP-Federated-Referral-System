# 6. Component design

> **Superseded in part by section 18 (spec v4, 2026-10-30).** Packet selection runs in the browser (floor) and through the AI relay on request; flags run in the browser (Layer 1) with an AI Layer 2; papers are read and encrypted on the device; the server-side selection, evaluator and OCR paths are kept only for tests and test-and-scan orders (sections 18.5 to 18.7).

This section describes each component's responsibilities, main rules and collaborators. The exact endpoints, request bodies and access checks are generated in Appendices F and G.

## 6.1 Referrals and the status machine (`central/app/referrals`)

**Two kinds of request.**

- **`referral`:** goes to a doctor or department at another clinic or hospital (`destination_institution`, `destination_department`, optional `destination_doctor`).
- **`test`:** one or more tests or scans. Each diagnostic request carries its own destination.

**Creating a request.** The doctor creates the request (`POST /referrals`, status `draft`) with:

- the reason (the headline) and optional **consultation notes** underneath (symptoms, history, examination), which go into the letter, the package and, de-identified, the AI recommendation;
- the urgency (`urgency`: urgent within 1 week, soon within 2 weeks, routine within 4 to 6 weeks);
- the procedure status (`procedure_status`: `planned`, `none` or `unknown`);
- for a planned procedure, its name in their own words and its features (`procedure_tags`, Section 10.4).

The patient is taken from the referring institution's own index (`GET /patients/search`, which calls that institution's service with the user's token). Name, date of birth, sex and CNIC are copied onto the referral for display and for the receiving side's identity check.

**Status machine.** `state.py` holds the transition table (Appendix H). `transition()` rejects any move that isn't listed (`409 invalid_transition`). It increments `row_version`, applies the working-set rule for the new status, and writes a `referral_events` row and an audit event.

**Editing.** Clinical edits check `ensure_clinical_edit_allowed()`, which blocks them in `response_returned`, `followup_pending`, `closed`, `declined` and `cancelled`. `mark_clinical_change()` handles a change after a version was sent: it sets `amendment_open`, writes an `amendment_started` event and notifies staff that a new version must be sent. Every edit carries the expected `row_version` (optimistic concurrency).

**Status labels.** "In progress" becomes "With the doctor for review" once staff mark it ready, and "Ready to send" once the doctor marks the packet reviewed. For test requests, "submitted" reads "Tests sent" and "response returned" reads "Results received".

## 6.2 Identity and patient linking (`central/app/identity`)

**Link kinds.**

- **`records`:** "you have treated this patient; confirm the record and share it".
- **`intake`:** "this patient is arriving with a referral or order; match them to a record or register them as new".

**Flow.**

1. Staff at the requesting institution create a link request with the patient's identity details from their own record (`POST /patient-links` or `POST /referrals/{id}/links`).
2. Staff at the target institution see it under Records requests. `POST /patient-links/{id}/lookup` asks their own service (`/identity/lookup`) for candidates, each field compared (name, date of birth, sex, CNIC).
3. They approve with the matching local ID (or register the patient as new, for intake only), or reject with a note. Matching IDs or names are never enough on their own (invariant 3), and one target record cannot be linked to two different requester patients (`409 record_linked_elsewhere`).
4. **On approval of a `records` link:** the platform asks the target service to create an access grant (`POST /sharing/grants`, default 14 days, tied to the referral reference).
5. **On approval of an `intake` link:** the target service is told which local record the incoming referral and orders belong to (`POST /intake/patient`).
6. **Invalidation** (`POST /patient-links/{id}/invalidate`) keeps the history in `patient_link_events`. Records from that link stop being used, and referrals that used them are flagged for review.

**Account administration.**

- **Disable and enable:** `POST /admin/users/{id}/disable|enable` can be used only by an administrator of the same institution, and never on their own account. They do three things:
  - set the user's `enabled` flag in Keycloak through its admin API;
  - on disable, end the user's sessions and clear the token cache;
  - set the central `account_status`, which `security.get_principal` checks on every request (Section 8.2).
- **Role templates:** `POST /admin/users/{id}/apply-template` changes the user's realm roles in Keycloak through its admin API. It replaces only roles that templates manage, and never touches service roles. The change applies at the user's next sign-in and is audited.

## 6.3 Retrieval (`central/app/integration`)

`retrieval.retrieve()`:

1. **Start the working set.** If it was previously removed, this begins a new one with fresh rows.
2. **Collect the sources:** the referring institution's own record plus every **verified** `records` link (`linked_sources`). Intake links and patients registered as new are not record sources.
3. **Ask when the patient was last seen** at each linked institution (`GET /patients/{id}/activity`), in parallel. Denied, expired or unavailable sources are recorded with that status. A denial revokes the centrally held copies from that source (`access_revoked`).
4. **Choose the sources:** every reachable institution, most recently visited first, up to `MAX_RETRIEVAL_SOURCES` (5) besides the referring one. Any beyond the limit get a `skipped` row stating the last-seen date, and their items are deselected.
5. **Fetch the records** from every chosen source in parallel (`GET /fhir/patients/{id}/records?since=…`). `since` is the start of the specialty's history window (`SPECIALTY_HISTORY_YEARS`, otherwise `REFERRAL_HISTORY_YEARS`, 3).
6. **Import the records** (`importer.parse_bundle`): validate each FHIR resource and map it to an evidence item. Existing source versions are deduplicated, and newer versions supersede older ones. Each source's outcome is stored in `source_retrievals`: `successful`, `partial` (some categories withheld or some resources invalid), `empty`, `denied`, `expired`, `unavailable` (retryable), `invalid` or `skipped`.
7. **Apply the default selection** to every new item, then re-run the medication evaluation (`workflow.after_change`).

`sources.py` forwards the **user's own token** with an `X-Referral-Id` header, so each institution decides about that user and records the referral context in its audit. Transient failures (connect, timeout, protocol) are retried up to `SOURCE_MAX_RETRIES` with a `SOURCE_TIMEOUT_SECONDS` timeout. Denials and invalid data return at once as distinct outcomes.

## 6.4 Documents and OCR (`central/app/documents`)

**Upload** (`POST /referrals/{id}/documents`):

- **Who:** staff or the doctor upload; only the doctor opens a paper, its fields or page images.
- **Accepted types:** PDF, PNG and JPEG, detected from the content, not the file name.
- **Limits:** at most 10 MB and 10 PDF pages (`MAX_UPLOAD_BYTES`, `MAX_PAGES`).
- **Storage:** stored under a generated name with its SHA-256. A `jobs` row is created and `process_document` is queued.

**Processing** (worker, `processing.process`):

1. **Choose the text source per page.** Digital PDF pages with reliable embedded text use it. Scanned pages and images are rasterised and preprocessed (EXIF orientation, grey scale, upscaling below 1600 px).
2. **OCR the page.** `OCR_ENGINE=tesseract` (default) reads printed text on this computer. `google_vision` sends the page image to Google Cloud Vision (`DOCUMENT_TEXT_DETECTION`), which also reads handwriting. If Vision fails, the page falls back to Tesseract and the run says so. Lines carry positions and a confidence, stored as tool metadata, never as clinical probability.
3. **Extract fields.**
   - **Language model** (`EXTRACTION_MODE=auto` or `llm`, model configured): the model receives the de-identified lines (dates kept) and must return JSON matching a strict schema. Every proposed field must cite existing line IDs, or the whole answer is rejected.
   - **Rules** (otherwise, or on rejection with `auto`): the deterministic `rules-extractor/2`.

   Both propose only medicine and laboratory fields.
4. **Store the proposals.** Fields become evidence items with `review_state=proposed` and `verification_status=unverified`, linked to their page and region. A medicine from a paper enters the medicine list only after staff verify it.

**Access to files.** Files and page images are served only through authenticated endpoints that check access to the referral (`GET /documents/{id}/file`, `/pages/{n}`).

## 6.5 Evidence review (`central/app/evidence_router.py`)

Every action here is **doctor-only**. Staff get the staff view of each record: its title (`refcommon.exchange.record_title`, for example "Lab result: HbA1c"), source, date and whether it is ticked, never values, findings or AI reasoning.

| Action | Endpoint | Effect |
|---|---|---|
| Select or deselect for the packet | `POST /evidence/{id}/select` | The doctor's decision; always wins over default and AI (`selection_source=staff`, meaning a person's choice, with who and when) |
| Verify against the paper | `POST /evidence/{id}/verify` | `verification_status=verified` |
| Correct a value | `POST /evidence/{id}/correct` | New current value; original kept; revision written |
| Mark unresolved | `POST /evidence/{id}/unresolve` | Cannot be confirmed |
| Exclude or restore | `POST /evidence/{id}/exclude|restore` | Reason required; stays in history |
| Manual entry | `POST /referrals/{id}/evidence/manual` | `origin=manual`, always in the default selection |

Every action writes an `evidence_revisions` row and an audit event, checks the item's `row_version`, and triggers re-evaluation of the medication flags. A clinical change after sending opens an amendment.

## 6.6 Medicines (`central/app/medications`)

**The current-medicine list** (`service.py`):

- **Sources of medicines:** active prescriptions from sources, verified paper fields, and medicines staff add after asking the patient (including over-the-counter ones).
- **Duplicates:** entries are grouped by ingredient (or normalised name when unrecognised). One representative is shown per strength; the others point to it with `duplicate_of` and keep their sources. Different strengths of the same ingredient set `dose_differs`, which staff must resolve before sending.

**Name mapping** (`mapping.py`): a written name maps to an ingredient and drug class through `medicine_names`.

- **Statuses:** `mapped`, `ambiguous`, `unmapped`, `staff_mapped`. A name that matches more than one ingredient is never treated as a match.
- **DRAP register brands** (`register_brand`): matched only where the written name *starts* with the brand. Short names, ordinary words and generic-name words are excluded. Hand-checked names always win.
- **Ambiguous register names** (`register_ambiguous`, such as Glare, which is both gliclazide and ibuprofen): carry `options` and stay unmapped until the doctor or staff pick the product by its company (`POST /referrals/{id}/medications/{entry}/mapping` with `company` and `drap_reg_no`). The choice is audited.

**Rules** (`rules.py`):

- **Manual drug-class-by-procedure rules** are edited in the app. Each edit creates a draft version, and only the approved version is active.
- **Imported data:** DDInter interactions and drug-label rules. They are active as loaded and labelled automatically generated, not clinically reviewed.
- **Rule set fingerprint:** `ruleset_releases` records the exact set in force by hash.

**Evaluation:** see Section 10. Every change to records, papers, medicines or the procedure calls `workflow.after_change()`, which runs `reevaluate()`. That writes an `evaluation_runs` row and supersedes or creates flag versions.

**Who:** the whole medicine list is doctor-only (decision 2026-10-29): viewing names and flags, adding medicines the patient reports, excluding, mapping ambiguous brands and confirming the list. Staff get a summary (number of medicines and flags, how many await the doctor).

**Doctor's decisions** (`POST /referrals/{id}/flags/{flag_id}/acknowledge`): `reviewed`, `ignore` (not relevant for this patient) or `research` (needs follow-up), with an optional note. A decision means the flag was seen, never treatment clearance (invariant 5). Ignored flags stay visible.

**AI suggestions:** possible clashes for pairs with no DDInter entry, scored offline. The doctor marks each `ignore` or `research`. They travel in the package labelled "AI suggestion, not verified" and never block sending.

## 6.7 Packet selection (`central/app/selection`)

1. **Default (always):** `in_default()` selects:
   - staff-entered and paper items;
   - active conditions, surgeries, current medicines and allergies;
   - visits, results and imaging from the last 6 months (`REFERRAL_WINDOW_DAYS`, 183).

   Older items and resolved conditions start unselected.
2. **AI recommendation (optional):** after retrieval, `recommend_selection` runs in the worker. It sends at most 150 candidates, each cut to 300 characters and de-identified. The model returns, for every record id, `include`, `exclude` or `optional`, a relevance and a reason of at most 25 words, plus up to 5 "missing" phrases.
3. **Validation** (`validate()`): every id must belong to this referral and appear once, and the values must come from the allowed sets. Any failure there rejects the whole answer, and the default stands. A reason with treatment, dosing or action words is withheld instead: it is never shown, and that record keeps its default (section 9.2).
4. **Applying the answer:**
   - The model may add records and mark defaults as low relevance.
   - It can never remove a default item, and it never overrides a staff choice.
   - Excluded items are listed under "Not included" with the reason.
5. **The doctor decides:** they tick or untick anything, and their choice always wins. Staff see the ticks and titles only.

Each attempt is a `selection_runs` row: status, provider, model, prompt version and hash, item count, truncation, missing phrases and error. The package's `selection` field records how every item was chosen.

## 6.8 Sending (`central/app/sending`)

**Readiness** (`readiness.py`) is one checklist with no repeated items:

- **Staff items** (before "ready for the doctor"): records retrieved; papers uploaded and read.
- **Doctor items** (after that): papers checked; medicine list confirmed with the patient, including over-the-counter ones; dose differences resolved; medicines checked against the rules (system); every flag that requires a decision decided.
- **The doctor's packet review** (`POST /referrals/{id}/packet-reviewed`): allowed only when the doctor items are done. It sets `packet_reviewed_by`/`_at`. Any later clinical change clears it (`workflow.clear_packet_review`, `mark_clinical_change`, and an AI recommendation that changes the selection).

Staff send only when every blocking item is done. The receiving institution confirms the patient on arrival, so that is not a condition for sending. The letter preview and the sent package's content are doctor-only; staff see the version, sender, time and fingerprint.

**The brief** (`brief.py`) is deterministic, with no model involved. It is laid out like a referral letter:

- reason, consultation notes and planned procedure;
- current medicines, history and recent visits;
- investigations, grouped by panel, and imaging;
- "what could not be obtained": unavailable, skipped, denied or expired sources, stated as limitations, never as "no history".

Every record-derived line cites its evidence id. Medication flags are not restated in the letter; they travel as structured flags.

**Sending** (`packages.send`):

1. Build the `PackageEnvelope` (Appendix G) with the selected evidence snapshots, flag snapshots with decisions, the evaluation summary, limitations, diagnostic requests, AI suggestions, the selection record and a FHIR `collection` Bundle.
2. Compute the SHA-256 over the hashed fields.
3. In **one transaction**, insert the `referral_packages` row (with its manifest), a `deliver_package` outbox row to the receiving institution, and a `sender_copy` outbox row to the referring institution.

The delivery key is `<source>:<reference>:v<version>`. A resend after an amendment creates version + 1 and marks the earlier version superseded.

**Verification.** `POST /referrals/{id}/packages/{v}/verify` recomputes the hash. `verify-own-copy` checks the sending clinic's lasting copy against it.

## 6.9 Delivery and inbound events (`central/app/delivery`)

**Outbox** (`outbox.py`, every 5 s):

- **Pending rows** are posted to the institution endpoint for their kind (Appendix G) with the central service token.
- **Retries** use the same message key. The wait after attempt *n* is 2^*n* seconds, capped at 120 s. After 8 attempts the row is `failed`, the referral's `delivery_status` becomes `failed`, and staff see it under delivery problems and can retry it. A timed-out request may already have succeeded, so the receiver returns the original result for a repeat.
- **On success:** for a package, the referral becomes `submitted` and `delivery_status=delivered`, and the result is stored.

**Inbound** (`inbound.py`, `POST /inbound/provider-events`):

- **Who may send:** only a `svc_provider` identity whose institution matches the event.
- **Deduplication:** by `event_key` in `inbound_messages`.
- **Applying an event:**

| Event | Effect |
|---|---|
| `acknowledged` | `submitted` → `acknowledged` |
| `accepted` | → `accepted`; doctor and staff notified; 30-day hold starts |
| `declined` | → `declined` with reason; doctor and staff notified; purge queued at once |
| `info_requested` | `clarifications` row; doctor and staff notified |
| `response_returned` | Legacy: response stored, sender copy queued |
| `completed` | Receiver finished; records removed 72 h later; both sides notified |
| `hold_extended` | Expiry moved to 30 days from now |
| `order_accepted`, `order_rejected`, `order_scheduled`, `order_done`, `order_reported` | Applied to the diagnostic request; results stored with attachments |

## 6.10 Diagnostics (`central/app/diagnostics`)

**Lifecycle.** A test request lists one or more diagnostic requests, each `draft` until staff send it. Sending writes a `deliver_order` outbox row with a `DiagnosticOrder` envelope, which carries the patient's identity for intake. The laboratory or imaging department then moves the order through `requested` → `accepted` or `rejected` (with reason) → `scheduled` → `done` → `reported`.

**Reports.** A report carries text, findings, impression, values and, for scans, image attachments. The department also files it in its own records. On the platform, attachments are stored in the protected file store and served through authenticated endpoints.

**Seeing results.** The doctor marks each result seen, and a test request can be closed only after every result is seen.

**Forwarding is not built.** The contract (`ResultForward`), the outbox kind `forward_result` and the institution endpoint `POST /inbound/results` exist so a report could be shown beside a referral at the receiving hospital. No current code path creates a `forward_result` message (Section 16).

## 6.11 Follow-through (`central/app/followup`)

**Before closing a referral:**

- the receiving hospital must have accepted it;
- staff must have recorded that the patient was told the outcome (`POST /referrals/{id}/patient-informed`);
- every optional follow-up task must have an outcome.

Then the doctor or staff close it (`POST /referrals/{id}/close`).

**Clarifications.** Requests for more information are answered by the doctor with `POST /clarifications/{id}/answer` (staff see that a question exists, not its text). The answer is delivered to the receiving institution as a `clarification_answer` outbox row.

**Legacy responses.** The response review endpoint remains for responses sent before 2026-10-28 (decision "no specialist response").

## 6.12 Notifications and work queue

**Notifications** (`notifications.py`) go to one user (`recipient_id`) or to a role at an institution (for example the referral desk staff). They carry a kind, title, body and a link to the relevant tab. They are listed and marked read through `/notifications`, and every query is scoped to the caller.

**The work queue** (`GET /work-queue`) is role-based. It contains:

- **For doctors:** `drafts`, `flags_to_acknowledge`, `results_to_see`, `responses_to_review` (legacy) and `in_progress`.
- **For staff:** `to_prepare` (with readiness progress), `link_requests` from other institutions, `tests_to_send`, `delivery_problems` and `follow_up`.
- **For everyone:** `info_requests` and the latest unread notifications.

## 6.13 Institution service (`services/provider/app`)

**Receiving a referral.** `POST /inbound/referrals` stores the package idempotently by delivery key and creates or updates the `case`. **Intake staff** see the case details and the attached records by title only; the **doctors** see the letter, flags and records (decision 2026-10-29). Case lifecycle:

- `received`
- → `acknowledged` (staff)
- → `assigned` (staff choose the doctor; changeable until the doctor decides)
- → `accepted` or `declined` (doctor; decline needs a reason)
- → completed (doctor, any time after accepting; never automatic)

`hold_until` mirrors the platform's 30-day hold, and `POST /cases/{id}/extend-hold` extends it. On `POST /inbound/referral-expired` the service removes its copy of the packages and forwarded results and sets `shared_removed_at`. Its own decision, questions and response are kept.

**Diagnostic orders.** `POST /inbound/orders` creates the order, then `accept`, `reject`, `schedule`, `done` and `report` (with attachments stored in `order_attachments`).

**Outbound events.** Every decision writes an `outbox` row in the same transaction. A daemon thread started with the application (`_outbox_loop`) posts pending rows to `POST /inbound/provider-events` with the institution's service token, retrying with the same event key. `POST /outbox/{id}/retry` lets the doctor retry a failed one.

**Access.** Doctors, staff and diagnostics staff use their own institution's system directly through the web proxy. Every endpoint checks the caller's institution and role (`require_own`). Only the platform's service identity may call the `inbound/*` endpoints.
