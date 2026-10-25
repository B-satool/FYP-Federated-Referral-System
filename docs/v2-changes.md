# Version 2: what changed and why

Version 2 rebuilds the prototype around the team's review feedback: any clinic or hospital can refer a patient to any department of another hospital. The seed data is five Karachi patients with different conditions. Work is split between doctors and staff, and the steps are simpler. Everything is still synthetic.

This branch (`v2`) is not merged into `main`. It changes database schemas, the exchange formats in `libs/common/refcommon/exchange.py` and every member's modules, so AGENTS.md requires the owners' review first.

## 1. Feedback and what was done

| Feedback | What v2 does |
|---|---|
| Seed data should be local, more varied, and limited | All earlier data was removed. The five patients in `seed-data/` (Rubina Akhtar, Muhammad Tariq Mahmood, Abdul Rehman Gondal, Shazia Parveen, Imtiaz Ali Soomro) each have a different department and a few medicines and records. Each institution loads only its own part of each patient. |
| Institutions specific to Pakistan | Dr Ali's Clinic, Clifton (clinic); Chughtai Lab (laboratory); Ziauddin Hospital and Aga Khan University Hospital (hospitals with departments, laboratory and radiology). The names are used as source-system names only. |
| Show the department being referred to, and optionally the doctor | The form asks for: referring department and doctor; destination hospital, department (that hospital's list) and, optionally, a doctor from that department. The receiving hospital's doctors see the referrals for their own department, or those naming them. |
| Any specialty, not just orthodontics | 17 clinical departments and a procedure list for each department. |
| "Priority" was vague | It is now called urgency, with time frames: Urgent (within 1 week), Soon (within 2 weeks), Routine (within 4 to 6 weeks). The form also says emergencies go to the emergency department. The system never sets urgency. |
| We could verify a patient link ourselves | The other institution now confirms the link. Its staff look the patient up by CNIC in their own records, then confirm the matching record, register the patient as new, or reject. Records open only after that, because approving also creates their sharing grant. |
| Retrieve only what a referral needs, from the most recent place | Each institution returns conditions, previous surgery, current medicines only, plus visits, results (latest per test) and imaging from the last 6 months. The platform uses only the most recently visited hospital, clinic and laboratory. Older ones are listed as "not the most recent" with dates. An unavailable source is shown as unavailable, never as "no history". |
| Duplicate records (the same prescription brought in and held at a linked place) | Medicines are grouped by ingredient and strength. The same medicine from several places is shown once, listing every place that records it. A different dose is highlighted for staff to resolve. |
| Add over-the-counter medicines | Staff add any medicine the patient reports, marked as over-the-counter, and confirm they asked the patient about all medicines. |
| Doctor and staff need different interfaces | Doctors fill in the form, acknowledge medication flags, see results and review the response. Staff link the patient, gather records, check papers and medicines, send test orders, send the referral, inform the patient and close it. Each role has its own work queue, navigation and steps. |
| Medication flags: automatic, not manual reviewing | Flags are calculated automatically from the current medicines and the planned procedure. The doctor acknowledges each one. The old step of confirming each medicine's current use is gone, because only current medicines come in. |
| Checklist and clarifications: too much repetition | Replaced by one "before sending" list: request submitted, destination confirmed the patient, records retrieved, papers checked, patient asked about medicines, dose differences resolved, rules checked, doctor acknowledged the flags. |
| Medication use verified several times | Verified once: a medicine counts once it is a current source record, a paper item staff have checked, or something staff recorded from the patient. |
| Medical rules should not be hard-coded | Rules and medicine names live in the database. They are edited in the app (Medication rules, Medicine names) and versioned. A clinical reviewer approves each version before it applies. A rule is "drug class × procedure features" (for example antiplatelet × major surgery), so it covers every procedure with that feature. |
| Tests, scans and equipment the clinic does not have | Diagnostic requests are part of the referral but are separate orders. Each goes to a laboratory, radiology or ECG department, with its own status: requested → accepted or rejected (with a reason) → scheduled → done → result returned. The department confirms the patient first. Results come back into the referral, the doctor is notified, and if the referral was already sent the result is forwarded to the specialist. |
| Specialist response | Acknowledge → accept, decline (with a reason) or ask for more information → write and send the response (assessment, plan, instructions for the clinic, appointment). |
| Follow-through | Staff record that the patient was told. Tasks are tracked to an outcome. The referral closes once the doctor has reviewed the outcome. |

## 2. Decisions the team made

1. **Who refers:** any clinic or hospital can refer to any department of another hospital.
2. **Which records:** only the most recently visited hospital, clinic and laboratory are used. Trade-off: something recorded only at an older hospital is not retrieved automatically. It is listed as skipped with the date, so staff can see it was not used.
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
| All linked sources retrieved | The most recent of each kind (decision 2) |

## 4. Not done, or still open

- **Drug-to-drug interactions** are not implemented. The checks are drug against procedure only, as agreed. Pakistan-specific brand names are already mapped to ingredients (`rules/terminology/medicine-names.pk.json`). An interaction check would go on to map ingredients to RxNorm or ATC codes, look them up in DDInter or a licensed source, and have a pharmacist confirm them.
- **Clinical content** is plausible but not reviewed. This covers the rules, references, procedure features and brand mappings. The seed marks the rules as approved by a demo reviewer so the demo works straight away. A named clinician must check them before any real use.
- **Documents not updated:** `docs/architecture.md`, `docs/traceability.md` and `docs/demo-script.md` sections that describe v1 in detail. The integration examples in `contracts/` were not regenerated either, because they belong to their owner (`scripts/export_contract_examples.py` and `scripts/export_fhir_samples.py` need updating for v2).
- **The shared Neon copy** still holds v1 data. Republish it with `scripts/publish-shared-db.ps1` after setting it up for the new databases.
- A test order carries the sending institution's name inside the patient block (`patient.sender_name`), because the order envelope has no field for it. Add one if the format is revised.

## 5. Running v2

v2 uses new databases and new Keycloak accounts, so start from a clean volume:

```powershell
git checkout v2
docker compose down -v          # deletes the old v1 data
docker compose up -d --build
.\scripts\reset-and-seed.ps1 -Force
```

`.env` needs the new settings (`DRALI_*`, `CHUGHTAI_*`, `ZIAUDDIN_*`, `AKUH_*`); see `.env.example`.

Checks on this branch:
- **API flow:** `tests/` runs the full P5 flow and every patient's expected flags. 7 tests.
- **Rule logic:** `services/central/tests` has 15 unit tests.
- **Browser journey:** `web/e2e/smoke.spec.ts` runs the whole journey across six accounts in Chrome.
