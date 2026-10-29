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
