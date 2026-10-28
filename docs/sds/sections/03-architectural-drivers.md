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

Some invariants were changed by recorded decisions: the temporary working set (2026-10-27), referral expiry (2026-10-28) and the DRAP brand load (2026-10-28). Appendix P lists the records.
