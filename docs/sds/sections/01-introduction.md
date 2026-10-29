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
