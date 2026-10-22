# FYP Federated Referral System
### Referral Preparation and Follow-through Platform

A web application that helps a **referring clinic** prepare a verified referral for a **specialist**. It pulls the patient's records from three independent hospital systems (clinic, laboratory, specialist) and reads uploaded paper documents with OCR. It highlights medications that matter for the planned procedure. It then tracks the referral through the specialist's response and follow-up until closure.

> **Prototype with synthetic (fake) patient data only. Not for clinical use.**

| Document | Where |
|---|---|
| Requirements (SRS, FR-01 to FR-72) | [`docs/requirements/FYP SRS.pdf`](docs/requirements/FYP%20SRS.pdf) |
| Development roadmap | [`docs/requirements/FYP Development Roadmap.pdf`](docs/requirements/FYP%20Development%20Roadmap.pdf) |
| Step-by-step demo / test walkthrough | [`docs/demo-script.md`](docs/demo-script.md) |
| Which code and test covers each SRS requirement | [`docs/traceability.md`](docs/traceability.md) |
| Design decisions (Stage 0) | [`docs/architecture.md`](docs/architecture.md) |
| Web interface redesign: issues, flow, compliance notes | [`docs/ui-redesign.md`](docs/ui-redesign.md) |
| Test results and known limitations | [`docs/release-notes.md`](docs/release-notes.md), [`docs/testing.md`](docs/testing.md) |
| Deployment, backup/restore, security operations | [`docs/operations.md`](docs/operations.md) |

---

## 1. What runs, and why Docker

The system is **9 programs that run together**:

| Container | What it is | Port on your PC |
|---|---|---|
| `web` | The website (React), served by nginx | **3000** |
| `central` | Central referral platform API (Python / FastAPI) | 8000 |
| `clinic` | Clinic A's own system and API | 8001 |
| `lab` | Lab B's own system and API | 8002 |
| `specialist` | Specialist C's own system and API | 8003 |
| `worker` | Background jobs: OCR on uploads, AI drafting, sending referrals | — |
| `keycloak` | Login server (accounts, passwords, roles) | **8080** |
| `postgres` | PostgreSQL: one database per system, each with its own login | (5432, optional) |
| `redis` | Job queue for the worker | — |

**Why Docker?** Without it, every teammate would have to install and configure Python, Node.js, PostgreSQL, Redis, Java, Keycloak and the Tesseract OCR engine at matching versions. Docker packages all of that so **one command** starts the whole system identically on any computer. It also keeps the clinic, lab and specialist systems genuinely separate, as the SRS requires.

**End users (doctors, staff) never touch Docker.** In a real deployment, IT runs these containers once on a server and users simply open the website address in a browser. On your laptop, *you* are both the IT person and the user, which is why you see the Docker side.

**Put it online for free:** [`docs/deploy-cloud.md`](docs/deploy-cloud.md) explains how to run it on an Oracle Cloud Always Free server with HTTPS. You get a public link and nobody else installs anything; on the server it's one command, `bash scripts/deploy-server.sh`.

---

## 2. Run it on your computer

