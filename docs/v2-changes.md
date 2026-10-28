# Version 2: what changed and why

Version 2 rebuilds the prototype around the team's review feedback: any clinic or hospital can refer a patient to any department of another hospital. The seed data is five Karachi patients with different conditions. Work is split between doctors and staff, and the steps are simpler. Everything is still synthetic.

Version 2 was merged into `main` on 2026-10-27, with the supervisor's go-ahead. It changes database schemas, the exchange formats in `libs/common/refcommon/exchange.py` and every member's modules, so the owners should still review the changes listed in [decisions/](decisions/). Where a later section differs from an earlier one, the later one applies.

## 1. Feedback and what was done

| Feedback | What v2 does |
|---|---|
| Seed data should be local, more varied, and limited | All earlier data was removed. The five patients in `seed-data/` (Rubina Akhtar, Muhammad Tariq Mahmood, Abdul Rehman Gondal, Shazia Parveen, Imtiaz Ali Soomro) each have a different department and a few medicines and records. Each institution loads only its own part of each patient. |
| Institutions specific to Pakistan | Dr Ali's Clinic, Clifton (clinic); Chughtai Lab (laboratory); Ziauddin Hospital and Aga Khan University Hospital (hospitals with departments, laboratory and radiology). The names are used as source-system names only. |
| Show the department being referred to, and optionally the doctor | The form asks for: referring department and doctor; destination hospital, department (that hospital's list) and, optionally, a doctor from that department. The receiving hospital's doctors see the referrals for their own department, or those naming them. |
| Any specialty, not just orthodontics | 17 clinical departments and a procedure list for each department. |
| "Priority" was vague | It is now called urgency, with time frames: Urgent (within 1 week), Soon (within 2 weeks), Routine (within 4 to 6 weeks). The form also says emergencies go to the emergency department. The system never sets urgency. |
| We could verify a patient link ourselves | The other institution now confirms the link. Its staff look the patient up by CNIC in their own records, then confirm the matching record, register the patient as new, or reject. Records open only after that, because approving also creates their sharing grant. |
| Retrieve only what a referral needs | Each institution returns conditions, previous surgery and current medicines only, plus visits, results and imaging. (Later changed: every linked institution, up to five, with history years per specialty; see 1c and 1d.) An unavailable source is shown as unavailable, never as "no history". |
| Duplicate records (the same prescription brought in and held at a linked place) | Medicines are grouped by ingredient and strength. The same medicine from several places is shown once, listing every place that records it. A different dose is highlighted for staff to resolve. |
| Add over-the-counter medicines | Staff add any medicine the patient reports, marked as over-the-counter, and confirm they asked the patient about all medicines. |
| Doctor and staff need different interfaces | Doctors fill in the form, acknowledge medication flags, see results and can close the referral. Staff link the patient, gather records, check papers and medicines, send test orders, send the referral, inform the patient and close it. Each role has its own work queue, navigation and steps. |
| Medication flags: automatic, not manual reviewing | Flags are calculated automatically from the current medicines and the planned procedure. The doctor acknowledges each one. The old step of confirming each medicine's current use is gone, because only current medicines come in. |
| Checklist and clarifications: too much repetition | Replaced by one "before sending" list: request submitted, destination confirmed the patient, records retrieved, papers checked, patient asked about medicines, dose differences resolved, rules checked, doctor acknowledged the flags. |
| Medication use verified several times | Verified once: a medicine counts once it is a current source record, a paper item staff have checked, or something staff recorded from the patient. |
| Medical rules should not be hard-coded | Rules and medicine names live in the database. They are edited in the app (Medication rules, Medicine names) and versioned. A clinical reviewer approves each version before it applies. Only clinical reviewers see these two screens; doctors and staff see the flags, not the rule list. A rule is "drug class × procedure features" (for example antiplatelet × major surgery), so it covers every procedure with that feature. |
| Tests, scans and equipment the clinic does not have | Diagnostic requests are part of the referral but are separate orders. Each goes to a laboratory, radiology or ECG department, with its own status: requested → accepted or rejected (with a reason) → scheduled → done → result returned. The department confirms the patient first. Results come back into the referral, the doctor is notified, and if the referral was already sent the result is forwarded to the specialist. |
| Specialist response | Acknowledge → accept, decline (with a reason) or ask for more information. (The written response was removed on 2026-10-28; see 1d.) |
| Follow-through | Staff record that the patient was told. Tasks are tracked to an outcome. The doctor or staff close the referral. |

## 1b. Second round of feedback (after testing v2)

Where this section differs from section 1 (procedure list, tests inside a referral, confirming the patient before sending, the doctor acknowledging flags while staff still gather records), this section applies.

| Feedback | What changed |
|---|---|
| Procedures do not need a list | The doctor writes the procedure in their own words and ticks what it involves (major surgery, general anaesthesia, fasting, contrast, endoscopy, bleeding risk and so on). Words in the name pre-tick likely features, e.g. "laparoscopic ... ectomy" ticks surgery, anaesthesia, fasting and bleeding risk. The rules match on these features. If a procedure is written but nothing is ticked, procedure checks are shown as not run; nothing is guessed. |
| A doctor may only need a test or scan | **New request** first asks: *Refer to a doctor or department* or *Request a test or scan*. A test request has no hospital-referral part. It is a list of tests, each sent as its own order. Requests are labelled *Referral* or *Test or scan*, with a filter. References are `REF-…` and `TST-…`. |
| Chughtai Lab in the scan options | Chughtai Lab now has a radiology department (account `rad.chughtai`) as well as its laboratory. |
| Doctor's role: request, then review flags | After submitting, the request shows **In progress**. Staff gather records, papers and medicines, then press **Ready for the doctor's review**. Only then does the doctor see the medication flags and mark each as reviewed. Doctors do not add medicines; staff do. |
| Reports need real content | A laboratory report needs every result with its value. A scan or cardiac report needs findings, an impression and at least one image or file (PNG, JPEG or PDF). Images are stored with the result, shown to the requesting doctor, and the result is filed in the department's own records. |
| Tests removed from the referral steps | A referral no longer carries tests. Tests are always a separate test request. |
| Order of events; link confirmation not needed before sending | Sending no longer waits for the receiving hospital to confirm the patient. The referral (or test order) carries the patient's name, date of birth, sex and CNIC with a request to confirm. When it arrives, their staff match their record or register the patient as new. Before sending, staff only contact other places to ask for records. |
| Staff must not stop a referral | Only the requesting doctor can withdraw a request. |
| "Patient does not exist" yet records retrieved | Two kinds of patient-link request now exist. A **records request** (staff ask a place for records): that place matches a record or answers *No record here*, and it cannot register the patient. An **arriving patient** (sent with a referral or order): the receiver matches or registers the patient as new. A patient registered as new is never treated as a source of earlier records. The referring clinic is told which happened. |
| Read like a medical report | The summary is laid out as a referral letter: To/From, patient (with CNIC), urgency, reason, planned procedure, a medicines table, history, recent visits, investigations grouped by panel with date and place, imaging, the medication review (who reviewed each flag) and what could not be obtained. The receiving side sees the same letter. |
| Hospital staff should see referrals, not only the doctor | Incoming referrals go to the receiving institution's staff. They acknowledge receipt, confirm the patient and assign a doctor. A doctor sees only the referrals assigned to them. The referrer's preferred doctor is shown as a suggestion. |
| Clinics and hospitals both receive referrals | Any clinic or hospital can refer to any other, and every one of them has **Incoming referrals**. Any of them can send a test request to any laboratory or radiology department. |
| No "New referral" in the sidebar | Removed. **New request** is on the work queue and the request list. |
| After accepting, go to the response | (Superseded on 2026-10-28: there is no response form; see 1d.) |

## 1c. Spec v3 and the data-lifecycle change (2026-10-27)

Ported from `architecture-spec-v3.md` and `data-lifecycle.patch` (both written for v1). The approval is recorded in [decisions/2026-10-27-data-lifecycle-and-v3.md](decisions/2026-10-27-data-lifecycle-and-v3.md).

| Work package | What was built |
|---|---|
| Temporary access | Grants expire (14 days by default, 30 at most), can be extended with a reason, and are revoked at every institution when the referral finishes. An expired grant shows the source as "expired", never as "no records". The **Source access** screen has an end-date column, Extend, and an "ending within 3 days" filter. |
| A. Working set | Retrieved content is held only while the referral needs it (timing replaced on 2026-10-28; see 1d). The purge waits for every delivery, including the clinic's own copy, which is now sent to the clinic's system (`sent_copies`). The platform keeps the manifest, fingerprint and audit. The screens show "Held for this referral until …", and after the purge "Content has been removed. Reference and fingerprint kept." with a button to check the clinic's copy. See [data-lifecycle.md](data-lifecycle.md) and [data-inventory.md](data-inventory.md). |
| B. Packet selection | Three years of history are retrieved. The rule-based default selects what v2 selected (current conditions and medicines, surgery, and the last 6 months). With a model configured, an AI recommendation adds records or marks them low relevance, with a reason. It cannot remove a default item, and what it leaves out is listed under "Not included". **Staff** decide, and each choice is recorded. Without a model the default applies and the screen says "AI recommendation unavailable". |
| C. Role screens | The menu and home screen come from the role templates through `GET /me`. Administrators change a user's role by applying a template on **Accounts**. |
| D. AI medication suggestions | Ignore / Research (as for flags). They are sent in the package labelled "AI suggestion, not verified", never as flags. |

## 1d. Third round (2026-10-28)

| Change | What was built | Decision |
|---|---|---|
| Role templates actually assign roles | **Accounts and roles**: an admin picks staff, doctor, lab/radiology, administrator or rule reviewer for an account. Fixed: central's Keycloak account lacked `view-realm`, so every change used to fail. | [2026-10-27](decisions/2026-10-27-data-lifecycle-and-v3.md) |
| When shared records expire | No limit until accepted; then 30 days, which the receiving doctor can extend; removed 72 h after they **mark the referral complete**, straight away if declined, and 72 h after a cancel. Removed at the receiving hospital too; it keeps its own decision and questions. The 60-day maximum and the planned 7/30/90-day window are gone. | [referral-expiry](decisions/2026-10-28-referral-expiry.md) |
| No specialist response | The receiving doctor accepts or declines; the requesting doctor and staff are told. **Mark as complete** is a separate, manual button. The clinic tells the patient, then the **doctor or staff** close it. | [no-specialist-response](decisions/2026-10-28-no-specialist-response.md) |
| Retrieval from every linked institution (Sumaiya) | Up to five, most recently visited first; visits, results and imaging back as many years as the specialty needs. | [retrieval-all-sources](decisions/2026-10-28-retrieval-all-sources.md) |
| DRAP brand names | 5,398 brands from Sumaiya's DRAP snapshot loaded as verified (by decision), matched only at the start of a name. Names DRAP uses for two medicines (e.g. Glare) are chosen by company by doctor or staff. Known veterinary products are left out. | [drap-brands-loaded](decisions/2026-10-28-drap-brands-loaded.md), [drap-register-snapshot](decisions/2026-10-28-drap-register-snapshot.md) |
| Test requests show where they went | The "To" column lists the lab or hospital, department and tests. | — |
| AI model and privacy | Gemma 4 through Ollama (`gemma4:cloud`) for packet selection and paper reading. Input always de-identified; external models only with `LLM_EXTERNAL_ALLOWED=true` and https; every call audited. Needs Ollama credits to run. | [cloud-model-privacy](decisions/2026-10-28-cloud-model-privacy.md) |
| Handwriting | Google Cloud Vision reads handwritten prescriptions (`OCR_ENGINE=google_vision`), falling back to Tesseract. Needs a key. | [handwriting-ocr](decisions/2026-10-28-handwriting-ocr.md) |

## 2. Decisions the team made

1. **Who refers:** any clinic or hospital can refer to any department of another hospital.
2. **Which records:** every linked institution, up to five, most recently visited first (2026-10-28; earlier only the most recent of each kind). Any beyond five are listed as not retrieved.
3. **Rules:** edited in the app, still approved by a clinical reviewer (keeps FR-61).
4. **Sending:** staff send once the checks are done. The doctor authorises the referral by submitting the request and acknowledges every medication flag.

## 3. Differences from the SRS (agree these with the supervisor)

| SRS | v2 |
|---|---|
| A clinician approves the exact version that is sent (FR-47) | The doctor submits the request and acknowledges the flags. Staff compile and send each version. Each sent version is still immutable and hashed, and records who requested, who acknowledged and who sent. |
| Orthodontics only (Stage 0 decision) | Any department, with a procedure list per department |
| Language-model brief drafting with evidence citations (FR-41 to FR-46) | The summary is built deterministically from the checked records, with source references. With no clinician approving the final text, an unreviewed AI draft is not sent. The language model is still used, only if configured, to read uploaded papers. Staff check every field it reads. |
| Completeness checklist with overrides (FR-35 to FR-40) | One "before sending" list without overrides |
| Specialist reviews each flag (FR-67) | The specialist sees the flags and the referring doctor's acknowledgments. There is no separate specialist acknowledgment. |
| All linked sources retrieved | Every linked institution, up to five (decision 2) |
| The specialist writes and returns a response (FR-50, FR-51) | The receiving doctor accepts or declines; no written response (2026-10-28) |

## 4. Not done, or still open

- **Drug-to-drug interactions and drug-label rules** were added afterwards (spec v2). DDInter interactions and rules read from US drug labels are flagged with their source, marked automatically generated, and the doctor can Ignore or Research each. See [medication-flagging.md](medication-flagging.md) for what was built, the coverage figures and what is still open.
- **Clinical content** is plausible but not reviewed. This covers the rules, references, procedure features and brand mappings. The seed marks the rules as approved by a demo reviewer so the demo works straight away. A named clinician must check them before any real use.
- **Integration examples** in `contracts/` were not regenerated for v2, because they belong to their owner (`scripts/export_contract_examples.py` and `scripts/export_fhir_samples.py` need updating). The architecture, traceability, demo script and testing pages were rewritten for v2 on 2026-10-28.
- **Live AI and handwriting calls** have not run yet: the Ollama account needs usage credits for `gemma4:cloud`, and there is no Google Vision key. The platform falls back to the rule-based selection and Tesseract.
- **From the access-window plan** (`decisions/2026-10-28-referral-access-window.md`), parts B, C, D and F are not built: the receiver getting only a notification and reading on the platform, the sender copy holding only what the clinic wrote, the watermark and the read-only view. Today the receiver gets the package and removes it at expiry.
- **DRAP:** 5,434 rows have never had their DRAP page checked (they could include veterinary products); 645 combination products are not loaded. See `decisions/2026-10-28-drap-brands-loaded.md`.
- **Accounts:** admins change roles in the app but create accounts in Keycloak.
- **The shared Neon copy** still holds v1 data. Republish it with `scripts/publish-shared-db.ps1` after setting it up for the new databases.
- A test order carries the sending institution's name inside the patient block (`patient.sender_name`), because the order envelope has no field for it. Add one if the format is revised.
- Round two also put the CNIC, a known local record and the intake link request id in the `patient` block of the referral and order envelopes. It added optional `source`, `date` and `group` fields to `BriefStatement` in `exchange.py`, so the letter can be laid out. The contract owner should review these. `ResultForward` and `/inbound/results` are no longer used, because tests are no longer part of a referral.
- Test requests are not checked against the medication rules. For example, metformin before contrast at a scan is left to the radiology department.
- Report images are stored inside the institution database, and in the central file store under `results/`. A real deployment would use the institutions' imaging systems (PACS).
- Keycloak imports accounts only on first start. After pulling, delete the `referral` realm and restart Keycloak to get `rad.chughtai` (see the README troubleshooting). The realm file is generated by `scripts/make_keycloak_realm.py`.

## 5. Running v2

v2 uses new databases and new Keycloak accounts, so start from a clean volume:

```powershell
git checkout main
docker compose down -v          # deletes the old v1 data
docker compose up -d --build
.\scripts\reset-and-seed.ps1 -Force
```

`.env` needs the new settings (`DRALI_*`, `CHUGHTAI_*`, `ZIAUDDIN_*`, `AKUH_*`); see `.env.example`.

Checks on this branch:
- **API:** 22 tests in `tests/` (see `docs/testing.md`).
- **Unit:** 130 tests in `services/central/tests`.
- **Browser:** 3 journeys in `web/e2e`.
