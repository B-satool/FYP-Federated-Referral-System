# Referral Preparation and Follow-through Platform

FYP prototype. A referring clinic prepares a verified referral package. Medications relevant to the receiving specialty and planned procedure are highlighted. The package goes to a specialist, missing information is resolved, and the response and follow-up are tracked to closure.

All data is **synthetic**. This is not a clinical system.

| | |
|---|---|
| Requirements | `docs/requirements/FYP SRS.pdf` (FR-01 to FR-72) |
| Implementation guide | `docs/requirements/FYP Development Roadmap.pdf` |
| Scope decisions (Stage 0) | [docs/architecture.md](docs/architecture.md) |
| Supervisor demo walkthrough | [docs/demo-script.md](docs/demo-script.md) |
| Requirement → code → test traceability | [docs/traceability.md](docs/traceability.md) |
| Test checkpoints T0–T7 and results | [docs/testing.md](docs/testing.md) |
| Operations: deploy, backup/restore, retention, revocation | [docs/operations.md](docs/operations.md) |
| OCR / AI evaluation | [docs/evaluation.md](docs/evaluation.md) |
| Supported FHIR subset | [docs/fhir-subset.md](docs/fhir-subset.md) |

## Architecture in one picture

```
 Browser (React + MUI)  ──OIDC code+PKCE──►  Keycloak (identity)
        │ /api/central /api/clinic /api/lab /api/specialist (nginx)
        ▼
 ┌──────────────────────── central platform (FastAPI, modular monolith) ───────────────────────┐
 │ referrals · identity/links · integration (adapters client + FHIR importer) · documents      │
 │ evidence · medications (mapping + deterministic rules) · checklist · brief generation       │
 │ approvals/packages · delivery outbox · inbound events · follow-up · audit                   │
 └──────┬───────────────────────────┬───────────────────────────────┬──────────────────────────┘
        │ HTTPS API only (never DBs) │ Celery worker (OCR, LLM,       │ PostgreSQL central_db
        ▼                            │ delivery outbox) via Redis     ▼ + protected file volume
 Clinic A service ── clinic_db   Lab B service ── lab_db   Specialist C service ── specialist_db
 (own adapter + own access decisions, FHIR R4 4.0.1 subset)
```

Each source service owns its database and decides access itself. The central platform calls source APIs with the user's verified token and never reads source databases directly.

## Quick start (Windows PowerShell; macOS/Linux use the `.sh` scripts)

Prerequisites: Docker Desktop (about 4 GB RAM for Docker) and Git. Python 3.11+ and Node 20+ are needed only for the tests.

```powershell
Copy-Item .env.example .env           # set your own secrets; optionally ANTHROPIC_API_KEY
docker compose up -d --build          # first build takes several minutes
.\scripts\reset-and-seed.ps1 -Force   # deterministic synthetic data in every owner's database
```

Open **http://localhost:3000** and sign in with one of these accounts (password `demo1234`, or `DEMO_USER_PASSWORD` from `.env`):

| Username | Institution | Role | Use it to… |
|---|---|---|---|
| `staff.a` | Clinic A | clinic staff / coordinator | create drafts, retrieve records, upload documents, request information |
| `dr.malik` | Clinic A | referring clinician | verify evidence and medication use, review flags, approve and send, review response |
| `dr.reviewer` | Clinic A | clinician + **rule reviewer** | approve the draft medication rules (required before flags appear) |
| `admin.a` | Clinic A | institution administrator | accounts, Clinic A source access grants, audit, link corrections (no clinical access) |
| `lab.b` | Lab B | laboratory staff | answer information requests, correct results |
| `admin.b` | Lab B | administrator | Lab B access grants and audit |
| `dr.ortho` | Specialist C | specialist | acknowledge, review flags, accept or decline, respond |
| `admin.c` | Specialist C | administrator | Specialist C access grants and audit |
| `staff.x` | Clinic X | other clinic | demonstrates cross-institution denial |
| `dr.locum` | Clinic A | clinician | used by the account-revocation test |

The API documentation is generated from the implementation. You can open the OpenAPI docs for each service directly: central http://localhost:8000/docs · clinic :8001/docs · lab :8002/docs · specialist :8003/docs.

### Language model (optional)

Put `ANTHROPIC_API_KEY=...` in `.env` and run `docker compose up -d central worker` to enable "Draft with AI" (model `claude-opus-5-5`) and model-based field extraction. Without a key the platform still works fully:
- Generation fails visibly.
- The **evidence template** and **manual editor** remain available.
- Document fields come from the deterministic rule-based extractor.

This is by design (FR-58).

## Running the checks

```powershell
python -m venv .venv; .\.venv\Scripts\pip install httpx pytest
.\.venv\Scripts\python -m pytest tests -q                       # T1–T7 API integration checks (reseeds first)
docker compose run --rm --no-deps -v ${PWD}/services/central/tests:/srv/tests central python -m pytest tests -q   # rule table + AI guardrails
cd web; npm ci; npx playwright install chromium; npx playwright test e2e/smoke.spec.ts   # 3 browser smoke journeys
.\.venv\Scripts\python scripts\loadtest.py --users 10 --seconds 60                          # p95 < 2 s target
.\scripts\backup.ps1; .\scripts\restore-check.ps1 -BackupDir backups\<timestamp>          # restore into a disposable environment
```

## Repository layout

```
web/                    React application (role-specific screens) + Playwright smoke journeys
services/central/       Central API + Celery worker (same image), Alembic migrations, unit tests
services/clinic|lab|specialist/   Independent source services: own DB, adapter, access grants, seed
libs/common/            Shared token verification, pinned FHIR subset, exchange envelopes
contracts/              Published request/response examples and FHIR samples
rules/                  Versioned medication rules (drafts), checklist, terminology dictionary
samples/, evaluation/   Synthetic documents; OCR dev/held-out sets and results
infra/                  PostgreSQL init (one DB + login per owner), Keycloak realm import
scripts/                Reset/seed, backup/restore check, load test, FHIR validation, evaluation
tests/                  Stage checkpoint integration checks (T1–T7)
docs/                   Decisions, demo script, traceability, operations, evaluation
worker/                 Notes on the background worker
```