### Prerequisites (install once)
1. **[Docker Desktop](https://www.docker.com/products/docker-desktop/)**: install it, start it, and wait until it says *"Engine running"*. It needs about 4 GB of RAM.
2. **[Git](https://git-scm.com/downloads)**
3. *Only for running the automated tests:* **Python 3.11+** and **Node.js 20+**.

### First time
Open **PowerShell** (Windows) or a terminal (macOS/Linux):

```powershell
git clone https://github.com/B-satool/FYP-Federated-Referral-System.git
cd FYP-Federated-Referral-System

# 1. Create your local settings file from the template (defaults work for a local demo)
Copy-Item .env.example .env          # macOS/Linux: cp .env.example .env

# 2. Build and start everything (first build takes 5–10 minutes)
docker compose up -d --build

# 3. Wait until the services say "healthy" (Keycloak takes about 1 minute)
docker compose ps

# 4. Load the synthetic demo patients into every system's database
.\scripts\reset-and-seed.ps1 -Force   # macOS/Linux: sh scripts/reset-and-seed.sh --force
```

Then open **http://localhost:3000**, click **Sign in with your institution account**, and log in with an account from section 3.

### Every day after that

| What | Command (in the project folder) |
|---|---|
| Start | Open Docker Desktop, then `docker compose up -d` |
| Stop (data is kept) | `docker compose stop` |
| Reset to clean demo data (before a demo) | `.\scripts\reset-and-seed.ps1 -Force` |
| See what's running | `docker compose ps` |
| See errors | `docker compose logs -f central` (or `web`, `worker`, `keycloak`, `clinic`, …) |
| After pulling new code | `git pull` then `docker compose up -d --build` |
| Delete everything including data | `docker compose down -v` (**permanent**) |

---

## 3. Access: logins, addresses, databases

### Demo user accounts (password for all: `demo1234`)

| Username | Person | Institution | What they do |
|---|---|---|---|
| `staff.a` | Hina Raza | Clinic A | Receptionist: creates referrals, uploads documents, asks for information |
| `dr.malik` | Dr Sana Malik | Clinic A | Referring doctor: checks medicines, approves and sends, reviews the reply |
| `dr.reviewer` | Dr Omar Farooq | Clinic A | Senior doctor who approves the medication rules (one-time setup) |
| `admin.a` | Adeel Shah | Clinic A | IT admin: accounts, access, audit (no access to patient records) |
| `lab.b` | Kamran Butt | Lab B | Lab technician: answers questions, corrects results |
| `admin.b` | Nadia Aslam | Lab B | Lab admin |
| `dr.ortho` | Dr Faisal Haider | Specialist C | Orthodontist: receives, accepts or declines, responds |
| `admin.c` | Rabia Javed | Specialist C | Specialist admin |
| `staff.x` | Zara Iqbal | Clinic X | Another clinic; shows that clinics can't see each other's data |
| `dr.locum` | Dr Usman Tariq | Clinic A | Used to test disabling an account |

### Admin and developer addresses

| What | Address | Login |
|---|---|---|
| The web app | http://localhost:3000 | Accounts above |
| Keycloak admin console | http://localhost:8080/admin | `admin` / value of `KEYCLOAK_ADMIN_PASSWORD` in `.env` (default `change-me-kc-admin`) |
| API docs (Swagger) | Central http://localhost:8000/docs · Clinic :8001/docs · Lab :8002/docs · Specialist :8003/docs | Bearer token |

### Local database (on your own computer)
By default the database is only reachable inside Docker. To open it to tools on your computer (pgAdmin, DBeaver) at `localhost:5432`, start with the extra file:

```powershell
docker compose -f docker-compose.yml -f docker-compose.dbaccess.yml up -d
```

| Database | Username | Password (default from `.env`) | Contains |
|---|---|---|---|
| `central_db` | `central` | `change-me-central` | Referrals, evidence, medication flags, approved packages, audit |
| `clinic_db` | `clinic` | `change-me-clinic` | Clinic A patients, prescriptions, conditions |
| `lab_db` | `lab` | `change-me-lab` | Lab B results and reports |
| `specialist_db` | `specialist` | `change-me-specialist` | Specialist C incoming referrals and responses |
| `keycloak` | `keycloak` | `change-me-keycloak` | Login accounts (use the Keycloak console instead) |
| any | `postgres` | `change-me-postgres` | Superuser |

Without a database tool, use: `docker compose exec postgres psql -U central -d central_db`

These defaults are only safe because the database is reachable from your own machine only. **Change every value in `.env` before running this anywhere shared.**

### Shared team database on Neon (cloud PostgreSQL)

So that teammates can look at the data from anywhere, a **copy** of the demo databases is published to a free cloud PostgreSQL on [Neon](https://neon.tech):

- **Neon project:** *Federated referral system* (owner: Eesha), region AWS US East 2.
- **What's in it:** `central_db`, `clinic_db`, `lab_db` and `specialist_db`. Each has its own login (`ref_central`, `ref_clinic`, `ref_lab`, `ref_specialist`), and each login can open only its own database, the same separation as the real system.
- **Getting the credentials:** host, passwords and connection strings are in **`shared-db-credentials.md`**. That file is deliberately **not in GitHub** (it's git-ignored, because the repo would expose the passwords). Ask Eesha to send it privately.
- **Connecting with DBeaver or pgAdmin:** new PostgreSQL connection with the host from the sheet, port `5432`, database / username / password from the sheet, and **SSL mode `require`**.
- **It's a snapshot, not live.** The app keeps running on each person's fast local database. Whoever holds the credentials refreshes the shared copy with:
  ```powershell
  .\scripts\publish-shared-db.ps1
  ```
  Each publish **replaces** the shared copy, so anything changed directly in Neon is overwritten. Login accounts (Keycloak) and uploaded document files are not copied.
- **Why the app doesn't run on Neon directly:** the project is in the US, and each query from Pakistan takes about 240 ms. This app makes 30–60 queries per screen, so pages would take 10+ seconds. To share a *live* database instead, create a Neon project in **AWS Singapore (ap-southeast-1)** and run the setup script without `--copy-only`. It then writes `*_DATABASE_URL` lines into `.env` that point the app at Neon.
- **Setting it up again (new Neon project or new owner):**
  1. In Neon, copy the **direct** (not "pooled") connection string of the owner role.
  2. Run:
     ```powershell
     docker compose run --rm --no-deps -v ${PWD}:/repo central python /repo/scripts/setup_shared_db.py --copy-only "postgresql://OWNER:PASSWORD@HOST/neondb?sslmode=require"
     .\scripts\publish-shared-db.ps1
     ```
  This creates the four databases with new random passwords, writes `*_SHARED_DATABASE_URL` lines into `.env`, and writes a fresh `shared-db-credentials.md`.

### AI brief drafting (optional)
"Draft with AI" uses Claude (`claude-opus-5-5`). Add your key to `.env`:
```
ANTHROPIC_API_KEY=sk-ant-...
```
then run `docker compose up -d central worker`. Keys come from https://console.anthropic.com. **Without a key everything still works:** the AI button reports that no model is configured, and doctors use **Start from evidence template** or write the letter manually. The SRS (FR-58) requires that manual path.

---

## 4. Try the full workflow

[`docs/demo-script.md`](docs/demo-script.md) walks through one complete referral, role by role:
1. **One-time setup:** `dr.reviewer` approves the 5 medication rules under **Medication rules**. Until then no medication warnings appear (SRS FR-61).
2. **Hina** (`staff.a`) creates a referral for **Ayesha Khan**, retrieves records, uploads `samples/documents/prescription_cardiology_digital.pdf`, links her Specialist C record (`SP-7781`) and asks Lab B a question.
3. **Kamran** (`lab.b`) answers from his **Work queue**.
4. **Dr Sana** (`dr.malik`):
   - verifies the link and the document
   - confirms current medicines, which raises the warfarin + extraction warning
   - resolves the 5 mg vs 7.5 mg conflict
   - approves and sends
5. **Dr Faisal** (`dr.ortho`) acknowledges, reviews the warnings, accepts, and returns a response.
6. **Dr Sana and Hina** review the response, complete the follow-up task and **close** the referral. The **Audit trail** shows every step.

Sample documents (synthetic) for testing uploads are in [`samples/documents/`](samples/documents/).

---

## 5. Automated tests

```powershell
python -m venv .venv
.\.venv\Scripts\pip install httpx pytest

# API checks for every SRS workflow (resets demo data first). Expect: 29 passed, 1 skipped (AI, no key)
.\.venv\Scripts\python -m pytest tests -q

# Medication-rule logic and AI safety checks. Expect: 37 passed
docker compose run --rm --no-deps -v ${PWD}/services/central/tests:/srv/tests central python -m pytest tests -q

# Browser robot: 3 full journeys in Chrome. Expect: 3 passed
cd web; npm ci; npx playwright install chromium; npx playwright test e2e/smoke.spec.ts; cd ..

# 10-user load test (target: 95% of requests under 2 s)
docker compose run --rm --no-deps -v ${PWD}:/repo -e REPO=/repo -e CENTRAL_URL=http://central:8000 -e KEYCLOAK_URL=http://keycloak:8080 central python /repo/scripts/loadtest.py

# Backup, then restore into a throwaway environment and verify
.\scripts\backup.ps1
.\scripts\restore-check.ps1 -BackupDir backups\<timestamp-folder>
```

Latest results: [`docs/release-notes.md`](docs/release-notes.md).

---

## 6. Troubleshooting

| Problem | Fix |
|---|---|
| Login page says **"We are sorry… An internal server error has occurred"** | Keycloak lost its database connection (usually after the database restarted). Run `docker compose restart keycloak`, wait about 1 minute, and refresh. |
| `docker compose` says it can't connect | Docker Desktop isn't running. Start it and wait for *Engine running*. |
| Page shows **"Not Found"** after rebuilding | Run `docker compose up -d` to make sure every service is up, then refresh. |
| Port already in use (3000, 8000–8003, 8080, 5432) | Another program uses it. Close it, or change the left-hand port in `docker-compose.yml`. |
| Very slow or out of memory | Give Docker Desktop at least 4 GB (Settings → Resources) and close other heavy apps. |
| No medication warnings appear | The rules aren't approved yet. Sign in as `dr.reviewer` → **Medication rules** → approve all 5. |
| Data looks messy after testing | `.\scripts\reset-and-seed.ps1 -Force` |

---

## 7. What's in the repository

```
web/                              React website (all screens) + Playwright browser tests
services/central/                 Central platform API + background worker, database migrations, unit tests
services/clinic|lab|specialist/   The three independent systems: own database, FHIR adapter, access rules, demo data
libs/common/                      Shared code: login-token checks, FHIR rules, message formats
rules/                            Medication rules (drafts), referral checklist, medicine dictionary
samples/documents/                Synthetic test documents (PDF, scanned image, unreadable, invalid)
evaluation/                       OCR test sets and results
infra/                            Database setup and Keycloak accounts/roles configuration
scripts/                          Reset/seed, backup/restore, Neon setup/publish, load test, FHIR validation
tests/                            End-to-end API checks (T1–T7)
contracts/                        Example data formats and FHIR samples (+ HL7 validator report)
docs/                             All documentation (see table at the top)
docker-compose.yml                Defines all 9 containers
docker-compose.dbaccess.yml       Optional: open the database to your own computer
.env.example                      Settings template; copy to .env (never commit .env)
```

## 8. Known limitations (be upfront in demos)

- **Synthetic data and provisional decisions.** Orthodontics, the medication classes and the checklist rules were chosen to build the prototype. The medication rules were drafted with AI help and need sign-off by a real clinician.
- **OCR** was tested only on clean machine-generated documents. There's no claim about handwriting.
- **AI drafting** is untested until an API key is added.
- **Not production-hardened:** it runs over HTTP on localhost with demo passwords. See [`docs/operations.md`](docs/operations.md) for what a real hosted deployment needs.
