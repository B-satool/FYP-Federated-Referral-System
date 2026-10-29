## Web application (`web/`)

### Routes (`web/src/App.tsx`)

| Path | Screen component |
|---|---|
| `*` | `NotFound` |
| `*` | `SignIn` |
| `/` | `Home` |
| `/accessibility` | `AccessibilityStatement` |
| `/admin/audit` | `AuditLog` |
| `/admin/keys` | `DoctorKeys` |
| `/admin/users` | `AdminUsers` |
| `/callback` | `Home` |
| `/documents/:id` | `DocumentReview` |
| `/incoming` | `IncomingList` |
| `/incoming/:id` | `IncomingCase` |
| `/keys` | `KeysPage` |
| `/medicine-names` | `MedicineNames` |
| `/orders` | `OrderList` |
| `/orders/:id` | `OrderView` |
| `/patient-links` | `PatientLinks` |
| `/privacy` | `PrivacyNotice` |
| `/referrals` | `ReferralList` |
| `/referrals/:id` | `ReferralWorkspace` |
| `/referrals/new` | `NewReferral` |
| `/release-requests` | `ReleaseRequests` |
| `/rules` | `RulesPage` |
| `/terms` | `TermsOfUse` |
| `/work-queue` | `WorkQueue` |

### Feature modules (`web/src/features`)

| Feature | Files |
|---|---|
| `admin` | AdminUsers.tsx, AuditLog.tsx, DoctorKeys.tsx |
| `auth` | NotFound.tsx, SignIn.tsx |
| `documents` | DocumentReview.tsx, DocumentsTab.tsx |
| `e2e` | AiSuggest.tsx, FlagViews.tsx, Papers.tsx, ReceivedPackage.tsx, ai.ts, approve.ts, bundle.ts, deidentify.ts, flags.ts, ocr.ts, records.ts, selection.ts, upload.ts |
| `identity` | ConfirmPatient.tsx, PatientLinks.tsx |
| `incoming` | Incoming.tsx |
| `keys` | DeviceKey.tsx |
| `legal` | LegalPages.tsx |
| `orders` | Orders.tsx |
| `patient` | Consent.tsx, MyCopy.tsx, PatientApp.tsx |
| `referrals` | AuditTab.tsx, HoldNotice.tsx, Journey.tsx, LinksTab.tsx, MedicinesTab.tsx, NewReferral.tsx, Records.tsx, ReferralForm.tsx, ReferralList.tsx, ReferralWorkspace.tsx, RequestTab.tsx, ResponseTab.tsx, SendTab.tsx, TestsTab.tsx, steps.ts |
| `release` | ReleaseRequests.tsx |
| `rules` | MedicineNames.tsx, RulesPage.tsx |
| `workqueue` | WorkQueue.tsx, queue.ts |

### Role templates and menus (`rules/roles/templates.v2.json`)

The menu is built from `GET /me`; it only hides screens. The API checks are the enforcement.

| Screen | Route | Menu group | Roles that see it |
|---|---|---|---|
| `work_queue` | `/work-queue` | Work | clinician, clinic_staff |
| `requests` | `/referrals` | Work | clinician, clinic_staff |
| `incoming` | `/incoming` | Work | clinician, clinic_staff, institution_admin |
| `records_requests` | `/patient-links` | Work | clinic_staff, institution_admin |
| `release_requests` | `/release-requests` | Work | clinic_staff, institution_admin, diagnostics_staff |
| `orders` | `/orders` | Work | diagnostics_staff |
| `rules` | `/rules` | Rules | rule_reviewer |
| `medicine_names` | `/medicine-names` | Rules | rule_reviewer |
| `accounts` | `/admin/users` | Administration | institution_admin |
| `doctor_keys` | `/admin/keys` | Administration | institution_admin |
| `audit` | `/admin/audit` | Administration | institution_admin |
| `device_key` | `/keys` | Security | clinician |

