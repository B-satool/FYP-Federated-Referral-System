# Software Design Specification: Federated Referral Preparation and Follow-through Platform

| | |
|---|---|
| Document version | **v1.1.0** |
| Released | 2026-10-29 |
| System | Federated referral preparation and follow-through platform (FYP), v2 code base |
| Status | Living document: regenerated from the code on every change, frozen per release in `docs/sds/versions/` |
| Structure fingerprint | `4abc1cd543c76b39` |
| Written-sections fingerprint | `36962e9bc84937a1` |
| Source fingerprint | `85b4897e8f0cd6ac` |
| Maintained by | The project team. See section 17 for how to update and release it. |

## Contents

- [1. Introduction](#1-introduction)
  - [1.1 Purpose](#11-purpose)
  - [1.2 Scope](#12-scope)
  - [1.3 Intended readers](#13-intended-readers)
  - [1.4 Definitions](#14-definitions)
  - [1.5 References](#15-references)
  - [1.6 How this document is produced](#16-how-this-document-is-produced)
- [2. System overview](#2-system-overview)
  - [2.1 Context](#21-context)
  - [2.2 Actors and roles](#22-actors-and-roles)
  - [2.3 Main capabilities](#23-main-capabilities)
  - [2.4 End-to-end flow (referral)](#24-end-to-end-flow-referral)
- [3. Architectural drivers](#3-architectural-drivers)
  - [3.1 Quality goals, in priority order](#31-quality-goals-in-priority-order)
  - [3.2 Constraints](#32-constraints)
  - [3.3 Design principles](#33-design-principles)
  - [3.4 Non-negotiable invariants](#34-non-negotiable-invariants)
- [4. Architecture](#4-architecture)
  - [4.1 Container view](#41-container-view)
  - [4.2 Component view: central platform](#42-component-view-central-platform)
  - [4.3 Component view: institution service](#43-component-view-institution-service)
  - [4.4 Shared library (`libs/common/refcommon`)](#44-shared-library-libscommonrefcommon)
  - [4.5 Web application](#45-web-application)
  - [4.6 Technology stack](#46-technology-stack)
- [5. Data architecture](#5-data-architecture)
  - [5.1 Databases and ownership](#51-databases-and-ownership)
  - [5.2 Central data model by domain](#52-central-data-model-by-domain)
  - [5.3 Identifiers and keys](#53-identifiers-and-keys)
  - [5.4 Versioning and history patterns](#54-versioning-and-history-patterns)
  - [5.5 Data lifecycle](#55-data-lifecycle)
  - [5.6 Record exchange format (FHIR R4 4.0.1 subset)](#56-record-exchange-format-fhir-r4-401-subset)
- [6. Component design](#6-component-design)
  - [6.1 Referrals and the status machine (`central/app/referrals`)](#61-referrals-and-the-status-machine-centralappreferrals)
  - [6.2 Identity and patient linking (`central/app/identity`)](#62-identity-and-patient-linking-centralappidentity)
  - [6.3 Retrieval (`central/app/integration`)](#63-retrieval-centralappintegration)
  - [6.4 Documents and OCR (`central/app/documents`)](#64-documents-and-ocr-centralappdocuments)
  - [6.5 Evidence review (`central/app/evidence_router.py`)](#65-evidence-review-centralappevidence_routerpy)
  - [6.6 Medicines (`central/app/medications`)](#66-medicines-centralappmedications)
  - [6.7 Packet selection (`central/app/selection`)](#67-packet-selection-centralappselection)
  - [6.8 Sending (`central/app/sending`)](#68-sending-centralappsending)
  - [6.9 Delivery and inbound events (`central/app/delivery`)](#69-delivery-and-inbound-events-centralappdelivery)
  - [6.10 Diagnostics (`central/app/diagnostics`)](#610-diagnostics-centralappdiagnostics)
  - [6.11 Follow-through (`central/app/followup`)](#611-follow-through-centralappfollowup)
  - [6.12 Notifications and work queue](#612-notifications-and-work-queue)
  - [6.13 Institution service (`services/provider/app`)](#613-institution-service-servicesproviderapp)
- [7. Key workflows](#7-key-workflows)
  - [7.1 Sign-in and request authentication](#71-sign-in-and-request-authentication)
  - [7.2 Patient link confirmation and access grant](#72-patient-link-confirmation-and-access-grant)
  - [7.3 Retrieval across linked institutions](#73-retrieval-across-linked-institutions)
  - [7.4 AI packet recommendation](#74-ai-packet-recommendation)
  - [7.5 Uploaded paper: OCR and field review](#75-uploaded-paper-ocr-and-field-review)
  - [7.6 Medicines, flags and the doctor's review](#76-medicines-flags-and-the-doctors-review)
  - [7.7 Sending a version and delivery](#77-sending-a-version-and-delivery)
  - [7.8 Receiving side: intake, decision, completion and expiry](#78-receiving-side-intake-decision-completion-and-expiry)
  - [7.9 Referring side follow-through](#79-referring-side-follow-through)
  - [7.10 Test and scan request](#710-test-and-scan-request)
  - [7.11 Account disabling and grant close-out](#711-account-disabling-and-grant-close-out)
- [8. Security architecture](#8-security-architecture)
  - [8.1 Authentication](#81-authentication)
  - [8.2 Authorisation on the central platform](#82-authorisation-on-the-central-platform)
  - [8.3 Authorisation at institutions (source access)](#83-authorisation-at-institutions-source-access)
  - [8.4 Audit](#84-audit)
  - [8.5 Data protection](#85-data-protection)
  - [8.6 Language-model privacy](#86-language-model-privacy)
  - [8.7 Threat model (STRIDE summary)](#87-threat-model-stride-summary)
- [9. AI and machine-learning design](#9-ai-and-machine-learning-design)
  - [9.1 Provider abstraction (`generation/provider.py`)](#91-provider-abstraction-generationproviderpy)
  - [9.2 Packet selection prompt and validation (`selection/selection.py`)](#92-packet-selection-prompt-and-validation-selectionselectionpy)
  - [9.3 Paper field extraction (`documents/processing.py`)](#93-paper-field-extraction-documentsprocessingpy)
  - [9.4 AI suggestions (offline logistic regression)](#94-ai-suggestions-offline-logistic-regression)
  - [9.5 Guardrails summary](#95-guardrails-summary)
- [10. Medication flagging design](#10-medication-flagging-design)
  - [10.1 Principles](#101-principles)
  - [10.2 Data sources](#102-data-sources)
  - [10.3 Inputs to the evaluator](#103-inputs-to-the-evaluator)
  - [10.4 Procedure features](#104-procedure-features)
  - [10.5 Flag kinds](#105-flag-kinds)
  - [10.6 Versioning, decisions and the package](#106-versioning-decisions-and-the-package)
  - [10.7 Rule maintenance](#107-rule-maintenance)
- [11. Interfaces](#11-interfaces)
  - [11.1 Interface catalogue](#111-interface-catalogue)
  - [11.2 API conventions](#112-api-conventions)
  - [11.3 Envelope versioning](#113-envelope-versioning)
  - [11.4 Idempotency keys](#114-idempotency-keys)
- [12. Reliability and error handling](#12-reliability-and-error-handling)
  - [12.1 Failure semantics](#121-failure-semantics)
  - [12.2 Consistency model](#122-consistency-model)
  - [12.3 Background job safety](#123-background-job-safety)
- [13. Quality attributes](#13-quality-attributes)
- [14. Deployment and operations](#14-deployment-and-operations)
  - [14.1 Environments](#141-environments)
  - [14.2 Deployment view (hosted)](#142-deployment-view-hosted)
  - [14.3 Configuration and secrets](#143-configuration-and-secrets)
  - [14.4 Database schema management](#144-database-schema-management)
  - [14.5 Seeding and reset](#145-seeding-and-reset)
  - [14.6 CI pipeline](#146-ci-pipeline)
  - [14.7 Backup, restore and upgrades](#147-backup-restore-and-upgrades)
  - [14.8 Monitoring](#148-monitoring)
- [15. Testing strategy](#15-testing-strategy)
- [16. Known limitations, risks and open decisions](#16-known-limitations-risks-and-open-decisions)
  - [16.1 Built differently from the SRS or not built](#161-built-differently-from-the-srs-or-not-built)
  - [16.2 Risks](#162-risks)
  - [16.3 Policy values awaiting confirmation](#163-policy-values-awaiting-confirmation)
  - [16.4 Documentation debt](#164-documentation-debt)
- [17. Maintaining this document](#17-maintaining-this-document)
  - [17.1 Rule](#171-rule)
  - [17.2 Procedure for a change](#172-procedure-for-a-change)
  - [17.3 Files](#173-files)
  - [17.4 How the generator reads the code](#174-how-the-generator-reads-the-code)
- [Appendix A. ERD: central platform](#appendix-a-erd-central-platform)
- [Appendix B. ERD: institution service](#appendix-b-erd-institution-service)
- [Appendix C. References across system boundaries](#appendix-c-references-across-system-boundaries)
- [Appendix D. Data dictionary: central platform](#appendix-d-data-dictionary-central-platform)
- [Appendix E. Data dictionary: institution service](#appendix-e-data-dictionary-institution-service)
- [Appendix F. API inventory](#appendix-f-api-inventory)
- [Appendix G. Exchange contracts and request bodies](#appendix-g-exchange-contracts-and-request-bodies)
- [Appendix H. State machines and status values](#appendix-h-state-machines-and-status-values)
- [Appendix I. Background jobs](#appendix-i-background-jobs)
- [Appendix J. Configuration and deployment descriptors](#appendix-j-configuration-and-deployment-descriptors)
- [Appendix K. Web application, roles and identity provider](#appendix-k-web-application-roles-and-identity-provider)
- [Appendix L. Database migrations](#appendix-l-database-migrations)
- [Appendix M. Dependencies](#appendix-m-dependencies)
- [Appendix N. Rules and reference data](#appendix-n-rules-and-reference-data)
- [Appendix O. Automated tests](#appendix-o-automated-tests)
- [Appendix P. Decision records and invariants](#appendix-p-decision-records-and-invariants)

# 1. Introduction

## 1.1 Purpose

This Software Design Specification (SDS) describes how the Federated Referral Preparation and Follow-through Platform is built. It covers the architecture, components, data model, interfaces, security design, AI design, deployment and operation, and the design decisions behind them. It is the reference for the project team, the supervisor and examiners, and anyone who changes the system.

The SRS (`docs/requirements/FYP SRS.pdf`) states *what* the system must do. This document states *how* the current code base does it. Where the built system differs from the SRS, the decision records in `docs/decisions/` explain why, and Appendix P lists them.

## 1.2 Scope

The system prepares a referral from one healthcare institution to another in Karachi, Pakistan, sends it, and follows it through. A referral can go to a doctor or department, or it can be a test or scan request to a laboratory or imaging department.

Along the way the system:

- links the patient's records across institutions, with each link confirmed by the other institution's staff;
- retrieves records from every linked institution through that institution's own API;
- reads the papers the patient brings (OCR);
- builds the current-medicine list and checks it against approved and imported medication rules;
- chooses which records go in the referral packet (rule-based default, optional AI recommendation, staff decision);
- sends an immutable, hashed package, tracks its delivery, acceptance and completion;
- removes the shared clinical content when the referral no longer needs it.

All data in this repository is synthetic. Four demonstration institutions are modelled: Dr Ali's Clinic (`drali`), Ziauddin Hospital (`ziauddin`), Aga Khan University Hospital (`akuh`) and Chughtai Lab (`chughtai`).

Out of scope: billing, appointment scheduling at the receiving hospital, e-prescribing, treatment advice of any kind, and connection to any real hospital system.

## 1.3 Intended readers

| Reader | Read first |
|---|---|
| Supervisor, examiners | Sections 2, 3 and 4, then 8 (security), 9 (AI) and 16 (limitations) |
| Developers changing the code | Sections 4 to 7, 11, 17, then the generated appendices |
| Operators deploying the system | Sections 12 to 14, Appendix J |
| Clinical reviewer | Sections 9 and 10 |

## 1.4 Definitions

| Term | Meaning |
|---|---|
| Institution | A clinic, hospital or laboratory that owns its patient records. Each runs its own instance of the institution service with its own database. |
| Central platform | The service (`central`) that coordinates referrals. It never connects to an institution's database (invariant 1). |
| Referring institution | Where the referral starts. Its doctor requests the referral and its staff prepare and send it. |
| Receiving institution | The hospital (or laboratory or imaging department) the referral or order is sent to. |
| Patient link | A confirmed statement that patient record X at institution A and record Y at institution B are the same person. It is verified only by staff at the other institution, never inferred from matching IDs or names. |
| Access grant | A temporary permission, created by an institution's own staff, for another institution to read one patient's referral-relevant records (default 14 days, maximum 30). |
| Evidence item | One record held for a referral: retrieved from a source, read from an uploaded paper, or entered by staff. It keeps its provenance. |
| Working set | All clinical content held centrally for one referral (evidence, papers, medicine list, flags, letter, package content). It is temporary and is removed when the referral's rules say so. |
| Packet / package | One sent version of a referral: the brief (letter), selected evidence, medication flags and a FHIR Bundle in a versioned envelope, fingerprinted with SHA-256. |
| Flag | A medication finding raised only by the deterministic evaluator from approved rules or imported rule data. It never advises treatment. |
| AI suggestion | A possible drug–drug clash for a pair with no source entry, scored offline. It is labelled "AI suggestion, not verified" and is never a flag. |
| Outbox | A table row written in the same transaction as a decision to send. A worker delivers it, retrying with the same key. |
| DRAP | Drug Regulatory Authority of Pakistan. Its public product register is the source of Pakistani brand names. |
| DDInter | DDInter 2.0, a drug–drug interaction database (CC BY-NC-SA 4.0). |
| FHIR | HL7 FHIR R4 4.0.1. The project uses a pinned subset (`docs/fhir-subset.md`). |
| CNIC | Pakistani national identity card number (13 digits). Used only to help a person look a patient up. |

## 1.5 References

| Document | Location |
|---|---|
| Software Requirements Specification | `docs/requirements/FYP SRS.pdf` |
| Development roadmap | `FYP Development Roadmap.pdf` |
| Agent and contributor rules, invariants | `AGENTS.md` |
| Decision records | `docs/decisions/*.md` (Appendix P) |
| Version 2 change log | `docs/v2-changes.md` |
| FHIR subset | `docs/fhir-subset.md` |
| Data lifecycle and data inventory | `docs/data-lifecycle.md`, `docs/data-inventory.md` |
| Medication flagging | `docs/medication-flagging.md` |
| Operations, deployment, testing | `docs/operations.md`, `docs/deploy-cloud.md`, `docs/testing.md` |
| Exchange contract examples | `contracts/examples/`, `contracts/fhir-samples/` |
| SRS evaluation report | `docs/srs-evaluation-report.md` |

## 1.6 How this document is produced

Sections 1 to 17 are written by the team (`docs/sds/sections/`). Appendices A to P are generated from the code by `scripts/sds/build_sds.py`: the ERDs, data dictionary, API inventory, contracts, state machines, jobs, configuration, roles, migrations, dependencies, rule data, tests and decisions. They are therefore exact for the version they were generated from.

Each released version is frozen in `docs/sds/versions/SDS-vX.Y.Z.md`, and `docs/sds/CHANGELOG.md` lists the structural changes detected automatically. CI fails if the code's structure changes without a new SDS version. Section 17 describes the procedure.

Diagrams use Mermaid, which GitHub and most Markdown viewers render.


# 2. System overview

## 2.1 Context

Patients in Karachi are commonly treated at several unconnected places: a neighbourhood clinic, one or more hospitals, and a private laboratory. When a doctor refers a patient, the receiving specialist usually sees a short handwritten note. The patient's history at the other places, the current medicines and the results are missing. This platform assembles that information from the institutions that hold it, with each institution keeping control of its own records, and delivers it as a checked, versioned referral.

```mermaid
flowchart LR
    subgraph People
        D["Referring doctor"]
        S["Referring staff"]
        RD["Receiving doctor"]
        RS["Receiving staff"]
        DX["Laboratory / imaging staff"]
        AD["Institution administrator"]
        CR["Clinical rule reviewer"]
    end
    W["Web application (browser)"]
    C["Central referral platform"]
    I1["Dr Ali's Clinic system"]
    I2["Ziauddin Hospital system"]
    I3["AKUH system"]
    I4["Chughtai Lab system"]
    KC["Keycloak (identity provider)"]
    LLM["Language model (optional): Ollama local or cloud, Anthropic, OpenAI-compatible"]
    OCR["Google Cloud Vision (optional, handwriting)"]

    People --> W
    W -->|"OIDC sign-in"| KC
    W -->|"REST, user token"| C
    W -->|"REST, user token (own institution's system)"| I1 & I2 & I3 & I4
    C -->|"REST, forwarded user token or service token"| I1 & I2 & I3 & I4
    I1 & I2 & I3 & I4 -->|"events, service token"| C
    C -->|"de-identified text, only if allowed"| LLM
    C -->|"page images, only if configured"| OCR
    C & I1 & I2 & I3 & I4 -->|"token verification, introspection"| KC
```

## 2.2 Actors and roles

| Actor | Realm role | What they do |
|---|---|---|
| Doctor | `clinician` | Requests referrals and test requests with the reason and consultation notes. **The only role that sees clinical content:** checks uploaded papers, confirms the medicine list (including over-the-counter), decides on flags, reviews the records ticked for the packet and the letter, then marks the packet reviewed. Receives referrals for their department, accepts or declines them, marks them complete, extends the records hold, answers information requests |
| Staff (referral coordinator) | `clinic_staff` | Requests and approves patient links, retrieves records, uploads papers, marks a referral ready for the doctor, sends it after the doctor's review, takes in incoming referrals and assigns a doctor, records that the patient was told, closes referrals. **Sees titles, statuses and counts only, never clinical content** (decision 2026-10-29) |
| Laboratory, radiology or ECG staff | `diagnostics_staff` | Confirms arriving patients, accepts or rejects orders, schedules them, reports results with images |
| Institution administrator | `institution_admin` | Accounts and role templates, source access grants and their expiry, audit log. No clinical record access |
| Clinical rule reviewer | `rule_reviewer` | Approves medication rule versions and medicine names; sees the imported interaction data, label rules and AI model figures |
| Central platform service | `svc_central` | Machine identity: delivers packages, orders and copies; closes grants |
| Institution service | `svc_provider` | Machine identity: sends acknowledgement, decision, completion and order events to the platform |

A user's institution is their top-level Keycloak group, and their department is the subgroup (Appendix K).

## 2.3 Main capabilities

| Capability | Where it is built |
|---|---|
| Referral and test requests, status and timeline | `central/app/referrals`, `diagnostics` |
| Patient linking confirmed by the other institution | `central/app/identity`, institution `/identity/*`, `/sharing/grants` |
| Retrieval of history from every linked institution | `central/app/integration` |
| Uploaded papers: OCR and field extraction | `central/app/documents` |
| Evidence review: verify, correct, exclude, manual entry | `central/app/evidence_router.py` |
| Current-medicine list, name mapping (incl. DRAP brands) | `central/app/medications/service.py`, `mapping.py` |
| Deterministic medication flags | `central/app/medications/evaluator.py` |
| Packet selection (default, AI, staff) | `central/app/selection` |
| Referral letter (brief), package, hash, delivery | `central/app/sending`, `delivery` |
| Receiving side: intake, assignment, decision, completion | institution service `/cases/*` |
| Test and scan orders and reports | `central/app/diagnostics`, institution `/orders/*` |
| Follow-through: patient informed, tasks, closure | `central/app/followup` |
| Temporary working set and grant close-out | `central/app/lifecycle`, `integration/grant_closeout.py`, `tasks.py` |
| Notifications and work queue | `central/app/notifications.py`, `workqueue.py` |
| Audit | every service (`audit_events`) |

## 2.4 End-to-end flow (referral)

```mermaid
flowchart TD
    A["Doctor creates a referral (draft), states reason, destination, urgency, procedure"] --> B["Doctor submits the request (requested)"]
    B --> C["Staff request patient links to places the patient has been"]
    C --> D["Other institution's staff confirm the patient: link verified, grant created"]
    D --> E["Staff retrieve records from every linked institution (up to 5)"]
    E --> F["Rule-based default selection, then optional AI recommendation"]
    B --> G["Staff upload the patient's papers: OCR proposes fields"]
    E & G --> H["Current-medicine list built, duplicates grouped, names mapped"]
    H --> I["Deterministic evaluator raises medication flags"]
    I --> J["Staff mark it ready for the doctor (they see titles only)"]
    J --> K["Doctor checks papers, confirms medicines, decides on each flag, reviews the records and letter, marks the packet reviewed"]
    K --> L["Staff send: brief built, package hashed, outbox written (submitted)"]
    L --> M["Receiving hospital: staff acknowledge, confirm the patient, assign a doctor"]
    M --> N{"Receiving doctor decides"}
    N -->|"accept"| O["accepted: records kept 30 days, extendable"]
    N -->|"decline (with reason)"| P["declined: shared records removed at once, referring side notified"]
    O --> Q["Referring staff tell the patient, optional tasks, close"]
    O --> R["Receiving doctor marks complete: records removed 72 h later"]
```

Test requests follow a shorter path: the doctor lists the tests, staff send each one as its own order, and the laboratory or imaging department accepts, schedules, performs and reports it. Results return to the referral (Section 7.10).


# 3. Architectural drivers

## 3.1 Quality goals, in priority order

1. **Patient safety.** The system must never present missing information as "none" or "safe", never let a language model create or change a medication flag, and never send unapproved or changed content as if approved.
2. **Institutional control of records.** Each institution owns its database and decides every access itself. The platform reads records only through institutions' APIs, with the user's own token or an explicit grant.
3. **Minimal, temporary central storage.** Clinical content is held centrally only while a referral needs it, then removed. What stays is identifiers, status, audit and fingerprints.
4. **Traceability.** Every access, link change, correction, flag decision, approval, send and status change is audited with actor, institution, action, target, time and outcome.
5. **Resilience to unreliable institutions.** A slow or unavailable source gives a partial result marked as such, never a blocked referral or a silent gap. Deliveries are retried safely.
6. **Replaceability.** OCR engine, language model, identity provider details and storage sit behind small interfaces.

## 3.2 Constraints

| Constraint | Effect on the design |
|---|---|
| Final year project, three members, synthetic data only | One repository, Docker Compose, hand-built synthetic seed; no real patient data, credentials or model weights committed (invariant 11) |
| Runs on a student laptop (about 8 GB RAM, weak GPU) | One PostgreSQL server with separate databases; optional AI; cloud model or rule-based fallbacks |
| Free hosting option (Oracle Cloud Always Free) | `docker-compose.prod.yml` overlay with Caddy and automatic HTTPS (`docs/deploy-cloud.md`) |
| No access to real hospital systems | Each institution is simulated by the same institution service code, one instance per institution |
| FHIR R4 interoperability expected by the SRS | Pinned FHIR 4.0.1 subset for record exchange; project envelopes for workflow messages |
| No pharmacist available for review of every brand | DRAP register brands loaded as mappings by decision 2026-10-28 (Appendix P), marked by source |

## 3.3 Design principles

- **Database per owner.** The platform and each institution have separate databases and logins on one PostgreSQL server. Only the owning service's credentials reach its database.
- **Decide at the source.** Every institution endpoint makes its own authorisation decision. The platform forwards the user's verified token; identity headers are never trusted.
- **Deterministic core, AI at the edges.** Flags, selection defaults, the letter and every safety check are deterministic code. Models only propose (record relevance, paper fields), and their output is validated in code and confirmed by people.
- **Unavailable is not none.** Every gap (source unavailable, access denied or expired, records removed, medicine not recognised, procedure unknown) is a visible state with its own wording (invariant 7).
- **Append, do not overwrite.** Corrections create revisions, flags create new versions, and packages are immutable once written (invariants 4 and 8).
- **Transactional outbox.** A decision to send and the outbox row are written in one transaction. Delivery is idempotent by key (invariant 9).
- **Modular monolith centrally.** The platform is one deployable FastAPI service with feature modules, plus a Celery worker from the same image. This keeps operations simple while module boundaries stay clear.

## 3.4 Non-negotiable invariants

The invariants in `AGENTS.md` bind every change. They are reproduced exactly in Appendix P. In short:

| # | Invariant | Main enforcement point |
|---|---|---|
| 1 | The platform never connects to an institution database | Compose: `central` has only `central_db` credentials; `integration/sources.py` uses HTTP |
| 2 | Each source decides access itself; forward the user's token | `refcommon.sourcekit.decide_access`, `refcommon.auth.TokenVerifier` |
| 3 | Never link on matching IDs or names; only verified links are used; invalidation keeps history | `identity/router.py`, `identity/links.py`, `patient_link_events` |
| 4 | Only clinicians approve (v2: the doctor requests and reviews flags); only current versions are sent; changes after sending start an amendment; packages are immutable | `referrals/state.py` (`mark_clinical_change`), `sending/packages.py` |
| 5 | Flags only from `evaluate_medications()`; no model may create, change or restate them; "reviewed" is not clearance; no treatment advice | `medications/evaluator.py`, `medications/label_validation.py` |
| 6 | Model output is a draft, cites supplied evidence IDs, is validated; document text is untrusted; no tools | `selection/selection.py` (`validate`), `documents/processing.py`, `generation/provider.py` |
| 7 | Unavailable is never "none" | Retrieval statuses, purge markers, flag kinds `records_incomplete`, `interactions_not_checked`, `procedure_not_checked` |
| 8 | Never overwrite original data | `evidence_revisions`, flag versions, source record versions |
| 9 | Idempotent delivery; outbox write in the same transaction | `outbox`, `inbound_messages`, institution `outbox`, unique keys |
| 10 | Audit every access and change | `audit_events` in every database |
| 11 | Synthetic data only | Seed data, `.gitignore` |
| 12 | Only doctors see clinical content; the doctor reviews the packet | `security.sees_clinical`, `require_doctor`, staff views in `serializers.py`, institution `get_case`; `sending/readiness.py`, `POST /referrals/{id}/packet-reviewed` |

Some invariants were changed by recorded decisions: the temporary working set (2026-10-27), referral expiry (2026-10-28) and the DRAP brand load (2026-10-28). Appendix P lists the records.


# 4. Architecture

## 4.1 Container view

```mermaid
flowchart TB
    subgraph Browser
        SPA["Web app: React 18, MUI 6, TanStack Query, oidc-client-ts"]
    end
    subgraph Docker["Docker Compose project 'referral'"]
        WEB["web: nginx 1.27, static app and /api/* reverse proxy (port 3000)"]
        KC["keycloak: Keycloak 26.0, realm 'referral' (port 8080)"]
        CEN["central: FastAPI, Python 3.12 (port 8000)"]
        WRK["worker: Celery worker and beat, same image as central"]
        RED["redis: Redis 7, job queue only"]
        PG[("postgres: PostgreSQL 16, one server, separate databases and logins")]
        DRA["drali: institution service (8001)"]
        CHU["chughtai: institution service (8002)"]
        ZIA["ziauddin: institution service (8003)"]
        AKU["akuh: institution service (8004)"]
        VOL[("documents volume: uploaded papers and page images")]
    end
    EXT1["Ollama (on the host) and ollama.com, Anthropic API, OpenAI-compatible server"]
    EXT2["Google Cloud Vision"]

    SPA --> WEB
    SPA --> KC
    WEB -->|"/api/central/*"| CEN
    WEB -->|"/api/drali, /api/chughtai, /api/ziauddin, /api/akuh"| DRA & CHU & ZIA & AKU
    CEN --> PG
    WRK --> PG
    DRA & CHU & ZIA & AKU --> PG
    CEN --> RED
    WRK --> RED
    CEN & WRK --> VOL
    CEN & WRK -->|"HTTP, token"| DRA & CHU & ZIA & AKU
    DRA & CHU & ZIA & AKU -->|"events"| CEN
    CEN & DRA & CHU & ZIA & AKU & WRK -->|"JWKS, introspection, client credentials"| KC
    KC --> PG
    WRK --> EXT1
    CEN --> EXT1
    WRK --> EXT2
```

| Container | Responsibility | Owns | Technology |
|---|---|---|---|
| `web` | Serves the single-page app; proxies `/api/central/*` to the platform and `/api/<institution>/*` to each institution's own system; security headers | Nothing | nginx 1.27 serving a Vite build (React 18, TypeScript 5.6, MUI 6) |
| `central` | Referral workflow API: requests, links, retrieval, evidence, documents, medicines, flags, selection, sending, inbound events, follow-up, notifications, work queue, audit | `central_db`, documents volume | FastAPI 0.115, SQLAlchemy 2.0, Alembic, pydantic 2, httpx, PyJWT |
| `worker` | Document processing, outbox delivery, AI selection, purges, retention, grant close-out | Nothing of its own (job state in `central_db`) | Celery 5.4 with beat, same image as `central` |
| `drali`, `chughtai`, `ziauddin`, `akuh` | One institution's own system: patient records, identity lookup and registration, access grants, FHIR record API, receiving referrals (cases), diagnostic orders, sent copies, outbox to the platform | `<institution>_db` | FastAPI; one image, `INSTITUTION_ID` selects the institution |
| `keycloak` | Accounts, roles, institution and department groups, OIDC tokens, introspection, admin API for role templates | `keycloak` database | Keycloak 26.0 |
| `postgres` | One server, separate databases and logins (`infra/postgres/init/01-databases.sh`) | — | PostgreSQL 16 |
| `redis` | Celery broker; never a source of truth | — | Redis 7 |

## 4.2 Component view: central platform

The platform is a modular monolith (`services/central/app`). `main.py` mounts one router per feature module. Modules talk to each other through plain function calls in the same transaction, never through HTTP.

```mermaid
flowchart LR
    subgraph API["HTTP routers"]
        REF["referrals/router"]
        IDN["identity/router"]
        EVR["evidence_router"]
        DOC["documents/router"]
        MED["medications/router"]
        SND["sending/router"]
        DXR["diagnostics/router"]
        FUP["followup/router"]
        INB["delivery/inbound"]
        NOT["notifications"]
        WQ["workqueue"]
        AUD["audit_router"]
    end
    subgraph Core["Domain services"]
        ST["referrals/state: transitions, amendments"]
        RET["integration/retrieval, sources, importer"]
        LNK["identity/links, role_templates"]
        PROC["documents/processing, extract_rules, storage"]
        MS["medications/service, mapping, rules"]
        EV["medications/evaluator (pure)"]
        SUG["medications/suggestions, ai_view"]
        SEL["selection/selection"]
        BR["sending/brief, readiness, packages"]
        LC["lifecycle/working_set, manifest"]
        GC["integration/grant_closeout"]
        OB["delivery/outbox"]
        WF["workflow.after_change"]
    end
    subgraph AI["Model access"]
        PRV["generation/provider: LLMProvider"]
        PRI["generation/privacy: de-identification, destination check"]
    end
    SEC["security: tokens, roles, institution scope, audit"]
    DB[("central_db")]

    REF --> ST & RET & SEL & LC
    IDN --> LNK
    EVR --> WF
    DOC --> PROC
    MED --> MS & SUG
    SND --> BR & OB
    INB --> ST & LC
    WF --> MS --> EV
    SEL --> PRI --> PRV
    PROC --> PRI
    BR --> LC
    API --> SEC
    Core --> DB
```

| Module | Responsibility |
|---|---|
| `referrals` | Create, edit, submit and cancel requests; patient search; links for a referral; retrieval trigger; AI recommendation trigger; event timeline. `state.py` holds the status machine and amendment rule. |
| `identity` | Patient-link requests, lookup, approval (creates the target's grant), rejection, invalidation; account administration (disable, enable, apply role template); institutions list. |
| `integration` | Calls to institution APIs with the user's token (`sources.py`); retrieval across linked institutions (`retrieval.py`); FHIR to evidence mapping (`importer.py`); grant close-out (`grant_closeout.py`). |
| `evidence_router` | Record and paper-field review: select, verify, correct, unresolve, exclude, restore, manual entry. Every change is an `evidence_revisions` row. |
| `documents` | Upload with type and size checks, protected storage, OCR (Tesseract or Google Vision), field extraction (language model or rules), page images. |
| `medications` | Current-medicine list and duplicate grouping (`service.py`), name mapping including DRAP brands (`mapping.py`), rule versions and approval (`rules.py`), the pure evaluator (`evaluator.py`), label-rule validation, AI suggestions. |
| `selection` | Rule-based default packet selection, AI recommendation (validated), staff decisions, selection snapshot for the package. |
| `sending` | Readiness checklist, brief (letter), package building and hashing, sending, retry, package verification. |
| `delivery` | Outbox delivery to institutions (`outbox.py`); inbound events from institutions, deduplicated (`inbound.py`). |
| `diagnostics` | Test and scan requests: draft, send as orders, track order events, results and attachments. |
| `followup` | Clarification answers, patient informed, follow-up tasks, closure; legacy response review. |
| `lifecycle` | Working-set expiry rules and purge (`working_set.py`); package manifest and purged envelope (`manifest.py`). |
| `generation` | `LLMProvider` with Anthropic, Ollama and OpenAI-compatible implementations and schema checking; privacy gate and de-identification. |
| `notifications`, `workqueue` | Notifications to a user or a role at an institution; role-based work queue. |
| `security` | Principal resolution, account status check, role and institution checks, audit helpers, optimistic concurrency. |
| `tasks` | Celery app, beat schedule, job execution with permission re-check (Appendix I). |
| `seed` | Loads medicine names, rules, ingredients, DDInter subset, label rules and seeded links. |

## 4.3 Component view: institution service

The same code (`services/provider/app`) runs once per institution. `INSTITUTION_ID` selects which one, and each instance has its own database and Keycloak client.

| Part | Responsibility |
|---|---|
| Patient records | `patients`, `conditions`, `surgeries`, `visits`, `medications`, `lab_results`, `imaging_reports`, all versioned (`Versioned` mixin) |
| Access decisions | `refcommon.sourcekit.decide_access`: own institution by role category, or another institution with a live grant (Section 8.3) |
| Identity | `/patients` index, `/identity/lookup` (field-by-field comparison for a person to judge), `/identity/register` (new patient), `/intake/patient` |
| Record API | `/fhir/patients/{id}/records` (FHIR searchset Bundle of the referral profile), `/patients/{id}/activity` (last seen) |
| Grants | `/sharing/grants` (created on link approval), `/admin/grants*` (administrator: list, create, extend, revoke), `/grants/revoke-by-referral` (platform service only) |
| Receiving referrals | `cases` and `incoming_packages`: acknowledge, assign, decide, information requests, complete, extend hold, legacy response; `/inbound/referral-expired` removes the shared copy |
| Diagnostic orders | `orders`, `order_attachments`: accept, reject, schedule, done, report with images |
| Sender's copies | `sent_copies` via `/outbound-copies` |
| Outbox | Events to the platform (`POST /inbound/provider-events`), retried with the same event key |
| Adapter | Local rows to FHIR resources; incoming envelopes to local rows (`adapter.py`) |

## 4.4 Shared library (`libs/common/refcommon`)

| Module | Contents |
|---|---|
| `auth.py` | `Principal`, `KeycloakConfig`, `TokenVerifier` (signature, issuer, audience, introspection cached 10 s), `ServiceTokenProvider` (client credentials), FastAPI principal dependency |
| `sourcekit.py` | Access categories by role, `decide_access`, grant lifecycle (`grant_state`, `grant_expiry`, default 14 and maximum 30 days), audit and grant mixins, shared routers (health, admin grants, grant close-out), FHIR records bundle |
| `exchange.py` | Versioned envelopes: `PackageEnvelope`, `DiagnosticOrder`, `ResultForward`, `ProviderEvent`, `ClarificationAnswer`, canonical hashing (Appendix G) |
| `fhir.py` | Builders for the pinned FHIR R4 subset (Bundle, OperationOutcome and resources) |
| `db.py` | Session factory, `utcnow`, FastAPI session dependency |

## 4.5 Web application

The single-page app (`web/src`) authenticates with Keycloak using authorization code with PKCE (public client `referral-web`, `oidc-client-ts`). It calls the platform at `/api/central/*`. Institution staff also use their own institution's system directly at `/api/<institution>/*` for incoming cases and orders, with the same user token. The routes, feature modules and role-based menus are listed in Appendix K.

| Area | Screens |
|---|---|
| Work | Work queue, requests sent, new referral, referral workspace (Request, Links, Records, Papers, Medicines, Tests, Send, Response, Audit tabs), document review, records requests, incoming referrals and case view, test and scan orders |
| Rules (reviewer) | Medication rules (manual rules, interactions, label rules, AI figures), medicine names |
| Administration | Accounts and role templates, source access (grants), audit log |
| Public | Sign-in, privacy notice, terms of use, accessibility statement |

The menu comes from the role templates (`GET /me`). Hiding a screen is a convenience only: every API call is checked on the server.

## 4.6 Technology stack

| Layer | Choice | Reason |
|---|---|---|
| Backend | Python 3.12, FastAPI, pydantic 2, SQLAlchemy 2.0, Alembic | Typed request validation, OpenAPI for free, mature ORM and migrations |
| Background work | Celery 5.4 with beat, Redis 7 | Retries, schedules, separation of slow work (OCR, AI) from requests |
| Database | PostgreSQL 16 | JSON columns for FHIR and envelopes, transactions for the outbox |
| Identity | Keycloak 26 (OIDC, PKCE, client credentials, introspection, admin API) | Standard protocols, groups for institutions and departments, immediate revocation |
| OCR | Tesseract 5 (pytesseract, pypdfium2, Pillow); optional Google Cloud Vision | Offline by default; handwriting when allowed |
| Language model | Behind `LLMProvider`: Ollama (local or `:cloud`, e.g. `gemma4:cloud`), Anthropic, OpenAI-compatible | Replaceable; optional; privacy-gated |
| Frontend | React 18, TypeScript 5.6, MUI 6, TanStack Query 5, React Router 6, react-hook-form, oidc-client-ts 3, Vite 6 | Accessible components, caching and polling |
| Testing | pytest (unit and integration), Playwright (browser) | Section 15 |
| Delivery | Docker Compose; Caddy 2 for HTTPS in production; GitHub Actions CI | Section 14 |


# 5. Data architecture

## 5.1 Databases and ownership

```mermaid
flowchart LR
    subgraph PG["PostgreSQL 16 server (one container)"]
        CDB[("central_db<br/>login: central")]
        D1[("drali_db<br/>login: drali")]
        D2[("chughtai_db<br/>login: chughtai")]
        D3[("ziauddin_db<br/>login: ziauddin")]
        D4[("akuh_db<br/>login: akuh")]
        KDB[("keycloak<br/>login: keycloak")]
    end
    CEN["central + worker"] --> CDB
    I1["drali service"] --> D1
    I2["chughtai service"] --> D2
    I3["ziauddin service"] --> D3
    I4["akuh service"] --> D4
    KC["keycloak"] --> KDB
```

`infra/postgres/init/01-databases.sh` creates each database with its own login on first start. Each service receives only its own connection string. Redis holds only Celery messages. Uploaded papers and page images are files in the `documents` volume, under generated names outside any web root, served only through authenticated endpoints (`documents/storage.py`).

| Database | Tables (exact list: Appendices A, B) | Content |
|---|---|---|
| `central_db` | about 34 | Users (references to Keycloak accounts), patient links, referrals and their timeline, evidence, documents and extraction, packet selection runs, medicine list, medicine names, ingredients, interaction and label rules, manual rule versions, evaluation runs, flags and reviews, AI suggestions, briefs, packages, outbox, inbound messages, clarifications, responses, tasks, diagnostic requests, notifications, jobs, audit |
| `<institution>_db` (×4) | about 18 | The institution's own patient records, access grants, audit, received referrals (cases, packages, information requests, responses, forwarded results), diagnostic orders and attachments, sent copies, outbox |
| `keycloak` | Keycloak's own | Accounts, credentials, sessions, realm configuration |

The complete ERDs are in Appendices A and B, the column-level data dictionary in Appendices D and E, and the identifiers that cross service boundaries in Appendix C.

## 5.2 Central data model by domain

```mermaid
flowchart TB
    subgraph Referral["Referral workflow (models/referrals.py)"]
        R["referrals"] --- RE["referral_events"]
        R --- BRF["briefs"] --- PK["referral_packages"]
        R --- OB["outbox"]
        R --- IM["inbound_messages"]
        R --- CL["clarifications"]
        R --- CR["consultation_responses"]
        R --- FT["followup_tasks"]
        R --- DR["diagnostic_requests"]
        R --- NT["notifications"]
    end
    subgraph Evidence["Evidence and documents (models/evidence.py)"]
        SR["source_retrievals"]
        EI["evidence_items"] --- ER["evidence_revisions"]
        DOC["documents"] --- XR["extraction_runs"]
        JB["jobs"]
        SL["selection_runs"]
    end
    subgraph Meds["Medicines (models/medications.py)"]
        ME["medication_entries"]
        MN["medicine_names"]
        ING["ingredients"]
        DI["drug_interactions"]
        LR["label_rules"]
        MR["medication_rules"]
        RR["ruleset_releases"]
        EVR["evaluation_runs"] --- MF["medication_flags"] --- FR["flag_reviews"]
        AS["ai_suggestions"] --- SRV["suggestion_reviews"]
    end
    subgraph Identity["Identity and audit (models/identity.py, audit.py)"]
        U["users"]
        PL["patient_links"] --- PLE["patient_link_events"]
        AE["audit_events"]
    end
    R --- SR & EI & DOC & JB & SL & ME & EVR & FR & SRV
    EI --- ME
    PL -.-> EI
```

**Reference data versus referral data.** `medicine_names`, `ingredients`, `drug_interactions`, `label_rules`, `medication_rules`, `ruleset_releases` and `ai_suggestions` are reference data, loaded by the seed or maintained by the clinical reviewer. They are not tied to a referral. Everything else hangs off `referrals` and forms the working set (Section 5.5).

## 5.3 Identifiers and keys

| Identifier | Format | Where it is made |
|---|---|---|
| Referral reference | `REF-<year>-<id:05>` (referral) or `TST-<year>-<id:05>` (test request) | `referrals/router.py` on creation |
| Diagnostic request reference | `DX-<year>-<id:05>` | `referrals/router.py` |
| Institution patient ID | Institution prefix and number, e.g. `DA…`, `ZH…`, `AK…`, `MD…` (`LOCAL_ID_PREFIX`) | Institution service |
| Package delivery key | `<source institution>:<referral reference>:v<version>` | `sending/packages.py` |
| Sender copy key | `copy:<delivery key>` or `copy:<event key>` | `sending/packages.py`, `delivery/inbound.py` |
| Order key | `<source institution>:<DX reference>` | `diagnostics/router.py` |
| Provider event key | Unique per event, chosen by the institution service | Institution outbox |
| Flag key | `rule:<rule_id>:<ingredient>`, `ddi:<a>:<b>`, label rule key, `unrecognised:<entry>`, `procedure:<ingredient>`, `interactions_not_checked`, `records_incomplete` | `medications/evaluator.py` |
| Evidence source key | (referral, source institution, record type, record id, record version), unique | `uq_evidence_source_version` |
| User id | Keycloak subject (`sub`) | Keycloak |

## 5.4 Versioning and history patterns

| Pattern | Used for | How |
|---|---|---|
| Optimistic concurrency | `referrals`, `evidence_items`, institution `consultation_responses` | `row_version` column. Clients send `expected_row_version`; a stale value gets `409 stale_version` (`security.check_version`). |
| Append-only revisions | Evidence corrections, verification and exclusion | `evidence_revisions` (prior and new value, state, editor, note). Raw extraction is never overwritten (invariant 8). |
| Source record versions | Retrieved records | Each FHIR resource's `meta.versionId` is stored. A newer version creates a new evidence row and supersedes the old one (`superseded_by`); a staff selection carries over. |
| Flag versions | Medication flags | A material change supersedes the flag row and inserts version + 1. Reviews refer to a specific flag version. |
| Rule versions | Manual medication rules | Each edit is a new draft version. Only an approved version raises flags; approving a newer version supersedes the older. |
| Immutable packages | Sent versions | `referral_packages` rows are never updated except the supersession marker and the purge. The SHA-256 covers every clinical field. |
| Amendments | Clinical change after sending | `mark_clinical_change()` sets `amendment_open`; a new version must be sent and the sent one stays untouched. |
| Record versions at institutions | Patient records | `Versioned` mixin: `version` and `updated_at` on every record table. |

## 5.5 Data lifecycle

"Shared records" means a referral's working set: retrieved records, papers and their text, the medicine list, flags, the letter and the sent package content. They exist on the platform and in the receiving hospital's copy. The rules are in `lifecycle/working_set.py` (decision 2026-10-28, referral expiry).

```mermaid
stateDiagram-v2
    [*] --> Held: first retrieval, paper or medicine added
    Held --> HeldNoLimit: sent, awaiting decision
    HeldNoLimit --> Hold30: receiving doctor accepts (expiry = now + ACCEPTED_HOLD_DAYS)
    Hold30 --> Hold30: doctor extends (expiry = now + 30 days)
    Hold30 --> Grace72: doctor marks complete (expiry = now + 72 h)
    HeldNoLimit --> Removed: doctor declines (expiry = now)
    Held --> Grace72: referral cancelled
    HeldNoLimit --> Grace72: referral cancelled
    Hold30 --> Removed: 30-day safety limit reached
    Grace72 --> Removed: grace period over
    Removed --> Held: retrieval again (new working set, fresh rows)
```

| Event | Shared records |
|---|---|
| Sent, not yet accepted | Kept, no time limit |
| Receiving doctor accepts | Kept until 30 days after acceptance (`ACCEPTED_HOLD_DAYS`) |
| Receiving doctor extends (reason required, any number of times) | Limit reset to 30 days from then, never shorter |
| Receiving doctor marks complete (never automatic) | Removed 72 hours later (`WORKING_SET_GRACE_HOURS`) |
| Receiving doctor declines | Removed straight away (the worker purge is queued at once) |
| Referring side cancels | Removed 72 hours later |
| Test request | Removed 72 hours after all results are back, or after closing or cancelling |

**What the purge does** (`purge_working_sets`, every 10 minutes, `lifecycle/working_set.py::purge`):

- **Evidence:** display and values are replaced with `[removed: working set ended]`, and the FHIR copy, source text, regions, confidence and AI reason are cleared. The row keeps its id, category and the purged record version. It drops out of every list.
- **Papers:** the files and page images are deleted, and the extracted text is replaced with a marker.
- **Medicine list, flags, reviews, letter, responses, clarifications, results, outbox and inbound payloads:** text cleared. Flags become `purged`.
- **Packages:** the envelope is replaced by a purged envelope (identifiers and hash). The `manifest` (what it contained, by source record and version, flags and rule set) and the SHA-256 stay.
- **At the receiving hospital:** the platform sends `expire_shared` (`POST /inbound/referral-expired`). The hospital removes its copy of the packages and forwarded results, and keeps its own decision, questions and response.

**What the purge waits for:** content is never removed while a package, order or the sender's copy is not yet confirmed delivered, or before the sending clinic has confirmed its own copy of each sent package (`blockers()`). A deferred purge is audited with its reasons.

**What always stays:** referral identifiers and status, the event timeline, audit events, patient links, users, selection-run metadata (no record values), package manifests and fingerprints.

**After removal:** screens say the records are "no longer held", never "none" (invariant 7). `POST /referrals/{id}/packages/{v}/verify-own-copy` checks the sending clinic's lasting copy against the kept hash.

**Other retention:**

- **Uploaded papers of closed referrals:** deleted after `DOCUMENT_RETENTION_DAYS` (365) by `retention_sweep`, if still present.
- **Access grants:** expire after 14 days by default (30 at most). They are also revoked by `close_referral_grants` when a referral reaches a final status.
- **Audit:** append-only, never purged.

## 5.6 Record exchange format (FHIR R4 4.0.1 subset)

Institutions return a FHIR `searchset` Bundle from `GET /fhir/patients/{id}/records?since=…&categories=…`, built by `services/provider/app/adapter.py`:

| Category | FHIR resource | Date limit |
|---|---|---|
| demographics | Patient | — |
| conditions | Condition (SNOMED CT where known, clinical status, onset) | none: all non-error conditions |
| surgeries | Procedure | none |
| visits | Encounter (setting, reason, narrative summary, participant) | since the specialty's history window |
| medications | MedicationRequest (original name, dosage text, route, timing; active only) | none: active only |
| labs | Observation (LOINC, value and unit as recorded, reference range); latest result per test | since the window |
| imaging | DiagnosticReport (study, findings, impression) | since the window |

Every resource carries `meta.versionId` (the source record version) and `meta.source`. Withheld categories are reported in an `OperationOutcome` entry, so the platform shows a **partial** result instead of silently missing data. The central importer (`integration/importer.py`) validates each resource, keeps original values, units, codes and dates in `original`, and counts invalid resources instead of dropping them. The referral package carries a `collection` Bundle with a `ServiceRequest` for the referral. Responses use a `Task`. Workflow messages travel in project envelopes (Appendix G), never inside FHIR resources.


# 6. Component design

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
3. **Validation** (`validate()`): every id must belong to this referral and appear once, the values must come from the allowed sets, and reasons must contain no treatment or dosing words. Any failure rejects the whole answer, and the default stands.
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


# 7. Key workflows

Each diagram shows the calls that happen in the code. Names in `code` are the endpoints or functions involved. Every request carries a Keycloak access token that the receiving service verifies (Section 8.1); the diagrams omit this for brevity.

## 7.1 Sign-in and request authentication

```mermaid
sequenceDiagram
    actor U as User
    participant W as Web app
    participant K as Keycloak
    participant C as Central or institution service
    U->>W: open the site
    W->>K: authorization code request with PKCE (client referral-web)
    U->>K: username and password
    K-->>W: authorization code
    W->>K: exchange code and verifier for tokens
    K-->>W: access token (5 min) and refresh token
    W->>C: API call with Authorization Bearer token
    C->>K: JWKS (cached), verify signature, issuer, audience
    C->>K: token introspection (cached 10 s)
    K-->>C: active, roles, groups
    C->>C: central only: users row upserted, account_status must be active
    C-->>W: response, or 401 or 403 (denials audited)
```

## 7.2 Patient link confirmation and access grant

```mermaid
sequenceDiagram
    actor SA as Staff, referring clinic
    participant C as Central
    actor SB as Staff, hospital B
    participant B as Hospital B service
    SA->>C: POST /referrals/{id}/links (target B)
    C->>C: patient_links row (requested), patient_link_events, audit
    C-->>SB: appears under Records requests (work queue)
    SB->>C: POST /patient-links/{id}/lookup
    C->>B: POST /identity/lookup (staff token)
    B-->>C: candidates with field-by-field comparison
    SB->>C: POST /patient-links/{id}/approve (local id, note)
    C->>C: refuse if that record is linked to another patient
    C->>B: POST /sharing/grants (grantee A, patient, referral reference)
    B->>B: access_grants row, expires in 14 days, audit
    C->>C: link verified, event, audit, notify requester
    Note over SA,B: Records at B are now readable by A's doctors and staff for this patient until the grant expires or is revoked
```

## 7.3 Retrieval across linked institutions

```mermaid
sequenceDiagram
    actor S as Staff
    participant C as Central
    participant I as Each linked institution (parallel)
    participant Wk as Worker
    S->>C: POST /referrals/{id}/retrieve
    C->>C: working_set.start, sources = own record + verified records links
    par for every linked institution
        C->>I: GET /patients/{id}/activity (user token, X-Referral-Id)
        I->>I: decide_access (own staff or live grant), audit
        I-->>C: last activity, or 403 denied or expired, or timeout
    end
    C->>C: order by last activity, keep up to MAX_RETRIEVAL_SOURCES, mark the rest skipped
    par for every chosen institution
        C->>I: GET /fhir/patients/{id}/records?since=specialty window
        I-->>C: FHIR searchset Bundle (OperationOutcome lists withheld categories)
    end
    C->>C: importer validates resources, evidence rows, dedupe by source version
    C->>C: source_retrievals rows (successful, partial, empty, denied, expired, unavailable, invalid, skipped)
    C->>C: default selection, medication re-evaluation, audit per source
    C->>Wk: enqueue recommend_selection (if a model is configured)
    C-->>S: per-source results
```

## 7.4 AI packet recommendation

```mermaid
sequenceDiagram
    participant Wk as Worker
    participant P as privacy.py
    participant M as Language model
    participant DB as central_db
    Wk->>DB: candidates (at most 150, older non-default dropped first)
    Wk->>P: check_destination(provider)
    alt external model and LLM_EXTERNAL_ALLOWED is false, or remote without https
        P-->>Wk: refused (ProviderUnavailable)
        Wk->>DB: selection_runs status unavailable, default stands
    else allowed
        Wk->>P: de-identify (no name, CNIC, IDs, birth date, institution or doctor names, dates as days before)
        Wk->>M: system prompt, JSON schema, untrusted data payload (no tools)
        M-->>Wk: JSON answer
        Wk->>Wk: check_schema, validate ids, values, reason length, no advice or dosing words
        alt valid
            Wk->>DB: apply: may add records and mark low relevance, never removes defaults or staff choices
            Wk->>DB: selection_runs completed, audit (destination, deidentified, counts)
        else invalid
            Wk->>DB: selection_runs rejected with the reason, default stands
        end
    end
```

## 7.5 Uploaded paper: OCR and field review

```mermaid
sequenceDiagram
    actor S as Staff
    actor D as Doctor
    participant C as Central
    participant Wk as Worker
    participant V as OCR engine (Tesseract, or Google Vision)
    participant M as Language model (optional)
    S->>C: POST /referrals/{id}/documents (file, type)
    C->>C: content-type detection, size and page limits, store with SHA-256
    C->>Wk: jobs row, enqueue process_document
    Wk->>Wk: re-check requester is active and in the referral's institution
    Wk->>Wk: embedded text, or rasterise and preprocess pages
    Wk->>V: page image
    V-->>Wk: lines with positions and confidence
    alt model configured and EXTRACTION_MODE auto or llm
        Wk->>M: de-identified lines (dates kept), strict schema
        M-->>Wk: medicines and labs, each citing line ids
        Wk->>Wk: reject the answer if any id is unknown, fall back to rules (auto)
    else
        Wk->>Wk: rules-extractor/2
    end
    Wk->>C: evidence rows proposed and unverified, linked to page regions
    Note over S,C: staff see the paper's name and status only
    D->>C: review against the page image: verify, correct, unresolve or exclude
    C->>C: evidence_revisions, medicine list and flags re-evaluated
```

## 7.6 Medicines, flags and the doctor's review

```mermaid
sequenceDiagram
    actor S as Staff
    actor D as Doctor
    participant C as Central
    participant E as evaluate_medications (pure)
    Note over C: any change to records, papers, medicines or the procedure calls workflow.after_change
    C->>C: rebuild the medicine list, group duplicates, map names (DRAP brands, ambiguity)
    C->>E: medicines, procedure tags, conditions, approved rules, DDInter pairs, label rules
    E-->>C: flag candidates (deterministic)
    C->>C: evaluation_runs row, new flag versions, supersede changed flags
    S->>C: POST /referrals/{id}/prepared (records retrieved, papers uploaded)
    Note over S,C: staff see counts only, never medicine names or flags
    D->>C: POST /medications/manual, /medications/checked (asked the patient, incl. OTC)
    D->>C: resolve dose differences
    D->>C: POST /referrals/{id}/flags/{flag}/acknowledge (reviewed, ignore or research, note)
    C->>C: flag_reviews row for that flag version, audit
    D->>C: POST /referrals/{id}/ai-suggestions/review (ignore or research)
    D->>C: POST /referrals/{id}/packet-reviewed (records, papers, medicines, flags, letter)
    C-->>S: notification: ready to send
```

## 7.7 Sending a version and delivery

```mermaid
sequenceDiagram
    actor S as Staff
    participant C as Central
    participant Wk as Worker (deliver_outbox, every 5 s)
    participant B as Receiving hospital
    participant A as Referring institution
    S->>C: POST /referrals/{id}/send
    C->>C: readiness: every blocking item done, including the doctor's packet review
    C->>C: brief (deterministic), PackageEnvelope, SHA-256, manifest
    C->>C: one transaction: referral_packages + outbox deliver_package + outbox sender_copy
    Wk->>B: POST /inbound/referrals (delivery key, service token)
    B->>B: verify hash, store case and package (idempotent by delivery key)
    B-->>Wk: received or already_received
    Wk->>C: referral submitted, delivery_status delivered
    Wk->>A: POST /outbound-copies (copy key)
    A-->>Wk: stored
    Note over Wk,B: on failure the same key is retried, 2^n s up to 120 s, 8 attempts, then delivery problem shown to staff
```

## 7.8 Receiving side: intake, decision, completion and expiry

```mermaid
sequenceDiagram
    actor RS as Receiving staff
    actor RD as Receiving doctor
    participant B as Hospital B service
    participant C as Central
    participant Wk as Worker
    RS->>B: POST /cases/{id}/acknowledge
    B->>C: event acknowledged (outbox thread)
    RS->>C: confirm the arriving patient (intake link approve or register new)
    C->>B: POST /intake/patient
    RS->>B: POST /cases/{id}/assign (doctor)
    alt accept
        RD->>B: POST /cases/{id}/decision accept
        B->>C: event accepted
        C->>C: status accepted, expiry = now + 30 days, notify doctor and staff
        opt needs longer
            RD->>B: POST /cases/{id}/extend-hold (reason)
            B->>C: event hold_extended, expiry = now + 30 days
        end
        RD->>B: POST /cases/{id}/complete
        B->>C: event completed, expiry = now + 72 h, notify both sides
    else decline
        RD->>B: POST /cases/{id}/decision decline (reason)
        B->>C: event declined
        C->>C: status declined, expiry = now, notify doctor and staff
        C->>Wk: enqueue purge_working_sets
    end
    Wk->>C: purge_due: blockers? then remove content, keep manifest and hash
    Wk->>B: outbox expire_shared to POST /inbound/referral-expired
    B->>B: remove packages and forwarded results, keep own decision and notes
```

## 7.9 Referring side follow-through

```mermaid
sequenceDiagram
    actor S as Referring staff
    actor D as Referring doctor
    participant C as Central
    C-->>S: notification: accepted, tell the patient
    S->>C: POST /referrals/{id}/patient-informed (note)
    opt follow-up needed
        S->>C: POST /referrals/{id}/tasks
        S->>C: POST /tasks/{id}/outcome
    end
    alt answer to an information request
        S->>C: POST /clarifications/{id}/answer
        C->>C: outbox clarification_answer to the hospital
    end
    D->>C: POST /referrals/{id}/close (or staff)
    C->>C: requires accepted, patient informed, no open tasks
    Note over C: close-out sweep (every 60 s) asks each institution to revoke grants opened for this referral
```

## 7.10 Test and scan request

```mermaid
sequenceDiagram
    actor D as Doctor
    actor S as Staff
    participant C as Central
    participant L as Laboratory or imaging department
    D->>C: POST /referrals (kind test) and POST /referrals/{id}/diagnostics
    D->>C: POST /referrals/{id}/submit
    S->>C: POST /diagnostics/{dx}/send
    C->>C: outbox deliver_order (DiagnosticOrder with patient identity)
    C->>L: POST /inbound/orders
    L->>L: confirm the patient (match or register new)
    L->>C: events order_accepted or order_rejected (reason), order_scheduled, order_done
    L->>C: event order_reported (text, values, findings, impression, images)
    C->>C: report and attachments stored, doctor notified
    D->>C: POST /diagnostics/{dx}/seen
    D->>C: close once every result is seen (records removed 72 h later)
```

## 7.11 Account disabling and grant close-out

```mermaid
sequenceDiagram
    actor AD as Institution administrator
    participant C as Central
    participant K as Keycloak
    participant I as Institution services
    participant Wk as Worker
    AD->>C: POST /admin/users/{id}/disable (reason)
    C->>C: only an administrator of the same institution, never their own account
    C->>K: admin API: user enabled=false, then logout (ends sessions)
    C->>C: users.account_status disabled, token cache cleared, audit
    Note over C: every later request by that user gets 401 account_disabled at once, and queued jobs fail the permission re-check
    Note over K,I: introspection reports the token inactive, so every institution service refuses it within 10 s
    Wk->>C: close_referral_grants (every 60 s): referrals in closed, declined or cancelled
    Wk->>I: POST /grants/revoke-by-referral (service token)
    I->>I: revoke grants with that referral_ref, audit
    Wk->>C: grants_closed event, audit (retried next sweep on failure, expiry is the backstop)
```


# 8. Security architecture

## 8.1 Authentication

| Party | Mechanism |
|---|---|
| People (browser) | OIDC authorization code with PKCE. Public client `referral-web`, library `oidc-client-ts`. Access tokens last 5 minutes, sessions go idle after 30 minutes and last at most 10 hours. Brute-force protection is on in the realm. |
| Integration tests and scripts | Public client `dev-cli` with the password grant. For local development only; it must be removed or disabled for a hosted deployment. |
| Services | Confidential clients with client credentials: `central-api` (role `svc_central`) and `drali-api`, `chughtai-api`, `ziauddin-api`, `akuh-api` (role `svc_provider`). `ServiceTokenProvider` fetches and caches the token. |

**Verification at every service** (`refcommon.auth.TokenVerifier`):

1. The JWT signature is checked against Keycloak's JWKS (keys cached).
2. The issuer must be the realm, by its public or internal URL.
3. The audience must be the service's own client.
4. The token is introspected with Keycloak, using the service's client credentials, and the result is cached for 10 seconds. So a disabled account or ended session stops working within seconds, before the token expires.

Identity comes only from the verified token: never from request headers or the request body (invariant 2). The `Principal` carries the subject, username, display name, institution (top-level group), department (subgroup), roles and the raw token for forwarding.

**Central only.** `security.get_principal` creates or updates the `users` row on each request and rejects an account whose `account_status` is not `active` (`401 account_disabled`). The rejection is audited.

## 8.2 Authorisation on the central platform

| Rule | Enforcement |
|---|---|
| A referral is visible and changeable only by its own institution's doctors and staff | `security.load_referral`: caller's institution must equal `referral.source_institution`, and the role must be in the allowed set (default `clinician`, `clinic_staff`). Every denial is audited and returns 403. |
| **Clinical content is doctor-only** (decision 2026-10-29): record content and selection, papers and their fields, the medicine list and flags, AI suggestion decisions, the letter preview, package content, own-copy verification, clarification answers, test results and attachments, legacy responses | `load_referral(..., roles=("clinician",))`, `require_doctor`; read endpoints return a staff view (`clinical=False`) instead of refusing where staff need the list (titles, statuses, counts) |
| Doctor-only workflow actions: create a request, submit, the packet review (`POST /referrals/{id}/packet-reviewed`) | `require_roles(principal, "clinician")`; `load_referral(..., roles=("clinician",))` |
| Staff actions: links, retrieval, paper upload, "ready for the doctor", send (after the doctor's review), test orders, patient informed | `load_referral(..., roles=("clinic_staff",))` or the default roles |
| Audit detail | Non-doctors never get the `changes` and `note` detail fields, which can hold clinical text |
| Patient-link decisions | `clinic_staff`, `institution_admin` or `diagnostics_staff` of the target institution |
| Administrators manage accounts, grants and audit; no clinical record access | `institution_admin` checks; `load_referral` does not accept it |
| Rule and medicine-name approval | `rule_reviewer` only |
| Service-to-service endpoints | `require_service(principal, "svc_provider")` plus the event's institution must match the caller's institution |
| Concurrent edits | `check_version` (`409 stale_version`) |
| Background jobs | `_start()` re-checks that the requester is still active and still in the referral's institution before running |

The per-endpoint checks are generated in Appendix F. The web menu only hides screens; it is not an enforcement point.

## 8.3 Authorisation at institutions (source access)

`refcommon.sourcekit.decide_access(db, grant_model, principal, own_institution, patient, requested_categories)` returns the allowed and denied categories:

```mermaid
flowchart TD
    A["Request for a patient's records"] --> B{"Caller's institution is this institution?"}
    B -->|"yes"| C["Allowed categories by role: clinician and clinic_staff all, diagnostics_staff demographics, labs, imaging"]
    B -->|"no"| D{"Role is clinician or clinic_staff?"}
    D -->|"no"| X["Denied: role may not access another institution's records"]
    D -->|"yes"| E{"Live grant for the caller's institution and this patient?"}
    E -->|"active, not expired"| F["Allowed: the grant's categories"]
    E -->|"expired"| G["Denied with expired = true (shown as 'access expired', never as 'no records')"]
    E -->|"none or revoked"| X2["Denied: no grant"]
```

**Grants:**

- **Creation:** only the institution's own staff (on link approval) or its administrator can create one. The platform cannot create or bypass a grant.
- **Duration:** default 14 days (`DEFAULT_GRANT_DAYS`), maximum 30 (`MAX_GRANT_DAYS`). Only the institution's administrator can extend.
- **Closing:** revoked when the referral reaches a final status (`/grants/revoke-by-referral`, platform service only).
- **Legacy grants** without an expiry are reported so an administrator can renew or revoke them.

Every decision is audited in the institution's own `audit_events`, with the referral context from `X-Referral-Id`.

## 8.4 Audit

Every database has an `audit_events` table with actor id and name, institution, action, target type and id, outcome (`success`, `denied`, `partial`, `deferred`, …), detail (JSON, no clinical content) and time. Centrally it also records the referral id; institutions record the referral context.

**Audited events:**

- every access and denial;
- retrieval per source;
- link requests, decisions and invalidations;
- evidence changes;
- flag and suggestion decisions;
- rule approvals;
- sends and deliveries;
- inbound events and status changes;
- AI calls: destination, de-identified, counts, model and prompt version, never content;
- purges and deferrals;
- grant creation, extension and revocation;
- account and role changes.

Denials that abort a request are written in a separate transaction (`audit_now`) so they are not rolled back. Audit rows are never purged. Administrators see their institution's audit metadata (`GET /admin/audit`), and doctors and staff see a referral's audit tab (`GET /referrals/{id}/audit`).

## 8.5 Data protection

| Concern | Measure |
|---|---|
| Separation | Separate database and login per owner. The platform has no institution credentials (invariant 1). |
| Minimisation | The referral profile returns only referral-relevant categories within the specialty window, the latest result per lab test, and active medicines only. Packet selection limits what is sent. |
| Temporary central storage | Working-set purge, at receiving hospitals too (Section 5.5). |
| Files | Uploaded papers are stored outside any web root under generated names, checked by content type, size and page count, served only after a referral access check. |
| Transport | Locally, HTTP inside the Docker network. Production: Caddy terminates TLS with Let's Encrypt and HSTS; only ports 80 and 443 are exposed and all services are reachable only inside the network (`docker-compose.prod.yml`). Remote model servers must use https. |
| Web hardening | nginx sets `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin` and `X-Frame-Options: DENY`; the upload limit is 12 MB. Caddy removes the `Server` header. |
| Secrets | Only in `.env` (git-ignored). `.env.example` holds placeholders. Keys are sent in headers, never URLs. No secrets in the SDS (Appendix J hides them). |
| Synthetic data | All seed data is fictional (`patients.synthetic = true`). Committing real patient data, credentials, model weights or uploads is forbidden (invariant 11). |
| At rest | PostgreSQL and the documents volume are not encrypted by the application. A hosted deployment must use encrypted disks (Section 16). |

## 8.6 Language-model privacy

Every call to a model goes through `generation/privacy.py` (decision 2026-10-28, cloud-model privacy):

- **Destination check:** a model that runs outside this computer is used only when `LLM_EXTERNAL_ALLOWED=true`. That covers any Ollama `:cloud` model (even through a local Ollama), ollama.com, Anthropic and any remote server. Otherwise the call is refused before anything is sent. Remote servers must use https.
- **De-identification, always:**
  - Never sent: name, CNIC, record numbers, date of birth or the referral reference.
  - Removed from the text: name parts, long numbers (ID and phone), doctors' names (`Dr …`) and institution names.
  - Calendar dates become "N days before the referral". Paper reading keeps dates, because a medicine's start date is a field.
  - The model receives age, sex, the reason, the department, the procedure, and each record's category and text.
- **Minimum necessary:** at most 150 records, 300 characters each.
- **No logging of content:** the audit records the destination, `deidentified: true`, the model and counts.
- **No tools:** the model can only return the fixed JSON schema. Record text is labelled as untrusted data.

Google Cloud Vision receives page images, which cannot be de-identified. It is used only when `OCR_ENGINE=google_vision`, and only with synthetic papers until the operating institution agrees (decision 2026-10-28, handwriting OCR).

## 8.7 Threat model (STRIDE summary)

| Threat | Example | Mitigation |
|---|---|---|
| Spoofing | Forged identity header; another institution's service sending events | Token-only identity; audience per service; introspection; event institution must match the service identity |
| Tampering | Package changed after sending; record edited in place | SHA-256 over the hashed fields, re-checked by the receiver and on verification; immutable packages; append-only revisions |
| Repudiation | "I did not approve that" | Audit with actor, institution, time and outcome; flag decisions bound to the flag version and rule-set hash |
| Information disclosure | Reading another institution's records; over-sharing to a model | Source-side `decide_access` with expiring grants; institution scoping in `load_referral`; working-set purge; de-identification and the external-model switch |
| Denial of service | Slow or failing institution | Timeouts, bounded retries, parallel calls, partial results; outbox decouples delivery |
| Elevation of privilege | Administrator reading records; staff approving rules | Role checks on the server; administrators excluded from clinical access; service roles never assignable from templates |
| Prompt injection | Text in a record that tells the model to do something | Record text passed as data; no tools; schema and id validation; model output cannot change flags or remove defaults |
| Duplicate side effects | Retry after a timeout delivers twice | Idempotency keys (delivery, copy, order, event, answer keys) with unique constraints |


# 9. AI and machine-learning design

The system uses AI in three places, each optional and each kept outside the safety-critical path:

| Use | Technique | Runs | Can it change flags or remove records? |
|---|---|---|---|
| Packet selection recommendation | Language model, structured JSON | Worker, after retrieval | No. It may add records and mark relevance; defaults and staff choices always stand |
| Reading fields from uploaded papers | Language model, structured JSON with line-id citations | Worker, per document | No. Proposals are unverified until staff check them against the page image |
| Possible drug–drug clashes not in DDInter | Logistic regression trained offline | Offline script; the app only looks results up | No. Labelled "AI suggestion, not verified"; never a flag |

Handwriting OCR through Google Cloud Vision is a service call, not a model the project trains or prompts (Section 6.4).

## 9.1 Provider abstraction (`generation/provider.py`)

Workflow code depends only on `LLMProvider.structured(system, user_payload, schema, max_tokens) -> dict`. Choose the implementation with `LLM_PROVIDER`:

| Provider | Configuration | Structured output |
|---|---|---|
| `anthropic` | `ANTHROPIC_API_KEY`, `LLM_MODEL` (default `claude-opus-5-5`) | JSON-schema output format enforced by the API; server-side refusal fallback; `refusal` and `max_tokens` stops are rejected |
| `ollama` | `OLLAMA_HOST` (default `http://host.docker.internal:11434`), `LLM_MODEL` (for example `gemma4:cloud`), optional `OLLAMA_API_KEY` for ollama.com | Local models get the schema as `format`. Ollama's cloud does not enforce schemas, so for `:cloud` models and ollama.com the schema goes in the prompt and the reply is checked by `check_schema` |
| `openai_compatible` | `LLM_BASE_URL` (…/v1), `LLM_API_KEY`, `LLM_MODEL` | Chat completions with a JSON response format; reply checked by `check_schema` |
| `disabled` | none configured | Raises `ProviderUnavailable`; rule-based paths apply |

**Error handling.**

- **`ProviderUnavailable`:** no model, unreachable server, 401 or 403, 429 or other status errors, or a refused destination.
- **`ProviderOutputInvalid`:** truncated output, invalid JSON, schema mismatch, or failed reference validation.

Callers treat both as "AI unavailable" and keep the deterministic result. Every answer goes through `check_schema()`, which checks the JSON Schema subset the project uses (type, properties, required, additionalProperties, items, enum), whatever the provider.

## 9.2 Packet selection prompt and validation (`selection/selection.py`)

**Prompt.** The system prompt (versioned by `PROMPT_VERSION`, fingerprinted by `PROMPT_HASH` over the version, prompt and schema) asks the model to return, for every record id:

- `recommendation`: include, exclude or optional;
- `relevance`: high, medium or low;
- `reason`: at most 25 words.

It also asks for at most 5 "missing" phrases, and forbids treatment, dosing or medicine advice and invented ids.

**Payload** (after de-identification):

- **Referral:** kind, reason, the doctor's consultation notes (at most 2,000 characters), department, planned procedure, procedure status and urgency, with age and sex. Prompt version `packet-selection/3`.
- **Each record:** id, category, relative date, default flag and text, cut to 300 characters.

**Validation** rejects the whole answer when:

- the keys aren't exactly `items` and `missing`;
- an id is unknown, a boolean or repeated;
- a value isn't in its allowed set;
- a reason is empty or longer than 25 words;
- a reason or a missing phrase contains advice or dosing words (patterns `ADVICE`, `DOSING`);
- a missing phrase is longer than 15 words.

**Applying the answer.**

- Staff choices are never overridden.
- Items in the default floor stay selected; the model's "exclude" on them is shown as a low-relevance hint only.
- Non-default items the model includes become selected with `selection_source=ai`.

The run is recorded in `selection_runs`, and the package's `selection` field records each item's source (default, AI or staff), the model and the prompt version.

**Observed behaviour with `gemma4:cloud`** (integration test run, 2026-10-28): 12 of 15 runs completed. 3 were rejected by the dosing-word check. In every rejected case the default selection stood, as designed.

## 9.3 Paper field extraction (`documents/processing.py`)

**Input.** The model receives the paper's OCR lines (`i`, page, text), de-identified with dates kept.

**Output.** It must return, under `extraction_schema()`:

- **medicines:** name, strength, dose, route, frequency, start date, line ids;
- **labs:** test, value, unit, date, line ids;
- the document date.

**Checks and fallback.** Any field that cites an unknown line id, or no line id, rejects the answer. With `EXTRACTION_MODE=auto` the deterministic `rules-extractor/2` then runs instead, and the run notes say so. With `llm` the failure is reported. The extractor version is recorded on each `extraction_runs` row (`llm:<model>` or `rules`).

## 9.4 AI suggestions (offline logistic regression)

`scripts/train_ai_suggestions.py` trains a logistic regression on DDInter 2.0. The positives are 160,235 known pairs; pairs absent from DDInter are unlabelled background, not negatives. Features:

- shared ATC group;
- how often each drug's ATC class-mates interact with the other drug;
- each drug's interaction count;
- the ATC main groups involved.

It scores every pair among the project's ingredients that has no DDInter entry and writes those scoring 0.8 or more to `rules/ai/suggestions.json`. The evaluation is in `rules/ai/evaluation.json`: at 0.8, 73% of held-out known interactions are found, with about 3.4 suggestions per 100 random pairs that DDInter doesn't cover.

The app only looks these up (`medications/suggestions.py`, `ai_view.py`). A pair that DDInter covers is never suggested. The evaluator has no input from this model: unit tests force every score to 0 and to 1 and check that the flags are identical. None of these figures is clinical accuracy.

## 9.5 Guardrails summary

| Guardrail | Where |
|---|---|
| Model output is a draft; people decide | Staff selection always wins; paper fields unverified until checked |
| Output validated in code; any failure rejects the whole answer | `check_schema`, `selection.validate`, extraction line-id check |
| Every record-derived statement cites supplied ids | Selection ids, extraction line ids; the letter itself is deterministic and cites evidence ids |
| Document and record text is untrusted data | Marked as data in the prompt; no tools; schema-only output |
| Never creates, changes or restates flags | The evaluator has no model input; flags are not in the model's output schema |
| Privacy | De-identification, external-model switch, https only, audit without content (Section 8.6) |
| Graceful absence | Without a model, or on any failure, deterministic defaults apply and the screen says "AI recommendation unavailable" |


# 10. Medication flagging design

## 10.1 Principles

- Flags come **only** from `evaluate_medications()`, a pure, deterministic function. The same medicines, procedure, conditions and rule set always give the same flags (invariant 5).
- A flag reports a recorded rule, interaction or label statement and its source. It never advises starting, stopping or changing a medicine, never prescribes and never assigns urgency.
- Nothing is reported as "safe". No match means "no matching rule on file".
- Every gap is a flag of its own kind, so missing checks are visible:
  - a medicine that isn't recognised;
  - an ingredient that isn't in the interaction source;
  - a procedure that isn't known;
  - records that are incomplete.
- A doctor's decision on a flag ("reviewed", "ignore", "research") means it was seen. It is never treatment clearance.

## 10.2 Data sources

| Source | Table and file | Status |
|---|---|---|
| Manual drug-class-by-procedure rules | `medication_rules` (seeded from `rules/medication/seed-rules.json`, edited in the app) | Active only when a `rule_reviewer` approves that exact version (content hash recorded) |
| Drug–drug interactions | `drug_interactions` (DDInter 2.0 subset, `rules/interactions/ddinter-subset.csv`, CC BY-NC-SA 4.0) | Imported as loaded; severity is DDInter's own (Major, Moderate, Minor, Unknown) |
| Drug-condition and drug-procedure statements from US drug labels | `label_rules` (`rules/labels/label-rules.json`, made by `scripts/extract_label_rules.py`) | Imported; each keeps the exact quoted sentence, section and source; validated by `label_validation.py` |
| Ingredients | `ingredients` (`rules/terminology/ingredients.json`): international name, label name, RxNorm and ATC codes, combination parts | Reference data |
| Medicine names | `medicine_names` (`rules/terminology/medicine-names.pk.json`): generic names, hand-checked brands, DRAP register brands, ambiguous register names | Reviewer-maintained; register brands loaded by decision 2026-10-28 |
| Rule set fingerprint | `ruleset_releases` | Hash of the approved manual rules, label rules and interaction data in force |

**Interaction explanations.** DDInter's download gives only the pair and its level. `scripts/extract_label_rules.py interactions` adds, for each pair, the shortest sentence from either drug's US label that names the other drug and talks about the combination. The drug-interactions section is preferred, and the sentence is kept verbatim in `rules/labels/interaction-quotes.json`, loaded onto `drug_interactions.label_quote`.
- **Excluded:** drug-class mentions ("calcium channel blockers"), fragments cut at headings, and pairs read and found irrelevant (`REVIEWED_NOT_RELEVANT`).
- **No quote, no explanation:** without a quote nothing is shown. No model writes explanations.

**How label rules are validated.** A rule from a drug label is kept only if:

- the quoted sentence appears verbatim in the cited section;
- the ingredient is one of the project's;
- the target is in the controlled vocabulary (`rules/vocab/label-targets.json`);
- the summary contains no advice to start, stop or change a medicine.

Sentences are matched to targets by fixed word patterns, so the same label always gives the same rules.

## 10.3 Inputs to the evaluator

- **Current medicines:** each entry's mapping status, ingredient(s), drug class, original name, source label and evidence ids. Duplicates are excluded and combination products are expanded into their parts.
- **Procedure:** the status (`planned`, `none`, `unknown`) and tags.
- **Conditions:** from the selected evidence.
- **Rule data:** approved manual rules, interaction pairs and coverage (which ingredients DDInter knows), and label rules.
- **Source outcomes:** the retrieval results, so incomplete records can be reported.

## 10.4 Procedure features

A doctor writes the procedure in their own words and ticks what it involves. Words in the name pre-tick likely features (`PROCEDURE_HINTS` in `config.py`, for example "extraction" ticks oral surgery and bleeding risk), and the doctor can change them. Nothing is guessed silently.

| Tag | Meaning |
|---|---|
| `oral_surgery` | Oral or dental surgery |
| `major_surgery` | Major or elective surgery |
| `minor_surgery` | Minor surgery |
| `general_anaesthesia` | General anaesthesia |
| `prolonged_fasting` | Fasting before and after the procedure |
| `iodinated_contrast` | Iodinated contrast media |
| `arterial_access` | Arterial puncture |
| `gi_endoscopy` | Gastrointestinal endoscopy |
| `sedation` | Sedation |
| `bleeding_risk` | Procedure with bleeding risk |

A manual rule matches a drug class against these tags, so one rule covers every procedure with the tag. Drug classes are listed in `DRUG_CLASSES` (`config.py`): anticoagulant, antiplatelet, NSAID, biguanide, sulfonylurea, SGLT2 inhibitor, insulin, bisphosphonate, systemic corticosteroid, statin, beta blocker, ACE inhibitor, ARB, calcium channel blocker, PPI, analgesic, opioid, antibiotic, antiviral, antispasmodic, iron, calcium and vitamin D, thyroid hormone, bronchodilator.

## 10.5 Flag kinds

| Kind | Raised when | Needs the doctor's decision before sending |
|---|---|---|
| `confirmed` | An approved manual rule's drug class matches a current medicine and the planned procedure has a matching tag | Yes |
| `interaction` | Two current ingredients form a DDInter pair. If a US drug label has a sentence naming both, it is shown verbatim as the flag's source quote, with the label and section | Only for Major |
| `label_warning` | A label rule's ingredient is current and its target matches a condition or procedure feature | Only for severity hint "high" |
| `unrecognised_medicine` | A medicine's name is unmapped or ambiguous (including DRAP names registered for different medicines) | Yes |
| `procedure_not_checked` | The procedure is unknown, or planned without features, and a current medicine has procedure rules | Yes |
| `interactions_not_checked` | A current ingredient is not covered by the interaction source | Yes |
| `records_incomplete` | A source was denied, expired, unavailable, invalid, partial or skipped | Yes |

When nothing matches, the evaluation summary says so in neutral words. If no rule data is loaded at all, the outcome is `no_rules`, never "no problems".

## 10.6 Versioning, decisions and the package

- **Evaluation runs.** Every evaluation is an `evaluation_runs` row: trigger, outcome, input hash, rule versions, rule-set hash and number of changed flags.
- **Flag versions.** A flag whose content changes is superseded and a new version is inserted. A decision (`flag_reviews`) is bound to one flag version and the rule-set hash. A new version needs a new decision.
- **In the package.** The package carries every active flag as a `FlagSnapshot` with its source (type, name, reference, version, quote), its severity, whether it was auto-generated, and the doctor's decision and note. The evaluation summary and the AI suggestions travel beside the flags.
- **At the receiving side.** The specialist sees the flags as structured items, not as text restated in the letter.

## 10.7 Rule maintenance

| Action | Who | Endpoint |
|---|---|---|
| Create a manual rule or a new version | Rule reviewer | `POST /rules`, `PUT /rules/{rule_id}` |
| Approve or reject a version (reference checked, note) | Rule reviewer | `POST /rules/{rule_id}/versions/{version}/decision` |
| Inspect interactions, label rules, AI model figures | Rule reviewer | `GET /rules/interactions`, `/rules/label-rules`, `/rules/ai` |
| Add or retire a medicine name | Rule reviewer | `POST /medicine-names`, `POST /medicine-names/{id}/retire` |
| Import DDInter, label rules, brand names | Developer, offline | `scripts/import_ddinter.py`, `extract_label_rules.py`, `import_brands.py`, `scrape_drap.py` |

The DRAP register snapshot (`rules/terminology/drap/`) comes from the public DRAP product search:

- **Products:** all 115,006 products, with structured details for 1,500 of them.
- **Brand mappings:** 5,398 brands loaded as register mappings; 21 ambiguous names held as options.
- **Veterinary products** are excluded wherever DRAP's detail page says so.

Decisions 2026-10-28 ("DRAP register snapshot", "DRAP brands loaded") record the method and the accepted risk.


# 11. Interfaces

## 11.1 Interface catalogue

| Interface | From → to | Protocol | Contract |
|---|---|---|---|
| Central REST API | Web app → `central` (`/api/central/*`) | HTTPS (production), JSON, user token | Appendix F; OpenAPI at `/docs` and `/openapi.json` on the service |
| Institution REST API (own staff) | Web app → institution (`/api/<institution>/*`) | JSON, user token | Appendix F (institution section) |
| Record retrieval | `central` → institution | JSON and FHIR R4 Bundle, forwarded user token, `X-Referral-Id` | Section 5.6, `docs/fhir-subset.md` |
| Identity lookup, registration, intake, grants | `central` → institution | JSON, user token | Appendix F |
| Package, order, copy, clarification answer, expiry delivery | `central` (worker) → institution `inbound/*` | JSON envelopes, `central-api` service token | Appendix G (`PackageEnvelope`, `DiagnosticOrder`, `ClarificationAnswer`, …) |
| Provider events | institution → `central` `POST /inbound/provider-events` | `ProviderEvent` envelope, institution service token | Appendix G |
| Grant close-out | `central` (worker) → institution `POST /grants/revoke-by-referral` | JSON, `central-api` service token | Appendix F |
| Identity provider | all → Keycloak | OIDC, JWKS, token introspection, client credentials, admin REST API (role templates, account status) | Appendix K |
| Language models | `central`, worker → Ollama, Anthropic, OpenAI-compatible | HTTPS (or local HTTP to Ollama) | Section 9.1 |
| OCR service | worker → Google Cloud Vision `images:annotate` | HTTPS, key in the `X-Goog-Api-Key` header | Section 6.4 |

## 11.2 API conventions

- **Resources** are referral-centred (`/referrals/{id}/...`), with sub-resources for evidence, documents, medicines, flags, links, retrievals, selection, packages, diagnostics, tasks and responses.
- **Writes** that change a referral carry `expected_row_version`. A stale version returns `409 stale_version` with `current_version`.
- **Errors** share one shape: `{"detail": {"code": "<machine code>", "message": "<sentence for a person>", ...}}`. Validation errors return `422 validation_error` naming the first failing field.

| Status | Codes |
|---|---|
| 401 | `account_disabled`, invalid or expired token |
| 403 | `forbidden` (audited), `access_denied` at sources, `wrong_institution`, `wrong_destination` |
| 404 | `not_found`, `unknown_referral` |
| 409 | `invalid_transition`, `stale_version`, `clinical_content_locked`, `record_linked_elsewhere`, `not_accepted`, `patient_not_informed`, `tasks_open`, `outcome_not_seen`, `already_closed` |
| 410 | `deleted` (document removed under retention) |
| 415 | `unsupported_type` (upload is not PDF, PNG or JPEG by content) |
| 422 | `too_large`, `too_many_pages`, `validation_error`; every upload rejection is audited |
| 502 | `identity_provider_refused` (Keycloak admin call failed) |
| 503 | `not_ready` |

- **Health:** every service exposes `GET /health` (process up) and `GET /ready` (database reachable). Compose health checks use `/ready`.
- **Lists** are bounded (for example 100 notifications, 500 medicine names, 150 AI candidates). There is no general pagination.

## 11.3 Envelope versioning

Envelopes carry an `envelope_version`:

- `referral-package/2.0`
- `diagnostic-order/1.0`
- `provider-event/1.0`

They also carry `contract_note = "Project API contract (not a standard FHIR resource)"`.

**Changing a contract.** Contract changes (`libs/common/refcommon/exchange.py`, `contracts/`) need the consuming owner's approval (AGENTS.md). Additive fields keep the version. A breaking change bumps it, and the receiver must reject versions it does not understand. `contracts/examples/` holds example payloads exported by `scripts/export_contract_examples.py`, and `contracts/fhir-samples/` holds FHIR samples validated by the official validator (`scripts/fhir-validate.ps1`).

## 11.4 Idempotency keys

| Message | Key | Receiver behaviour on repeat |
|---|---|---|
| Package delivery | `delivery_key` = `<source>:<reference>:v<version>` | `incoming_packages.delivery_key` unique: returns `already_received` with the original case |
| Sender copy | `copy_key` | `sent_copies.copy_key` unique |
| Diagnostic order | `order_key` = `<source>:<DX reference>` | `orders.order_key` unique |
| Provider event | `event_key` | `inbound_messages.message_key` unique: returns `duplicate` |
| Clarification answer | `answer_key` | `info_requests.answer_key` unique |
| Forwarded result (not built) | `forward_key` | `forwarded_results.forward_key` unique |
| Response (legacy) | `return_key` and event key | unique |

Retries always reuse the key, so a request that timed out but succeeded is never applied twice (invariant 9). The outbox row is written in the same transaction as the decision to send.


# 12. Reliability and error handling

## 12.1 Failure semantics

| Failure | Behaviour | What the user sees |
|---|---|---|
| Institution slow or down during retrieval | Timeout `SOURCE_TIMEOUT_SECONDS` (10 s), up to `SOURCE_MAX_RETRIES` (2) retries for transient errors; other sources continue in parallel | Source marked "unavailable" (retryable); `records_incomplete` flag; letter lists it as a limitation |
| Access denied or grant expired | No retry; centrally held copies from that source become `access_revoked` and deselected | "Denied" or "access expired", never "no records" |
| Invalid FHIR from a source | Invalid resources counted and listed; the rest imported | "Partial" with the reasons |
| Delivery to an institution fails | Outbox retry with the same key, backoff 2^n s up to 120 s, 8 attempts | Delivery problem in the staff work queue; manual retry (`POST /referrals/{id}/retry-delivery`) |
| Institution cannot reach the platform | Institution outbox thread retries with the same event key | Event applied once when the platform is back |
| Model unavailable, refused or invalid | Rule-based default selection or rules extractor | "AI recommendation unavailable" with the reason |
| OCR engine failure | Google Vision falls back to Tesseract; processing errors fail the job visibly | Document status `failed` with the error; reprocess available |
| Keycloak admin call fails | No partial role change | `502 identity_provider_refused` |
| Worker down | Jobs stay queued (Redis); outbox rows stay pending; purges wait | Jobs pending; nothing lost, because job state is in PostgreSQL |
| Purge while a delivery is unconfirmed | Purge deferred and audited with reasons | Content kept until delivery is confirmed |
| Concurrent edits | Optimistic concurrency | "Changed by someone else, reload" (409) |

## 12.2 Consistency model

- **Within a service:** one PostgreSQL transaction per request. Domain changes, audit rows, events, notifications and outbox rows commit together.
- **Between services:** eventual consistency through outboxes with idempotent receivers. Statuses reflect confirmed facts only:
  - a referral becomes `submitted` only when the receiving service confirms receipt;
  - acknowledgement, acceptance and completion come only from the receiver's events.
- **Out-of-order events:** an `accepted` event arriving while the referral is still `submitted` first applies `acknowledged`, so the state machine stays valid.

## 12.3 Background job safety

- **Delivery semantics:** `task_acks_late=True` and `worker_prefetch_multiplier=1` mean a task is acknowledged only after it finishes. A worker crash re-delivers it, and every task is idempotent.
- **Permission re-check:** document jobs re-check the requester's account and institution before running.
- **Scheduled sweeps** (beat):
  - outbox: every 5 s;
  - grant close-out: every 60 s;
  - working-set purge: every 10 min;
  - document retention: hourly.

  Each sweep only does work that is due, so a missed run is caught up by the next.


# 13. Quality attributes

| Attribute | Design measures | Evidence |
|---|---|---|
| Performance | Parallel calls to institutions; slow work (OCR, AI) in the worker; bounded lists and candidate caps; referral profile limited to relevant categories and windows | `scripts/loadtest.py`; results in `docs/evaluation-evidence/stage7` (10 concurrent users, direct and through nginx) |
| Scalability | Stateless API containers; the worker can be scaled; databases are separate per owner, so institutions scale independently | Compose services; not load-tested beyond the demo |
| Availability | Health and readiness checks with restart policies; partial results instead of failures; outbox delivery survives outages | `docs/operations.md` |
| Security | Section 8 | Stage 3 of `docs/srs-evaluation-report.md` |
| Privacy | Temporary working set, expiring grants, de-identification, external-model switch | Decision records 2026-10-27 and 2026-10-28; `test_privacy.py`, `test_lifecycle.py`, `test_referral_expiry.py` |
| Integrity | Hashing, immutable packages, revisions, versioned flags | `POST /packages/{v}/verify`; integration tests |
| Auditability | Audit in every database; event timeline | Audit views; stage 3 evidence |
| Usability and accessibility | Role-based menus and work queue; MUI components; keyboard focus checked | Accessibility statement page; stage 7 accessibility results (`docs/evaluation-evidence/stage7/accessibility-results.json`) |
| Maintainability | Modular monolith with feature modules; shared library for cross-service code; generated SDS appendices; decision records | This document; `AGENTS.md` module ownership |
| Portability | Docker images; one Compose file for local use and an overlay for hosting | `docker-compose.prod.yml`, `docs/deploy-cloud.md` |
| Replaceability | `LLMProvider`, OCR engine switch, storage interface, Keycloak configuration by environment | Sections 4 and 9 |
| Testability | Pure evaluator; fake HTTP endpoints for providers; integration tests against the stack | Section 15 |
| Observability | Structured logging (`%(asctime)s %(levelname)s %(name)s`); readiness endpoints; audit events; job and outbox tables queryable | `docs/operations.md` (health and monitoring) |


# 14. Deployment and operations

## 14.1 Environments

| Environment | How | Exposure |
|---|---|---|
| Local development | `docker compose up -d --build` (`docker-compose.yml`) | Web 3000, Keycloak 8080, central 8000, institutions 8001 to 8004 on localhost |
| Local with database tools | add `docker-compose.dbaccess.yml` | PostgreSQL on `127.0.0.1:5432` only; never on a shared server |
| Hosted (free tier) | `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build` with `SITE_HOST` (`docs/deploy-cloud.md`, Oracle Cloud Always Free) | Only Caddy on 80 and 443 with automatic HTTPS; website at `https://SITE_HOST/`, Keycloak at `https://SITE_HOST/auth`; every other port removed |
| CI | GitHub Actions (`.github/workflows/ci.yml`) | Ephemeral |

## 14.2 Deployment view (hosted)

```mermaid
flowchart LR
    Internet["Browser (internet)"] -->|"443 TLS (Let's Encrypt), HSTS"| CAD["caddy"]
    subgraph Host["One virtual machine, Docker network"]
        CAD -->|"/auth/*"| KC["keycloak (start, relative path /auth, proxy headers)"]
        CAD -->|"everything else"| WEB["web (nginx)"]
        WEB -->|"/api/central/*"| CEN["central"]
        WEB -->|"/api/<institution>/*"| INST["drali, chughtai, ziauddin, akuh"]
        CEN --- WRK["worker"]
        CEN & WRK & INST & KC --> PG[("postgres")]
        CEN & WRK --> RED[("redis")]
        CEN & WRK --> DOCV[("documents volume")]
    end
    WRK -.->|"optional, https"| EXT["Model and OCR services"]
```

In production, `KEYCLOAK_PUBLIC_URL` is `https://SITE_HOST/auth`, so token issuers match what the browser sees. Services still reach Keycloak internally at `http://keycloak:8080/auth`. The web image is built with `VITE_OIDC_AUTHORITY=https://SITE_HOST/auth/realms/referral`.

## 14.3 Configuration and secrets

- **Settings:** all come from environment variables. Appendix J lists every variable the code reads, with its default, and every Compose service's environment keys.
- **Installation:** copy `.env.example` to `.env` and set:
  - the database passwords (`*_DB_PASSWORD`) and the PostgreSQL superuser password;
  - the Keycloak administrator password;
  - every client secret (`*_CLIENT_SECRET`);
  - the demo user password.

  The Keycloak realm (`infra/keycloak/import/referral-realm.json`, generated by `scripts/make_keycloak_realm.py`) takes its client secrets from the environment **at first import**.

  Pitfall: an `.env` with missing secret names at first start produces empty client secrets in Keycloak, and the institution services then refuse every token because introspection is not configured. Fix it by setting the secrets and updating the Keycloak clients (or re-importing the realm).
- **Optional features:** `LLM_PROVIDER`, `LLM_MODEL`, `OLLAMA_HOST`, `LLM_EXTERNAL_ALLOWED`, `ANTHROPIC_API_KEY`, `LLM_BASE_URL`, `LLM_API_KEY`, `OCR_ENGINE`, `GOOGLE_VISION_API_KEY`.
- **Policy placeholders** (to be confirmed by the operating institution): `ACCEPTED_HOLD_DAYS` (30), `WORKING_SET_GRACE_HOURS` (72), `DEFAULT_GRANT_DAYS` (14), `MAX_GRANT_DAYS` (30), `REFERRAL_HISTORY_YEARS` (3), `REFERRAL_WINDOW_DAYS` (183), `MAX_RETRIEVAL_SOURCES` (5), `DOCUMENT_RETENTION_DAYS` (365), and `SPECIALTY_HISTORY_YEARS` (in code).

## 14.4 Database schema management

Each service runs `alembic upgrade head` on start (central: `services/central/migrations`; institution: `services/provider/migrations`). Appendix L lists the migration chains. New migrations are created by the module owner:

```
docker compose run --rm --no-deps -v ${PWD}/services/<svc>/migrations:/srv/migrations <svc> alembic revision --autogenerate -m "<what>"
```

## 14.5 Seeding and reset

`scripts/reset-and-seed.ps1 -Force` (or `.sh --force`) runs `python -m app.seed --reset --yes` in every institution service and in `central`. Each part is seeded as follows:

- **Institutions** load their own blocks of `seed-data/patients/*.json` (five fictional patients, P1 to P5).
- **The platform** loads the medicine names (including DRAP register brands), ingredients, the DDInter subset, label rules, seed manual rules, AI suggestions and the links each patient already has. The link to the destination hospital is not seeded; requesting it is part of the demo.

The seed version is `synthetic-seed/2.0`.

## 14.6 CI pipeline

| Job | Trigger | Steps |
|---|---|---|
| `web` | pull request, push to main | `npm ci`, `npm run typecheck`, `npm run build` |
| `backend-unit` | pull request, push to main | Build the central image; run `services/central/tests` (no paid model calls); `compileall` of services, libs and scripts |
| `images` | pull request, push to main | `docker compose build` with `.env.example` |
| `integration` | push to main | `docker compose up --wait`, reset and seed, `pytest tests` against the stack, logs on failure |
| `sds` | pull request, push to main | `python scripts/sds/build_sds.py check`: fails if the SDS is stale or the structure changed without a new SDS version (Section 17) |

## 14.7 Backup, restore and upgrades

- **Backup:** `scripts/backup.ps1` dumps every application database, the Keycloak database and the document storage, with a manifest (git commit, migration revisions, seed and rule versions).
- **Restore check:** `scripts/restore-check.ps1 -BackupDir <dir>` restores into a disposable network, database and volume, then verifies that the latest approved package and its documents reopen with matching SHA-256.
- **Upgrade:**
  1. Back up first.
  2. Deploy the new images; migrations run on start, and readiness must pass.
  3. Smoke test.
  4. Roll back images only when the schema is compatible; otherwise restore.

## 14.8 Monitoring

Each service exposes `/health` and `/ready`, and Compose restarts unhealthy containers. Operational signals live in the database:

- `outbox` rows that are failed or have many attempts;
- `jobs` rows that failed;
- `selection_runs` statuses;
- deferred purge audit events;
- `source_retrievals` statuses.

Delivery problems appear in the staff work queue. Logs carry request metadata, never clinical content or tokens.


# 15. Testing strategy

| Level | Location | Runs against | Command |
|---|---|---|---|
| Unit and component | `services/central/tests` | Nothing external: pure functions, fake HTTP endpoints for model and OCR providers, SQLite or in-memory where needed | `docker compose run --rm --no-deps -v ${PWD}/services/central/tests:/srv/tests central python -m pytest tests -q` |
| Integration (API) | `tests/` | The full Compose stack after reseeding (set `SKIP_RESET=1` to keep data) | `.venv\Scripts\python -m pytest tests -q` |
| Browser end-to-end | `web/e2e/*.spec.ts` | The running stack through the web app | `cd web; npx playwright test e2e/smoke.spec.ts` |
| Type check and build | `web/` | — | `npm run typecheck; npm run build` |
| FHIR validation | `contracts/fhir-samples` | HL7 validator | `scripts/fhir-validate.ps1` |
| OCR evaluation | `evaluation/ocr` (dev and held-out sets) | Tesseract | `scripts/evaluate_ocr.py` |
| Load | — | Running stack | `scripts/loadtest.py` |
| SDS currency | `docs/sds` | The code | `python scripts/sds/build_sds.py check` |

**What the unit tests protect:**

- the evaluator's determinism and flag kinds;
- AI guardrails: selection validation, de-identification, the external-model switch, and that AI suggestions cannot change flags;
- provider request shapes and error handling (Anthropic, Ollama, OpenAI-compatible);
- the lifecycle rules for each expiry case;
- grant close-out;
- Google Vision request shape and fallback;
- DRAP register name matching.

**What the integration tests cover end to end:**

- the five synthetic patient scenarios and their expected flags;
- retrieval from every linked hospital;
- uploaded prescription merging;
- default selection against each seed's expected view;
- temporary grants, manifests, own-copy verification and purge;
- role templates;
- referral expiry at both the platform and the receiving hospital;
- DRAP brand handling.

Appendix O lists every test with its description, generated from the test files.

**Latest results** (2026-10-29, local stack):

- 136 unit tests pass, including `test_staff_view.py`: staff views carry no clinical values, consultation notes keep older package hashes, interaction label quotes.
- 21 of 22 integration tests pass. The failure is `test_admin_assigns_a_role_by_template`: Keycloak refused the role change (`502 identity_provider_refused`). The local realm was imported before the role-template change, so the `service-account-central-api` user lacks the `realm-management` role `view-realm`, which `infra/keycloak/import/referral-realm.json` now grants (Section 16).
- The web type check passes.


# 16. Known limitations, risks and open decisions

## 16.1 Built differently from the SRS or not built

| Item | Status | Reference |
|---|---|---|
| Specialist response form | Replaced: the receiving doctor accepts or declines; response endpoints kept for old data | Decision 2026-10-28, no specialist response |
| Receiver gets a notification instead of the package (read-through access window) | Not built; the receiver still gets the package and removes it at expiry | Decisions 2026-10-28, access window and referral expiry |
| Forwarding test results to the receiving hospital | Contract, outbox kind and endpoint exist; nothing creates the message | Section 6.10 |
| List-then-fetch retrieval, cross-institution lab standardisation (LOINC and UCUM), merged medicine view for the AI | Planned | Decision 2026-10-28, retrieval from all sources |
| FHIR International Patient Summary per institution | Not adopted; future work | Same decision |
| Patient consent record | Not modelled, by team decision | Access-window decision |

## 16.2 Risks

| Risk | Impact | Current mitigation | Further action |
|---|---|---|---|
| DRAP register brands loaded without per-row pharmacist review | A wrong mapping gives the wrong interactions and rules | Strict matching, source note on the medicine, ambiguous names never guessed, veterinary products excluded where known | Clinical review of the register mappings; fetch details for the 5,434 rows not yet checked for veterinary use |
| Imported rules (DDInter, drug labels) are not clinically reviewed | Irrelevant or incomplete flags | Labelled "automatically generated, not clinically reviewed" with the source shown | A named clinical reviewer approves the rule sets |
| De-identification is pattern-based | A rare detail could identify someone | Synthetic data only; external models off by default | Agreement with the operating institution, or a local model, before real data |
| Page images to Google Vision cannot be de-identified | Names and CNICs on papers leave the computer | Off by default; synthetic papers only | Institutional agreement |
| No encryption at rest by the application | Disk theft exposes data | Temporary working set; separate databases | Encrypted volumes in any hosted deployment |
| A referral never sent, or sent but never accepted, keeps its working set indefinitely | Longer central storage than needed | Only on the platform; the referring side can cancel | A reminder or expiry for idle drafts and pending referrals |
| `dev-cli` password-grant client in the realm | Weakens sign-in policy if exposed | Development only | Remove or disable in hosted realms |
| Local realms imported before role templates | Role changes refused (`502 identity_provider_refused`) | — | Give `service-account-central-api` the `realm-management` role `view-realm` (as in the realm file), or re-import the realm |
| Single PostgreSQL server for all owners | Shared failure domain; separation is logical, not physical | Separate databases and logins | Separate servers for real institutions |
| The model's dosing-word filter rejects some harmless answers | AI recommendation unavailable more often | Default selection stands | Prompt asking the model not to mention doses |

## 16.3 Policy values awaiting confirmation

These are placeholders until the operating institution or a clinician confirms them:

- the history window per specialty (`SPECIALTY_HISTORY_YEARS`);
- the default selection window (183 days);
- the maximum number of sources (5);
- grant duration (14 and 30 days);
- the accepted-referral hold (30 days) and the grace period (72 hours);
- document retention (365 days);
- the wording of the flag disclaimer (`FLAG_DISCLAIMER`).

## 16.4 Documentation debt

`docs/architecture.md`, `docs/operations.md` and `docs/fhir-subset.md` still describe parts of version 1 (clinic, lab and specialist services). This SDS supersedes them for the current design. Those files should be updated or point here.


# 17. Maintaining this document

## 17.1 Rule

**Every change to the system produces a new version of this SDS.** A change is anything that alters:

- the database schema;
- an endpoint or its access checks;
- a setting;
- a background job or its schedule;
- the state machine;
- a web route, role or role template;
- a migration or a dependency;
- a decision record;
- the written sections.

CI enforces this: the `sds` job runs `build_sds.py check`, which fails when the generated appendices or `SDS.md` are stale, or when the structure or written sections changed since the last released version. `check --strict` also fails on any source-file change.

## 17.2 Procedure for a change

1. Make the code change.
2. If behaviour, design or reasoning changed, edit the matching written section in `docs/sds/sections/`. For a significant decision, also add a record in `docs/decisions/`.
3. Release a new version:

   ```
   python scripts/sds/build_sds.py release --level minor --summary "Retrieval reads every linked institution"
   ```

   The level follows semantic versioning:
   - `major`: a new architecture or a breaking contract;
   - `minor`: new or changed capabilities, tables, endpoints or settings;
   - `patch`: corrections to the text only.
4. Commit `docs/sds/` together with the code change.

`release` does five things:

- regenerates the appendices;
- computes the structural differences from the previous version (tables, columns, endpoints, access checks, settings, jobs, routes, roles, migrations, dependencies, decisions);
- bumps the version;
- freezes the full document as `docs/sds/versions/SDS-v<version>.md`;
- adds a `CHANGELOG.md` entry with your summary and the detected changes.

Other commands:

| Command | Use |
|---|---|
| `build_sds.py build` | Regenerate the appendices and `SDS.md` while working (the header says "Working draft after vX") |
| `build_sds.py diff` | Show what changed structurally since the last release |
| `build_sds.py check [--strict]` | What CI runs |

## 17.3 Files

| Path | Content |
|---|---|
| `docs/sds/SDS.md` | The current document: written sections plus generated appendices |
| `docs/sds/sections/*.md` | Written sections (edit these) |
| `docs/sds/generated/*.md` | Generated appendices (never edit by hand) |
| `docs/sds/versions/SDS-v*.md` | Frozen released versions |
| `docs/sds/CHANGELOG.md` | Version history with detected structural changes |
| `docs/sds/manifest.json` | Current version, release date, fingerprints and the structural inventory of the released version |
| `scripts/sds/build_sds.py` | The generator (static analysis: no running services needed) |

## 17.4 How the generator reads the code

- **ERDs and data dictionary:** SQLAlchemy model classes (`mapped_column`, `ForeignKey`, `UniqueConstraint`, mixins, column comments).
- **API inventory:** FastAPI decorators and router prefixes. Access checks are the authorisation calls in each handler, following helpers in the same module up to two levels.
- **Contracts and request bodies:** pydantic models.
- **Configuration:** environment reads in the Python code, plus the Compose files and `.env.example` (secret values never shown).
- **State machine:** `TRANSITIONS` in `referrals/state.py`.
- **Jobs:** the Celery beat schedule and task decorators.
- **Web, roles and identity:** `App.tsx`, `rules/roles/templates.v1.json` and the Keycloak realm export (no credentials).
- **Migrations, dependencies, rule data, tests and decisions:** their files.

When a new kind of structure is added (for example a new service), extend `build_sds.py` so the appendices cover it, then release a new major or minor version.


# Appendix A. ERD: central platform

_Generated from the code by `scripts/sds/build_sds.py`. Do not edit by hand._

### Central platform database (`central_db`)

Generated from the SQLAlchemy models. Solid lines are database foreign keys; dotted lines are logical references held as plain columns (no constraint). PK primary key, FK foreign key, UK unique.

#### Overview: all 34 tables and their relationships

```mermaid
erDiagram
    audit_events {
        int id PK "not null"
    }
    documents {
        int id PK "not null"
    }
    evidence_items {
        int id PK "not null"
    }
    evidence_revisions {
        int id PK "not null"
    }
    extraction_runs {
        int id PK "not null"
    }
    jobs {
        string id PK "not null, String(40)"
    }
    selection_runs {
        int id PK "not null"
    }
    source_retrievals {
        int id PK "not null"
    }
    patient_link_events {
        int id PK "not null"
    }
    patient_links {
        int id PK "not null"
    }
    users {
        string id PK "not null, String(64)"
    }
    ai_suggestions {
        string pair_key PK "not null, String(210)"
    }
    drug_interactions {
        int id PK "not null"
    }
    evaluation_runs {
        int id PK "not null"
    }
    flag_reviews {
        int id PK "not null"
    }
    ingredients {
        string name PK "not null, String(100)"
    }
    label_rules {
        int id PK "not null"
    }
    medication_entries {
        int id PK "not null"
    }
    medication_flags {
        int id PK "not null"
    }
    medication_rules {
        int id PK "not null"
    }
    medicine_names {
        int id PK "not null"
    }
    ruleset_releases {
        int id PK "not null"
    }
    suggestion_reviews {
        int id PK "not null"
    }
    briefs {
        int id PK "not null"
    }
    clarifications {
        int id PK "not null"
    }
    consultation_responses {
        int id PK "not null"
    }
    diagnostic_requests {
        int id PK "not null"
    }
    followup_tasks {
        int id PK "not null"
    }
    inbound_messages {
        int id PK "not null"
    }
    notifications {
        int id PK "not null"
    }
    outbox {
        int id PK "not null"
    }
    referral_events {
        int id PK "not null"
    }
    referral_packages {
        int id PK "not null"
    }
    referrals {
        int id PK "not null"
    }
    ai_suggestions |o..o{ suggestion_reviews : "pair_key (logical)"
    briefs ||--o{ referral_packages : "brief_id"
    documents |o--o{ evidence_items : "document_id"
    documents |o--o{ jobs : "document_id"
    documents ||--o{ extraction_runs : "document_id"
    evaluation_runs ||--o{ medication_flags : "run_id"
    evidence_items |o..o{ evidence_items : "superseded_by (logical)"
    evidence_items ||--o{ evidence_revisions : "evidence_id"
    evidence_items ||--o{ medication_entries : "evidence_id"
    ingredients |o..o{ drug_interactions : "ingredient_a (logical)"
    ingredients |o..o{ drug_interactions : "ingredient_b (logical)"
    ingredients |o..o{ label_rules : "ingredient (logical)"
    ingredients |o..o{ medication_entries : "ingredient (logical)"
    ingredients |o..o{ medicine_names : "ingredient (logical)"
    medication_entries |o..o{ medication_entries : "duplicate_of (logical)"
    medication_entries |o..o{ medication_flags : "medication_entry_id (logical)"
    medication_flags ||--o{ flag_reviews : "flag_id"
    medication_rules |o..o{ medication_flags : "rule_id (logical)"
    patient_links |o..o{ evidence_items : "link_id (logical)"
    patient_links |o..o{ source_retrievals : "link_id (logical)"
    patient_links ||--o{ patient_link_events : "link_id"
    referrals |o--o{ inbound_messages : "referral_id"
    referrals |o--o{ jobs : "referral_id"
    referrals |o--o{ notifications : "referral_id"
    referrals |o--o{ patient_links : "referral_id"
    referrals ||--o{ briefs : "referral_id"
    referrals ||--o{ clarifications : "referral_id"
    referrals ||--o{ consultation_responses : "referral_id"
    referrals ||--o{ diagnostic_requests : "referral_id"
    referrals ||--o{ documents : "referral_id"
    referrals ||--o{ evaluation_runs : "referral_id"
    referrals ||--o{ evidence_items : "referral_id"
    referrals ||--o{ flag_reviews : "referral_id"
    referrals ||--o{ followup_tasks : "referral_id"
    referrals ||--o{ medication_entries : "referral_id"
    referrals ||--o{ medication_flags : "referral_id"
    referrals ||--o{ outbox : "referral_id"
    referrals ||--o{ referral_events : "referral_id"
    referrals ||--o{ referral_packages : "referral_id"
    referrals ||--o{ selection_runs : "referral_id"
    referrals ||--o{ source_retrievals : "referral_id"
    referrals ||--o{ suggestion_reviews : "referral_id"
    selection_runs |o..o{ evidence_items : "ai_run_id (logical)"
    users |o..o{ notifications : "recipient_id (logical)"
    users |o..o{ patient_links : "requested_by_id (logical)"
    users |o..o{ referrals : "requesting_doctor_id (logical)"
```

#### ERD: `audit` domain (1 tables, `services/central/app/models/audit.py`)

```mermaid
erDiagram
    audit_events {
        int id PK "not null"
        string actor_id "not null, String(64)"
        string actor_name "not null, String(200)"
        string institution_id "nullable, String(50)"
        string action "not null, String(80)"
        string target_type "not null, String(60)"
        string target_id "not null, String(100)"
        int referral_id "nullable"
        string outcome "not null, String(20)"
        json detail "not null"
        datetime created_at "not null, DateTime(timezone=True)"
    }
```

#### ERD: `evidence` domain (7 tables, `services/central/app/models/evidence.py`)

```mermaid
erDiagram
    documents {
        int id PK "not null"
        int referral_id FK "not null"
        string patient_institution "not null, String(50)"
        string patient_local_id "not null, String(50)"
        string uploaded_by "not null, String(200)"
        string uploaded_by_id "not null, String(64)"
        string original_filename "not null, String(255)"
        string declared_type "not null, String(100)"
        string detected_type "not null, String(100)"
        int size_bytes "not null"
        string sha256 "not null, String(64)"
        string storage_key "not null, String(200)"
        string doc_type "not null, String(40)"
        int page_count "not null"
        string status "not null, String(20)"
        text error "nullable"
        datetime created_at "not null, DateTime(timezone=True)"
        datetime deleted_at "nullable, DateTime(timezone=True)"
    }
    evidence_items {
        int id PK "not null"
        int referral_id FK "not null"
        string patient_institution "not null, String(50)"
        string patient_local_id "not null, String(50)"
        string origin "not null, String(20)"
        string source_institution "not null, String(50)"
        string source_record_type "nullable, String(40)"
        string source_record_id "nullable, String(80)"
        string source_record_version "nullable, String(20)"
        int link_id "nullable"
        string category "not null, String(30)"
        text display "not null"
        json original "not null"
        json current "not null"
        json fhir "nullable"
        datetime clinical_time "nullable, DateTime(timezone=True)"
        datetime retrieved_at "not null, DateTime(timezone=True)"
        int document_id FK "nullable"
        int page "nullable"
        json region "nullable"
        text source_text "nullable"
        json confidence "nullable"
        string review_state "not null, String(20)"
        string verification_status "not null, String(20)"
        string verified_by "nullable, String(200)"
        datetime verified_at "nullable, DateTime(timezone=True)"
        bool selected "not null"
        bool in_default "not null"
        string selection_source "nullable, String(10)"
        string selected_by "nullable, String(200)"
        datetime selected_at "nullable, DateTime(timezone=True)"
        string ai_recommendation "nullable, String(10)"
        string ai_relevance "nullable, String(10)"
        text ai_reason "nullable"
        int ai_run_id "nullable"
        int superseded_by "nullable"
        string author "nullable, String(200)"
        int row_version "not null"
        datetime created_at "not null, DateTime(timezone=True)"
        datetime updated_at "not null, DateTime(timezone=True)"
    }
    evidence_revisions {
        int id PK "not null"
        int evidence_id FK "not null"
        string action "not null, String(30)"
        json prior_value "nullable"
        json new_value "nullable"
        string prior_state "nullable, String(20)"
        string new_state "nullable, String(20)"
        string editor "not null, String(200)"
        string editor_id "not null, String(64)"
        text note "not null"
        datetime created_at "not null, DateTime(timezone=True)"
    }
    extraction_runs {
        int id PK "not null"
        int document_id FK "not null"
        string job_id "nullable, String(40)"
        string text_source "nullable, String(20)"
        string ocr_engine "nullable, String(60)"
        string ocr_engine_version "nullable, String(40)"
        string extractor "nullable, String(80)"
        string extractor_version "nullable, String(40)"
        text raw_text "not null"
        json pages "not null"
        string status "not null, String(20)"
        text error "nullable"
        json notes "not null"
        int duration_ms "not null"
        datetime created_at "not null, DateTime(timezone=True)"
    }
    jobs {
        string id PK "not null, String(40)"
        string kind "not null, String(40)"
        string status "not null, String(20)"
        int referral_id FK "nullable"
        int document_id FK "nullable"
        json params "not null"
        json result "nullable"
        text error "nullable"
        int attempts "not null"
        string created_by "not null, String(200)"
        string created_by_id "not null, String(64)"
        string institution_id "nullable, String(50)"
        datetime created_at "not null, DateTime(timezone=True)"
        datetime started_at "nullable, DateTime(timezone=True)"
        datetime finished_at "nullable, DateTime(timezone=True)"
    }
    selection_runs {
        int id PK "not null"
        int referral_id FK "not null"
        string status "not null, String(20)"
        string provider "nullable, String(40)"
        string model "nullable, String(80)"
        string prompt_version "not null, String(40)"
        string prompt_hash "not null, String(64)"
        int item_count "not null"
        bool truncated "not null"
        json missing "not null"
        text error "nullable"
        string created_by "not null, String(200)"
        datetime created_at "not null, DateTime(timezone=True)"
    }
    source_retrievals {
        int id PK "not null"
        int referral_id FK "not null"
        string source_institution "not null, String(50)"
        string local_patient_id "not null, String(50)"
        int link_id "nullable"
        string institution_kind "nullable, String(20)"
        string last_activity "nullable, String(20)"
        string window_start "nullable, String(20)"
        string status "not null, String(20)"
        int record_count "not null"
        int new_count "not null"
        int duplicate_count "not null"
        int invalid_count "not null"
        json withheld "not null"
        text message "not null"
        bool retryable "not null"
        int attempts "not null"
        int duration_ms "not null"
        string requested_by "not null, String(200)"
        datetime requested_at "not null, DateTime(timezone=True)"
    }
    documents |o--o{ evidence_items : "document_id"
    documents |o--o{ jobs : "document_id"
    documents ||--o{ extraction_runs : "document_id"
    evidence_items |o..o{ evidence_items : "superseded_by (logical)"
    evidence_items ||--o{ evidence_revisions : "evidence_id"
    evidence_items ||--o{ medication_entries : "evidence_id"
    patient_links |o..o{ evidence_items : "link_id (logical)"
    patient_links |o..o{ source_retrievals : "link_id (logical)"
    referrals |o--o{ jobs : "referral_id"
    referrals ||--o{ documents : "referral_id"
    referrals ||--o{ evidence_items : "referral_id"
    referrals ||--o{ selection_runs : "referral_id"
    referrals ||--o{ source_retrievals : "referral_id"
    selection_runs |o..o{ evidence_items : "ai_run_id (logical)"
```

#### ERD: `identity` domain (3 tables, `services/central/app/models/identity.py`)

```mermaid
erDiagram
    patient_link_events {
        int id PK "not null"
        int link_id FK "not null"
        string action "not null, String(30)"
        string actor "not null, String(200)"
        string actor_id "not null, String(64)"
        string institution_id "nullable, String(50)"
        text note "not null"
        json detail "not null"
        datetime created_at "not null, DateTime(timezone=True)"
    }
    patient_links {
        int id PK "not null"
        string requester_institution "not null, String(50)"
        string requester_local_id "not null, String(50)"
        string target_institution "not null, String(50)"
        string target_local_id "nullable, String(50)"
        string patient_name "not null, String(200)"
        string patient_birth_date "nullable, String(20)"
        string patient_sex "nullable, String(10)"
        string patient_cnic "nullable, String(15)"
        int referral_id FK "nullable"
        text purpose "not null"
        string kind "not null, String(20)"
        string status "not null, String(20)"
        string status_key "not null, String(40)"
        string requested_by "not null, String(200)"
        string requested_by_id "not null, String(64)"
        datetime requested_at "not null, DateTime(timezone=True)"
        string decided_by "nullable, String(200)"
        string decided_by_id "nullable, String(64)"
        datetime decided_at "nullable, DateTime(timezone=True)"
        text decision_note "nullable"
        json match_check "nullable"
        bool registered_new "not null"
        string invalidated_by "nullable, String(200)"
        datetime invalidated_at "nullable, DateTime(timezone=True)"
        text invalidation_reason "nullable"
    }
    users {
        string id PK "not null, String(64)"
        string username "not null, String(100)"
        string display_name "not null, String(200)"
        string institution_id "nullable, String(50)"
        string department "nullable, String(60)"
        json roles "not null"
        string account_status "not null, String(20)"
        string status_changed_by "nullable, String(200)"
        datetime status_changed_at "nullable, DateTime(timezone=True)"
        datetime last_seen_at "not null, DateTime(timezone=True)"
    }
    patient_links |o..o{ evidence_items : "link_id (logical)"
    patient_links |o..o{ source_retrievals : "link_id (logical)"
    patient_links ||--o{ patient_link_events : "link_id"
    referrals |o--o{ patient_links : "referral_id"
    users |o..o{ notifications : "recipient_id (logical)"
    users |o..o{ patient_links : "requested_by_id (logical)"
    users |o..o{ referrals : "requesting_doctor_id (logical)"
```

#### ERD: `medications` domain (12 tables, `services/central/app/models/medications.py`)

```mermaid
erDiagram
    ai_suggestions {
        string pair_key PK "not null, String(210)"
        string ingredient_a "not null, String(100)"
        string ingredient_b "not null, String(100)"
        float score "not null"
        text reason "not null"
        string model_version "not null, String(60)"
        string data_version "not null, String(200)"
    }
    drug_interactions {
        int id PK "not null"
        string ingredient_a "not null, String(100)"
        string ingredient_b "not null, String(100)"
        string severity "not null, String(20)"
        string source "not null, String(40)"
        string source_version "not null, String(80)"
        string source_ref "not null, String(80)"
        text label_quote "nullable"
        string label_source "nullable, String(200)"
        string label_section "nullable, String(60)"
    }
    evaluation_runs {
        int id PK "not null"
        int referral_id FK "not null"
        string trigger "not null, String(160)"
        string status "not null, String(20)"
        string outcome "nullable, String(30)"
        text summary_message "nullable"
        json context "not null"
        json rule_versions "not null"
        string input_hash "not null, String(64)"
        string ruleset_hash "nullable, String(64)"
        text error "nullable"
        int changed_flags "not null"
        string triggered_by "not null, String(200)"
        datetime created_at "not null, DateTime(timezone=True)"
    }
    flag_reviews {
        int id PK "not null"
        int referral_id FK "not null"
        int flag_id FK "not null"
        int flag_version "not null"
        string side "not null, String(20)"
        string reviewer "not null, String(200)"
        string reviewer_id "not null, String(64)"
        string institution_id "not null, String(50)"
        int package_version "nullable"
        string decision "not null, String(20)"
        string ruleset_hash "nullable, String(64)"
        text note "not null"
        datetime created_at "not null, DateTime(timezone=True)"
    }
    ingredients {
        string name PK "not null, String(100)"
        string standard "nullable, String(100)"
        string label_name "nullable, String(100)"
        string rxnorm_id "nullable, String(20)"
        json atc_codes "not null"
        json components "not null"
        bool in_interaction_source "not null"
        text note "nullable"
    }
    label_rules {
        int id PK "not null"
        string rule_key UK "not null, String(200)"
        string kind "not null, String(20)"
        string ingredient "not null, String(100)"
        string target "not null, String(60)"
        string target_label "not null, String(120)"
        string severity_hint "not null, String(20)"
        text summary "not null"
        text quote "not null"
        string section "not null, String(40)"
        string source_type "not null, String(40)"
        string source_ref "not null, String(80)"
        string source_name "not null, String(200)"
        string source_version "not null, String(80)"
        string extractor_version "not null, String(40)"
        string status "not null, String(20)"
    }
    medication_entries {
        int id PK "not null"
        int referral_id FK "not null"
        int evidence_id FK "not null"
        string record_kind "not null, String(20)"
        string original_name "not null, String(200)"
        string brand "nullable, String(100)"
        string strength "nullable, String(60)"
        string dose "nullable, String(120)"
        string route "nullable, String(40)"
        string frequency "nullable, String(100)"
        string start_date "nullable, String(20)"
        bool over_the_counter "not null"
        string source_label "not null, String(300)"
        string ingredient "nullable, String(100)"
        json ingredients "not null"
        string drug_class "nullable, String(60)"
        string mapping_status "not null, String(20)"
        json mapping_choices "nullable"
        text mapping_note "nullable"
        int duplicate_of "nullable"
        bool dose_differs "not null"
        bool excluded "not null"
        string excluded_by "nullable, String(200)"
        text excluded_reason "nullable"
        datetime created_at "not null, DateTime(timezone=True)"
        datetime updated_at "not null, DateTime(timezone=True)"
    }
    medication_flags {
        int id PK "not null"
        int referral_id FK "not null"
        string flag_key "not null, String(200)"
        int version "not null"
        string kind "not null, String(40)"
        string severity "nullable, String(20)"
        json ingredients "not null"
        string source_type "nullable, String(40)"
        string source_name "nullable, String(200)"
        text source_ref "nullable"
        string source_version "nullable, String(80)"
        text source_quote "nullable"
        bool auto_generated "not null"
        bool requires_decision "not null"
        string title "not null, String(300)"
        text message "not null"
        string medication "nullable, String(300)"
        string drug_class "nullable, String(60)"
        string source_label "nullable, String(500)"
        string rule_id "nullable, String(60)"
        int rule_version "nullable"
        int medication_entry_id "nullable"
        json evidence_ids "not null"
        string content_hash "not null, String(64)"
        string status "not null, String(20)"
        int run_id FK "not null"
        datetime created_at "not null, DateTime(timezone=True)"
        datetime superseded_at "nullable, DateTime(timezone=True)"
    }
    medication_rules {
        int id PK "not null"
        string rule_id "not null, String(60)"
        int version "not null"
        string title "not null, String(300)"
        string drug_class "not null, String(60)"
        json procedure_tags "not null"
        text message "not null"
        text rationale "not null"
        text reference "not null"
        string status "not null, String(20)"
        string content_hash "not null, String(64)"
        string created_by "not null, String(200)"
        string created_by_id "not null, String(64)"
        datetime created_at "not null, DateTime(timezone=True)"
        string decided_by "nullable, String(200)"
        string decided_by_id "nullable, String(64)"
        datetime decided_at "nullable, DateTime(timezone=True)"
        text reference_checked "nullable"
        text decision_note "nullable"
    }
    medicine_names {
        int id PK "not null"
        string name UK "not null, String(120)"
        string display "not null, String(120)"
        string ingredient "not null, String(100)"
        string drug_class "not null, String(60)"
        string kind "not null, String(20)"
        string status "not null, String(20)"
        json options "nullable"
        string added_by "not null, String(200)"
        datetime created_at "not null, DateTime(timezone=True)"
    }
    ruleset_releases {
        int id PK "not null"
        string hash UK "not null, String(64)"
        text notes "not null"
        json counts "not null"
        datetime created_at "not null, DateTime(timezone=True)"
    }
    suggestion_reviews {
        int id PK "not null"
        int referral_id FK "not null"
        string pair_key "not null, String(210)"
        string decision "not null, String(20)"
        text note "not null"
        float score "not null"
        string model_version "not null, String(60)"
        string data_version "not null, String(200)"
        string reviewer "not null, String(200)"
        string reviewer_id "not null, String(64)"
        datetime created_at "not null, DateTime(timezone=True)"
    }
    ai_suggestions |o..o{ suggestion_reviews : "pair_key (logical)"
    evaluation_runs ||--o{ medication_flags : "run_id"
    evidence_items ||--o{ medication_entries : "evidence_id"
    ingredients |o..o{ drug_interactions : "ingredient_a (logical)"
    ingredients |o..o{ drug_interactions : "ingredient_b (logical)"
    ingredients |o..o{ label_rules : "ingredient (logical)"
    ingredients |o..o{ medication_entries : "ingredient (logical)"
    ingredients |o..o{ medicine_names : "ingredient (logical)"
    medication_entries |o..o{ medication_entries : "duplicate_of (logical)"
    medication_entries |o..o{ medication_flags : "medication_entry_id (logical)"
    medication_flags ||--o{ flag_reviews : "flag_id"
    medication_rules |o..o{ medication_flags : "rule_id (logical)"
    referrals ||--o{ evaluation_runs : "referral_id"
    referrals ||--o{ flag_reviews : "referral_id"
    referrals ||--o{ medication_entries : "referral_id"
    referrals ||--o{ medication_flags : "referral_id"
    referrals ||--o{ suggestion_reviews : "referral_id"
```

#### ERD: `referrals` domain (11 tables, `services/central/app/models/referrals.py`)

```mermaid
erDiagram
    briefs {
        int id PK "not null"
        int referral_id FK "not null"
        int version "not null"
        string kind "not null, String(20)"
        json sections "not null"
        json limitations "not null"
        json evidence_ids "not null"
        string created_by "not null, String(200)"
        datetime created_at "not null, DateTime(timezone=True)"
    }
    clarifications {
        int id PK "not null"
        int referral_id FK "not null"
        int provider_clarification_id "nullable"
        int package_version "nullable"
        text question "not null"
        string asked_by "not null, String(200)"
        datetime asked_at "not null, DateTime(timezone=True)"
        string status "not null, String(20)"
        text answer "nullable"
        string answered_by "nullable, String(200)"
        datetime answered_at "nullable, DateTime(timezone=True)"
    }
    consultation_responses {
        int id PK "not null"
        int referral_id FK "not null"
        string remote_key UK "not null, String(200)"
        int package_version "not null"
        json content "not null"
        string specialist_name "not null, String(200)"
        datetime returned_at "not null, DateTime(timezone=True)"
        datetime received_at "not null, DateTime(timezone=True)"
        string reviewed_by "nullable, String(200)"
        string reviewed_by_id "nullable, String(64)"
        datetime reviewed_at "nullable, DateTime(timezone=True)"
        text review_note "nullable"
        json fhir_task "nullable"
    }
    diagnostic_requests {
        int id PK "not null"
        string reference UK "not null, String(30)"
        int referral_id FK "not null"
        string category "not null, String(20)"
        string test "not null, String(200)"
        string body_area "nullable, String(100)"
        text clinical_question "not null"
        string urgency "not null, String(20)"
        string destination_institution "not null, String(50)"
        string destination_department "not null, String(60)"
        string status "not null, String(20)"
        string requested_by "not null, String(200)"
        string requested_by_id "not null, String(64)"
        string sent_by "nullable, String(200)"
        datetime sent_at "nullable, DateTime(timezone=True)"
        text reject_reason "nullable"
        datetime scheduled_for "nullable, DateTime(timezone=True)"
        json report "nullable"
        json attachments "not null"
        string local_patient_id "nullable, String(50)"
        string seen_by "nullable, String(200)"
        datetime seen_at "nullable, DateTime(timezone=True)"
        json history "not null"
        datetime created_at "not null, DateTime(timezone=True)"
        datetime updated_at "not null, DateTime(timezone=True)"
    }
    followup_tasks {
        int id PK "not null"
        int referral_id FK "not null"
        text description "not null"
        string specified_by "not null, String(200)"
        string assignee_name "nullable, String(200)"
        date due_date "nullable"
        string status "not null, String(20)"
        text outcome "nullable"
        string completed_by "nullable, String(200)"
        datetime completed_at "nullable, DateTime(timezone=True)"
        string created_by "not null, String(200)"
        datetime created_at "not null, DateTime(timezone=True)"
    }
    inbound_messages {
        int id PK "not null"
        string message_key UK "not null, String(200)"
        string message_type "not null, String(40)"
        int referral_id FK "nullable"
        json payload "not null"
        datetime received_at "not null, DateTime(timezone=True)"
    }
    notifications {
        int id PK "not null"
        string recipient_id "nullable, String(64)"
        string institution_id "not null, String(50)"
        string role "nullable, String(40)"
        int referral_id FK "nullable"
        string kind "not null, String(40)"
        string title "not null, String(300)"
        text body "not null"
        string link "nullable, String(200)"
        datetime created_at "not null, DateTime(timezone=True)"
        datetime read_at "nullable, DateTime(timezone=True)"
        string read_by "nullable, String(200)"
    }
    outbox {
        int id PK "not null"
        int referral_id FK "not null"
        string kind "not null, String(40)"
        string target_institution "not null, String(50)"
        string message_key UK "not null, String(200)"
        json payload "not null"
        string status "not null, String(20)"
        int attempts "not null"
        text last_error "nullable"
        datetime next_attempt_at "not null, DateTime(timezone=True)"
        datetime created_at "not null, DateTime(timezone=True)"
        datetime sent_at "nullable, DateTime(timezone=True)"
        json remote_result "nullable"
    }
    referral_events {
        int id PK "not null"
        int referral_id FK "not null"
        string event_type "not null, String(50)"
        string from_status "nullable, String(30)"
        string to_status "nullable, String(30)"
        string actor "not null, String(200)"
        string institution_id "nullable, String(50)"
        json detail "not null"
        datetime created_at "not null, DateTime(timezone=True)"
    }
    referral_packages {
        int id PK "not null"
        int referral_id FK "not null"
        int version "not null"
        int brief_id FK "not null"
        json envelope "not null"
        string content_hash "not null, String(64)"
        string delivery_key UK "not null, String(200)"
        string sent_by "not null, String(200)"
        string sent_by_id "not null, String(64)"
        datetime sent_at "not null, DateTime(timezone=True)"
        bool superseded "not null"
        json manifest "nullable"
        datetime content_purged_at "nullable, DateTime(timezone=True)"
    }
    referrals {
        int id PK "not null"
        string reference UK "not null, String(30)"
        string patient_institution "not null, String(50)"
        string patient_local_id "not null, String(50)"
        string patient_name "not null, String(200)"
        string patient_birth_date "nullable, String(20)"
        string patient_sex "nullable, String(10)"
        string patient_cnic "nullable, String(15)"
        string source_institution "not null, String(50)"
        string source_department "nullable, String(60)"
        string requesting_doctor_id "nullable, String(64)"
        string requesting_doctor_name "not null, String(200)"
        string created_by_id "not null, String(64)"
        string created_by_name "not null, String(200)"
        string kind "not null, String(20)"
        string destination_institution "nullable, String(50)"
        string destination_department "nullable, String(60)"
        string destination_doctor "nullable, String(200)"
        text reason "not null"
        text consultation_notes "not null"
        string urgency "not null, String(20)"
        string procedure_status "not null, String(20)"
        string planned_procedure "nullable, String(300)"
        json procedure_tags "not null"
        string status "not null, String(30)"
        int row_version "not null"
        datetime requested_at "nullable, DateTime(timezone=True)"
        string prepared_by "nullable, String(200)"
        datetime prepared_at "nullable, DateTime(timezone=True)"
        string packet_reviewed_by "nullable, String(200)"
        datetime packet_reviewed_at "nullable, DateTime(timezone=True)"
        bool amendment_open "not null"
        int current_package_version "nullable"
        int submitted_package_version "nullable"
        string delivery_status "not null, String(20)"
        string meds_checked_by "nullable, String(200)"
        datetime meds_checked_at "nullable, DateTime(timezone=True)"
        text meds_checked_note "nullable"
        string patient_informed_by "nullable, String(200)"
        datetime patient_informed_at "nullable, DateTime(timezone=True)"
        text patient_informed_note "nullable"
        text cancel_reason "nullable"
        text decline_reason "nullable"
        datetime closed_at "nullable, DateTime(timezone=True)"
        string closed_by "nullable, String(200)"
        datetime acknowledged_at "nullable, DateTime(timezone=True)"
        datetime accepted_at "nullable, DateTime(timezone=True)"
        datetime working_set_expires_at "nullable, DateTime(timezone=True)"
        datetime working_set_purged_at "nullable, DateTime(timezone=True)"
        datetime receiver_completed_at "nullable, DateTime(timezone=True)"
        string receiver_completed_by "nullable, String(200)"
        datetime created_at "not null, DateTime(timezone=True)"
        datetime updated_at "not null, DateTime(timezone=True)"
    }
    briefs ||--o{ referral_packages : "brief_id"
    referrals |o--o{ inbound_messages : "referral_id"
    referrals |o--o{ jobs : "referral_id"
    referrals |o--o{ notifications : "referral_id"
    referrals |o--o{ patient_links : "referral_id"
    referrals ||--o{ briefs : "referral_id"
    referrals ||--o{ clarifications : "referral_id"
    referrals ||--o{ consultation_responses : "referral_id"
    referrals ||--o{ diagnostic_requests : "referral_id"
    referrals ||--o{ documents : "referral_id"
    referrals ||--o{ evaluation_runs : "referral_id"
    referrals ||--o{ evidence_items : "referral_id"
    referrals ||--o{ flag_reviews : "referral_id"
    referrals ||--o{ followup_tasks : "referral_id"
    referrals ||--o{ medication_entries : "referral_id"
    referrals ||--o{ medication_flags : "referral_id"
    referrals ||--o{ outbox : "referral_id"
    referrals ||--o{ referral_events : "referral_id"
    referrals ||--o{ referral_packages : "referral_id"
    referrals ||--o{ selection_runs : "referral_id"
    referrals ||--o{ source_retrievals : "referral_id"
    referrals ||--o{ suggestion_reviews : "referral_id"
    users |o..o{ notifications : "recipient_id (logical)"
    users |o..o{ referrals : "requesting_doctor_id (logical)"
```


# Appendix B. ERD: institution service

_Generated from the code by `scripts/sds/build_sds.py`. Do not edit by hand._

### Institution service database (one per institution: `drali_db`, `chughtai_db`, `ziauddin_db`, `akuh_db`)

Generated from the SQLAlchemy models. Solid lines are database foreign keys; dotted lines are logical references held as plain columns (no constraint). PK primary key, FK foreign key, UK unique.

#### Overview: all 18 tables and their relationships

```mermaid
erDiagram
    access_grants {
        int id PK "not null"
    }
    audit_events {
        int id PK "not null"
    }
    cases {
        int id PK "not null"
    }
    conditions {
        string id PK "not null, String(40)"
    }
    consultation_responses {
        int id PK "not null"
    }
    forwarded_results {
        int id PK "not null"
    }
    imaging_reports {
        string id PK "not null, String(40)"
    }
    incoming_packages {
        int id PK "not null"
    }
    info_requests {
        int id PK "not null"
    }
    lab_results {
        string id PK "not null, String(40)"
    }
    medications {
        string id PK "not null, String(40)"
    }
    order_attachments {
        int id PK "not null"
    }
    orders {
        int id PK "not null"
    }
    outbox {
        int id PK "not null"
    }
    patients {
        string local_id PK "not null, String(30)"
    }
    sent_copies {
        int id PK "not null"
    }
    surgeries {
        string id PK "not null, String(40)"
    }
    visits {
        string id PK "not null, String(40)"
    }
    cases |o--o{ outbox : "case_id"
    cases ||--o{ consultation_responses : "case_id"
    cases ||--o{ forwarded_results : "case_id"
    cases ||--o{ incoming_packages : "case_id"
    cases ||--o{ info_requests : "case_id"
    orders |o--o{ outbox : "order_id"
    orders ||--o{ order_attachments : "order_id"
    patients |o..o{ access_grants : "local_patient_id (logical)"
    patients |o..o{ cases : "local_patient_id (logical)"
    patients |o..o{ orders : "local_patient_id (logical)"
    patients ||--o{ conditions : "patient_id"
    patients ||--o{ imaging_reports : "patient_id"
    patients ||--o{ lab_results : "patient_id"
    patients ||--o{ medications : "patient_id"
    patients ||--o{ surgeries : "patient_id"
    patients ||--o{ visits : "patient_id"
```

#### ERD with all columns

```mermaid
erDiagram
    access_grants {
        int id PK "not null"
        string grantee_institution "not null, String(50)"
        string local_patient_id "not null, String(50)"
        json categories "not null"
        string status "not null, String(20)"
        text basis "not null"
        string granted_by "not null, String(200)"
        datetime created_at "not null, DateTime(timezone=True)"
        string revoked_by "nullable, String(200)"
        datetime revoked_at "nullable, DateTime(timezone=True)"
        datetime expires_at "nullable, DateTime(timezone=True)"
        string referral_ref "nullable, String(60)"
    }
    audit_events {
        int id PK "not null"
        string actor_id "not null, String(100)"
        string actor_name "not null, String(200)"
        string institution_id "nullable, String(50)"
        string action "not null, String(100)"
        string target_type "not null, String(60)"
        string target_id "not null, String(100)"
        string outcome "not null, String(20)"
        string referral_context "nullable, String(60)"
        json detail "not null"
        datetime created_at "not null, DateTime(timezone=True)"
    }
    cases {
        int id PK "not null"
        string central_referral_id UK "not null, String(40)"
        string sender_institution "not null, String(50)"
        string sender_name "not null, String(200)"
        string department "not null, String(60)"
        string requested_doctor "nullable, String(200)"
        string patient_name "not null, String(200)"
        string patient_birth_date "nullable, String(20)"
        string patient_sex "nullable, String(10)"
        string patient_cnic "nullable, String(15)"
        string local_patient_id "nullable, String(30)"
        int link_request_id "nullable"
        string urgency "not null, String(20)"
        string status "not null, String(30)"
        int latest_version "not null"
        string assigned_doctor "nullable, String(200)"
        string assigned_by "nullable, String(200)"
        datetime assigned_at "nullable, DateTime(timezone=True)"
        text assign_note "nullable"
        string acknowledged_by "nullable, String(200)"
        datetime acknowledged_at "nullable, DateTime(timezone=True)"
        string decision "nullable, String(20)"
        string decision_by "nullable, String(200)"
        datetime decision_at "nullable, DateTime(timezone=True)"
        text decline_reason "nullable"
        string completed_by "nullable, String(200)"
        datetime completed_at "nullable, DateTime(timezone=True)"
        datetime hold_until "nullable, DateTime(timezone=True)"
        datetime shared_removed_at "nullable, DateTime(timezone=True)"
        datetime received_at "not null, DateTime(timezone=True)"
        datetime updated_at "not null, DateTime(timezone=True)"
    }
    conditions {
        string id PK "not null, String(40)"
        string patient_id FK "not null"
        string display "not null, String(300)"
        string snomed "nullable, String(30)"
        string clinical_status "not null, String(20)"
        string onset "nullable, String(10)"
        int version "not null"
        datetime updated_at "not null, DateTime(timezone=True)"
    }
    consultation_responses {
        int id PK "not null"
        int case_id FK "not null"
        int package_version "not null"
        json content "not null"
        string status "not null, String(20)"
        string drafted_by "not null, String(200)"
        datetime drafted_at "not null, DateTime(timezone=True)"
        int row_version "not null"
        string returned_by "nullable, String(200)"
        string returned_by_id "nullable, String(100)"
        datetime returned_at "nullable, DateTime(timezone=True)"
        string return_key UK "nullable, String(200)"
    }
    forwarded_results {
        int id PK "not null"
        string forward_key UK "not null, String(200)"
        int case_id FK "not null"
        json content "not null"
        datetime received_at "not null, DateTime(timezone=True)"
    }
    imaging_reports {
        string id PK "not null, String(40)"
        string patient_id FK "not null"
        date study_date "not null"
        string study "not null, String(200)"
        string body_part "nullable, String(100)"
        text findings "not null"
        text impression "not null"
        string reporter "nullable, String(200)"
        int version "not null"
        datetime updated_at "not null, DateTime(timezone=True)"
    }
    incoming_packages {
        int id PK "not null"
        int case_id FK "not null"
        int version "not null"
        string delivery_key UK "not null, String(200)"
        json envelope "not null"
        string content_hash "not null, String(64)"
        datetime received_at "not null, DateTime(timezone=True)"
    }
    info_requests {
        int id PK "not null"
        int case_id FK "not null"
        int package_version "not null"
        text question "not null"
        string status "not null, String(20)"
        string created_by "not null, String(200)"
        datetime created_at "not null, DateTime(timezone=True)"
        text answer "nullable"
        string answered_by "nullable, String(200)"
        datetime answered_at "nullable, DateTime(timezone=True)"
        string answer_key UK "nullable, String(200)"
    }
    lab_results {
        string id PK "not null, String(40)"
        string patient_id FK "not null"
        string panel "not null, String(200)"
        date collected "not null"
        string test "not null, String(120)"
        string loinc "nullable, String(20)"
        float value_num "nullable"
        string value_text "nullable, String(200)"
        string unit "nullable, String(40)"
        string reference_range "nullable, String(60)"
        string abnormal_flag "nullable, String(20)"
        string status "not null, String(20)"
        text note "nullable"
        int version "not null"
        datetime updated_at "not null, DateTime(timezone=True)"
    }
    medications {
        string id PK "not null, String(40)"
        string patient_id FK "not null"
        string name "not null, String(200)"
        string brand_as_written "nullable, String(100)"
        string dose "nullable, String(100)"
        string route "nullable, String(40)"
        string frequency "nullable, String(100)"
        date start_date "nullable"
        string status "not null, String(20)"
        string prescriber "nullable, String(200)"
        text note "nullable"
        int version "not null"
        datetime updated_at "not null, DateTime(timezone=True)"
    }
    order_attachments {
        int id PK "not null"
        int order_id FK "not null"
        string filename "not null, String(200)"
        string content_type "not null, String(100)"
        bytes data "not null"
        string uploaded_by "not null, String(200)"
        datetime created_at "not null, DateTime(timezone=True)"
    }
    orders {
        int id PK "not null"
        string order_key UK "not null, String(200)"
        string order_ref "not null, String(40)"
        string central_referral_id "not null, String(40)"
        string sender_institution "not null, String(50)"
        string sender_name "not null, String(200)"
        string department "not null, String(60)"
        string category "not null, String(20)"
        string test "not null, String(200)"
        string body_area "nullable, String(100)"
        text clinical_question "not null"
        string urgency "not null, String(20)"
        string patient_name "not null, String(200)"
        string patient_birth_date "nullable, String(20)"
        string patient_sex "nullable, String(10)"
        string patient_cnic "nullable, String(15)"
        string local_patient_id "nullable, String(30)"
        int link_request_id "nullable"
        string requested_by "not null, String(200)"
        string status "not null, String(20)"
        text reject_reason "nullable"
        datetime scheduled_for "nullable, DateTime(timezone=True)"
        text report_text "nullable"
        text findings "nullable"
        text impression "nullable"
        json values "not null"
        string reported_by "nullable, String(200)"
        datetime reported_at "nullable, DateTime(timezone=True)"
        json history "not null"
        datetime received_at "not null, DateTime(timezone=True)"
        datetime updated_at "not null, DateTime(timezone=True)"
    }
    outbox {
        int id PK "not null"
        string event_key UK "not null, String(200)"
        string event_type "not null, String(40)"
        int case_id FK "nullable"
        int order_id FK "nullable"
        json payload "not null"
        string status "not null, String(20)"
        int attempts "not null"
        text last_error "nullable"
        datetime next_attempt_at "not null, DateTime(timezone=True)"
        datetime created_at "not null, DateTime(timezone=True)"
        datetime sent_at "nullable, DateTime(timezone=True)"
    }
    patients {
        string local_id PK "not null, String(30)"
        string cnic "nullable, String(15)"
        string given "not null, String(100)"
        string family "not null, String(100)"
        date birth_date "not null"
        string sex "not null, String(10)"
        string phone "nullable, String(30)"
        string city "nullable, String(60)"
        string registered_by "nullable, String(200)"
        bool synthetic "not null"
        int version "not null"
        datetime updated_at "not null, DateTime(timezone=True)"
    }
    sent_copies {
        int id PK "not null"
        string copy_key UK "not null, String(220)"
        string central_referral_id "not null, String(40)"
        string kind "not null, String(20)"
        int version "not null"
        json content "not null"
        datetime received_at "not null, DateTime(timezone=True)"
    }
    surgeries {
        string id PK "not null, String(40)"
        string patient_id FK "not null"
        string procedure "not null, String(300)"
        string performed "nullable, String(10)"
        string location "nullable, String(200)"
        int version "not null"
        datetime updated_at "not null, DateTime(timezone=True)"
    }
    visits {
        string id PK "not null, String(40)"
        string patient_id FK "not null"
        date visit_date "not null"
        string setting "not null, String(200)"
        string clinician "nullable, String(200)"
        text reason "not null"
        text summary "not null"
        int version "not null"
        datetime updated_at "not null, DateTime(timezone=True)"
    }
    cases |o--o{ outbox : "case_id"
    cases ||--o{ consultation_responses : "case_id"
    cases ||--o{ forwarded_results : "case_id"
    cases ||--o{ incoming_packages : "case_id"
    cases ||--o{ info_requests : "case_id"
    orders |o--o{ outbox : "order_id"
    orders ||--o{ order_attachments : "order_id"
    patients |o..o{ access_grants : "local_patient_id (logical)"
    patients |o..o{ cases : "local_patient_id (logical)"
    patients |o..o{ orders : "local_patient_id (logical)"
    patients ||--o{ conditions : "patient_id"
    patients ||--o{ imaging_reports : "patient_id"
    patients ||--o{ lab_results : "patient_id"
    patients ||--o{ medications : "patient_id"
    patients ||--o{ surgeries : "patient_id"
    patients ||--o{ visits : "patient_id"
```


# Appendix C. References across system boundaries

_Generated from the code by `scripts/sds/build_sds.py`. Do not edit by hand._

### References across system boundaries

These identifiers point into another service's database. They are never joined: each service owns its database, and the values travel only in authenticated API calls (AGENTS.md invariant 1).

| Held in | Column | Points to | Target | How it is set |
|---|---|---|---|---|
| institution | `cases.central_referral_id` | central | `referrals.reference` | set from the package envelope |
| institution | `cases.link_request_id` | central | `patient_links.id` | intake link request for the arriving patient |
| institution | `orders.central_referral_id` | central | `referrals.reference` | set from the diagnostic order |
| institution | `orders.order_ref` | central | `diagnostic_requests.reference` | the order reference |
| institution | `orders.link_request_id` | central | `patient_links.id` | intake link request |
| institution | `sent_copies.central_referral_id` | central | `referrals.reference` | the sender's own copy |
| institution | `access_grants.referral_ref` | central | `referrals.reference` | grant opened for a referral |
| central | `referrals.patient_local_id` | institution | `patients.local_id` | the referring institution's record |
| central | `patient_links.requester_local_id / target_local_id` | institution | `patients.local_id` | confirmed by the target institution's staff |
| central | `evidence_items.source_record_id + version` | institution | `conditions / visits / medications / lab_results / imaging_reports .id` | FHIR resource id and version |
| central | `users.id` | keycloak | `user subject (sub)` | Keycloak is the account authority |


# Appendix D. Data dictionary: central platform

_Generated from the code by `scripts/sds/build_sds.py`. Do not edit by hand._

### Data dictionary: Central platform database (`central_db`)

#### `audit_events` (AuditEvent, `services/central/app/models/audit.py`)

FR-59/FR-60: actor, institution, action, affected record, timestamp, outcome.

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `actor_id` | String(64) | no |  |  |  |
| `actor_name` | String(200) | no |  |  |  |
| `institution_id` | String(50) | yes | indexed |  |  |
| `action` | String(80) | no | indexed |  |  |
| `target_type` | String(60) | no |  |  |  |
| `target_id` | String(100) | no |  |  |  |
| `referral_id` | Integer | yes | indexed |  |  |
| `outcome` | String(20) | no |  |  |  |
| `detail` | JSON | no |  | `dict` |  |
| `created_at` | DateTime(timezone=True) | no | indexed | `utcnow` |  |

#### `documents` (Document, `services/central/app/models/evidence.py`)

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `referral_id` | Integer | no | FK → referrals.id, indexed |  |  |
| `patient_institution` | String(50) | no |  |  |  |
| `patient_local_id` | String(50) | no |  |  |  |
| `uploaded_by` | String(200) | no |  |  |  |
| `uploaded_by_id` | String(64) | no |  |  |  |
| `original_filename` | String(255) | no |  |  |  |
| `declared_type` | String(100) | no |  |  |  |
| `detected_type` | String(100) | no |  |  |  |
| `size_bytes` | Integer | no |  |  |  |
| `sha256` | String(64) | no |  |  |  |
| `storage_key` | String(200) | no |  |  |  |
| `doc_type` | String(40) | no |  |  |  |
| `page_count` | Integer | no |  | `0` |  |
| `status` | String(20) | no |  | `'uploaded'` | uploaded \| queued \| processing \| extracted \| failed |
| `error` | Text | yes |  |  |  |
| `created_at` | DateTime(timezone=True) | no |  | `utcnow` |  |
| `deleted_at` | DateTime(timezone=True) | yes |  |  |  |

#### `evidence_items` (EvidenceItem, `services/central/app/models/evidence.py`)

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `referral_id` | Integer | no | FK → referrals.id, indexed |  |  |
| `patient_institution` | String(50) | no |  |  |  |
| `patient_local_id` | String(50) | no |  |  |  |
| `origin` | String(20) | no |  |  | source \| document \| manual |
| `source_institution` | String(50) | no |  |  |  |
| `source_record_type` | String(40) | yes |  |  |  |
| `source_record_id` | String(80) | yes |  |  |  |
| `source_record_version` | String(20) | yes |  |  |  |
| `link_id` | Integer | yes |  |  |  |
| `category` | String(30) | no | indexed |  |  |
| `display` | Text | no |  |  |  |
| `original` | JSON | no |  | `dict` |  |
| `current` | JSON | no |  | `dict` |  |
| `fhir` | JSON | yes |  |  |  |
| `clinical_time` | DateTime(timezone=True) | yes |  |  |  |
| `retrieved_at` | DateTime(timezone=True) | no |  | `utcnow` |  |
| `document_id` | Integer | yes | FK → documents.id |  |  |
| `page` | Integer | yes |  |  |  |
| `region` | JSON | yes |  |  |  |
| `source_text` | Text | yes |  |  |  |
| `confidence` | JSON | yes |  |  |  |
| `review_state` | String(20) | no |  |  | imported \| proposed \| corrected \| unresolved \| excluded \| manual |
| `verification_status` | String(20) | no |  |  | source_record \| unverified \| verified \| invalidated |
| `verified_by` | String(200) | yes |  |  |  |
| `verified_at` | DateTime(timezone=True) | yes |  |  |  |
| `selected` | Boolean | no |  | `False` |  |
| `in_default` | Boolean | no |  | `False` | packet selection (spec v3 B): rule-based default, AI recommendation, staff decision |
| `selection_source` | String(10) | yes |  |  | default \| ai \| staff |
| `selected_by` | String(200) | yes |  |  |  |
| `selected_at` | DateTime(timezone=True) | yes |  |  |  |
| `ai_recommendation` | String(10) | yes |  |  | include \| exclude \| optional |
| `ai_relevance` | String(10) | yes |  |  | high \| medium \| low |
| `ai_reason` | Text | yes |  |  |  |
| `ai_run_id` | Integer | yes |  |  |  |
| `superseded_by` | Integer | yes |  |  |  |
| `author` | String(200) | yes |  |  |  |
| `row_version` | Integer | no |  | `1` |  |
| `created_at` | DateTime(timezone=True) | no |  | `utcnow` |  |
| `updated_at` | DateTime(timezone=True) | no |  | `utcnow` |  |

Unique constraints: (referral_id, source_institution, source_record_type, source_record_id, source_record_version) `uq_evidence_source_version`

#### `evidence_revisions` (EvidenceRevision, `services/central/app/models/evidence.py`)

Append-only history; raw extraction is never overwritten (FR-28).

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `evidence_id` | Integer | no | FK → evidence_items.id, indexed |  |  |
| `action` | String(30) | no |  |  |  |
| `prior_value` | JSON | yes |  |  |  |
| `new_value` | JSON | yes |  |  |  |
| `prior_state` | String(20) | yes |  |  |  |
| `new_state` | String(20) | yes |  |  |  |
| `editor` | String(200) | no |  |  |  |
| `editor_id` | String(64) | no |  |  |  |
| `note` | Text | no |  | `''` |  |
| `created_at` | DateTime(timezone=True) | no |  | `utcnow` |  |

#### `extraction_runs` (ExtractionRun, `services/central/app/models/evidence.py`)

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `document_id` | Integer | no | FK → documents.id, indexed |  |  |
| `job_id` | String(40) | yes |  |  |  |
| `text_source` | String(20) | yes |  |  | embedded \| ocr \| mixed |
| `ocr_engine` | String(60) | yes |  |  |  |
| `ocr_engine_version` | String(40) | yes |  |  |  |
| `extractor` | String(80) | yes |  |  |  |
| `extractor_version` | String(40) | yes |  |  |  |
| `raw_text` | Text | no |  | `''` |  |
| `pages` | JSON | no |  | `list` |  |
| `status` | String(20) | no |  | `'running'` |  |
| `error` | Text | yes |  |  |  |
| `notes` | JSON | no |  | `list` |  |
| `duration_ms` | Integer | no |  | `0` |  |
| `created_at` | DateTime(timezone=True) | no |  | `utcnow` |  |

#### `jobs` (Job, `services/central/app/models/evidence.py`)

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | String(40) | no | PK |  |  |
| `kind` | String(40) | no |  |  |  |
| `status` | String(20) | no |  | `'queued'` | queued \| running \| completed \| failed |
| `referral_id` | Integer | yes | FK → referrals.id, indexed |  |  |
| `document_id` | Integer | yes | FK → documents.id |  |  |
| `params` | JSON | no |  | `dict` |  |
| `result` | JSON | yes |  |  |  |
| `error` | Text | yes |  |  |  |
| `attempts` | Integer | no |  | `0` |  |
| `created_by` | String(200) | no |  |  |  |
| `created_by_id` | String(64) | no |  |  |  |
| `institution_id` | String(50) | yes |  |  |  |
| `created_at` | DateTime(timezone=True) | no |  | `utcnow` |  |
| `started_at` | DateTime(timezone=True) | yes |  |  |  |
| `finished_at` | DateTime(timezone=True) | yes |  |  |  |

#### `selection_runs` (SelectionRun, `services/central/app/models/evidence.py`)

One AI packet-selection attempt: which model and prompt, and whether its answer was used.

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `referral_id` | Integer | no | FK → referrals.id, indexed |  |  |
| `status` | String(20) | no |  |  | completed \| unavailable (no model / API error) \| rejected (answer failed checks) \| nothing_to_review \| discarded (the working set was removed before the answer arrived) |
| `provider` | String(40) | yes |  |  |  |
| `model` | String(80) | yes |  |  |  |
| `prompt_version` | String(40) | no |  |  |  |
| `prompt_hash` | String(64) | no |  |  |  |
| `item_count` | Integer | no |  | `0` |  |
| `truncated` | Boolean | no |  | `False` |  |
| `missing` | JSON | no |  | `list` |  |
| `error` | Text | yes |  |  |  |
| `created_by` | String(200) | no |  |  |  |
| `created_at` | DateTime(timezone=True) | no |  | `utcnow` |  |

#### `source_retrievals` (SourceRetrieval, `services/central/app/models/evidence.py`)

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `referral_id` | Integer | no | FK → referrals.id, indexed |  |  |
| `source_institution` | String(50) | no |  |  |  |
| `local_patient_id` | String(50) | no |  |  |  |
| `link_id` | Integer | yes |  |  |  |
| `institution_kind` | String(20) | yes |  |  |  |
| `last_activity` | String(20) | yes |  |  |  |
| `window_start` | String(20) | yes |  |  |  |
| `status` | String(20) | no |  |  | successful \| empty \| partial \| denied \| unavailable \| invalid \| skipped (not the most recent of its kind) |
| `record_count` | Integer | no |  | `0` |  |
| `new_count` | Integer | no |  | `0` |  |
| `duplicate_count` | Integer | no |  | `0` |  |
| `invalid_count` | Integer | no |  | `0` |  |
| `withheld` | JSON | no |  | `list` |  |
| `message` | Text | no |  | `''` |  |
| `retryable` | Boolean | no |  | `False` |  |
| `attempts` | Integer | no |  | `1` |  |
| `duration_ms` | Integer | no |  | `0` |  |
| `requested_by` | String(200) | no |  |  |  |
| `requested_at` | DateTime(timezone=True) | no |  | `utcnow` |  |

#### `patient_link_events` (PatientLinkEvent, `services/central/app/models/identity.py`)

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `link_id` | Integer | no | FK → patient_links.id, indexed |  |  |
| `action` | String(30) | no |  |  |  |
| `actor` | String(200) | no |  |  |  |
| `actor_id` | String(64) | no |  |  |  |
| `institution_id` | String(50) | yes |  |  |  |
| `note` | Text | no |  | `''` |  |
| `detail` | JSON | no |  | `dict` |  |
| `created_at` | DateTime(timezone=True) | no |  | `utcnow` |  |

#### `patient_links` (PatientLink, `services/central/app/models/identity.py`)

A request from one institution to another to confirm which of the other's patient records is the same person. It becomes verified only when staff at the OTHER institution check it and approve it. Records are never linked on matching IDs or names.

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `requester_institution` | String(50) | no | indexed |  |  |
| `requester_local_id` | String(50) | no | indexed |  |  |
| `target_institution` | String(50) | no | indexed |  |  |
| `target_local_id` | String(50) | yes | indexed |  |  |
| `patient_name` | String(200) | no |  |  | Identity details sent with the request (from the requester's own record) |
| `patient_birth_date` | String(20) | yes |  |  |  |
| `patient_sex` | String(10) | yes |  |  |  |
| `patient_cnic` | String(15) | yes |  |  |  |
| `referral_id` | Integer | yes | FK → referrals.id |  |  |
| `purpose` | Text | no |  | `''` |  |
| `kind` | String(20) | no |  | `'records'` | records = asking a place the patient visited for their records (it matches a record or says it has none); intake = sent with a referral or test order, so the receiver matches the patient or registers them as new |
| `status` | String(20) | no | indexed | `'requested'` | requested \| verified \| rejected \| invalidated |
| `status_key` | String(40) | no |  | `'current'` | lets a rejected/invalidated pair be requested again without violating uniqueness |
| `requested_by` | String(200) | no |  |  |  |
| `requested_by_id` | String(64) | no |  |  |  |
| `requested_at` | DateTime(timezone=True) | no |  | `utcnow` |  |
| `decided_by` | String(200) | yes |  |  |  |
| `decided_by_id` | String(64) | yes |  |  |  |
| `decided_at` | DateTime(timezone=True) | yes |  |  |  |
| `decision_note` | Text | yes |  |  |  |
| `match_check` | JSON | yes |  |  |  |
| `registered_new` | Boolean | no |  | `False` |  |
| `invalidated_by` | String(200) | yes |  |  |  |
| `invalidated_at` | DateTime(timezone=True) | yes |  |  |  |
| `invalidation_reason` | Text | yes |  |  |  |

Unique constraints: (requester_institution, requester_local_id, target_institution, status_key)

#### `users` (User, `services/central/app/models/identity.py`)

Central reference to a Keycloak account. account_status is checked on every request.

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | String(64) | no | PK |  | Keycloak subject |
| `username` | String(100) | no | indexed |  |  |
| `display_name` | String(200) | no |  |  |  |
| `institution_id` | String(50) | yes | indexed |  |  |
| `department` | String(60) | yes |  |  |  |
| `roles` | JSON | no |  | `list` |  |
| `account_status` | String(20) | no |  | `'active'` |  |
| `status_changed_by` | String(200) | yes |  |  |  |
| `status_changed_at` | DateTime(timezone=True) | yes |  |  |  |
| `last_seen_at` | DateTime(timezone=True) | no |  | `utcnow` |  |

#### `ai_suggestions` (AiSuggestion, `services/central/app/models/medications.py`)

A possible clash between two ingredients that have no entry in the interaction source, scored offline by a small model. A suggestion is never a flag: it cannot add, remove or change a flag, never blocks sending and is not included in the sent referral.

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `pair_key` | String(210) | no | PK |  | "a\|b" with a < b |
| `ingredient_a` | String(100) | no | indexed |  |  |
| `ingredient_b` | String(100) | no | indexed |  |  |
| `score` | Float | no |  |  |  |
| `reason` | Text | no |  |  |  |
| `model_version` | String(60) | no |  |  |  |
| `data_version` | String(200) | no |  |  |  |

#### `drug_interactions` (DrugInteraction, `services/central/app/models/medications.py`)

A drug-drug interaction pair from an imported source (stored once, ingredient_a < ingredient_b). The severity is the source's own level, unchanged.

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `ingredient_a` | String(100) | no | indexed |  |  |
| `ingredient_b` | String(100) | no | indexed |  |  |
| `severity` | String(20) | no |  |  | Major \| Moderate \| Minor \| Unknown |
| `source` | String(40) | no |  |  | ddinter |
| `source_version` | String(80) | no |  |  |  |
| `source_ref` | String(80) | no |  |  |  |
| `label_quote` | Text | yes |  |  | Why, in the source's own words: a sentence quoted verbatim from a US drug label's interaction section that names the other ingredient (rules/labels/interaction-quotes.json). Empty when none exists. |
| `label_source` | String(200) | yes |  |  |  |
| `label_section` | String(60) | yes |  |  |  |

Unique constraints: (ingredient_a, ingredient_b, source)

#### `evaluation_runs` (EvaluationRun, `services/central/app/models/medications.py`)

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `referral_id` | Integer | no | FK → referrals.id, indexed |  |  |
| `trigger` | String(160) | no |  |  |  |
| `status` | String(20) | no |  |  | completed \| failed |
| `outcome` | String(30) | yes |  |  | flags \| no_match \| no_rules |
| `summary_message` | Text | yes |  |  |  |
| `context` | JSON | no |  | `dict` |  |
| `rule_versions` | JSON | no |  | `dict` |  |
| `input_hash` | String(64) | no |  |  |  |
| `ruleset_hash` | String(64) | yes |  |  |  |
| `error` | Text | yes |  |  |  |
| `changed_flags` | Integer | no |  | `0` |  |
| `triggered_by` | String(200) | no |  |  |  |
| `created_at` | DateTime(timezone=True) | no |  | `utcnow` |  |

#### `flag_reviews` (FlagReview, `services/central/app/models/medications.py`)

A doctor's decision on one flag version for this patient: reviewed, ignore (not relevant for this patient) or research (needs follow-up). Any decision means the flag has been seen; it is never treatment clearance. Ignored flags stay visible in the record.

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `referral_id` | Integer | no | FK → referrals.id, indexed |  |  |
| `flag_id` | Integer | no | FK → medication_flags.id, indexed |  |  |
| `flag_version` | Integer | no |  |  |  |
| `side` | String(20) | no |  | `'referring'` |  |
| `reviewer` | String(200) | no |  |  |  |
| `reviewer_id` | String(64) | no |  |  |  |
| `institution_id` | String(50) | no |  |  |  |
| `package_version` | Integer | yes |  |  |  |
| `decision` | String(20) | no |  | `'reviewed'` | reviewed \| ignore \| research |
| `ruleset_hash` | String(64) | yes |  |  |  |
| `note` | Text | no |  | `''` |  |
| `created_at` | DateTime(timezone=True) | no |  | `utcnow` |  |

#### `ingredients` (Ingredient, `services/central/app/models/medications.py`)

An ingredient as named in this project, with its international name (used by DDInter and drug labels), RxNorm and ATC codes, and the parts of a combination product.

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `name` | String(100) | no | PK |  |  |
| `standard` | String(100) | yes |  |  |  |
| `label_name` | String(100) | yes |  |  |  |
| `rxnorm_id` | String(20) | yes |  |  |  |
| `atc_codes` | JSON | no |  | `list` |  |
| `components` | JSON | no |  | `list` |  |
| `in_interaction_source` | Boolean | no |  | `False` |  |
| `note` | Text | yes |  |  |  |

#### `label_rules` (LabelRule, `services/central/app/models/medications.py`)

A drug-condition or drug-procedure rule read from a drug label by script, with the exact sentence it relies on. Imported rules are labelled automatically generated, not clinically reviewed.

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `rule_key` | String(200) | no | unique |  |  |
| `kind` | String(20) | no |  |  | drug_condition \| drug_procedure |
| `ingredient` | String(100) | no | indexed |  |  |
| `target` | String(60) | no |  |  |  |
| `target_label` | String(120) | no |  |  |  |
| `severity_hint` | String(20) | no |  |  | high \| moderate \| low (display only) |
| `summary` | Text | no |  |  |  |
| `quote` | Text | no |  |  |  |
| `section` | String(40) | no |  |  |  |
| `source_type` | String(40) | no |  | `'drug_label'` |  |
| `source_ref` | String(80) | no |  |  |  |
| `source_name` | String(200) | no |  |  |  |
| `source_version` | String(80) | no |  |  |  |
| `extractor_version` | String(40) | no |  |  |  |
| `status` | String(20) | no |  | `'auto_extracted'` | auto_extracted \| withdrawn |

#### `medication_entries` (MedicationEntry, `services/central/app/models/medications.py`)

One current medicine as recorded by one source. Entries for the same medicine and strength from different sources form a group shown once (duplicate_of points at the entry that represents the group).

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `referral_id` | Integer | no | FK → referrals.id, indexed |  |  |
| `evidence_id` | Integer | no | FK → evidence_items.id |  |  |
| `record_kind` | String(20) | no |  |  | prescription \| document \| manual |
| `original_name` | String(200) | no |  |  |  |
| `brand` | String(100) | yes |  |  |  |
| `strength` | String(60) | yes |  |  |  |
| `dose` | String(120) | yes |  |  |  |
| `route` | String(40) | yes |  |  |  |
| `frequency` | String(100) | yes |  |  |  |
| `start_date` | String(20) | yes |  |  |  |
| `over_the_counter` | Boolean | no |  | `False` |  |
| `source_label` | String(300) | no |  |  |  |
| `ingredient` | String(100) | yes |  |  |  |
| `ingredients` | JSON | no |  | `list` | every ingredient checked for this medicine (several for a combination product) |
| `drug_class` | String(60) | yes |  |  |  |
| `mapping_status` | String(20) | no |  |  | mapped \| ambiguous \| unmapped \| staff_mapped |
| `mapping_choices` | JSON | yes |  |  | ambiguous DRAP brand: the products it could be, for staff or the doctor to pick from by company |
| `mapping_note` | Text | yes |  |  |  |
| `duplicate_of` | Integer | yes |  |  |  |
| `dose_differs` | Boolean | no |  | `False` |  |
| `excluded` | Boolean | no |  | `False` |  |
| `excluded_by` | String(200) | yes |  |  |  |
| `excluded_reason` | Text | yes |  |  |  |
| `created_at` | DateTime(timezone=True) | no |  | `utcnow` |  |
| `updated_at` | DateTime(timezone=True) | no |  | `utcnow` |  |

Unique constraints: (referral_id, evidence_id)

#### `medication_flags` (MedicationFlag, `services/central/app/models/medications.py`)

A flag version. A material change supersedes the row and creates version+1.

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `referral_id` | Integer | no | FK → referrals.id, indexed |  |  |
| `flag_key` | String(200) | no |  |  |  |
| `version` | Integer | no |  | `1` |  |
| `kind` | String(40) | no |  |  | confirmed (approved manual rule) \| interaction \| label_warning \| unrecognised_medicine \| interactions_not_checked \| procedure_not_checked \| records_incomplete |
| `severity` | String(20) | yes |  |  | the source's level, unchanged |
| `ingredients` | JSON | no |  | `list` |  |
| `source_type` | String(40) | yes |  |  | manual_rule \| ddinter \| drug_label |
| `source_name` | String(200) | yes |  |  |  |
| `source_ref` | Text | yes |  |  |  |
| `source_version` | String(80) | yes |  |  |  |
| `source_quote` | Text | yes |  |  |  |
| `auto_generated` | Boolean | no |  | `False` |  |
| `requires_decision` | Boolean | no |  | `True` | the doctor must record a decision before sending (approved rules, Major interactions, high label warnings, gaps) |
| `title` | String(300) | no |  |  |  |
| `message` | Text | no |  |  |  |
| `medication` | String(300) | yes |  |  |  |
| `drug_class` | String(60) | yes |  |  |  |
| `source_label` | String(500) | yes |  |  |  |
| `rule_id` | String(60) | yes |  |  |  |
| `rule_version` | Integer | yes |  |  |  |
| `medication_entry_id` | Integer | yes |  |  |  |
| `evidence_ids` | JSON | no |  | `list` |  |
| `content_hash` | String(64) | no |  |  |  |
| `status` | String(20) | no |  | `'active'` | active \| superseded \| withdrawn |
| `run_id` | Integer | no | FK → evaluation_runs.id |  |  |
| `created_at` | DateTime(timezone=True) | no |  | `utcnow` |  |
| `superseded_at` | DateTime(timezone=True) | yes |  |  |  |

Unique constraints: (referral_id, flag_key, version)

#### `medication_rules` (MedicationRule, `services/central/app/models/medications.py`)

One version of a drug-against-procedure rule. Edited in the app; a new or changed rule is a draft until a clinical reviewer approves that exact version.

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `rule_id` | String(60) | no | indexed |  |  |
| `version` | Integer | no |  |  |  |
| `title` | String(300) | no |  |  |  |
| `drug_class` | String(60) | no |  |  |  |
| `procedure_tags` | JSON | no |  | `list` |  |
| `message` | Text | no |  |  |  |
| `rationale` | Text | no |  | `''` |  |
| `reference` | Text | no |  | `''` |  |
| `status` | String(20) | no | indexed | `'draft'` | draft \| approved \| rejected \| retired \| superseded |
| `content_hash` | String(64) | no |  |  |  |
| `created_by` | String(200) | no |  |  |  |
| `created_by_id` | String(64) | no |  |  |  |
| `created_at` | DateTime(timezone=True) | no |  | `utcnow` |  |
| `decided_by` | String(200) | yes |  |  |  |
| `decided_by_id` | String(64) | yes |  |  |  |
| `decided_at` | DateTime(timezone=True) | yes |  |  |  |
| `reference_checked` | Text | yes |  |  |  |
| `decision_note` | Text | yes |  |  |  |

Unique constraints: (rule_id, version)

#### `medicine_names` (MedicineName, `services/central/app/models/medications.py`)

A medicine name (brand or generic, as written in Pakistan) mapped to its ingredient and drug class. Maintained in the app by clinical reviewers.

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `name` | String(120) | no | unique |  | normalised lowercase |
| `display` | String(120) | no |  |  |  |
| `ingredient` | String(100) | no |  |  |  |
| `drug_class` | String(60) | no |  |  |  |
| `kind` | String(20) | no |  | `'generic'` | generic \| brand \| register_brand \| register_ambiguous (DRAP) |
| `status` | String(20) | no |  | `'active'` | active \| retired |
| `options` | JSON | yes |  |  | register_ambiguous only: the products behind the name (ingredient, company, DRAP number, strength, form) |
| `added_by` | String(200) | no |  |  |  |
| `created_at` | DateTime(timezone=True) | no |  | `utcnow` |  |

#### `ruleset_releases` (RulesetRelease, `services/central/app/models/medications.py`)

The exact rule set in force: approved manual rules, label rules and interaction data, by hash.

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `hash` | String(64) | no | unique |  |  |
| `notes` | Text | no |  | `''` |  |
| `counts` | JSON | no |  | `dict` |  |
| `created_at` | DateTime(timezone=True) | no |  | `utcnow` |  |

#### `suggestion_reviews` (SuggestionReview, `services/central/app/models/medications.py`)

A doctor's decision on one AI suggestion for one patient: ignore or research (logged).

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `referral_id` | Integer | no | FK → referrals.id, indexed |  |  |
| `pair_key` | String(210) | no |  |  |  |
| `decision` | String(20) | no |  |  | ignore \| research |
| `note` | Text | no |  | `''` |  |
| `score` | Float | no |  |  |  |
| `model_version` | String(60) | no |  |  |  |
| `data_version` | String(200) | no |  |  |  |
| `reviewer` | String(200) | no |  |  |  |
| `reviewer_id` | String(64) | no |  |  |  |
| `created_at` | DateTime(timezone=True) | no |  | `utcnow` |  |

#### `briefs` (Brief, `services/central/app/models/referrals.py`)

The referral summary built from the verified records when a version is sent. Immutable.

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `referral_id` | Integer | no | FK → referrals.id, indexed |  |  |
| `version` | Integer | no |  |  |  |
| `kind` | String(20) | no |  | `'template'` |  |
| `sections` | JSON | no |  |  |  |
| `limitations` | JSON | no |  | `list` |  |
| `evidence_ids` | JSON | no |  | `list` |  |
| `created_by` | String(200) | no |  |  |  |
| `created_at` | DateTime(timezone=True) | no |  | `utcnow` |  |

Unique constraints: (referral_id, version)

#### `clarifications` (Clarification, `services/central/app/models/referrals.py`)

A request for more information from the receiving doctor, answered by the referring clinic.

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `referral_id` | Integer | no | FK → referrals.id, indexed |  |  |
| `provider_clarification_id` | Integer | yes |  |  |  |
| `package_version` | Integer | yes |  |  |  |
| `question` | Text | no |  |  |  |
| `asked_by` | String(200) | no |  |  |  |
| `asked_at` | DateTime(timezone=True) | no |  | `utcnow` |  |
| `status` | String(20) | no | indexed | `'open'` | open \| answered |
| `answer` | Text | yes |  |  |  |
| `answered_by` | String(200) | yes |  |  |  |
| `answered_at` | DateTime(timezone=True) | yes |  |  |  |

#### `consultation_responses` (ConsultationResponse, `services/central/app/models/referrals.py`)

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `referral_id` | Integer | no | FK → referrals.id, indexed |  |  |
| `remote_key` | String(200) | no | unique |  |  |
| `package_version` | Integer | no |  |  |  |
| `content` | JSON | no |  |  |  |
| `specialist_name` | String(200) | no |  |  |  |
| `returned_at` | DateTime(timezone=True) | no |  |  |  |
| `received_at` | DateTime(timezone=True) | no |  | `utcnow` |  |
| `reviewed_by` | String(200) | yes |  |  |  |
| `reviewed_by_id` | String(64) | yes |  |  |  |
| `reviewed_at` | DateTime(timezone=True) | yes |  |  |  |
| `review_note` | Text | yes |  |  |  |
| `fhir_task` | JSON | yes |  |  |  |

#### `diagnostic_requests` (DiagnosticRequest, `services/central/app/models/referrals.py`)

A test, scan or equipment request added to a referral. It is a separate order with its own status; it does not wait for the specialist's decision.

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `reference` | String(30) | no | unique |  |  |
| `referral_id` | Integer | no | FK → referrals.id, indexed |  |  |
| `category` | String(20) | no |  |  | laboratory \| imaging \| cardiac |
| `test` | String(200) | no |  |  |  |
| `body_area` | String(100) | yes |  |  |  |
| `clinical_question` | Text | no |  |  |  |
| `urgency` | String(20) | no |  | `'routine'` |  |
| `destination_institution` | String(50) | no | indexed |  |  |
| `destination_department` | String(60) | no |  |  |  |
| `status` | String(20) | no | indexed | `'draft'` | draft (in the referral, not sent yet) \| requested \| accepted \| rejected \| scheduled \| done \| reported \| cancelled |
| `requested_by` | String(200) | no |  |  |  |
| `requested_by_id` | String(64) | no |  |  |  |
| `sent_by` | String(200) | yes |  |  |  |
| `sent_at` | DateTime(timezone=True) | yes |  |  |  |
| `reject_reason` | Text | yes |  |  |  |
| `scheduled_for` | DateTime(timezone=True) | yes |  |  |  |
| `report` | JSON | yes |  |  |  |
| `attachments` | JSON | no |  | `list` | Images or report files returned with the result: [{"n", "filename", "content_type", "storage_key", "size"}] |
| `local_patient_id` | String(50) | yes |  |  | at the destination, once confirmed |
| `seen_by` | String(200) | yes |  |  |  |
| `seen_at` | DateTime(timezone=True) | yes |  |  |  |
| `history` | JSON | no |  | `list` |  |
| `created_at` | DateTime(timezone=True) | no |  | `utcnow` |  |
| `updated_at` | DateTime(timezone=True) | no |  | `utcnow` |  |

#### `followup_tasks` (FollowupTask, `services/central/app/models/referrals.py`)

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `referral_id` | Integer | no | FK → referrals.id, indexed |  |  |
| `description` | Text | no |  |  |  |
| `specified_by` | String(200) | no |  |  |  |
| `assignee_name` | String(200) | yes |  |  |  |
| `due_date` | Date | yes |  |  |  |
| `status` | String(20) | no |  | `'open'` | open \| completed \| not_completed |
| `outcome` | Text | yes |  |  |  |
| `completed_by` | String(200) | yes |  |  |  |
| `completed_at` | DateTime(timezone=True) | yes |  |  |  |
| `created_by` | String(200) | no |  |  |  |
| `created_at` | DateTime(timezone=True) | no |  | `utcnow` |  |

#### `inbound_messages` (InboundMessage, `services/central/app/models/referrals.py`)

Deduplicates incoming events from the institution services.

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `message_key` | String(200) | no | unique |  |  |
| `message_type` | String(40) | no |  |  |  |
| `referral_id` | Integer | yes | FK → referrals.id |  |  |
| `payload` | JSON | no |  |  |  |
| `received_at` | DateTime(timezone=True) | no |  | `utcnow` |  |

#### `notifications` (Notification, `services/central/app/models/referrals.py`)

Something a person should act on or know about. Either addressed to one user, or to a role at an institution (for example the referral desk staff).

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `recipient_id` | String(64) | yes | indexed |  |  |
| `institution_id` | String(50) | no | indexed |  |  |
| `role` | String(40) | yes |  |  |  |
| `referral_id` | Integer | yes | FK → referrals.id |  |  |
| `kind` | String(40) | no |  |  |  |
| `title` | String(300) | no |  |  |  |
| `body` | Text | no |  | `''` |  |
| `link` | String(200) | yes |  |  |  |
| `created_at` | DateTime(timezone=True) | no | indexed | `utcnow` |  |
| `read_at` | DateTime(timezone=True) | yes |  |  |  |
| `read_by` | String(200) | yes |  |  |  |

#### `outbox` (Outbox, `services/central/app/models/referrals.py`)

Written in the same transaction that decides to send; a worker delivers it.

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `referral_id` | Integer | no | FK → referrals.id, indexed |  |  |
| `kind` | String(40) | no |  |  | deliver_package \| deliver_order \| forward_result \| clarification_answer |
| `target_institution` | String(50) | no |  |  |  |
| `message_key` | String(200) | no | unique |  |  |
| `payload` | JSON | no |  |  |  |
| `status` | String(20) | no |  | `'pending'` | pending \| sent \| failed |
| `attempts` | Integer | no |  | `0` |  |
| `last_error` | Text | yes |  |  |  |
| `next_attempt_at` | DateTime(timezone=True) | no |  | `utcnow` |  |
| `created_at` | DateTime(timezone=True) | no |  | `utcnow` |  |
| `sent_at` | DateTime(timezone=True) | yes |  |  |  |
| `remote_result` | JSON | yes |  |  |  |

#### `referral_events` (ReferralEvent, `services/central/app/models/referrals.py`)

Ordered timeline: status changes, deliveries and receiving-side activity.

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `referral_id` | Integer | no | FK → referrals.id, indexed |  |  |
| `event_type` | String(50) | no |  |  |  |
| `from_status` | String(30) | yes |  |  |  |
| `to_status` | String(30) | yes |  |  |  |
| `actor` | String(200) | no |  |  |  |
| `institution_id` | String(50) | yes |  |  |  |
| `detail` | JSON | no |  | `dict` |  |
| `created_at` | DateTime(timezone=True) | no |  | `utcnow` |  |

#### `referral_packages` (ReferralPackage, `services/central/app/models/referrals.py`)

One sent version. Never updated after insert except the supersession marker.

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `referral_id` | Integer | no | FK → referrals.id, indexed |  |  |
| `version` | Integer | no |  |  |  |
| `brief_id` | Integer | no | FK → briefs.id |  |  |
| `envelope` | JSON | no |  |  |  |
| `content_hash` | String(64) | no |  |  |  |
| `delivery_key` | String(200) | no | unique |  |  |
| `sent_by` | String(200) | no |  |  |  |
| `sent_by_id` | String(64) | no |  |  |  |
| `sent_at` | DateTime(timezone=True) | no |  |  |  |
| `superseded` | Boolean | no |  | `False` |  |
| `manifest` | JSON | yes |  |  | Reference list of what the package contained (no clinical values); survives the content purge. |
| `content_purged_at` | DateTime(timezone=True) | yes |  |  |  |

Unique constraints: (referral_id, version)

#### `referrals` (Referral, `services/central/app/models/referrals.py`)

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `reference` | String(30) | no | unique |  |  |
| `patient_institution` | String(50) | no | indexed |  | The patient as recorded at the referring institution |
| `patient_local_id` | String(50) | no | indexed |  |  |
| `patient_name` | String(200) | no |  |  |  |
| `patient_birth_date` | String(20) | yes |  |  |  |
| `patient_sex` | String(10) | yes |  |  |  |
| `patient_cnic` | String(15) | yes |  |  |  |
| `source_institution` | String(50) | no | indexed |  | Referring from |
| `source_department` | String(60) | yes |  |  |  |
| `requesting_doctor_id` | String(64) | yes | indexed |  |  |
| `requesting_doctor_name` | String(200) | no |  |  |  |
| `created_by_id` | String(64) | no |  |  |  |
| `created_by_name` | String(200) | no |  |  |  |
| `kind` | String(20) | no | indexed | `'referral'` | referral = to a doctor or department; test = a test or scan only (its orders carry the destinations) |
| `destination_institution` | String(50) | yes | indexed |  | Referring to (referrals only) |
| `destination_department` | String(60) | yes |  |  |  |
| `destination_doctor` | String(200) | yes |  |  |  |
| `reason` | Text | no |  | `''` | Clinical |
| `consultation_notes` | Text | no |  | `''` | the doctor's consultation notes under the reason: symptoms, history, examination (clinical content) |
| `urgency` | String(20) | no |  | `'routine'` |  |
| `procedure_status` | String(20) | no |  | `'unknown'` | planned \| none \| unknown |
| `planned_procedure` | String(300) | yes |  |  | in the doctor's words |
| `procedure_tags` | JSON | no |  | `list` | what the procedure involves |
| `status` | String(30) | no | indexed | `'draft'` | Workflow |
| `row_version` | Integer | no |  | `1` |  |
| `requested_at` | DateTime(timezone=True) | yes |  |  |  |
| `prepared_by` | String(200) | yes |  |  | Staff checkpoint: records, papers and medicines gathered; the doctor can now review the flags |
| `prepared_at` | DateTime(timezone=True) | yes |  |  |  |
| `packet_reviewed_by` | String(200) | yes |  |  | Doctor checkpoint: the doctor reviewed the records, papers, medicines and flags that go in the packet. Staff never see that content (decision 2026-10-29). A later clinical change clears it. |
| `packet_reviewed_at` | DateTime(timezone=True) | yes |  |  |  |
| `amendment_open` | Boolean | no |  | `False` |  |
| `current_package_version` | Integer | yes |  |  |  |
| `submitted_package_version` | Integer | yes |  |  |  |
| `delivery_status` | String(20) | no |  | `'none'` |  |
| `meds_checked_by` | String(200) | yes |  |  | Staff checkpoint: patient asked about all medicines, including over-the-counter ones |
| `meds_checked_at` | DateTime(timezone=True) | yes |  |  |  |
| `meds_checked_note` | Text | yes |  |  |  |
| `patient_informed_by` | String(200) | yes |  |  | Follow-through |
| `patient_informed_at` | DateTime(timezone=True) | yes |  |  |  |
| `patient_informed_note` | Text | yes |  |  |  |
| `cancel_reason` | Text | yes |  |  |  |
| `decline_reason` | Text | yes |  |  |  |
| `closed_at` | DateTime(timezone=True) | yes |  |  |  |
| `closed_by` | String(200) | yes |  |  |  |
| `acknowledged_at` | DateTime(timezone=True) | yes |  |  |  |
| `accepted_at` | DateTime(timezone=True) | yes |  |  |  |
| `working_set_expires_at` | DateTime(timezone=True) | yes | indexed |  | Temporary working set: retrieved records and everything derived from them are held only until working_set_expires_at, then their clinical content is removed (identifiers, status, audit, manifest and fingerprint stay). See lifecycle/working_set.py. |
| `working_set_purged_at` | DateTime(timezone=True) | yes |  |  |  |
| `receiver_completed_at` | DateTime(timezone=True) | yes |  |  | the receiving doctor marked the referral complete (its shared records are removed after the grace period) |
| `receiver_completed_by` | String(200) | yes |  |  |  |
| `created_at` | DateTime(timezone=True) | no | indexed | `utcnow` |  |
| `updated_at` | DateTime(timezone=True) | no |  | `utcnow` |  |


# Appendix E. Data dictionary: institution service

_Generated from the code by `scripts/sds/build_sds.py`. Do not edit by hand._

### Data dictionary: Institution service database (one per institution: `drali_db`, `chughtai_db`, `ziauddin_db`, `akuh_db`)

#### `access_grants` (AccessGrant, `services/provider/app/models.py`)

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  | (from AccessGrantMixin) |
| `grantee_institution` | String(50) | no | indexed |  | (from AccessGrantMixin) |
| `local_patient_id` | String(50) | no | indexed |  | (from AccessGrantMixin) |
| `categories` | JSON | no |  |  | (from AccessGrantMixin) |
| `status` | String(20) | no |  | `'active'` | (from AccessGrantMixin) |
| `basis` | Text | no |  | `''` | (from AccessGrantMixin) |
| `granted_by` | String(200) | no |  |  | (from AccessGrantMixin) |
| `created_at` | DateTime(timezone=True) | no |  | `utcnow` | (from AccessGrantMixin) |
| `revoked_by` | String(200) | yes |  |  | (from AccessGrantMixin) |
| `revoked_at` | DateTime(timezone=True) | yes |  |  | (from AccessGrantMixin) |
| `expires_at` | DateTime(timezone=True) | yes | indexed |  | (from AccessGrantMixin) Temporary access: the grant stops working at expires_at (NULL only for legacy grants). |
| `referral_ref` | String(60) | yes | indexed |  | (from AccessGrantMixin) The referral this grant was opened for, so it can be closed with the referral. |

#### `audit_events` (AuditEvent, `services/provider/app/models.py`)

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  | (from AuditMixin) |
| `actor_id` | String(100) | no |  |  | (from AuditMixin) |
| `actor_name` | String(200) | no |  |  | (from AuditMixin) |
| `institution_id` | String(50) | yes |  |  | (from AuditMixin) |
| `action` | String(100) | no | indexed |  | (from AuditMixin) |
| `target_type` | String(60) | no |  |  | (from AuditMixin) |
| `target_id` | String(100) | no |  |  | (from AuditMixin) |
| `outcome` | String(20) | no |  |  | (from AuditMixin) |
| `referral_context` | String(60) | yes |  |  | (from AuditMixin) |
| `detail` | JSON | no |  | `dict` | (from AuditMixin) |
| `created_at` | DateTime(timezone=True) | no | indexed | `utcnow` | (from AuditMixin) |

#### `cases` (Case, `services/provider/app/models.py`)

One referral received by this institution, across all sent versions.

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `central_referral_id` | String(40) | no | unique |  |  |
| `sender_institution` | String(50) | no |  |  |  |
| `sender_name` | String(200) | no |  |  |  |
| `department` | String(60) | no | indexed |  |  |
| `requested_doctor` | String(200) | yes |  |  |  |
| `patient_name` | String(200) | no |  |  |  |
| `patient_birth_date` | String(20) | yes |  |  |  |
| `patient_sex` | String(10) | yes |  |  |  |
| `patient_cnic` | String(15) | yes |  |  |  |
| `local_patient_id` | String(30) | yes |  |  | set once staff here confirm the patient (match a record or register them as new) |
| `link_request_id` | Integer | yes |  |  | the central intake link request |
| `urgency` | String(20) | no |  |  |  |
| `status` | String(30) | no |  | `'received'` | received -> acknowledged (staff) -> assigned (staff) -> accepted \| declined (doctor) -> responded -> completed |
| `latest_version` | Integer | no |  |  |  |
| `assigned_doctor` | String(200) | yes |  |  |  |
| `assigned_by` | String(200) | yes |  |  |  |
| `assigned_at` | DateTime(timezone=True) | yes |  |  |  |
| `assign_note` | Text | yes |  |  |  |
| `acknowledged_by` | String(200) | yes |  |  |  |
| `acknowledged_at` | DateTime(timezone=True) | yes |  |  |  |
| `decision` | String(20) | yes |  |  |  |
| `decision_by` | String(200) | yes |  |  |  |
| `decision_at` | DateTime(timezone=True) | yes |  |  |  |
| `decline_reason` | Text | yes |  |  |  |
| `completed_by` | String(200) | yes |  |  | the referred doctor has finished with it; the shared records are then removed after 72 hours |
| `completed_at` | DateTime(timezone=True) | yes |  |  |  |
| `hold_until` | DateTime(timezone=True) | yes |  |  | until when the shared records are kept (mirrors the platform: 30 days after acceptance, extendable) |
| `shared_removed_at` | DateTime(timezone=True) | yes |  |  | when the shared records (packages, forwarded results) were removed here; this institution's own decision, questions and response are kept |
| `received_at` | DateTime(timezone=True) | no |  | `utcnow` |  |
| `updated_at` | DateTime(timezone=True) | no |  | `utcnow` |  |

#### `conditions` (Condition, `services/provider/app/models.py`)

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | String(40) | no | PK |  |  |
| `patient_id` | String | no | FK → patients.local_id, indexed |  |  |
| `display` | String(300) | no |  |  |  |
| `snomed` | String(30) | yes |  |  |  |
| `clinical_status` | String(20) | no |  |  |  |
| `onset` | String(10) | yes |  |  | as recorded: YYYY, YYYY-MM or YYYY-MM-DD |
| `version` | Integer | no |  | `1` | (from Versioned) |
| `updated_at` | DateTime(timezone=True) | no |  | `utcnow` | (from Versioned) |

#### `consultation_responses` (ConsultationResponse, `services/provider/app/models.py`)

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `case_id` | Integer | no | FK → cases.id, indexed |  |  |
| `package_version` | Integer | no |  |  |  |
| `content` | JSON | no |  |  |  |
| `status` | String(20) | no |  | `'draft'` | draft \| returned |
| `drafted_by` | String(200) | no |  |  |  |
| `drafted_at` | DateTime(timezone=True) | no |  | `utcnow` |  |
| `row_version` | Integer | no |  | `1` |  |
| `returned_by` | String(200) | yes |  |  |  |
| `returned_by_id` | String(100) | yes |  |  |  |
| `returned_at` | DateTime(timezone=True) | yes |  |  |  |
| `return_key` | String(200) | yes | unique |  |  |

#### `forwarded_results` (ForwardedResult, `services/provider/app/models.py`)

A diagnostic report from another department or institution, attached to a case.

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `forward_key` | String(200) | no | unique |  |  |
| `case_id` | Integer | no | FK → cases.id, indexed |  |  |
| `content` | JSON | no |  |  |  |
| `received_at` | DateTime(timezone=True) | no |  | `utcnow` |  |

#### `imaging_reports` (ImagingReport, `services/provider/app/models.py`)

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | String(40) | no | PK |  |  |
| `patient_id` | String | no | FK → patients.local_id, indexed |  |  |
| `study_date` | Date | no | indexed |  |  |
| `study` | String(200) | no |  |  |  |
| `body_part` | String(100) | yes |  |  |  |
| `findings` | Text | no |  | `''` |  |
| `impression` | Text | no |  | `''` |  |
| `reporter` | String(200) | yes |  |  |  |
| `version` | Integer | no |  | `1` | (from Versioned) |
| `updated_at` | DateTime(timezone=True) | no |  | `utcnow` | (from Versioned) |

#### `incoming_packages` (IncomingPackage, `services/provider/app/models.py`)

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `case_id` | Integer | no | FK → cases.id, indexed |  |  |
| `version` | Integer | no |  |  |  |
| `delivery_key` | String(200) | no | unique |  |  |
| `envelope` | JSON | no |  |  |  |
| `content_hash` | String(64) | no |  |  |  |
| `received_at` | DateTime(timezone=True) | no |  | `utcnow` |  |

Unique constraints: (case_id, version)

#### `info_requests` (InfoRequest, `services/provider/app/models.py`)

'Ask for more information' from the receiving doctor to the referring clinic.

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `case_id` | Integer | no | FK → cases.id, indexed |  |  |
| `package_version` | Integer | no |  |  |  |
| `question` | Text | no |  |  |  |
| `status` | String(20) | no |  | `'open'` | open \| answered |
| `created_by` | String(200) | no |  |  |  |
| `created_at` | DateTime(timezone=True) | no |  | `utcnow` |  |
| `answer` | Text | yes |  |  |  |
| `answered_by` | String(200) | yes |  |  |  |
| `answered_at` | DateTime(timezone=True) | yes |  |  |  |
| `answer_key` | String(200) | yes | unique |  |  |

#### `lab_results` (LabResult, `services/provider/app/models.py`)

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | String(40) | no | PK |  |  |
| `patient_id` | String | no | FK → patients.local_id, indexed |  |  |
| `panel` | String(200) | no |  |  |  |
| `collected` | Date | no | indexed |  |  |
| `test` | String(120) | no |  |  |  |
| `loinc` | String(20) | yes |  |  |  |
| `value_num` | Float | yes |  |  |  |
| `value_text` | String(200) | yes |  |  |  |
| `unit` | String(40) | yes |  |  |  |
| `reference_range` | String(60) | yes |  |  |  |
| `abnormal_flag` | String(20) | yes |  |  |  |
| `status` | String(20) | no |  | `'final'` |  |
| `note` | Text | yes |  |  |  |
| `version` | Integer | no |  | `1` | (from Versioned) |
| `updated_at` | DateTime(timezone=True) | no |  | `utcnow` | (from Versioned) |

#### `medications` (Medication, `services/provider/app/models.py`)

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | String(40) | no | PK |  |  |
| `patient_id` | String | no | FK → patients.local_id, indexed |  |  |
| `name` | String(200) | no |  |  |  |
| `brand_as_written` | String(100) | yes |  |  |  |
| `dose` | String(100) | yes |  |  |  |
| `route` | String(40) | yes |  |  |  |
| `frequency` | String(100) | yes |  |  |  |
| `start_date` | Date | yes |  |  |  |
| `status` | String(20) | no |  |  | active \| stopped \| completed |
| `prescriber` | String(200) | yes |  |  |  |
| `note` | Text | yes |  |  |  |
| `version` | Integer | no |  | `1` | (from Versioned) |
| `updated_at` | DateTime(timezone=True) | no |  | `utcnow` | (from Versioned) |

#### `order_attachments` (OrderAttachment, `services/provider/app/models.py`)

An image or file returned with a report (scan images, ECG trace, report PDF).

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `order_id` | Integer | no | FK → orders.id, indexed |  |  |
| `filename` | String(200) | no |  |  |  |
| `content_type` | String(100) | no |  |  |  |
| `data` | LargeBinary | no |  |  |  |
| `uploaded_by` | String(200) | no |  |  |  |
| `created_at` | DateTime(timezone=True) | no |  | `utcnow` |  |

#### `orders` (Order, `services/provider/app/models.py`)

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `order_key` | String(200) | no | unique |  |  |
| `order_ref` | String(40) | no | indexed |  |  |
| `central_referral_id` | String(40) | no |  |  |  |
| `sender_institution` | String(50) | no |  |  |  |
| `sender_name` | String(200) | no |  |  |  |
| `department` | String(60) | no | indexed |  |  |
| `category` | String(20) | no |  |  |  |
| `test` | String(200) | no |  |  |  |
| `body_area` | String(100) | yes |  |  |  |
| `clinical_question` | Text | no |  |  |  |
| `urgency` | String(20) | no |  |  |  |
| `patient_name` | String(200) | no |  |  |  |
| `patient_birth_date` | String(20) | yes |  |  |  |
| `patient_sex` | String(10) | yes |  |  |  |
| `patient_cnic` | String(15) | yes |  |  |  |
| `local_patient_id` | String(30) | yes |  |  |  |
| `link_request_id` | Integer | yes |  |  |  |
| `requested_by` | String(200) | no |  |  |  |
| `status` | String(20) | no |  | `'requested'` | requested \| accepted \| rejected \| scheduled \| done \| reported |
| `reject_reason` | Text | yes |  |  |  |
| `scheduled_for` | DateTime(timezone=True) | yes |  |  |  |
| `report_text` | Text | yes |  |  |  |
| `findings` | Text | yes |  |  |  |
| `impression` | Text | yes |  |  |  |
| `values` | JSON | no |  | `list` |  |
| `reported_by` | String(200) | yes |  |  |  |
| `reported_at` | DateTime(timezone=True) | yes |  |  |  |
| `history` | JSON | no |  | `list` |  |
| `received_at` | DateTime(timezone=True) | no |  | `utcnow` |  |
| `updated_at` | DateTime(timezone=True) | no |  | `utcnow` |  |

#### `outbox` (Outbox, `services/provider/app/models.py`)

Events for the central platform, written in the same transaction as the change.

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `event_key` | String(200) | no | unique |  |  |
| `event_type` | String(40) | no |  |  |  |
| `case_id` | Integer | yes | FK → cases.id, indexed |  |  |
| `order_id` | Integer | yes | FK → orders.id, indexed |  |  |
| `payload` | JSON | no |  |  |  |
| `status` | String(20) | no |  | `'pending'` |  |
| `attempts` | Integer | no |  | `0` |  |
| `last_error` | Text | yes |  |  |  |
| `next_attempt_at` | DateTime(timezone=True) | no |  | `utcnow` |  |
| `created_at` | DateTime(timezone=True) | no |  | `utcnow` |  |
| `sent_at` | DateTime(timezone=True) | yes |  |  |  |

#### `patients` (Patient, `services/provider/app/models.py`)

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `local_id` | String(30) | no | PK |  |  |
| `cnic` | String(15) | yes | indexed |  | 13 digits, no dashes |
| `given` | String(100) | no |  |  |  |
| `family` | String(100) | no |  |  |  |
| `birth_date` | Date | no |  |  |  |
| `sex` | String(10) | no |  |  |  |
| `phone` | String(30) | yes |  |  |  |
| `city` | String(60) | yes |  |  |  |
| `registered_by` | String(200) | yes |  |  |  |
| `synthetic` | Boolean | no |  | `True` |  |
| `version` | Integer | no |  | `1` | (from Versioned) |
| `updated_at` | DateTime(timezone=True) | no |  | `utcnow` | (from Versioned) |

#### `sent_copies` (SentCopy, `services/provider/app/models.py`)

This institution's own copy of a referral it sent (and the response it received). Delivered by the central platform, whose working copy is temporary; this copy is the sender's lasting record.

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | Integer | no | PK |  |  |
| `copy_key` | String(220) | no | unique |  |  |
| `central_referral_id` | String(40) | no | indexed |  |  |
| `kind` | String(20) | no |  |  | package \| response |
| `version` | Integer | no |  | `0` |  |
| `content` | JSON | no |  |  |  |
| `received_at` | DateTime(timezone=True) | no |  | `utcnow` |  |

#### `surgeries` (Surgery, `services/provider/app/models.py`)

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | String(40) | no | PK |  |  |
| `patient_id` | String | no | FK → patients.local_id, indexed |  |  |
| `procedure` | String(300) | no |  |  |  |
| `performed` | String(10) | yes |  |  |  |
| `location` | String(200) | yes |  |  |  |
| `version` | Integer | no |  | `1` | (from Versioned) |
| `updated_at` | DateTime(timezone=True) | no |  | `utcnow` | (from Versioned) |

#### `visits` (Visit, `services/provider/app/models.py`)

| Column | Type | Null | Keys | Default | Meaning |
|---|---|---|---|---|---|
| `id` | String(40) | no | PK |  |  |
| `patient_id` | String | no | FK → patients.local_id, indexed |  |  |
| `visit_date` | Date | no | indexed |  |  |
| `setting` | String(200) | no |  |  |  |
| `clinician` | String(200) | yes |  |  |  |
| `reason` | Text | no |  | `''` |  |
| `summary` | Text | no |  | `''` |  |
| `version` | Integer | no |  | `1` | (from Versioned) |
| `updated_at` | DateTime(timezone=True) | no |  | `utcnow` | (from Versioned) |


# Appendix F. API inventory

_Generated from the code by `scripts/sds/build_sds.py`. Do not edit by hand._

### API inventory

Generated from the FastAPI route decorators. *Access checks* lists the authorisation calls made inside each handler (roles, institution scope, service identity, optimistic-concurrency checks). Every endpoint except `/health` and `/ready` also requires a valid Keycloak access token (verified signature, issuer, audience and introspection). Parameters exclude the database session and the caller's identity.

#### Central platform API (`central`, port 8000): 98 endpoints

##### audit and reference data

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| GET | `/admin/audit` | Administrators see audit metadata for their institution (no clinical record content). | require_roles(institution_admin, action=admin.audit) | action: str \| None; outcome: str \| None; limit: int | institution_audit (services/central/app/audit_router.py:52) |
| GET | `/me` | Me. | valid access token (any role) |  | me (services/central/app/audit_router.py:74) |
| GET | `/reference-data` | Reference data. | valid access token (any role) |  | reference_data (services/central/app/audit_router.py:88) |
| GET | `/referrals/{referral_id}/audit` | Referral audit. | load_referral(view_audit) | referral_id: int | referral_audit (services/central/app/audit_router.py:45) |

##### documents

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| GET | `/documents/{document_id}` | Get document. | _load_doc → load_referral() | document_id: int | get_document (services/central/app/documents/router.py:116) |
| GET | `/documents/{document_id}/file` | Download. | _load_doc → load_referral() | document_id: int | download (services/central/app/documents/router.py:135) |
| GET | `/documents/{document_id}/pages/{page}` | Page image. | _load_doc → load_referral() | document_id: int; page: int | page_image (services/central/app/documents/router.py:147) |
| POST | `/documents/{document_id}/reprocess` | Reprocess. | _load_doc → load_referral() | document_id: int | reprocess (services/central/app/documents/router.py:157) |
| GET | `/jobs/{job_id}` | Get job. | load_referral(view) | job_id: str | get_job (services/central/app/documents/router.py:170) |
| GET | `/referrals/{referral_id}/documents` | List documents. | load_referral(view) | referral_id: int | list_documents (services/central/app/documents/router.py:99) |
| POST | `/referrals/{referral_id}/documents` | Upload. | ensure_clinical_edit_allowed(); load_referral(upload) | referral_id: int; file: UploadFile; doc_type: str | upload (services/central/app/documents/router.py:47) |
| GET | `/referrals/{referral_id}/jobs` | Referral jobs. | load_referral(view) | referral_id: int | referral_jobs (services/central/app/documents/router.py:182) |

##### evidence

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| GET | `/evidence/{evidence_id}` | Get evidence. | _load → load_referral() | evidence_id: int | get_evidence (services/central/app/evidence_router.py:79) |
| POST | `/evidence/{evidence_id}/correct` | Correct. | _load → load_referral() | evidence_id: int; body: CorrectIn | correct (services/central/app/evidence_router.py:131) |
| POST | `/evidence/{evidence_id}/exclude` | Exclude. | _set_state → _load → load_referral() | evidence_id: int; body: StateIn | exclude (services/central/app/evidence_router.py:183) |
| POST | `/evidence/{evidence_id}/restore` | Restore. | _set_state → _load → load_referral() | evidence_id: int; body: StateIn | restore (services/central/app/evidence_router.py:188) |
| POST | `/evidence/{evidence_id}/select` | The doctor finalises the packet: their choice overrides the default and the AI recommendation. | _load → load_referral(); ensure_clinical_edit_allowed() | evidence_id: int; body: SelectIn | select_evidence (services/central/app/evidence_router.py:106) |
| POST | `/evidence/{evidence_id}/unresolve` | Mark unresolved. | _set_state → _load → load_referral() | evidence_id: int; body: StateIn | mark_unresolved (services/central/app/evidence_router.py:178) |
| POST | `/evidence/{evidence_id}/verify` | The doctor checks a field read from a paper against the page image; a checked medicine joins the current-medicine list. | _load → load_referral() | evidence_id: int; body: VerifyIn | verify (services/central/app/evidence_router.py:198) |
| GET | `/referrals/{referral_id}/evidence` | List evidence. | load_referral(view) | referral_id: int; category: str \| None; include_superseded: bool | list_evidence (services/central/app/evidence_router.py:66) |
| POST | `/referrals/{referral_id}/evidence/manual` | Manual transcription by the doctor, with an optional source reference; works without OCR (FR-58). | ensure_clinical_edit_allowed(); load_referral(edit, roles=('clinician',)) | referral_id: int; body: ManualIn | manual_entry (services/central/app/evidence_router.py:225) |

##### health

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| GET | `/health` | Health. | public (no token) |  | health (services/central/app/main.py:45) |
| GET | `/ready` | Ready. | public (no token) |  | ready (services/central/app/main.py:50) |

##### inbound (institution services)

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| POST | `/inbound/provider-events` | Provider event. | require_service(svc_provider) | body: ProviderEvent | provider_event (services/central/app/delivery/inbound.py:26) |

##### medications

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| GET | `/drug-classes` | Drug classes. | valid access token (any role) |  | drug_classes (services/central/app/medications/router.py:523) |
| GET | `/medicine-names` | Medicine names. | role rule_reviewer required | q: str | medicine_names (services/central/app/medications/router.py:300) |
| POST | `/medicine-names` | Add name. | require_roles(rule_reviewer, action=medicine_name.add) | body: NameIn | add_name (services/central/app/medications/router.py:321) |
| POST | `/medicine-names/{name_id}/retire` | Retire name. | require_roles(rule_reviewer, action=medicine_name.retire) | name_id: int | retire_name (services/central/app/medications/router.py:341) |
| POST | `/referrals/{referral_id}/ai-suggestions/review` | The doctor marks an AI suggestion Ignore (not relevant for this patient) or Research (needs follow-up). It changes no flag. | load_referral(review_ai_suggestion, roles=('clinician',)) | referral_id: int; body: SuggestionReviewIn | review_suggestion (services/central/app/medications/router.py:79) |
| POST | `/referrals/{referral_id}/flags/{flag_id}/acknowledge` | The doctor records a decision on the flag for this patient: reviewed, ignore or research. Any decision means 'seen'; it is never treatment clearance. Ignored flags stay in the record. | load_referral(acknowledge_flag, roles=('clinician',)) | referral_id: int; flag_id: int; body: AckIn | acknowledge_flag (services/central/app/medications/router.py:273) |
| GET | `/referrals/{referral_id}/medications` | Medications. | load_referral(view) | referral_id: int | medications (services/central/app/medications/router.py:33) |
| POST | `/referrals/{referral_id}/medications/checked` | Staff confirm they asked the patient about every medicine, including over-the-counter ones. | ensure_clinical_edit_allowed(); load_referral(edit, roles=('clinician',)) | referral_id: int; body: CheckedIn | medicines_checked (services/central/app/medications/router.py:254) |
| POST | `/referrals/{referral_id}/medications/manual` | Staff add a medicine the patient says they take, e.g. an over-the-counter painkiller. | ensure_clinical_edit_allowed(); load_referral(edit, roles=('clinician',)) | referral_id: int; body: ManualMedIn | add_medicine (services/central/app/medications/router.py:121) |
| POST | `/referrals/{referral_id}/medications/{entry_id}/exclude` | Staff mark a recorded medicine as not current (e.g. an old prescription, or the other side of a dose difference). The record is kept, with who and why. | ensure_clinical_edit_allowed(); load_referral(edit, roles=('clinician',)) | referral_id: int; entry_id: int; body: ReasonIn | exclude_medicine (services/central/app/medications/router.py:163) |
| POST | `/referrals/{referral_id}/medications/{entry_id}/mapping` | Doctor or staff resolve a name: choose a medicine from the name list, or, for a DRAP brand name used for different products, the product it is (by the company on the pack). | ensure_clinical_edit_allowed(); load_referral(map_medication, roles=('clinician',)) | referral_id: int; entry_id: int; body: MapIn | set_mapping (services/central/app/medications/router.py:215) |
| POST | `/referrals/{referral_id}/medications/{entry_id}/restore` | Restore medicine. | ensure_clinical_edit_allowed(); load_referral(edit, roles=('clinician',)) | referral_id: int; entry_id: int | restore_medicine (services/central/app/medications/router.py:181) |
| GET | `/rules` | List rules. | require_roles(rule_reviewer, action=rule.list); role rule_reviewer required |  | list_rules (services/central/app/medications/router.py:367) |
| POST | `/rules` | Reviewers draft a rule. It does nothing until a reviewer approves it. | require_roles(rule_reviewer, action=rule.create) | body: RuleIn | create_rule (services/central/app/medications/router.py:413) |
| GET | `/rules/ai` | The suggestion model's evaluation figures and its stored suggestions (reviewer only). | require_roles(rule_reviewer, action=rule.list) |  | ai_model (services/central/app/medications/router.py:96) |
| GET | `/rules/interactions` | Imported drug-drug interactions (read-only), searchable by ingredient. | require_roles(rule_reviewer, action=rule.list) | q: str | list_interactions (services/central/app/medications/router.py:491) |
| GET | `/rules/label-rules` | Rules read from drug labels by script (read-only), with the sentence each relies on. | require_roles(rule_reviewer, action=rule.list) | q: str; kind: str | list_label_rules (services/central/app/medications/router.py:502) |
| PUT | `/rules/{rule_id}` | An edit is a new draft version; the approved version keeps working until the new one is approved. | require_roles(rule_reviewer, action=rule.edit) | rule_id: str; body: RuleIn | edit_rule (services/central/app/medications/router.py:428) |
| POST | `/rules/{rule_id}/versions/{version}/decision` | Only a clinical rule reviewer may approve, reject or retire a rule version. | require_roles(rule_reviewer, action=rule.decision) | rule_id: str; version: int; body: RuleDecisionIn | decide_rule (services/central/app/medications/router.py:446) |

##### notifications

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| GET | `/notifications` | List notifications. | _mine() | unread_only: bool | list_notifications (services/central/app/notifications.py:56) |
| POST | `/notifications/read-all` | Mark all read. | _mine() |  | mark_all_read (services/central/app/notifications.py:75) |
| POST | `/notifications/{notification_id}/read` | Mark read. | _mine() | notification_id: int | mark_read (services/central/app/notifications.py:64) |

##### patient links

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| GET | `/admin/role-templates` | Templates this institution's administrator may apply. | require_roles(institution_admin, action=admin.role_templates) |  | list_role_templates (services/central/app/identity/router.py:412) |
| GET | `/admin/users` | List users. | require_roles(institution_admin, action=admin.users) |  | list_users (services/central/app/identity/router.py:320) |
| POST | `/admin/users/{user_id}/apply-template` | Replace the user's template-managed realm roles with the template's (never service roles, never oneself). | require_roles(institution_admin, action=admin.apply_template) | user_id: str; body: ApplyTemplateIn | apply_role_template (services/central/app/identity/router.py:419) |
| POST | `/admin/users/{user_id}/disable` | Disable user. | _set_status → require_roles(institution_admin, action=admin.user_status) | user_id: str; body: StatusIn | disable_user (services/central/app/identity/router.py:375) |
| POST | `/admin/users/{user_id}/enable` | Enable user. | _set_status → require_roles(institution_admin, action=admin.user_status) | user_id: str; body: StatusIn | enable_user (services/central/app/identity/router.py:380) |
| GET | `/institutions` | Institutions. | valid access token (any role) |  | institutions (services/central/app/identity/router.py:385) |
| GET | `/patient-links` | Links of one of your own patient records (all states, with history). | require_roles(clinic_staff, clinician, institution_admin, diagnostics_staff, action=patient_link.view) | institution: str \| None; local_id: str \| None | list_links (services/central/app/identity/router.py:81) |
| POST | `/patient-links` | Ask another institution to confirm their record of one of your patients. | require_roles(clinic_staff, clinician, action=patient_link.request) | body: LinkIn | request_link (services/central/app/identity/router.py:127) |
| GET | `/patient-links/incoming` | Requests from other institutions for your staff to check. | require_roles(clinic_staff, clinician, institution_admin, diagnostics_staff, action=patient_link.incoming) | status: str | incoming (services/central/app/identity/router.py:102) |
| GET | `/patient-links/outgoing` | Outgoing. | require_roles(clinic_staff, clinician, institution_admin, diagnostics_staff, action=patient_link.outgoing) | status: str | outgoing (services/central/app/identity/router.py:112) |
| POST | `/patient-links/{link_id}/approve` | Only staff at the target institution approve. Approval records the basis and shares the patient's referral-relevant records with the requesting institution. | require_roles(clinic_staff, institution_admin, diagnostics_staff, action=patient_link.approve) | link_id: int; body: ApproveIn | approve_link (services/central/app/identity/router.py:161) |
| POST | `/patient-links/{link_id}/invalidate` | Stops future use. History is kept, and referrals that used it are flagged for review. | require_roles(clinician, institution_admin, clinic_staff, action=patient_link.invalidate) | link_id: int; body: DecisionIn | invalidate_link (services/central/app/identity/router.py:256) |
| POST | `/patient-links/{link_id}/lookup` | Target staff search their own patient index for the person in the request. | require_roles(clinic_staff, institution_admin, diagnostics_staff, action=patient_link.lookup) | link_id: int | lookup (services/central/app/identity/router.py:138) |
| POST | `/patient-links/{link_id}/reject` | Reject link. | require_roles(clinic_staff, institution_admin, diagnostics_staff, action=patient_link.reject) | link_id: int; body: DecisionIn | reject_link (services/central/app/identity/router.py:236) |
| GET | `/patients/search` | Search your own institution's patient index (name, local ID or CNIC). | require_roles(clinic_staff, clinician, institution_admin, diagnostics_staff, action=patients.search) | q: str | search_patients (services/central/app/identity/router.py:295) |

##### referrals

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| GET | `/referrals` | List referrals. | require_roles(clinic_staff, clinician, action=referral.search); role clinician required | patient: str \| None; reference: str \| None; status: str \| None; destination: str \| None; kind: str \| None; mine: bool; date_from: date \| None; date_to: date \| None; limit: int | list_referrals (services/central/app/referrals/router.py:179) |
| POST | `/referrals` | Only a doctor applies for a referral or a test. | require_roles(clinician, action=referral.create) | body: ReferralForm | create_referral (services/central/app/referrals/router.py:143) |
| GET | `/referrals/{referral_id}` | Get referral. | load_referral(view); role clinician required | referral_id: int | get_referral (services/central/app/referrals/router.py:253) |
| PATCH | `/referrals/{referral_id}` | Doctors edit their request. After it was sent, a clinical change opens an amendment. | check_version(); load_referral(edit) | referral_id: int; body: ReferralUpdate | update_referral (services/central/app/referrals/router.py:288) |
| POST | `/referrals/{referral_id}/cancel` | Only a doctor withdraws a request; staff cannot stop it. | check_version(); load_referral(cancel) | referral_id: int; body: CancelIn | cancel (services/central/app/referrals/router.py:428) |
| GET | `/referrals/{referral_id}/events` | Events. | load_referral(view) | referral_id: int | events (services/central/app/referrals/router.py:439) |
| POST | `/referrals/{referral_id}/links` | Staff ask another institution (where the patient has been) to confirm the patient. | load_referral(link) | referral_id: int; body: LinkRequestIn | request_referral_link (services/central/app/referrals/router.py:351) |
| POST | `/referrals/{referral_id}/recommend` | Staff ask for the AI recommendation again (for example after adding papers). | load_referral(prepare, roles=('clinic_staff',)) | referral_id: int | recommend_selection (services/central/app/referrals/router.py:402) |
| GET | `/referrals/{referral_id}/retrievals` | Retrieval history. | load_referral(view) | referral_id: int | retrieval_history (services/central/app/referrals/router.py:416) |
| POST | `/referrals/{referral_id}/retrieve` | Retrieve records. | load_referral(retrieve) | referral_id: int | retrieve_records (services/central/app/referrals/router.py:365) |
| GET | `/referrals/{referral_id}/selection` | Selection status. | load_referral(view) | referral_id: int | selection_status (services/central/app/referrals/router.py:391) |
| POST | `/referrals/{referral_id}/submit` | Submit request. | check_version(); load_referral(submit_request) | referral_id: int; body: VersionIn | submit_request (services/central/app/referrals/router.py:332) |

##### response and follow-through

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| POST | `/clarifications/{clarification_id}/answer` | Answer the receiving doctor's request for more information; the answer is sent back. | load_referral(answer_info_request) | clarification_id: int; body: AnswerIn | answer (services/central/app/followup/router.py:58) |
| POST | `/referrals/{referral_id}/close` | Closure means the workflow is complete, not a statement about the patient's condition. | check_version(); load_referral(close) | referral_id: int; body: CloseIn | close (services/central/app/followup/router.py:149) |
| POST | `/referrals/{referral_id}/patient-informed` | Staff record that the patient was told the outcome and what happens next. | load_referral(inform_patient) | referral_id: int; body: InformedIn | patient_informed (services/central/app/followup/router.py:84) |
| GET | `/referrals/{referral_id}/responses` | Responses. | load_referral(view) | referral_id: int | responses (services/central/app/followup/router.py:27) |
| GET | `/referrals/{referral_id}/tasks` | Tasks. | load_referral(view) | referral_id: int | tasks (services/central/app/followup/router.py:104) |
| POST | `/referrals/{referral_id}/tasks` | Tasks such as a repeat test or making sure the patient attends. | load_referral(followup) | referral_id: int; body: TaskIn | add_task (services/central/app/followup/router.py:110) |
| POST | `/responses/{response_id}/review` | The referring doctor records that the outcome has been seen. | load_referral(review_response) | response_id: int; body: ReviewIn | review_response (services/central/app/followup/router.py:38) |
| POST | `/tasks/{task_id}/outcome` | Task outcome. | load_referral(followup) | task_id: int; body: TaskOutcomeIn | task_outcome (services/central/app/followup/router.py:131) |

##### sending

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| GET | `/referrals/{referral_id}/brief-preview` | What the specialist will receive if the referral is sent now (clinical content: doctors only). | load_referral(view) | referral_id: int | brief_preview (services/central/app/sending/router.py:36) |
| GET | `/referrals/{referral_id}/delivery` | Delivery. | load_referral(view) | referral_id: int | delivery (services/central/app/sending/router.py:113) |
| GET | `/referrals/{referral_id}/packages/{version}` | Get package. | load_referral(view) | referral_id: int; version: int | get_package (services/central/app/sending/router.py:122) |
| POST | `/referrals/{referral_id}/packages/{version}/verify` | Compare a copy of the package (held by the sender or the receiver) with the fingerprint kept at sending. | load_referral(view) | referral_id: int; version: int; body: VerifyCopyIn | verify_package_copy (services/central/app/sending/router.py:146) |
| POST | `/referrals/{referral_id}/packages/{version}/verify-own-copy` | Fetch this clinic's own stored copy (from its own system, with the user's token) and check it. The copy is clinical content, so this is for doctors. | load_referral(view) | referral_id: int; version: int | verify_own_copy (services/central/app/sending/router.py:158) |
| POST | `/referrals/{referral_id}/packet-reviewed` | The doctor has reviewed the clinical content of the packet: papers, medicines, flags and the records chosen. Staff can then send it. Any later clinical change clears this (workflow.after_change). | check_version(); load_referral(review_packet) | referral_id: int; body: SendIn | mark_packet_reviewed (services/central/app/sending/router.py:68) |
| POST | `/referrals/{referral_id}/prepared` | Staff have retrieved the records and uploaded the papers; the doctor can now review the clinical content. | check_version(); load_referral(prepare) | referral_id: int; body: SendIn | mark_prepared (services/central/app/sending/router.py:47) |
| GET | `/referrals/{referral_id}/readiness` | Get readiness. | load_referral(view) | referral_id: int | get_readiness (services/central/app/sending/router.py:30) |
| POST | `/referrals/{referral_id}/retry-delivery` | Retry reuses the same delivery key, so the receiver never gets a duplicate. | load_referral(send) | referral_id: int | retry_delivery (services/central/app/sending/router.py:103) |
| POST | `/referrals/{referral_id}/send` | Staff send the referral once every check is done. | check_version(); load_referral(send) | referral_id: int; body: SendIn | send (services/central/app/sending/router.py:92) |

##### tests and scans

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| GET | `/diagnostics/{dx_id}/attachments/{n}` | An image or file returned with the report. | _load → load_referral() | dx_id: int; n: int | attachment (services/central/app/diagnostics/router.py:148) |
| POST | `/diagnostics/{dx_id}/cancel` | The doctor withdraws a test that has not been sent (or was rejected). | _load → load_referral() | dx_id: int; body: CancelIn | cancel_request (services/central/app/diagnostics/router.py:118) |
| POST | `/diagnostics/{dx_id}/seen` | The requesting doctor records that they have seen the result. | _load → load_referral() | dx_id: int | mark_seen (services/central/app/diagnostics/router.py:132) |
| POST | `/diagnostics/{dx_id}/send` | Staff check the request and send the order, with the patient's identity details. | _load → load_referral() | dx_id: int | send_request (services/central/app/diagnostics/router.py:79) |
| GET | `/referrals/{referral_id}/diagnostics` | List requests. | load_referral(view) | referral_id: int | list_requests (services/central/app/diagnostics/router.py:57) |
| POST | `/referrals/{referral_id}/diagnostics` | The doctor adds a test to their test request (before it is sent). | load_referral(add_diagnostic) | referral_id: int; body: DiagnosticIn | add_request (services/central/app/diagnostics/router.py:64) |

##### work queue

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| GET | `/work-queue` | Work queue. | require_roles(clinician, clinic_staff, action=work_queue); role clinic_staff required; role clinician required |  | work_queue (services/central/app/workqueue.py:27) |

#### Institution service API (`drali` 8001, `chughtai` 8002, `ziauddin` 8003, `akuh` 8004): 42 endpoints

##### fhir

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| GET | `/fhir/patients/{local_id}/records` | Referral profile, kept to what a referral needs: conditions, surgeries, current medications only, and visits, results and imaging since the window start (latest result per test). Returned as a FHIR searchset Bundle. | decide_access(); forbid() | local_id: str; categories: str \| None; since: str \| None | patient_records (services/provider/app/main.py:366) |

##### grant close-out

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| POST | `/grants/revoke-by-referral` | Revoke by referral. | forbid(Only the central platform service can close grants by referral); role svc_central required | body: RevokeByReferralIn | revoke_by_referral (libs/common/refcommon/sourcekit.py:302) |

##### health

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| GET | `/health` | Health. | public (no token) |  | health (libs/common/refcommon/sourcekit.py:339) |
| GET | `/ready` | Ready. | public (no token) |  | ready (libs/common/refcommon/sourcekit.py:343) |

##### identity

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| POST | `/identity/lookup` | Own staff look up who a link request refers to. Candidates are shown to a person, with each field compared; nothing is linked automatically. | require_own(clinic_staff, clinician, institution_admin, diagnostics_staff, what=look up a patient for a link request) | body: LookupIn | identity_lookup (services/provider/app/main.py:232) |
| POST | `/identity/register` | Register a patient who is new to this institution (first referral or test here). | require_own(clinic_staff, institution_admin, diagnostics_staff, what=register a new patient) | body: RegisterIn | register_patient (services/provider/app/main.py:270) |

##### inbound (central platform)

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| POST | `/inbound/clarification-answers` | Receive answer. | _require_central() | body: ClarificationAnswer | receive_answer (services/provider/app/main.py:587) |
| POST | `/inbound/orders` | Receive order. | _require_central() | body: DiagnosticOrder | receive_order (services/provider/app/main.py:486) |
| POST | `/inbound/referral-expired` | The referral's time is up: remove this institution's copy of the shared records (the packages and the results forwarded with them). Its own decision, questions and response are its record and are kept. | _require_central() | body: ExpiredIn | referral_expired (services/provider/app/main.py:464) |
| POST | `/inbound/referrals` | Idempotent receipt of a sent referral version (keyed by delivery key). | _require_central() | raw: dict | receive_package (services/provider/app/main.py:419) |
| POST | `/inbound/results` | Receive result. | _require_central() | body: ResultForward | receive_result (services/provider/app/main.py:514) |
| POST | `/outbound-copies` | Store our own copy of a referral we sent, or of the response to it (idempotent by key). | _require_central() | body: SentCopyIn | receive_sent_copy (services/provider/app/main.py:537) |

##### incoming referrals

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| GET | `/cases` | List cases. | _visible → _is_intake → has_any(clinic_staff, institution_admin); _visible → role clinician required; require_own(clinician, clinic_staff, institution_admin, what=see incoming referrals) |  | list_cases (services/provider/app/main.py:647) |
| GET | `/cases/{case_id}` | Get case. | _get_case(); require_own(clinician, clinic_staff, institution_admin, what=see incoming referrals); role clinician required | case_id: int | get_case (services/provider/app/main.py:702) |
| POST | `/cases/{case_id}/acknowledge` | Staff confirm the referral has been received here. | _get_case(); require_own(clinic_staff, institution_admin, what=acknowledge a referral) | case_id: int | acknowledge (services/provider/app/main.py:654) |
| POST | `/cases/{case_id}/assign` | Staff send the referral to the doctor who will see the patient (can be changed until they decide). | _get_case(); require_own(clinic_staff, institution_admin, what=assign a referral) | case_id: int; body: AssignIn | assign (services/provider/app/main.py:675) |

##### intake

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| POST | `/intake/patient` | Staff here confirmed who an arriving patient is (through the central link request): the incoming referral and test orders for that request now point at this record. | require_own(clinic_staff, institution_admin, diagnostics_staff, what=confirm an arriving patient) | body: IntakeIn | intake_patient (services/provider/app/main.py:570) |

##### laboratory and imaging

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| GET | `/orders` | List orders. | _require_diagnostics() |  | list_orders (services/provider/app/main.py:949) |
| GET | `/orders/{order_id}` | Get order. | _get_order(); _require_diagnostics() | order_id: int | get_order (services/provider/app/main.py:956) |
| POST | `/orders/{order_id}/accept` | Accept order. | _get_order(); _require_diagnostics() | order_id: int | accept_order (services/provider/app/main.py:973) |
| GET | `/orders/{order_id}/attachments/{attachment_id}` | Order attachment. | _get_order(); _require_diagnostics() | order_id: int; attachment_id: int | order_attachment (services/provider/app/main.py:962) |
| POST | `/orders/{order_id}/done` | Order done. | _get_order(); _require_diagnostics() | order_id: int | order_done (services/provider/app/main.py:1013) |
| POST | `/orders/{order_id}/reject` | A rejection always carries a reason (wrong test, preparation needed, no capacity). | _get_order(); _require_diagnostics() | order_id: int; body: RejectIn | reject_order (services/provider/app/main.py:988) |
| POST | `/orders/{order_id}/report` | Return the report (with images for scans). It is also filed in this institution's own records. | _get_order(); _require_diagnostics() | order_id: int; body: ReportIn | report_order (services/provider/app/main.py:1073) |
| POST | `/orders/{order_id}/schedule` | Schedule order. | _get_order(); _require_diagnostics() | order_id: int; body: ScheduleIn | schedule_order (services/provider/app/main.py:1003) |

##### patients

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| GET | `/patients` | Own patient index (name, local ID or CNIC). | require_own(clinic_staff, clinician, institution_admin, diagnostics_staff, what=search the patient index) | q: str | search_patients (services/provider/app/main.py:195) |
| GET | `/patients/{local_id}` | Get patient. | require_own(clinic_staff, clinician, institution_admin, diagnostics_staff, what=view patient details) | local_id: str | get_patient (services/provider/app/main.py:215) |

##### receiving doctor

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| POST | `/cases/{case_id}/complete` | The referred doctor has finished with the referral. The shared records are removed 72 hours later. | _get_case(); _require_doctor → require_own(clinician, what=act on incoming referrals) | case_id: int | complete_case (services/provider/app/main.py:871) |
| POST | `/cases/{case_id}/decision` | Decide. | _get_case(); _require_doctor → require_own(clinician, what=act on incoming referrals) | case_id: int; body: DecisionIn | decide (services/provider/app/main.py:745) |
| POST | `/cases/{case_id}/extend-hold` | The referred doctor needs the shared records for longer: kept for another 30 days from now. | _get_case(); _require_doctor → require_own(clinician, what=act on incoming referrals) | case_id: int; body: ExtendHoldIn | extend_hold (services/provider/app/main.py:891) |
| POST | `/cases/{case_id}/info-requests` | Request info. | _get_case(); _require_doctor → require_own(clinician, what=act on incoming referrals) | case_id: int; body: InfoIn | request_info (services/provider/app/main.py:774) |
| PUT | `/cases/{case_id}/response` | Save response. | _get_case(); _require_doctor → require_own(clinician, what=act on incoming referrals) | case_id: int; body: ResponseIn | save_response (services/provider/app/main.py:810) |
| POST | `/cases/{case_id}/response/send` | The receiving doctor signs off and returns the response in one step. | _get_case(); _require_doctor → require_own(clinician, what=act on incoming referrals) | case_id: int; body: SendIn | send_response (services/provider/app/main.py:838) |
| POST | `/outbox/{item_id}/retry` | Retry outbox. | require_own(clinician, diagnostics_staff, institution_admin, what=retry delivery) | item_id: int | retry_outbox (services/provider/app/main.py:1111) |

##### records

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| GET | `/outbound-copies` | Our own copies for one referral (doctors and staff here). | require_own(clinician, clinic_staff, what=read our copies of sent referrals); role clinician required | referral_id: str | list_sent_copies (services/provider/app/main.py:553) |
| GET | `/patients/{local_id}/activity` | When the patient was last seen here (visit, test or scan). Used to choose the most recently visited institution of each kind. | decide_access(); forbid() | local_id: str | patient_activity (services/provider/app/main.py:348) |

##### sharing

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| POST | `/sharing/grants` | Created when this institution's own staff approve a patient-link request: the requesting institution may then read this patient's referral-relevant records. | require_own(clinic_staff, institution_admin, what=share patient records) | body: ShareIn | share_records (services/provider/app/main.py:301) |

##### source administration

| Method | Path | Purpose | Access checks | Parameters | Handler |
|---|---|---|---|---|---|
| GET | `/admin/audit` | List audit. | require_admin() | limit: int | list_audit (libs/common/refcommon/sourcekit.py:280) |
| GET | `/admin/grants` | List grants. | require_admin() |  | list_grants (libs/common/refcommon/sourcekit.py:222) |
| POST | `/admin/grants` | Create grant. | require_admin() | body: GrantIn | create_grant (libs/common/refcommon/sourcekit.py:227) |
| POST | `/admin/grants/{grant_id}/extend` | Only this source's administrator can extend. Counted from now, capped at MAX_GRANT_DAYS. | require_admin() | grant_id: int; body: ExtendIn | extend_grant (libs/common/refcommon/sourcekit.py:248) |
| POST | `/admin/grants/{grant_id}/revoke` | Revoke grant. | require_admin() | grant_id: int | revoke_grant (libs/common/refcommon/sourcekit.py:267) |


# Appendix G. Exchange contracts and request bodies

_Generated from the code by `scripts/sds/build_sds.py`. Do not edit by hand._

### Exchange contracts (`libs/common/refcommon/exchange.py`)

Project API contracts between the central platform and the institution services. They are not standard FHIR resources; a FHIR R4 4.0.1 Bundle travels inside the referral package unchanged.

| Constant | Value |
|---|---|
| `PACKAGE_ENVELOPE_VERSION` | `referral-package/2.0` |
| `ORDER_ENVELOPE_VERSION` | `diagnostic-order/1.0` |
| `EVENT_ENVELOPE_VERSION` | `provider-event/1.0` |
| `CONTRACT_NOTE` | `Project API contract (not a standard FHIR resource)` |

#### Provider event types

Events an institution service sends to `POST /inbound/provider-events` (deduplicated by `event_key`):

`acknowledged`, `accepted`, `declined`, `info_requested`, `response_returned`, `completed`, `hold_extended`, `order_accepted`, `order_rejected`, `order_scheduled`, `order_done`, `order_reported`

#### Outbox message kinds (central → institution)

| Outbox kind | Institution endpoint |
|---|---|
| `deliver_package` | `/inbound/referrals` |
| `deliver_order` | `/inbound/orders` |
| `forward_result` | `/inbound/results` |
| `clarification_answer` | `/inbound/clarification-answers` |
| `sender_copy` | `/outbound-copies` |
| `expire_shared` | `/inbound/referral-expired` |

#### Fields covered by the package SHA-256

Transport fields (delivery key, FHIR bundle timestamp) are excluded so a retry never changes the hash: `referral_id`, `package_version`, `sender_institution`, `sender_department`, `destination_institution`, `destination_department`, `destination_doctor`, `urgency`, `reason`, `procedure_status`, `planned_procedure`, `procedure_label`, `patient`, `requesting_doctor`, `brief_sections`, `medication_flags`, `medication_evaluation`, `evidence`, `limitations`, `diagnostic_requests`, `ai_suggestions`, `selection`, `sent_by`, `sent_by_id`, `sent_at`

#### `BriefStatement`


| Field | Type | Default | Note |
|---|---|---|---|
| `id` | str | (required) |  |
| `text` | str | (required) |  |
| `evidence_ids` | list[int] | Field(default_factory=list) |  |
| `author_kind` | Literal['model', 'clinician', 'template'] | 'template' |  |
| `author_name` | str \| None | None |  |
| `edited_by` | str \| None | None |  |
| `verification` | Literal['verified', 'unresolved', 'unverified', 'mixed', 'none'] | 'none' |  |
| `source` | str \| None | None |  |
| `date` | str \| None | None |  |
| `group` | str \| None | None |  |

#### `BriefSection`


| Field | Type | Default | Note |
|---|---|---|---|
| `key` | str | (required) |  |
| `title` | str | (required) |  |
| `statements` | list[BriefStatement] | Field(default_factory=list) |  |

#### `FlagSnapshot`


| Field | Type | Default | Note |
|---|---|---|---|
| `flag_id` | int | (required) |  |
| `version` | int | (required) |  |
| `kind` | str | (required) |  |
| `title` | str | (required) |  |
| `message` | str | (required) |  |
| `medication` | str \| None | None |  |
| `drug_class` | str \| None | None |  |
| `source_label` | str \| None | None |  |
| `rule_id` | str \| None | None |  |
| `rule_version` | int \| None | None |  |
| `evidence_ids` | list[int] | Field(default_factory=list) |  |
| `acknowledged` | dict[str, Any] \| None | None | {by, at, decision: reviewed\|ignore\|research, note} |
| `severity` | str \| None | None |  |
| `ingredients` | list[str] | Field(default_factory=list) |  |
| `source_type` | str \| None | None |  |
| `source_name` | str \| None | None |  |
| `source_ref` | str \| None | None |  |
| `source_version` | str \| None | None |  |
| `source_quote` | str \| None | None |  |
| `auto_generated` | bool | False |  |

#### `EvidenceSnapshot`


| Field | Type | Default | Note |
|---|---|---|---|
| `evidence_id` | int | (required) |  |
| `category` | str | (required) |  |
| `display` | str | (required) |  |
| `original` | dict[str, Any] | Field(default_factory=dict) |  |
| `origin` | str | (required) |  |
| `source_institution` | str | (required) |  |
| `source_record_type` | str \| None | None |  |
| `source_record_id` | str \| None | None |  |
| `source_record_version` | str \| None | None |  |
| `clinical_time` | str \| None | None |  |
| `verification_status` | str | (required) |  |
| `document_ref` | dict[str, Any] \| None | None |  |
| `also_recorded_in` | list[str] | Field(default_factory=list) |  |

#### `PackageEnvelope`

One sent version of a referral. The requesting doctor authorised the request; staff compiled and sent this exact version (recorded separately).

| Field | Type | Default | Note |
|---|---|---|---|
| `envelope_version` | str | PACKAGE_ENVELOPE_VERSION |  |
| `contract_note` | str | CONTRACT_NOTE |  |
| `delivery_key` | str | (required) |  |
| `referral_id` | str | (required) |  |
| `package_version` | int | (required) |  |
| `sender_institution` | str | (required) |  |
| `sender_department` | str \| None | None |  |
| `destination_institution` | str | (required) |  |
| `destination_department` | str | (required) |  |
| `destination_doctor` | str \| None | None |  |
| `urgency` | str | (required) |  |
| `reason` | str | (required) |  |
| `consultation_notes` | str \| None | None |  |
| `procedure_status` | str | (required) |  |
| `planned_procedure` | str \| None | None |  |
| `procedure_label` | str \| None | None |  |
| `patient` | dict[str, Any] | (required) |  |
| `requesting_doctor` | dict[str, Any] | (required) |  |
| `brief_sections` | list[BriefSection] | (required) |  |
| `medication_flags` | list[FlagSnapshot] | (required) |  |
| `medication_evaluation` | dict[str, Any] | (required) |  |
| `evidence` | list[EvidenceSnapshot] | (required) |  |
| `limitations` | list[str] | Field(default_factory=list) |  |
| `diagnostic_requests` | list[dict[str, Any]] | Field(default_factory=list) |  |
| `ai_suggestions` | list[dict[str, Any]] | Field(default_factory=list) |  |
| `selection` | dict[str, Any] | Field(default_factory=dict) |  |
| `sent_by` | str | (required) |  |
| `sent_by_id` | str | (required) |  |
| `sent_at` | datetime | (required) |  |
| `content_hash` | str | (required) |  |
| `fhir_bundle` | dict[str, Any] | (required) |  |
| `supersedes_version` | int \| None | None |  |

#### `DiagnosticOrder`

A test or scan request sent to a laboratory or imaging department. It is a separate order: it does not depend on the specialist's decision about the referral.

| Field | Type | Default | Note |
|---|---|---|---|
| `envelope_version` | str | ORDER_ENVELOPE_VERSION |  |
| `contract_note` | str | CONTRACT_NOTE |  |
| `order_key` | str | (required) |  |
| `order_ref` | str | (required) |  |
| `referral_id` | str | (required) |  |
| `sender_institution` | str | (required) |  |
| `destination_institution` | str | (required) |  |
| `destination_department` | str | (required) |  |
| `category` | Literal['laboratory', 'imaging', 'cardiac'] | (required) |  |
| `test` | str | (required) |  |
| `body_area` | str \| None | None |  |
| `clinical_question` | str | (required) |  |
| `urgency` | str | (required) |  |
| `patient` | dict[str, Any] | (required) |  |
| `requested_by` | str | (required) |  |
| `requested_at` | datetime | (required) |  |

#### `ResultForward`

A returned diagnostic report forwarded to the referral's receiving hospital, so the specialist sees it next to the brief.

| Field | Type | Default | Note |
|---|---|---|---|
| `contract_note` | str | CONTRACT_NOTE |  |
| `forward_key` | str | (required) |  |
| `referral_id` | str | (required) |  |
| `order_ref` | str | (required) |  |
| `test` | str | (required) |  |
| `performed_by_institution` | str | (required) |  |
| `report_text` | str | '' |  |
| `values` | list[dict[str, Any]] | Field(default_factory=list) |  |
| `reported_by` | str | (required) |  |
| `reported_at` | datetime | (required) |  |

#### `ProviderEvent`


| Field | Type | Default | Note |
|---|---|---|---|
| `envelope_version` | str | EVENT_ENVELOPE_VERSION |  |
| `contract_note` | str | CONTRACT_NOTE |  |
| `event_key` | str | (required) |  |
| `referral_id` | str | (required) |  |
| `order_ref` | str \| None | None |  |
| `package_version` | int \| None | None |  |
| `type` | ProviderEventType | (required) |  |
| `actor_id` | str | (required) |  |
| `actor_name` | str | (required) |  |
| `institution_id` | str | (required) |  |
| `occurred_at` | datetime | (required) |  |
| `data` | dict[str, Any] | Field(default_factory=dict) |  |

#### `ClarificationAnswer`


| Field | Type | Default | Note |
|---|---|---|---|
| `contract_note` | str | CONTRACT_NOTE |  |
| `answer_key` | str | (required) |  |
| `referral_id` | str | (required) |  |
| `provider_clarification_id` | int | (required) |  |
| `answer` | str | (required) |  |
| `answered_by` | str | (required) |  |
| `answered_at` | datetime | (required) |  |

### Request bodies (API input models)

#### `CancelIn` (services/central/app/diagnostics/router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `reason` | str | Field(min_length=3) |  |

#### `SelectIn` (services/central/app/evidence_router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `selected` | bool | (required) |  |

#### `CorrectIn` (services/central/app/evidence_router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `fields` | dict[str, Any] | (required) |  |
| `note` | str | '' |  |
| `expected_row_version` | int | (required) |  |

#### `StateIn` (services/central/app/evidence_router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `note` | str | '' |  |

#### `VerifyIn` (services/central/app/evidence_router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `note` | str | '' |  |
| `expected_row_version` | int | (required) |  |

#### `ManualIn` (services/central/app/evidence_router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `category` | Literal['medication', 'lab', 'condition', 'note'] | (required) |  |
| `fields` | dict[str, Any] | (required) |  |
| `document_id` | int \| None | None |  |
| `page` | int \| None | None |  |
| `note` | str | '' |  |

#### `ReviewIn` (services/central/app/followup/router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `note` | str | '' |  |

#### `AnswerIn` (services/central/app/followup/router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `answer` | str | Field(min_length=2) |  |

#### `InformedIn` (services/central/app/followup/router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `note` | str | Field(min_length=3) |  |

#### `TaskIn` (services/central/app/followup/router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `description` | str | Field(min_length=3) |  |
| `assignee_name` | str \| None | None |  |
| `due_date` | date \| None | None |  |

#### `TaskOutcomeIn` (services/central/app/followup/router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `status` | Literal['completed', 'not_completed'] | (required) |  |
| `outcome` | str | Field(min_length=2) |  |

#### `CloseIn` (services/central/app/followup/router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `expected_version` | int | (required) |  |

#### `LinkIn` (services/central/app/identity/router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `local_id` | str | (required) |  |
| `target_institution` | str | (required) |  |
| `purpose` | str | Field(min_length=5) |  |

#### `ApproveIn` (services/central/app/identity/router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `local_patient_id` | str \| None | None |  |
| `register_new` | bool | False |  |
| `note` | str | Field(min_length=3) |  |

#### `DecisionIn` (services/central/app/identity/router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `note` | str | Field(min_length=3) |  |

#### `StatusIn` (services/central/app/identity/router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `reason` | str | Field(min_length=3) |  |

#### `ApplyTemplateIn` (services/central/app/identity/router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `template_id` | str | (required) |  |
| `reason` | str | Field(min_length=3) |  |

#### `SuggestionReviewIn` (services/central/app/medications/router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `pair_key` | str | (required) |  |
| `decision` | Literal['ignore', 'research'] | (required) |  |
| `note` | str | '' |  |

#### `ManualMedIn` (services/central/app/medications/router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `name` | str | Field(min_length=2) |  |
| `strength` | str \| None | None |  |
| `dose` | str \| None | None |  |
| `frequency` | str \| None | None |  |
| `route` | str \| None | None |  |
| `over_the_counter` | bool | False |  |
| `note` | str | '' |  |

#### `ReasonIn` (services/central/app/medications/router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `reason` | str | Field(min_length=3) |  |

#### `MapIn` (services/central/app/medications/router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `ingredient` | str | (required) |  |
| `company` | str \| None | None |  |
| `drap_reg_no` | str \| None | None |  |

#### `CheckedIn` (services/central/app/medications/router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `note` | str | '' |  |

#### `AckIn` (services/central/app/medications/router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `flag_version` | int | (required) |  |
| `decision` | Literal['reviewed', 'ignore', 'research'] | 'reviewed' |  |
| `note` | str | '' |  |

#### `NameIn` (services/central/app/medications/router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `display` | str | Field(min_length=2) |  |
| `ingredient` | str | Field(min_length=2) |  |
| `drug_class` | str | Field(min_length=2) |  |
| `kind` | Literal['generic', 'brand'] | 'brand' |  |

#### `RuleIn` (services/central/app/medications/router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `title` | str | Field(min_length=5) |  |
| `drug_class` | str | (required) |  |
| `procedure_tags` | list[str] | Field(min_length=1) |  |
| `message` | str | Field(min_length=10) |  |
| `rationale` | str | '' |  |
| `reference` | str | '' |  |

#### `RuleDecisionIn` (services/central/app/medications/router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `decision` | Literal['approve', 'reject', 'retire'] | (required) |  |
| `reference_checked` | str | Field(min_length=5) |  |
| `note` | str | '' |  |

#### `DiagnosticIn` (services/central/app/referrals/router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `category` | str | (required) |  |
| `test` | str | Field(min_length=2) |  |
| `body_area` | str \| None | None |  |
| `clinical_question` | str | Field(min_length=3) |  |
| `urgency` | str | 'routine' |  |
| `destination_institution` | str | (required) |  |
| `destination_department` | str | (required) |  |

#### `ReferralForm` (services/central/app/referrals/router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `patient_local_id` | str | (required) |  |
| `kind` | str | 'referral' |  |
| `source_department` | str \| None | None |  |
| `destination_institution` | str \| None | None |  |
| `destination_department` | str \| None | None |  |
| `destination_doctor` | str \| None | None |  |
| `reason` | str | '' |  |
| `consultation_notes` | str | Field('', max_length=20000) |  |
| `urgency` | str | 'routine' |  |
| `procedure_status` | str | 'unknown' |  |
| `planned_procedure` | str \| None | None |  |
| `procedure_tags` | list[str] | Field(default_factory=list) |  |
| `diagnostic_requests` | list[DiagnosticIn] | Field(default_factory=list) |  |
| `submit` | bool | False |  |

#### `VersionIn` (services/central/app/referrals/router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `expected_version` | int | (required) |  |

#### `LinkRequestIn` (services/central/app/referrals/router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `target_institution` | str | (required) |  |

#### `CancelIn` (services/central/app/referrals/router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `expected_version` | int | (required) |  |
| `reason` | str | Field(min_length=3) |  |

#### `SendIn` (services/central/app/sending/router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `expected_version` | int | (required) |  |

#### `VerifyCopyIn` (services/central/app/sending/router.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `package` | dict | (required) |  |

#### `LookupIn` (services/provider/app/main.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `cnic` | str \| None | None |  |
| `name` | str \| None | None |  |
| `birth_date` | str \| None | None |  |
| `sex` | str \| None | None |  |

#### `RegisterIn` (services/provider/app/main.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `cnic` | str | (required) |  |
| `given` | str | (required) |  |
| `family` | str | (required) |  |
| `birth_date` | date | (required) |  |
| `sex` | str | (required) |  |
| `phone` | str \| None | None |  |
| `city` | str \| None | None |  |

#### `ShareIn` (services/provider/app/main.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `grantee_institution` | str | (required) |  |
| `local_patient_id` | str | (required) |  |
| `basis` | str | Field(min_length=5) |  |
| `duration_days` | int | DEFAULT_GRANT_DAYS |  |
| `referral_ref` | str \| None | None |  |

#### `ExpiredIn` (services/provider/app/main.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `expire_key` | str | (required) |  |
| `referral_id` | str | (required) |  |
| `expired_at` | datetime | (required) |  |

#### `SentCopyIn` (services/provider/app/main.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `copy_key` | str | (required) |  |
| `referral_id` | str | (required) |  |
| `kind` | Literal['package', 'response'] | (required) |  |
| `version` | int | 0 |  |
| `content` | dict | (required) |  |

#### `IntakeIn` (services/provider/app/main.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `referral_id` | str | (required) |  |
| `local_patient_id` | str | (required) |  |

#### `AssignIn` (services/provider/app/main.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `doctor` | str | Field(min_length=3) |  |
| `note` | str | '' |  |

#### `DecisionIn` (services/provider/app/main.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `decision` | Literal['accept', 'decline'] | (required) |  |
| `reason` | str \| None | None |  |

#### `InfoIn` (services/provider/app/main.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `question` | str | Field(min_length=3) |  |

#### `ResponseIn` (services/provider/app/main.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `assessment` | str | '' |  |
| `plan` | str | '' |  |
| `instructions_for_clinic` | str | '' |  |
| `appointment` | str | '' |  |
| `expected_row_version` | int \| None | None |  |

#### `SendIn` (services/provider/app/main.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `expected_row_version` | int | (required) |  |

#### `ExtendHoldIn` (services/provider/app/main.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `reason` | str | Field(min_length=3) |  |

#### `RejectIn` (services/provider/app/main.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `reason` | str | Field(min_length=3) |  |

#### `ScheduleIn` (services/provider/app/main.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `scheduled_for` | datetime | (required) |  |

#### `ValueIn` (services/provider/app/main.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `test` | str | (required) |  |
| `value` | str | (required) |  |
| `unit` | str \| None | None |  |
| `reference` | str \| None | None |  |
| `flag` | str \| None | None |  |

#### `AttachmentIn` (services/provider/app/main.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `filename` | str | Field(min_length=1, max_length=200) |  |
| `content_type` | str | (required) |  |
| `data` | str | (required) | base64 |

#### `ReportIn` (services/provider/app/main.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `findings` | str | '' |  |
| `impression` | str | '' |  |
| `values` | list[ValueIn] | Field(default_factory=list) |  |
| `attachments` | list[AttachmentIn] | Field(default_factory=list, max_length=6) |  |

#### `Decision` (libs/common/refcommon/sourcekit.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `allowed` | set[str] | (required) |  |
| `denied` | set[str] | (required) |  |
| `reason` | str | (required) |  |
| `expired` | bool | False |  |

#### `GrantIn` (libs/common/refcommon/sourcekit.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `grantee_institution` | str | (required) |  |
| `local_patient_id` | str | (required) |  |
| `categories` | list[str] | (required) |  |
| `basis` | str | '' |  |
| `duration_days` | int | DEFAULT_GRANT_DAYS |  |
| `referral_ref` | str \| None | None |  |

#### `ExtendIn` (libs/common/refcommon/sourcekit.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `days` | int | (required) |  |
| `reason` | str | (required) |  |

#### `RevokeByReferralIn` (libs/common/refcommon/sourcekit.py)


| Field | Type | Default | Note |
|---|---|---|---|
| `referral_ref` | str | (required) |  |
| `reason` | str | 'referral finished' |  |


# Appendix H. State machines and status values

_Generated from the code by `scripts/sds/build_sds.py`. Do not edit by hand._

### Referral status state machine (`services/central/app/referrals/state.py`)

Enforced on the server by `transition()`: any move not listed raises `409 invalid_transition`. Each transition writes a `referral_events` row and an audit event, and updates the working-set expiry.

```mermaid
stateDiagram-v2
    [*] --> draft
    draft --> cancelled
    draft --> requested
    requested --> cancelled
    requested --> draft
    requested --> submitted
    submitted --> acknowledged
    submitted --> cancelled
    submitted --> declined
    submitted --> response_returned
    acknowledged --> accepted
    acknowledged --> cancelled
    acknowledged --> declined
    accepted --> cancelled
    accepted --> closed
    accepted --> followup_pending
    accepted --> response_returned
    response_returned --> closed
    response_returned --> followup_pending
    followup_pending --> closed
    cancelled --> [*]
    closed --> [*]
    declined --> [*]
```

| Status | Label | Allowed next statuses |
|---|---|---|
| `draft` | Draft (doctor) | `cancelled`, `requested` |
| `requested` | In progress | `cancelled`, `draft`, `submitted` |
| `submitted` | Sent | `acknowledged`, `cancelled`, `declined`, `response_returned` |
| `acknowledged` | Acknowledged | `accepted`, `cancelled`, `declined` |
| `accepted` | Accepted | `cancelled`, `closed`, `followup_pending`, `response_returned` |
| `response_returned` | Response received | `closed`, `followup_pending` |
| `followup_pending` | Follow-up | `closed` |
| `closed` | Closed | (final) |
| `declined` | Declined | (final) |
| `cancelled` | Cancelled | (final) |

Status groups: **PRE_SUBMISSION** = `draft`, `requested`; **IN_FLIGHT** = `accepted`, `acknowledged`, `submitted`; **CLINICAL_LOCKED** = `cancelled`, `closed`, `declined`, `followup_pending`, `response_returned`; **TERMINAL** = `cancelled`, `closed`, `declined`

#### Other status fields (from the model column comments)

| Database | Column | Values | Default |
|---|---|---|---|
| central | `documents.status` | uploaded \| queued \| processing \| extracted \| failed | `'uploaded'` |
| central | `evidence_items.origin` | source \| document \| manual |  |
| central | `evidence_items.review_state` | imported \| proposed \| corrected \| unresolved \| excluded \| manual |  |
| central | `evidence_items.verification_status` | source_record \| unverified \| verified \| invalidated |  |
| central | `evidence_items.selection_source` | default \| ai \| staff |  |
| central | `jobs.status` | queued \| running \| completed \| failed | `'queued'` |
| central | `selection_runs.status` | completed \| unavailable (no model / API error) \| rejected (answer failed checks) \| nothing_to_review \| discarded (the working set was removed before the answer arrived) |  |
| central | `source_retrievals.status` | successful \| empty \| partial \| denied \| unavailable \| invalid \| skipped (not the most recent of its kind) |  |
| central | `patient_links.kind` | records = asking a place the patient visited for their records (it matches a record or says it has none); intake = sent with a referral or test order, so the receiver matches the patient or registers them as new | `'records'` |
| central | `patient_links.status` | requested \| verified \| rejected \| invalidated | `'requested'` |
| central | `evaluation_runs.status` | completed \| failed |  |
| central | `flag_reviews.decision` | reviewed \| ignore \| research | `'reviewed'` |
| central | `label_rules.kind` | drug_condition \| drug_procedure |  |
| central | `label_rules.status` | auto_extracted \| withdrawn | `'auto_extracted'` |
| central | `medication_entries.mapping_status` | mapped \| ambiguous \| unmapped \| staff_mapped |  |
| central | `medication_flags.kind` | confirmed (approved manual rule) \| interaction \| label_warning \| unrecognised_medicine \| interactions_not_checked \| procedure_not_checked \| records_incomplete |  |
| central | `medication_flags.status` | active \| superseded \| withdrawn | `'active'` |
| central | `medication_rules.status` | draft \| approved \| rejected \| retired \| superseded | `'draft'` |
| central | `medicine_names.kind` | generic \| brand \| register_brand \| register_ambiguous (DRAP) | `'generic'` |
| central | `medicine_names.status` | active \| retired | `'active'` |
| central | `suggestion_reviews.decision` | ignore \| research |  |
| central | `clarifications.status` | open \| answered | `'open'` |
| central | `diagnostic_requests.status` | draft (in the referral, not sent yet) \| requested \| accepted \| rejected \| scheduled \| done \| reported \| cancelled | `'draft'` |
| central | `followup_tasks.status` | open \| completed \| not_completed | `'open'` |
| central | `outbox.kind` | deliver_package \| deliver_order \| forward_result \| clarification_answer |  |
| central | `outbox.status` | pending \| sent \| failed | `'pending'` |
| central | `referrals.kind` | referral = to a doctor or department; test = a test or scan only (its orders carry the destinations) | `'referral'` |
| central | `referrals.procedure_status` | planned \| none \| unknown | `'unknown'` |
| central | `referrals.status` | Workflow | `'draft'` |
| institution | `cases.status` | received -> acknowledged (staff) -> assigned (staff) -> accepted \| declined (doctor) -> responded -> completed | `'received'` |
| institution | `consultation_responses.status` | draft \| returned | `'draft'` |
| institution | `info_requests.status` | open \| answered | `'open'` |
| institution | `medications.status` | active \| stopped \| completed |  |
| institution | `orders.status` | requested \| accepted \| rejected \| scheduled \| done \| reported | `'requested'` |
| institution | `sent_copies.kind` | package \| response |  |


# Appendix I. Background jobs

_Generated from the code by `scripts/sds/build_sds.py`. Do not edit by hand._

### Background jobs (`services/central/app/tasks.py`, Celery worker with beat)

Redis is the queue only; job state lives in PostgreSQL (`jobs` table).

| Task | Schedule | Purpose | Function |
|---|---|---|---|
| `process_document` | on demand | Process document. | `process_document` |
| `deliver_outbox` | every 5 s | Deliver outbox. | `deliver_outbox` |
| `retention_sweep` | every 3600 s | Delete uploaded document copies of closed referrals after the retention period. Approved package snapshots and audit history are retained by policy. | `retention_sweep` |
| `close_referral_grants` | every 60 s | For finished referrals, ask each institution to revoke the access grants opened for them. | `close_referral_grants` |
| `purge_working_sets` | every 600 s | Remove the clinical content of working sets whose time is up (see lifecycle/working_set.py). | `purge_working_sets` |
| `recommend_selection` | on demand | AI packet-selection recommendation, run in the background after retrieval (it can take a minute). | `recommend_selection` |


# Appendix J. Configuration and deployment descriptors

_Generated from the code by `scripts/sds/build_sds.py`. Do not edit by hand._

### Configuration

#### Environment variables read by the code

Every variable read with `os.environ.get`, `os.getenv` or a boolean helper, with its default and where it is read.

| Variable | Default | Meaning | Read in |
|---|---|---|---|
| `ACCEPTED_HOLD_DAYS` | `'30'` | a received referral's shared records: kept ACCEPTED_HOLD_DAYS after acceptance (extendable by the referred doctor), and removed GRACE_HOURS after they mark it complete (the platform applies the same rules) | services/central/app/config.py:54, services/provider/app/config.py:17 |
| `ANTHROPIC_API_KEY` | `''` |  | services/central/app/config.py:25 |
| `CENTRAL_URL` | `'http://central:8000'` |  | services/provider/app/config.py:9 |
| `DATABASE_URL` | `'postgresql+psycopg://central:central@postgres/central_db'` |  | services/central/app/config.py:13, services/provider/app/main.py:76, services/provider/app/seed.py:120 |
| `DEFAULT_GRANT_DAYS` | `'14'` | Access grants are temporary. New grants always get an expiry; the duration is chosen up to this limit (days). Grants created before expiry existed have none and are reported as "legacy" so an administrator can renew or revoke them. | libs/common/refcommon/sourcekit.py:39 |
| `DOCUMENT_RETENTION_DAYS` | `'365'` |  | services/central/app/config.py:48 |
| `EXTRACTION_MODE` | `'auto'` | auto \| llm \| rules | services/central/app/config.py:37 |
| `GOOGLE_VISION_API_KEY` | `''` |  | services/central/app/config.py:41 |
| `GOOGLE_VISION_ENDPOINT` | `'https://vision.googleapis.com/v1/images:annotate'` |  | services/central/app/config.py:42 |
| `INSTITUTION_ID` | `(required)` | drali \| chughtai \| ziauddin \| akuh | services/provider/app/config.py:6 |
| `INSTITUTION_NAME` | `INSTITUTION` |  | services/provider/app/config.py:7 |
| `INTROSPECT_TOKENS` | `True` |  | libs/common/refcommon/auth.py:68 |
| `KEYCLOAK_INTERNAL_URL` | `'http://keycloak:8080'` |  | libs/common/refcommon/auth.py:63 |
| `KEYCLOAK_PUBLIC_URL` | `'http://localhost:8080'` |  | libs/common/refcommon/auth.py:64 |
| `KEYCLOAK_REALM` | `'referral'` |  | libs/common/refcommon/auth.py:65 |
| `LLM_API_KEY` | `''` |  | services/central/app/config.py:36 |
| `LLM_BASE_URL` | `''` | openai_compatible: vLLM, Kimi or any other chat-completions server (…/v1) | services/central/app/config.py:35 |
| `LLM_CONTEXT_TOKENS` | `'16384'` | local Ollama models | services/central/app/config.py:30 |
| `LLM_EXTERNAL_ALLOWED` | `False` | Patient data (always de-identified) may go to a model outside this computer (an Ollama ":cloud" model, ollama.com, Anthropic, any remote server) only if this is true: docs/decisions/2026-10-28-cloud-model-privacy.md | services/central/app/config.py:33 |
| `LLM_MODEL` | `'claude-opus-5-5'` |  | services/central/app/config.py:24 |
| `LLM_PROVIDER` | `'anthropic'` | anthropic \| ollama \| openai_compatible | services/central/app/config.py:23 |
| `LLM_TIMEOUT_SECONDS` | `'120'` |  | services/central/app/config.py:44 |
| `LOCAL_ID_PREFIX` | `'PT'` |  | services/provider/app/config.py:8 |
| `MAX_GRANT_DAYS` | `'30'` |  | libs/common/refcommon/sourcekit.py:40 |
| `MAX_PAGES` | `'10'` |  | services/central/app/config.py:47 |
| `MAX_RETRIEVAL_SOURCES` | `'5'` | Retrieval asks every linked institution, up to this many besides the referring one (most recently visited first), so the AI recommendation stays within what it can read. The rest are listed as not retrieved, never as "no records". | services/central/app/config.py:61 |
| `MAX_UPLOAD_BYTES` | `str(10 * 1024 * 1024)` |  | services/central/app/config.py:46 |
| `OCR_ENGINE` | `'tesseract'` | Reading papers: tesseract (printed text, on this computer) \| google_vision (printed and handwritten; the page image is sent to Google Cloud Vision) | services/central/app/config.py:40 |
| `OCR_TIMEOUT_SECONDS` | `'60'` |  | services/central/app/config.py:43 |
| `OLLAMA_API_KEY` | `''` |  | services/central/app/config.py:29 |
| `OLLAMA_HOST` | `'http://host.docker.internal:11434'` | Ollama: a local server (which also serves ":cloud" models once `ollama signin` has run on that computer), or https://ollama.com directly with OLLAMA_API_KEY. | services/central/app/config.py:28 |
| `REDIS_URL` | `'redis://redis:6379/0'` |  | services/central/app/config.py:14 |
| `REFERRAL_HISTORY_YEARS` | `'3'` | How far back retrieval asks each source (the 6-month window is the default selection, not a fetch limit), for a destination with no entry in SPECIALTY_HISTORY_YEARS | services/central/app/config.py:57 |
| `REFERRAL_WINDOW_DAYS` | `'183'` | Visits, results and imaging older than this are not retrieved for a referral. | services/central/app/config.py:21, services/provider/app/config.py:14 |
| `REPO_ASSETS` | `'/srv/assets'` |  | services/central/app/config.py:16 |
| `RUN_JOBS_INLINE` | `False` |  | services/central/app/config.py:63 |
| `SEED_DATA_DIR` | `'/srv/seed-data/patients'` |  | services/provider/app/seed.py:24 |
| `SERVICE_CLIENT_ID` | (none) |  | libs/common/refcommon/auth.py:66 |
| `SERVICE_CLIENT_SECRET` | (none) |  | libs/common/refcommon/auth.py:67 |
| `SOURCE_MAX_RETRIES` | `'2'` |  | services/central/app/config.py:19 |
| `SOURCE_TIMEOUT_SECONDS` | `'10'` |  | services/central/app/config.py:18 |
| `STORAGE_ROOT` | `'/data/documents'` |  | services/central/app/config.py:15 |
| `TOKEN_AUDIENCE` | `f'{INSTITUTION}-api'` |  | services/provider/app/config.py:10 |
| `WORKING_SET_GRACE_HOURS` | `'72'` | How long a referral's shared records are kept (docs/decisions/2026-10-28-referral-expiry.md): no limit until the receiving doctor accepts; then a safety limit of ACCEPTED_HOLD_DAYS, which that doctor can extend by the same again; removed WORKING_SET_GRACE_HOURS after they mark the referral complete (or it is cancelled), and straight away if they decline it. | services/central/app/config.py:53, services/provider/app/config.py:18 |

#### `.env.example` (installation settings)

Secret values are never shown here. Copy `.env.example` to `.env` and set every secret per installation.

| Key | Example value | Comment |
|---|---|---|
| `POSTGRES_SUPERUSER_PASSWORD` | secret: set per installation | PostgreSQL (one server, separate database + credentials per owner) |
| `CENTRAL_DB_PASSWORD` | secret: set per installation |  |
| `DRALI_DB_PASSWORD` | secret: set per installation |  |
| `CHUGHTAI_DB_PASSWORD` | secret: set per installation |  |
| `ZIAUDDIN_DB_PASSWORD` | secret: set per installation |  |
| `AKUH_DB_PASSWORD` | secret: set per installation |  |
| `KEYCLOAK_DB_PASSWORD` | secret: set per installation |  |
| `KEYCLOAK_ADMIN_PASSWORD` | secret: set per installation | Keycloak |
| `DEMO_USER_PASSWORD` | secret: set per installation | Password given to every seeded synthetic demo account |
| `CENTRAL_CLIENT_SECRET` | secret: set per installation | Confidential client secrets (each service validates/introspects its own tokens) |
| `DRALI_CLIENT_SECRET` | secret: set per installation |  |
| `CHUGHTAI_CLIENT_SECRET` | secret: set per installation |  |
| `ZIAUDDIN_CLIENT_SECRET` | secret: set per installation |  |
| `AKUH_CLIENT_SECRET` | secret: set per installation |  |
| `LLM_PROVIDER` | `anthropic` | Language model (optional; used only to read uploaded papers). Leave ANTHROPIC_API_KEY empty to use the rule-based reader instead. |
| `ANTHROPIC_API_KEY` | secret: set per installation |  |
| `LLM_MODEL` | `claude-opus-5-5` |  |
| `OLLAMA_HOST` |  | Open models through Ollama instead: LLM_PROVIDER=ollama LLM_MODEL=gemma4:cloud   (free plan; run `ollama signin` on the computer running Ollama) OLLAMA_HOST=http://host.docker.internal:11434   (Ollama on this computer, as seen from the containers) or call Ollama's cloud directly: OLLAMA_HOST=https://ollama.com, OLLAMA_API_KEY=<key from https://ollama.com/settings/keys>, and the model's API name (e.g. gemma4:31b) as LLM_MODEL. |
| `OLLAMA_API_KEY` | secret: set per installation |  |
| `LLM_EXTERNAL_ALLOWED` | `false` | Privacy: patient data (always de-identified first) may go to a model outside this computer (a ":cloud" model, ollama.com, Anthropic) only when this is true. Synthetic data only until the operating institution has agreed (docs/decisions/2026-10-28-cloud-model-privacy.md). Remote servers must use https. |
| `LLM_TIMEOUT_SECONDS` | `120` |  |
| `EXTRACTION_MODE` | `auto` | Extraction: "llm" uses the language model when configured, otherwise "rules" |
| `OCR_ENGINE` | `tesseract` | Reading uploaded papers. "tesseract" reads printed text on this computer. "google_vision" also reads handwriting (doctors' prescriptions) with Google Cloud Vision: the page image is sent to Google. Key: Google Cloud console > APIs & Services > Credentials > API key, restricted to the Cloud Vision API. Synthetic data only until the operating institution has agreed to this (docs/decisions/2026-10-28-handwriting-ocr.md). |
| `GOOGLE_VISION_API_KEY` | secret: set per installation |  |
| `DOCUMENT_RETENTION_DAYS` | `365` | Retention (days) for uploaded document copies after referral closure |

#### `docker-compose.yml`

| Service | Image / build | Ports | Depends on | Environment keys | Volumes | Command | Health check |
|---|---|---|---|---|---|---|---|
| `postgres` | postgres:16-alpine |  |  | AKUH_DB_PASSWORD, CENTRAL_DB_PASSWORD, CHUGHTAI_DB_PASSWORD, DRALI_DB_PASSWORD, KEYCLOAK_DB_PASSWORD, POSTGRES_PASSWORD, POSTGRES_USER, ZIAUDDIN_DB_PASSWORD | pgdata:/var/lib/postgresql/data, ./infra/postgres/init:/docker-entrypoint-initdb.d:ro |  | yes |
| `redis` | redis:7-alpine |  |  |  |  |  | yes |
| `keycloak` | quay.io/keycloak/keycloak:26.0 | 8080:8080 | postgres | AKUH_CLIENT_SECRET, CENTRAL_CLIENT_SECRET, CHUGHTAI_CLIENT_SECRET, DEMO_USER_PASSWORD, DRALI_CLIENT_SECRET, JAVA_OPTS_KC_HEAP, KC_BOOTSTRAP_ADMIN_PASSWORD, KC_BOOTSTRAP_ADMIN_USERNAME, KC_DB, KC_DB_PASSWORD, KC_DB_URL, KC_DB_USERNAME, KC_HEALTH_ENABLED, KC_HOSTNAME, KC_HTTP_ENABLED, WEB_ORIGIN, ZIAUDDIN_CLIENT_SECRET | ./infra/keycloak/import:/opt/keycloak/data/import:ro | `start-dev --import-realm` | yes |
| `drali` | build: services/provider/Dockerfile | 8001:8000 | keycloak, postgres | CENTRAL_URL, DATABASE_URL, INSTITUTION_ID, INSTITUTION_NAME, INTROSPECT_TOKENS, KEYCLOAK_INTERNAL_URL, KEYCLOAK_PUBLIC_URL, KEYCLOAK_REALM, LOCAL_ID_PREFIX, SERVICE_CLIENT_ID, SERVICE_CLIENT_SECRET |  |  | yes |
| `chughtai` | build: services/provider/Dockerfile | 8002:8000 | keycloak, postgres | CENTRAL_URL, DATABASE_URL, INSTITUTION_ID, INSTITUTION_NAME, INTROSPECT_TOKENS, KEYCLOAK_INTERNAL_URL, KEYCLOAK_PUBLIC_URL, KEYCLOAK_REALM, LOCAL_ID_PREFIX, SERVICE_CLIENT_ID, SERVICE_CLIENT_SECRET |  |  | yes |
| `ziauddin` | build: services/provider/Dockerfile | 8003:8000 | keycloak, postgres | CENTRAL_URL, DATABASE_URL, INSTITUTION_ID, INSTITUTION_NAME, INTROSPECT_TOKENS, KEYCLOAK_INTERNAL_URL, KEYCLOAK_PUBLIC_URL, KEYCLOAK_REALM, LOCAL_ID_PREFIX, SERVICE_CLIENT_ID, SERVICE_CLIENT_SECRET |  |  | yes |
| `akuh` | build: services/provider/Dockerfile | 8004:8000 | keycloak, postgres | CENTRAL_URL, DATABASE_URL, INSTITUTION_ID, INSTITUTION_NAME, INTROSPECT_TOKENS, KEYCLOAK_INTERNAL_URL, KEYCLOAK_PUBLIC_URL, KEYCLOAK_REALM, LOCAL_ID_PREFIX, SERVICE_CLIENT_ID, SERVICE_CLIENT_SECRET |  |  | yes |
| `central` | build: services/central/Dockerfile | 8000:8000 | keycloak, postgres, redis | AKUH_URL, ANTHROPIC_API_KEY, CHUGHTAI_URL, DATABASE_URL, DOCUMENT_RETENTION_DAYS, DRALI_URL, EXTRACTION_MODE, GOOGLE_VISION_API_KEY, INTROSPECT_TOKENS, KEYCLOAK_INTERNAL_URL, KEYCLOAK_PUBLIC_URL, KEYCLOAK_REALM, LLM_CONTEXT_TOKENS, LLM_EXTERNAL_ALLOWED, LLM_MODEL, LLM_PROVIDER, LLM_TIMEOUT_SECONDS, OCR_ENGINE, OLLAMA_API_KEY, OLLAMA_HOST, REDIS_URL, SERVICE_CLIENT_ID, SERVICE_CLIENT_SECRET, STORAGE_ROOT, ZIAUDDIN_URL | documents:/data/documents |  | yes |
| `worker` | build: services/central/Dockerfile |  | central, redis | AKUH_URL, ANTHROPIC_API_KEY, CHUGHTAI_URL, DATABASE_URL, DOCUMENT_RETENTION_DAYS, DRALI_URL, EXTRACTION_MODE, GOOGLE_VISION_API_KEY, INTROSPECT_TOKENS, KEYCLOAK_INTERNAL_URL, KEYCLOAK_PUBLIC_URL, KEYCLOAK_REALM, LLM_CONTEXT_TOKENS, LLM_EXTERNAL_ALLOWED, LLM_MODEL, LLM_PROVIDER, LLM_TIMEOUT_SECONDS, OCR_ENGINE, OLLAMA_API_KEY, OLLAMA_HOST, REDIS_URL, SERVICE_CLIENT_ID, SERVICE_CLIENT_SECRET, STORAGE_ROOT, ZIAUDDIN_URL | documents:/data/documents | `celery -A app.tasks worker -B --loglevel=info --concurrency=2 -Q referral` |  |
| `web` | build: Dockerfile | 3000:80 | central |  |  |  |  |

Named volumes: `documents`, `pgdata`

#### `docker-compose.prod.yml`

| Service | Image / build | Ports | Depends on | Environment keys | Volumes | Command | Health check |
|---|---|---|---|---|---|---|---|
| `caddy` | caddy:2-alpine | 80:80, 443:443 | keycloak, web | SITE_HOST | ./infra/caddy/Caddyfile:/etc/caddy/Caddyfile:ro, caddy_data:/data, caddy_config:/config |  |  |
| `keycloak` |  |  |  | KC_HOSTNAME, KC_HTTP_ENABLED, KC_HTTP_MANAGEMENT_RELATIVE_PATH, KC_HTTP_RELATIVE_PATH, KC_PROXY_HEADERS, WEB_ORIGIN |  | `start --import-realm` |  |
| `web` | build: Dockerfile |  |  |  |  |  |  |
| `postgres` |  |  |  |  |  |  |  |
| `drali` |  |  |  | KEYCLOAK_INTERNAL_URL, KEYCLOAK_PUBLIC_URL |  |  |  |
| `chughtai` |  |  |  | KEYCLOAK_INTERNAL_URL, KEYCLOAK_PUBLIC_URL |  |  |  |
| `ziauddin` |  |  |  | KEYCLOAK_INTERNAL_URL, KEYCLOAK_PUBLIC_URL |  |  |  |
| `akuh` |  |  |  | KEYCLOAK_INTERNAL_URL, KEYCLOAK_PUBLIC_URL |  |  |  |
| `central` |  |  |  | KEYCLOAK_INTERNAL_URL, KEYCLOAK_PUBLIC_URL |  |  |  |
| `worker` |  |  |  | KEYCLOAK_INTERNAL_URL, KEYCLOAK_PUBLIC_URL |  |  |  |

Named volumes: `caddy_config`, `caddy_data`

#### `docker-compose.dbaccess.yml`

| Service | Image / build | Ports | Depends on | Environment keys | Volumes | Command | Health check |
|---|---|---|---|---|---|---|---|
| `postgres` |  | 127.0.0.1:5432:5432 |  |  |  |  |  |


# Appendix K. Web application, roles and identity provider

_Generated from the code by `scripts/sds/build_sds.py`. Do not edit by hand._

### Web application (`web/`)

#### Routes (`web/src/App.tsx`)

| Path | Screen component |
|---|---|
| `*` | `NotFound` |
| `*` | `SignIn` |
| `/` | `Home` |
| `/accessibility` | `AccessibilityStatement` |
| `/admin/access` | `SourceAccess` |
| `/admin/audit` | `AuditLog` |
| `/admin/users` | `AdminUsers` |
| `/callback` | `Home` |
| `/documents/:id` | `DocumentReview` |
| `/incoming` | `IncomingList` |
| `/incoming/:id` | `IncomingCase` |
| `/medicine-names` | `MedicineNames` |
| `/orders` | `OrderList` |
| `/orders/:id` | `OrderView` |
| `/patient-links` | `PatientLinks` |
| `/privacy` | `PrivacyNotice` |
| `/referrals` | `ReferralList` |
| `/referrals/:id` | `ReferralWorkspace` |
| `/referrals/new` | `NewReferral` |
| `/rules` | `RulesPage` |
| `/terms` | `TermsOfUse` |
| `/work-queue` | `WorkQueue` |

#### Feature modules (`web/src/features`)

| Feature | Files |
|---|---|
| `admin` | AdminUsers.tsx, AuditLog.tsx, SourceAccess.tsx |
| `auth` | NotFound.tsx, SignIn.tsx |
| `documents` | DocumentReview.tsx, DocumentsTab.tsx |
| `identity` | ConfirmPatient.tsx, PatientLinks.tsx |
| `incoming` | Incoming.tsx |
| `legal` | LegalPages.tsx |
| `orders` | Orders.tsx |
| `referrals` | AuditTab.tsx, HoldNotice.tsx, Journey.tsx, LinksTab.tsx, MedicinesTab.tsx, NewReferral.tsx, RecordsTab.tsx, ReferralForm.tsx, ReferralList.tsx, ReferralWorkspace.tsx, RequestTab.tsx, ResponseTab.tsx, SendTab.tsx, TestsTab.tsx, steps.ts |
| `rules` | MedicineNames.tsx, RulesPage.tsx |
| `workqueue` | WorkQueue.tsx, queue.ts |

#### Role templates and menus (`rules/roles/templates.v1.json`)

The menu is built from `GET /me`; it only hides screens. The API checks are the enforcement.

| Screen | Route | Menu group | Roles that see it |
|---|---|---|---|
| `work_queue` | `/work-queue` | Work | clinician, clinic_staff |
| `requests` | `/referrals` | Work | clinician, clinic_staff |
| `incoming` | `/incoming` | Work | clinician, clinic_staff, institution_admin |
| `records_requests` | `/patient-links` | Work | clinic_staff, institution_admin |
| `orders` | `/orders` | Work | diagnostics_staff |
| `rules` | `/rules` | Rules | rule_reviewer |
| `medicine_names` | `/medicine-names` | Rules | rule_reviewer |
| `accounts` | `/admin/users` | Administration | institution_admin |
| `source_access` | `/admin/access` | Administration | institution_admin |
| `audit` | `/admin/audit` | Administration | institution_admin |

| Template | Name | Realm roles | Institution kinds | Default grant days | Home | Menu |
|---|---|---|---|---|---|---|
| `front_desk` | Staff (referral coordinator) | clinic_staff | clinic, hospital | 7 | work_queue | work_queue, requests, incoming, records_requests |
| `doctor` | Doctor | clinician | clinic, hospital | 14 | work_queue | work_queue, requests, incoming |
| `lab_radiology` | Laboratory, radiology or ECG staff | diagnostics_staff | laboratory, hospital, clinic | 7 | orders | orders |
| `institution_administrator` | Institution administrator | institution_admin | clinic, hospital, laboratory | 14 | accounts | accounts, source_access, audit, incoming, records_requests |
| `rule_reviewer` | Clinical rule reviewer | rule_reviewer | clinic, hospital | 14 | rules | rules, medicine_names |

#### npm scripts

| Script | Command |
|---|---|
| `dev` | `vite` |
| `build` | `tsc -b && vite build` |
| `typecheck` | `tsc -b --noEmit` |
| `preview` | `vite preview` |
| `test:e2e` | `playwright test` |

### Identity provider (Keycloak realm `referral`, `infra/keycloak/import/referral-realm.json`)

#### Realm roles

| Role | Meaning |
|---|---|
| `clinician` | Doctor: requests referrals, acknowledges medication flags, receives referrals for their department |
| `clinic_staff` | Staff: patient links, records, papers and medicines; sends referrals; follow-up |
| `diagnostics_staff` | Laboratory, imaging or ECG staff: test and scan orders |
| `institution_admin` | Institution administrator (accounts, source access, audit; no clinical access) |
| `rule_reviewer` | Clinical reviewer who approves medication rules and medicine names |
| `svc_central` | Central platform service identity |
| `svc_provider` | Institution service identity |

#### Clients

| Client | Type | Flows |
|---|---|---|
| referral-web | public | authorization code + PKCE |
| dev-cli | public | password grant (dev only) |
| central-api | confidential | client credentials |
| drali-api | confidential | client credentials |
| chughtai-api | confidential | client credentials |
| ziauddin-api | confidential | client credentials |
| akuh-api | confidential | client credentials |

#### Institutions and departments (groups)

A user's institution is their top-level group; the department is the subgroup.

| Institution group | Department subgroups |
|---|---|
| drali | general_practice, clinic_tests |
| ziauddin | cardiology, gastro_hepatology, radiology, cardiac_diagnostics, laboratory |
| akuh | dentistry, orthopaedics, general_surgery, radiology, laboratory |
| chughtai | laboratory, radiology |

#### Demonstration accounts (synthetic; passwords are not listed)

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

#### Token and session settings

| Setting | Value |
|---|---|
| `accessTokenLifespan` | 300 |
| `ssoSessionIdleTimeout` | 1800 |
| `ssoSessionMaxLifespan` | 36000 |
| `bruteForceProtected` | True |


# Appendix L. Database migrations

_Generated from the code by `scripts/sds/build_sds.py`. Do not edit by hand._

### Database migrations (Alembic, applied at service start: `alembic upgrade head`)

#### `services/central/migrations`

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

#### `services/provider/migrations`

| Order | Revision | Revises | Change | File |
|---|---|---|---|---|
| 1 | `64628844a0ce` | `(base)` | institution schema | `services/provider/migrations/versions/64628844a0ce_institution_schema.py` |
| 2 | `f90a83a36cf0` | `64628844a0ce` | round two: intake, assignment, report images | `services/provider/migrations/versions/f90a83a36cf0_round_two_intake_assignment_report_.py` |
| 3 | `6608cba6436e` | `f90a83a36cf0` | grant expiry and sent copies | `services/provider/migrations/versions/6608cba6436e_grant_expiry_and_sent_copies.py` |
| 4 | `eb77d5fffde7` | `6608cba6436e` | case completion and hold | `services/provider/migrations/versions/eb77d5fffde7_case_completion_and_hold.py` |


# Appendix M. Dependencies

_Generated from the code by `scripts/sds/build_sds.py`. Do not edit by hand._

### Dependencies

#### `services/central/requirements.txt`

| Package |
|---|
| `fastapi==0.115.6` |
| `uvicorn[standard]==0.32.1` |
| `sqlalchemy==2.0.36` |
| `psycopg[binary]==3.2.3` |
| `alembic==1.14.0` |
| `httpx==0.28.1` |
| `pyjwt[crypto]==2.10.1` |
| `pydantic==2.10.3` |
| `python-multipart==0.0.19` |
| `celery[redis]==5.4.0` |
| `anthropic==1.11.0` |
| `pypdfium2==4.30.0` |
| `pytesseract==0.3.13` |
| `pillow==11.0.0` |
| `reportlab==4.2.5` |
| `pytest==8.3.4` |

#### `services/provider/requirements.txt`

| Package |
|---|
| `fastapi==0.115.6` |
| `uvicorn[standard]==0.32.1` |
| `sqlalchemy==2.0.36` |
| `psycopg[binary]==3.2.3` |
| `alembic==1.14.0` |
| `httpx==0.28.1` |
| `pyjwt[crypto]==2.10.1` |
| `pydantic==2.10.3` |

#### `libs/common/pyproject.toml`

| Package |
|---|
| `fastapi>=0.115` |
| `httpx>=0.27` |

#### `web/package.json`

| Package | Version |
|---|---|
| `@emotion/react` | `^11.13.5` |
| `@emotion/styled` | `^11.13.5` |
| `@mui/icons-material` | `^6.1.9` |
| `@mui/material` | `^6.1.9` |
| `@tanstack/react-query` | `^5.62.0` |
| `oidc-client-ts` | `^3.1.0` |
| `react` | `^18.3.1` |
| `react-dom` | `^18.3.1` |
| `react-hook-form` | `^7.53.2` |
| `react-router-dom` | `^6.28.0` |
| `@playwright/test` | `^1.49.0` |
| `@types/react` | `^18.3.12` |
| `@types/react-dom` | `^18.3.1` |
| `@vitejs/plugin-react` | `^4.3.4` |
| `typescript` | `~5.6.3` |
| `vite` | `^6.0.1` |


# Appendix N. Rules and reference data

_Generated from the code by `scripts/sds/build_sds.py`. Do not edit by hand._

### Rules and reference data (`rules/`)

Data files loaded at seed time or read by the services. Large data sets are summarised.

| File | Size | Contents |
|---|---|---|
| `rules/ai/atc-class-names.json` | 55 KB | 0, A, A01, A01A, A01AA, A01AB |
| `rules/ai/ddinter-atc.json` | 57 KB | abacavir: 1, abaloparatide: 1, abametapir (topical): 0, abarelix: 1, abatacept: 1, abciximab: 1 |
| `rules/ai/evaluation.json` | 2 KB | model_version, trained, training_data, known_interactions, drugs, drugs_with_atc |
| `rules/ai/model.json` | 1 KB | model_version, data_version, features: 24, coefficients: 24, intercept, threshold |
| `rules/ai/suggestions.json` | 25 KB | model_version, data_version, threshold, label, suggestions: 66 |
| `rules/interactions/README.md` | 1 KB |  |
| `rules/interactions/ddinter-import-report.json` | 1 KB | imported, files: 8, files_sha256, ddinter_rows, ddinter_drugs, ddinter_drugs_not_mapped_to_our_ingredients |
| `rules/interactions/ddinter-subset.csv` | 28 KB | 342 rows |
| `rules/labels/interaction-quotes.json` | 20 KB | version, extractor_version, content_sha256, status, stats: 4, quotes: 37 |
| `rules/labels/label-rules.json` | 88 KB | version, extractor_version, vocabulary, content_sha256, status, stats: 7 |
| `rules/medication/seed-rules.json` | 6 KB | version, note, rules: 11 |
| `rules/roles/templates.v1.json` | 4 KB | template_set_id, version, note, screens: 10, templates: 5 |
| `rules/sources.json` | 3 KB | note, ddinter: 13, openfda_labels: 6, rxnav: 5, brand_names: 4 |
| `rules/terminology/brand-import-template.csv` | 0 KB | 2 rows |
| `rules/terminology/brand-sources.csv` | 965 KB | 5433 rows |
| `rules/terminology/drap/brand-import.csv` | 689 KB | 6122 rows |
| `rules/terminology/drap/details.jsonl` | 588 KB | 1517 rows |
| `rules/terminology/drap/drugs.csv` | 162 KB | 1360 rows |
| `rules/terminology/drap/products.csv` | 11,643 KB | 115006 rows |
| `rules/terminology/ingredients.json` | 8 KB | version, note, ingredients: 44, codes_retrieved |
| `rules/terminology/medicine-names.pk.json` | 123 KB | version, note, entries: 43, register_ambiguous: 21 |
| `rules/vocab/label-targets.json` | 6 KB | version, note, procedure: 7, condition: 8, severity_by_section: 5 |


# Appendix O. Automated tests

_Generated from the code by `scripts/sds/build_sds.py`. Do not edit by hand._

### Automated tests

113 tests in 21 files.

#### `services/central/tests/test_ai_suggestions.py` (unit (no services), 4)

| Test | What it checks |
|---|---|
| `test_pair_in_interaction_table_is_never_a_suggestion` |  |
| `test_forcing_scores_never_changes_flags` |  |
| `test_suggestions_only_for_current_medicines_and_carry_versions` |  |
| `test_committed_suggestions_exclude_ddinter_pairs_and_are_labelled` |  |

#### `services/central/tests/test_evaluator.py` (unit (no services), 11)

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

#### `services/central/tests/test_flagging.py` (unit (no services), 19)

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

#### `services/central/tests/test_grant_closeout.py` (unit (no services), 2)

| Test | What it checks |
|---|---|
| `test_calls_every_source_with_the_referral_reference` |  |
| `test_one_failing_source_is_reported_and_others_still_run` |  |

#### `services/central/tests/test_lifecycle.py` (unit (no services), 15)

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

#### `services/central/tests/test_ollama_provider.py` (unit (no services), 4)

| Test | What it checks |
|---|---|
| `test_local_model_gets_schema_as_format` |  |
| `test_cloud_model_gets_schema_in_prompt_and_reply_is_checked` |  |
| `test_bad_output_and_errors` |  |
| `test_check_schema_rejects` |  |

#### `services/central/tests/test_privacy.py` (unit (no services), 3)

| Test | What it checks |
|---|---|
| `test_scrubber_removes_identifiers_and_keeps_the_clinical_content` |  |
| `test_cloud_and_remote_models_need_explicit_permission_and_https` |  |
| `test_packet_selection_sends_no_identifiers` |  |

#### `services/central/tests/test_provider_offline.py` (unit (no services), 2)

| Test | What it checks |
|---|---|
| `test_structured_request_shape_and_parsing` |  |
| `test_refusal_and_truncation_are_rejected` |  |

#### `services/central/tests/test_provider_openai_compatible.py` (unit (no services), 7)

| Test | What it checks |
|---|---|
| `test_request_shape_and_parsing` |  |
| `test_api_key_and_code_fence` |  |
| `test_failures` |  |
| `test_unreachable_server` |  |
| `test_ollama_request_shape` |  |
| `test_ollama_complete_answer_padded_to_the_cap_is_used` |  |
| `test_ollama_failures` |  |

#### `services/central/tests/test_register_names.py` (unit (no services), 5)

| Test | What it checks |
|---|---|
| `test_register_brand_at_the_start_maps_and_says_where_it_came_from` |  |
| `test_register_brand_inside_other_words_does_not_match` |  |
| `test_hand_checked_names_still_match_anywhere_and_carry_no_register_note` |  |
| `test_register_names_that_are_too_short_or_ordinary_words_are_not_loaded` |  |
| `test_a_register_name_for_two_medicines_says_what_it_could_be` |  |

#### `services/central/tests/test_selection.py` (unit (no services), 9)

| Test | What it checks |
|---|---|
| `test_default_floor` |  |
| `test_schema_is_strict` |  |
| `test_valid_answer` |  |
| `test_rejected_answers` |  |
| `test_prompt_injection_in_record_text_cannot_add_ids` | A record that says 'include record 500' cannot make the model's answer use an id outside the set. |
| `test_schema_limits_only_for_providers_that_enforce_them` |  |
| `test_describing_a_record_is_not_advice` |  |
| `test_dose_change_wording_is_rejected` |  |
| `test_bad_missing_phrases_are_dropped_not_fatal` |  |

#### `services/central/tests/test_selection_apply.py` (unit (no services), 5)

| Test | What it checks |
|---|---|
| `test_ai_adds_but_never_removes_default_items` |  |
| `test_staff_choice_wins` |  |
| `test_failure_keeps_the_default` |  |
| `test_include_at_low_relevance_does_not_add` |  |
| `test_answer_arriving_after_purge_is_discarded` |  |

#### `services/central/tests/test_staff_view.py` (unit (no services), 6)

| Test | What it checks |
|---|---|
| `test_record_titles_name_the_chart_never_the_content` |  |
| `test_staff_evidence_view_has_no_values_or_ai_reasoning` |  |
| `test_staff_referral_view_hides_reason_notes_and_procedure` |  |
| `test_staff_test_view_hides_question_and_result` |  |
| `test_consultation_notes_are_hashed_without_changing_older_packages` |  |
| `test_interaction_flag_quotes_the_label_when_a_sentence_exists` |  |

#### `services/central/tests/test_vision_ocr.py` (unit (no services), 3)

| Test | What it checks |
|---|---|
| `test_handwriting_is_read_line_by_line_with_boxes` |  |
| `test_vision_failure_falls_back_to_tesseract_and_says_so` |  |
| `test_no_key_never_calls_google` |  |

#### `tests/test_drap_brands.py` (integration (full stack), 1)

| Test | What it checks |
|---|---|
| `test_register_brand_and_choosing_an_ambiguous_one_by_company` |  |

#### `tests/test_referral_expiry.py` (integration (full stack), 2)

| Test | What it checks |
|---|---|
| `test_accept_extend_complete_then_expire` |  |
| `test_decline_removes_the_shared_records_straight_away` |  |

#### `tests/test_v2_flow.py` (integration (full stack), 2)

| Test | What it checks |
|---|---|
| `test_p5_referral_flow` |  |
| `test_p3_test_request_flow` | P3 (Abdul Rehman Gondal): MRI knee at AKUH radiology (never seen there) and blood tests at Chughtai Lab (known there). |

#### `tests/test_v2_scenarios.py` (integration (full stack), 5)

| Test | What it checks |
|---|---|
| `test_scenario_flags` |  |
| `test_imported_flags_show_source_and_decisions_are_logged` | P3: DDInter interactions and drug-label flags carry their source; Ignore and Research are logged with the rule-set version, and an ignored flag stays in the record. |
| `test_procedure_without_features_is_not_checked` | A procedure written without saying what it involves: procedure rules are not run, and say so. |
| `test_p2_every_linked_hospital_and_stopped_medicine` | P2 was seen at AKUH (Aug 2026) and at Ziauddin radiology (Oct 2026): both are read, so his history is not cut to the last hospital visited. Diclofenac was stopped and must not appear as a current medicine. |
| `test_uploaded_prescription_merges_with_recorded_medicines` | P5's cardiology prescription (photo) lists the same medicines as the clinic record: after staff check the read fields, each medicine is shown once. |

#### `tests/test_v3_lifecycle.py` (integration (full stack), 5)

| Test | What it checks |
|---|---|
| `test_grants_are_temporary` |  |
| `test_role_menus` |  |
| `test_admin_assigns_a_role_by_template` | An institution administrator turns a lab account into front-desk staff and back. The change is made in Keycloak, so it applies on the user's next sign-in, and it is audited. |
| `test_selection_manifest_own_copy_and_purge` |  |
| `test_default_selection_matches_seed_expected_view` | The rule-based default (no model) selects exactly the visits from the last 6 months listed in the seed's expected_retrieval_view; older visits are retrieved but start unselected. |

#### `web/e2e/admin.spec.ts` (browser end-to-end (Playwright), 1)

| Test | What it checks |
|---|---|
| `administrator changes a role with a template; the menu follows on the next sign-in` |  |

#### `web/e2e/smoke.spec.ts` (browser end-to-end (Playwright), 2)

| Test | What it checks |
|---|---|
| `referral: doctor requests, staff prepare, doctor reviews flags, staff send, hospital takes it in and responds` |  |
| `test request: MRI at Aga Khan radiology with images, result back to the doctor` |  |


# Appendix P. Decision records and invariants

_Generated from the code by `scripts/sds/build_sds.py`. Do not edit by hand._

### Decision records (`docs/decisions`)

Design decisions taken after the SRS, newest last. Each record states what was decided and why.

| Record | Title | Status |
|---|---|---|
| [2026-10-27-data-lifecycle-and-v3](../decisions/2026-10-27-data-lifecycle-and-v3.md) | Decision: data lifecycle, AI packet selection and role screens (spec v3) | approved by the project lead (repository owner); **the supervisor gave the go-ahead on 2026-10-27** (reported by the project lead), and v2 with this change was merged into `main`. Module owners should still record their |
| [2026-10-28-cloud-model-privacy](../decisions/2026-10-28-cloud-model-privacy.md) | Decision: Gemma 4 through Ollama's cloud, with patient data de-identified | decided by the project lead on 2026-10-28. Built the same day. The live model call needs |
| [2026-10-28-drap-brands-loaded](../decisions/2026-10-28-drap-brands-loaded.md) | Decision: load the DRAP register brand names as verified mappings | decided by the project lead on 2026-10-28, against the reviewer step in |
| [2026-10-28-drap-register-snapshot](../decisions/2026-10-28-drap-register-snapshot.md) | Decision: local snapshot of the DRAP product register | agreed by all three members (reported by the project lead on 2026-10-28). This replaces the "Do not scrape" rule in `scripts/import_brands.py`. |
| [2026-10-28-handwriting-ocr](../decisions/2026-10-28-handwriting-ocr.md) | Decision: read handwritten prescriptions with Google Cloud Vision | decided by the project lead on 2026-10-28. Built the same day. Not yet tried against the real |
| [2026-10-28-no-specialist-response](../decisions/2026-10-28-no-specialist-response.md) | Decision: the receiving doctor accepts or declines; no specialist response | decided by the project lead on 2026-10-28. Built the same day. |
| [2026-10-28-referral-access-window](../decisions/2026-10-28-referral-access-window.md) | Decision: shared records are viewed through the platform, for an access window the referred doctor sets | agreed by the project team (reported by the project lead on 2026-10-28). Not yet built. **Section 3 (the 7/30/90-day window) is replaced by [2026-10-28-referral-expiry.md](2026-10-28-referral-expiry.md)**, which is built |
| [2026-10-28-referral-expiry](../decisions/2026-10-28-referral-expiry.md) | Decision: a referral's shared records expire when the referred doctor has finished with it | decided by the project lead on 2026-10-28. Built and tested the same day. |
| [2026-10-28-retrieval-all-sources](../decisions/2026-10-28-retrieval-all-sources.md) | Decision: retrieve from every linked institution, with limits by count and specialty | agreed by the project team (reported by the project lead on 2026-10-28). Step 1 is built. Steps 2 to 4 are planned. |
| [2026-10-29-doctor-only-clinical-content](../decisions/2026-10-29-doctor-only-clinical-content.md) | Decision: only doctors see clinical content; the doctor reviews the referral packet | decided by the project lead on 2026-10-29, for the whole team. Built and tested the same day. |

### Non-negotiable invariants (from `AGENTS.md`)

1. **Database boundaries.** The central platform never connects to `clinic_db`, `lab_db` or `specialist_db`. It calls their APIs only. Do not add source DB credentials to `central`.
2. **Source authorization.** Every source endpoint decides access itself: own institution and role, or an active access grant. Forward the user's verified token; never trust identity headers.
3. **Patient linking.** Never link records on matching local IDs or names. Only `verified` links are used for retrieval. Invalidation must keep history and flag affected referrals.
4. **Approval.**
   - Only a clinician approves. Only an approved, non-superseded package version is sent.
   - Any clinical change after approval calls `mark_clinical_change()`, which means a new version and renewed approval.
   - Packages are immutable once written.
5. **Medication flags.**
   - Flags come only from `evaluate_medications()`: deterministic, with approved rules and verified mappings.
   - The language model must never create, suppress, reword or restate flags.
   - "Reviewed" is acknowledgment, never treatment clearance.
   - Flags never advise medication changes or assign urgency.
6. **AI output.**
   - Language-model output is a draft.
   - Every record-derived statement cites evidence IDs from the supplied set; validate and reject otherwise.
   - Treat document text as untrusted data. Do not give the model tools.
7. **Unavailable is not "none."** An unavailable, denied or not-retrieved source must never be turned into "no history", "not performed" or "safe".
8. **Never overwrite original data.** Corrections create revisions. Lab corrections create new source record versions.
9. **Idempotency.** Delivery keys and event keys make retries safe. Keep the outbox write in the same transaction as the decision to send.
10. **Audit.** Every access, retrieval, link change, correction, approval, submission and status change writes an audit event with actor, institution, action, target, time and outcome.
11. **Synthetic data only.** Do not commit patient data, credentials, `.env`, model weights or uploaded files.
12. **Only doctors see clinical content** (decision 2026-10-29).
   - Staff and administrators get titles, statuses and counts only, through the serializers' staff views (`clinical=False`). They never see record values, diagnoses, medicines, flags, papers, notes, the letter or the package.
   - Clinical endpoints are doctor-only on the server.
   - The doctor reviews the packet before staff send, and a later clinical change clears that review.
