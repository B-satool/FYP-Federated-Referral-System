# FYP Federated Referral System
### Referral Preparation and Follow-through Platform (version 2)

A web application for referring a patient from one clinic or hospital in Karachi to a doctor or department at another, or for requesting a test or scan from a laboratory or radiology department elsewhere.
- **Doctor:** chooses a referral or a test/scan request and fills it in. For a referral, the doctor later reviews the medication flags.
- **Referring staff:**
  - gather the patient's records from the most recently visited hospital, clinic and laboratory
  - check the papers the patient brought (OCR)
  - confirm the current medicines, including over-the-counter ones
  - mark the referral ready for the doctor, then send it once the doctor has reviewed the flags
  - send test and scan orders
- **Receiving staff:** take the referral in, confirm the patient (match their record or register them as new) and assign a doctor. Laboratory and radiology staff confirm the patient on orders the same way.
- **Platform:**
  - checks every current medicine against the planned procedure (reviewer-approved rules), against each other (DDInter interactions) and against the procedure and recorded conditions (rules read from US drug labels), showing the source of every flag
  - sends the referral as a readable letter, and results back with their report and images
  - tracks each request through the response or results and follow-up until closure

> **Synthetic (fake) patient data only. Not for clinical use.** The institution names are used only as source-system names; nothing comes from those organisations.

| Document | Where |
|---|---|
| **What changed in version 2, and differences from the SRS** | [`docs/v2-changes.md`](docs/v2-changes.md) |
| Medication flags: DDInter interactions, drug-label rules, sources and coverage | [`docs/medication-flagging.md`](docs/medication-flagging.md) |
| Requirements (SRS) | [`docs/requirements/FYP SRS.pdf`](docs/requirements/FYP%20SRS.pdf) |
| Development roadmap | [`docs/requirements/FYP Development Roadmap.pdf`](docs/requirements/FYP%20Development%20Roadmap.pdf) |
| Seed patients (5 synthetic Karachi patients) and their expected results | [`seed-data/README.md`](seed-data/README.md) |
| Design decisions (version 1; see v2-changes for what differs) | [`docs/architecture.md`](docs/architecture.md) |
| Deployment, backup/restore, security operations | [`docs/operations.md`](docs/operations.md) |

---

## 1. What runs, and why Docker

The system is **11 programs that run together**:

| Container | What it is | Port on your PC |
|---|---|---|
| `web` | The website (React), served by nginx | **3000** |
| `central` | Central referral platform API (Python / FastAPI) | 8000 |
| `drali` | Dr Ali's Clinic, Clifton: its own patient records and API | 8001 |
| `chughtai` | Chughtai Lab: its own records, test orders | 8002 |
| `ziauddin` | Ziauddin Hospital: records, incoming referrals, lab and radiology orders | 8003 |
| `akuh` | Aga Khan University Hospital: the same | 8004 |
| `worker` | Background jobs: OCR on uploads, sending referrals, orders and results | none |
| `keycloak` | Login server (accounts, passwords, roles, departments) | **8080** |
| `postgres` | PostgreSQL: one database per institution, each with its own login | (5432, optional) |
| `redis` | Job queue for the worker | none |

The four institution containers run **the same program**, each configured as a different institution with its own database. The central platform never touches their databases; it calls their APIs, and each institution decides who may see what.

**Why Docker?** Without it, every teammate would have to install and configure Python, Node.js, PostgreSQL, Redis, Java, Keycloak and the Tesseract OCR engine at matching versions. Docker packages all of that so **one command** starts the whole system identically on any computer.

**End users (doctors, staff) never touch Docker.** In a real deployment, IT runs these containers once on a server and users open the website in a browser. Free hosting: [`docs/deploy-cloud.md`](docs/deploy-cloud.md) (`bash scripts/deploy-server.sh` on an Oracle Always Free server).

---

## 2. Run it on your computer