| Template | Name | Realm roles | Institution kinds | Record visibility | Holds keys | Home | Menu |
|---|---|---|---|---|---|---|---|
| `front_desk` | Staff (referral coordinator) | clinic_staff | clinic, hospital | titles_only | no | work_queue | work_queue, requests, incoming, records_requests, release_requests |
| `doctor` | Doctor | clinician | clinic, hospital | content | yes | work_queue | work_queue, requests, incoming, device_key |
| `lab_radiology` | Laboratory, radiology or ECG staff | diagnostics_staff | laboratory, hospital, clinic | titles_only | no | orders | orders, release_requests |
| `institution_administrator` | Institution administrator | institution_admin | clinic, hospital, laboratory | titles_only | no | accounts | accounts, doctor_keys, release_requests, audit, incoming, records_requests |
| `rule_reviewer` | Medicine-name reviewer | rule_reviewer | clinic, hospital | none | no | rules | rules, medicine_names |
| `patient` | Patient | patient |  | content | yes |  |  |

### npm scripts

| Script | Command |
|---|---|
| `dev` | `node scripts/copy-ocr-assets.mjs && vite` |
| `build` | `node scripts/copy-ocr-assets.mjs && tsc -b && vite build` |
| `typecheck` | `tsc -b --noEmit` |
| `preview` | `vite preview` |
| `test:e2e` | `playwright test` |

## Identity provider (Keycloak realm `referral`, `infra/keycloak/import/referral-realm.json`)

### Realm roles

| Role | Meaning |
|---|---|
| `clinician` | Doctor: requests referrals, acknowledges medication flags, receives referrals for their department |
| `clinic_staff` | Staff: patient links, records, papers and medicines; sends referrals; follow-up |
| `diagnostics_staff` | Laboratory, imaging or ECG staff: test and scan orders |
| `institution_admin` | Institution administrator (accounts, source access, audit; no clinical access) |
| `rule_reviewer` | Clinical reviewer who approves medication rules and medicine names |
| `patient` | Patient: sees their own referrals and reads their own records from each institution |
| `svc_central` | Central platform service identity |
| `svc_provider` | Institution service identity |

### Clients

| Client | Type | Flows |
|---|---|---|
| referral-web | public | authorization code + PKCE |
| dev-cli | public | password grant (dev only) |
| central-api | confidential | client credentials |
| drali-api | confidential | client credentials |
| chughtai-api | confidential | client credentials |
| ziauddin-api | confidential | client credentials |
| akuh-api | confidential | client credentials |

### Institutions and departments (groups)

A user's institution is their top-level group; the department is the subgroup.

| Institution group | Department subgroups |
|---|---|
| drali | general_practice, clinic_tests |
| ziauddin | cardiology, gastro_hepatology, radiology, cardiac_diagnostics, laboratory |
| akuh | dentistry, orthopaedics, general_surgery, radiology, laboratory |
| chughtai | laboratory, radiology |

### Demonstration accounts (synthetic; passwords are not listed)

| Username | Realm roles | Groups |
|---|---|---|
| dr.ali | clinician | /drali/general_practice |
| staff.ali | clinic_staff | /drali/general_practice |
| tech.ali | diagnostics_staff | /drali/clinic_tests |
| admin.ali | institution_admin | /drali |
| dr.asma | clinician | /ziauddin/cardiology |
| dr.irfan | clinician | /ziauddin/gastro_hepatology |
| staff.zia | clinic_staff | /ziauddin |
| rad.zia | diagnostics_staff | /ziauddin/radiology |
| tech.zia | diagnostics_staff | /ziauddin/cardiac_diagnostics |
| lab.zia | diagnostics_staff | /ziauddin/laboratory |
| dr.faisal | clinician | /akuh/dentistry |
| dr.salman | clinician | /akuh/orthopaedics |
| dr.naveed | clinician | /akuh/general_surgery |
| staff.aku | clinic_staff | /akuh |
| rad.aku | diagnostics_staff | /akuh/radiology |
| lab.aku | diagnostics_staff | /akuh/laboratory |
| admin.aku | institution_admin | /akuh |
| dr.reviewer | rule_reviewer | /akuh |
| lab.chughtai | diagnostics_staff | /chughtai/laboratory |
| rad.chughtai | diagnostics_staff | /chughtai/radiology |
| staff.chughtai | clinic_staff | /chughtai |
| rubina.akhtar | patient |  |
| muhammad.tariq.mahmood | patient |  |
| abdul.rehman.gondal | patient |  |
| shazia.parveen | patient |  |
| imtiaz.ali.soomro | patient |  |

### Token and session settings

| Setting | Value |
|---|---|
| `accessTokenLifespan` | 300 |
| `ssoSessionIdleTimeout` | 1800 |
| `ssoSessionMaxLifespan` | 36000 |
| `bruteForceProtected` | True |