### Prerequisites (install once)
1. **[Docker Desktop](https://www.docker.com/products/docker-desktop/)**: start it and wait for *"Engine running"*. Give it at least 4 GB of RAM.
2. **[Git](https://git-scm.com/downloads)**
3. *Only for the automated tests:* **Python 3.11+** and **Node.js 20+**.

### First time
```powershell
git clone https://github.com/B-satool/FYP-Federated-Referral-System.git
cd FYP-Federated-Referral-System

# 1. Local settings from the template (defaults work for a local demo)
Copy-Item .env.example .env          # macOS/Linux: cp .env.example .env

# 2. Build and start everything (first build 5-10 minutes)
docker compose up -d --build

# 3. Wait until everything says "healthy" (Keycloak takes about 1 minute)
docker compose ps

# 4. Load the five synthetic patients into every institution's database
.\scripts\reset-and-seed.ps1 -Force   # macOS/Linux: sh scripts/reset-and-seed.sh --force
```

Open **http://localhost:3000**, click **Sign in with your institution account**, and use an account from section 3.

**Coming from version 1?** Version 2 uses different databases and accounts. Run `docker compose down -v` once (this deletes the old demo data), add the new `DRALI_*`, `CHUGHTAI_*`, `ZIAUDDIN_*` and `AKUH_*` lines from `.env.example` to your `.env`, then follow the steps above.

### Every day after that

| What | Command (in the project folder) |
|---|---|
| Start | Open Docker Desktop, then `docker compose up -d` |
| Stop (data is kept) | `docker compose stop` |
| Reset to clean demo data (before a demo) | `.\scripts\reset-and-seed.ps1 -Force` |
| See errors | `docker compose logs -f central` (or `web`, `worker`, `akuh`, …) |
| After pulling new code | `git pull` then `docker compose up -d --build` |
| Delete everything including data | `docker compose down -v` (**permanent**) |

---

## 3. Access: logins, addresses, databases

### Demo accounts (password for all: `demo1234`)

| Username | Person | Institution, department | What they do |
|---|---|---|---|
| `dr.ali` | Dr Ali Raza | Dr Ali's Clinic, General practice | **Doctor**: makes referrals and test requests, reviews medication flags, sees results, reviews the response |
| `staff.ali` | Hina Raza | Dr Ali's Clinic | **Staff**: retrieves records, checks papers and medicines, sends referrals and test orders, follow-up; takes in referrals sent to the clinic |
| `tech.ali` | Bilal Ahmed | Dr Ali's Clinic, in-clinic tests (ECG) | Test orders done at the clinic |
| `admin.ali` | Adeel Shah | Dr Ali's Clinic | Administrator: accounts, record sharing, audit (no patient records) |
| `dr.asma` | Dr Asma Rauf | Ziauddin, Cardiology | Receives cardiology referrals; can also refer |
| `dr.irfan` | Dr Irfan Siddiqui | Ziauddin, Gastroenterology and Hepatology | Receives GI and liver referrals |
| `staff.zia` | Kiran Shah | Ziauddin | Takes in incoming referrals and assigns a doctor; answers records requests; prepares Ziauddin's own referrals |
| `rad.zia` | Dr Hira Anwar | Ziauddin, Radiology | Imaging orders: accept or reject, schedule, report |
| `tech.zia` | Usman Ali | Ziauddin, Cardiac diagnostics | ECG and echo orders |
| `lab.zia` | Rabia Qureshi | Ziauddin, Laboratory | Laboratory orders |
| `dr.faisal` | Dr Faisal Haider | Aga Khan, Dentistry | Receives dental and oral surgery referrals |
| `dr.salman` | Dr Salman Akhtar | Aga Khan, Orthopaedics | Receives orthopaedic referrals |
| `dr.naveed` | Dr Naveed Baig | Aga Khan, General Surgery | Receives general surgery referrals |
| `staff.aku` | Mariam Noor | Aga Khan | Takes in incoming referrals, confirms the patient, assigns a doctor; answers records requests |
| `rad.aku` | Dr Sana Javed | Aga Khan, Radiology | Imaging orders |
| `lab.aku` | Kamran Butt | Aga Khan, Laboratory | Laboratory orders |
| `admin.aku` | Rabia Javed | Aga Khan | Administrator |
| `dr.reviewer` | Dr Nadia Hassan | Aga Khan | Clinical rule reviewer: approves medication rules and medicine names |
| `lab.chughtai` | Imran Butt | Chughtai Lab, Laboratory | Laboratory orders |
| `rad.chughtai` | Dr Zainab Ali | Chughtai Lab, Radiology | Imaging orders |
| `staff.chughtai` | Ayesha Malik | Chughtai Lab | Answers records requests |

### Addresses

| What | Address | Login |
|---|---|---|
| The web app | http://localhost:3000 | Accounts above |
| Keycloak admin console | http://localhost:8080/admin | `admin` / `KEYCLOAK_ADMIN_PASSWORD` from `.env` |
| API docs (Swagger) | Central http://localhost:8000/docs · Dr Ali's :8001/docs · Chughtai :8002/docs · Ziauddin :8003/docs · Aga Khan :8004/docs | Bearer token |

### Local database
To open PostgreSQL to tools on your computer at `localhost:5432`:
```powershell
docker compose -f docker-compose.yml -f docker-compose.dbaccess.yml up -d
```

| Database | Username | Contains |
|---|---|---|
| `central_db` | `central` | Referrals, links, records retrieved for referrals, medicines and flags, rules, sent versions, orders, audit |
| `drali_db` | `drali` | Dr Ali's Clinic patients and records |
| `chughtai_db` | `chughtai` | Chughtai Lab patients, results, orders |
| `ziauddin_db` | `ziauddin` | Ziauddin patients, records, incoming referrals, orders |
| `akuh_db` | `akuh` | Aga Khan patients, records, incoming referrals, orders |
| `keycloak` | `keycloak` | Login accounts (use the Keycloak console instead) |

Passwords are the values in your `.env`. Without a database tool: `docker compose exec postgres psql -U central -d central_db`. **Change every value in `.env` before running this anywhere shared.**

### Shared team database on Neon
A **copy** of the demo databases can be published to a free cloud PostgreSQL on [Neon](https://neon.tech) so teammates can inspect the data. Credentials live in `shared-db-credentials.md`, which is git-ignored; ask Eesha. Setup and publishing: `scripts/setup_shared_db.py --copy-only` then `scripts/publish-shared-db.ps1` (see the script headers). The current shared copy still holds version 1 data until it is republished.

### Reading papers with a language model (optional)
Uploaded papers are read with Tesseract OCR and a rule-based reader. If you add `ANTHROPIC_API_KEY=...` to `.env` (and restart `central` and `worker`), Claude is used to read the fields instead. Staff still check every field against the paper. The referral summary itself is always built from the checked records, never written by a model.

---

## 4. Try the full workflow

Each seed patient has a referral scenario in [`seed-data/README.md`](seed-data/README.md). Example, **P5 Imtiaz Ali Soomro → Aga Khan, General Surgery, laparoscopic cholecystectomy**:

1. **Dr Ali** (`dr.ali`): **Work queue** → **New request** → **Refer to a doctor or department** → find *Imtiaz* → Aga Khan University Hospital, General Surgery → reason → **A procedure is planned** → type *Laparoscopic cholecystectomy* (the features it involves tick themselves; correct them if needed) → **Submit request**. It now shows **In progress**; Medicines & flags says staff are still gathering.
2. **Hina** (`staff.ali`) opens it from her **Work queue**:
   - **Records** → **Retrieve records** (own clinic, Ziauddin, Chughtai Lab). If the patient says he was seen elsewhere, **Ask for records** there.
   - **Papers** → upload `seed-data/documents/P5_prescription_cardiology_2025-06-18.jpg`. Open it and confirm each medicine against the photo; each one merges with the clinic's record.
   - **Medicines & flags** → **Add a medicine** (e.g. Panadol, over the counter) → **I asked the patient about all their medicines**.
   - **Check & send** → **Ready for the doctor's review**.
3. **Dr Ali**: **Medicines & flags** → **Mark as reviewed** on the 4 flags (aspirin and clopidogrel before surgery, insulin and metformin around fasting).
4. **Hina**: **Check & send** → read the referral letter → **Send to Aga Khan University Hospital**. It carries his name, date of birth, sex and CNIC; Aga Khan has not been asked anything before this.
5. **Mariam** (`staff.aku`): **Incoming referrals** → open it → **Acknowledge receipt** → **Confirm the patient** (he is not registered there: write how you checked → **Register as a new patient**) → **Assign to doctor**: Dr Naveed Baig → **Assign**. Dr Ali's Clinic is told he was registered as new.
6. **Dr Naveed** (`dr.naveed`): **Incoming referrals** (only referrals assigned to him) → **Accept referral** → the response form opens at the top → **Send response to the referring clinic**.
7. **Dr Ali**: **Response & follow-up** → **I have reviewed the outcome**. **Hina**: **Record that the patient was told** → add any task → **Close referral**. **History** shows every step.

**A test or scan request**, e.g. P3 *Abdul Rehman Gondal*:
1. **Dr Ali**: **New request** → **Request a test or scan** → *Gondal* → Imaging or scan, *MRI knee*, Where: Aga Khan University Hospital → **Submit request**.
2. **Hina**: **Tests & results** → **Send to Aga Khan University Hospital**.
3. **Dr Sana** (`rad.aku`): **Test and scan orders** → open it → **Confirm the patient** (register as new) → **Accept order** → findings, impression, and **Choose files**: `seed-data/documents/imaging/synthetic_mri-knee-coronal.png` → **Send report**. A report needs findings, an impression and the images; a laboratory report needs each result with its value.
4. **Dr Ali**: **Tests & results** shows the report with the image → **I have seen the result**. **Hina**: **Record that the patient was told** → **Close request**.

Other scenarios: P2 (Ziauddin cardiology, metformin with contrast; Ziauddin staff match their existing record when it arrives); P1 (Aga Khan dentistry, alendronate with oral surgery); P3 (Aga Khan orthopaedics); P4 (Ziauddin gastroenterology). Any clinic or hospital can refer to another, and receive referrals: try `dr.asma` (Ziauddin) referring to Aga Khan.

**Rules:** sign in as `dr.reviewer` → **Medication rules** to see, edit (a change is a new draft) and approve rules, and **Medicine names** to add a brand name.

---

## 5. Automated tests

```powershell
python -m venv .venv
.\.venv\Scripts\pip install httpx pytest

# API checks: P5 referral, P3 test request with an image, every patient's expected flags, OCR merge (resets demo data first). Expect: 10 passed
.\.venv\Scripts\python -m pytest tests -q

# Medication-rule logic, interactions, label rules and the extraction validator. Expect: 39 passed
docker compose run --rm --no-deps -v ${PWD}/services/central/tests:/srv/tests central python -m pytest tests -q

# Browser robot: the referral and test-request journeys across 7 accounts in Chrome (reset the demo data first). Expect: 2 passed
cd web; npm ci; npx playwright install chromium; npx playwright test e2e/smoke.spec.ts; cd ..
```

---

## 6. Troubleshooting

| Problem | Fix |
|---|---|
| Login page says **"We are sorry… An internal server error has occurred"** | Run `docker compose restart keycloak`, wait about 1 minute, refresh. |
| `rad.chughtai` cannot sign in after pulling | The login accounts are imported only once. Delete the realm and restart Keycloak: `docker compose exec keycloak sh -c '/opt/keycloak/bin/kcadm.sh config credentials --server http://localhost:8080 --realm master --user admin --password "$KC_BOOTSTRAP_ADMIN_PASSWORD" && /opt/keycloak/bin/kcadm.sh delete realms/referral'` then `docker compose restart keycloak` and reseed. |
| Login works but every page errors after switching from version 1 | The old database volume is still there. Run `docker compose down -v`, then the first-time steps. |
| `docker compose` can't connect, or hangs | Docker Desktop isn't running, or its WSL backend froze. Quit Docker Desktop, run `wsl --shutdown`, start Docker Desktop again. |
| Port already in use (3000, 8000-8004, 8080, 5432) | Close the other program, or change the left-hand port in `docker-compose.yml`. |
| Very slow or out of memory | Give Docker Desktop at least 4 GB (Settings → Resources). |
| Data looks messy after testing | `.\scripts\reset-and-seed.ps1 -Force` |

---

## 7. What's in the repository

```
web/                    React website (all screens) + Playwright browser test
services/central/       Central platform API + background worker, migrations, unit tests
services/provider/      Each institution's own system (one program, run once per institution)
libs/common/            Shared code: login-token checks, FHIR subset, message formats
seed-data/              The five synthetic patients, their papers, and expected results
rules/                  Starting medication rules and Pakistani medicine names (loaded into the app)
infra/                  Database setup and Keycloak accounts, roles and departments
scripts/                Reset/seed, backup/restore, Neon, deployment
tests/                  End-to-end API checks
docs/                   Documentation (see the table at the top)
docker-compose.yml      Defines all 11 containers
.env.example            Settings template; copy to .env (never commit .env)
```

## 8. Known limitations (be upfront in demos)

- **Synthetic data, unreviewed clinical content.** The rules, references, procedure features and brand mappings are plausible but not clinically reviewed. The seed marks the rules as approved by a demo reviewer.
- **Drug-to-drug interactions are not checked.** Only drug against procedure. See [`docs/v2-changes.md`](docs/v2-changes.md) for the planned approach.
- **Most recent place only:** records held only at an older hospital are not retrieved automatically; they are listed as skipped.
- **OCR:** printed prescriptions read well. The handwriting-style samples read with small errors, which staff correct when checking.
- **Not production-hardened:** HTTP on localhost with demo passwords. See [`docs/operations.md`](docs/operations.md).
