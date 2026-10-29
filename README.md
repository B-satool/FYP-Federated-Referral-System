# FYP Federated Referral System
### Referral Preparation and Follow-through Platform (end-to-end encrypted, architecture spec v4)

A web application for referring a patient from one clinic or hospital in Karachi to a doctor or department at another, or for requesting a test or scan from a laboratory or radiology department elsewhere. **Records are stored encrypted and decrypted only on the clinician's device**; the platform never holds readable records ([`docs/security-model.md`](docs/security-model.md)).
- **Referring doctor:** fills in the request; reads the records on their own device (decrypted there); chooses what goes in (with optional AI suggestions, sent de-identified only when asked); enters the medicines asked from the patient (flags are checked on the device); adds papers (read on the device); and **signs the package**.
- **Patient:** gives consent in the patient app (signed on the phone), can add papers, is told when the referral is accepted, and **keeps a verified copy on the phone** after the referral is purged.
- **Referring staff:** ask the patient for consent, request the records, and send the signed package. **Staff see titles only, never content.** They also send test and scan orders.
- **Each institution:** answers records requests under the patient's consent and its own policy, with records encrypted for the doctor, or a refusal with its reason.
- **Receiving staff:** take the referral in (titles only), confirm the patient, assign a doctor, and can add their own hospital's records (encrypted for the department).
- **Receiving doctor:** opens the referral with the department's key, checks the referring doctor's signature, accepts or declines, may ask for more information, and closes it (or extends it, at most 180 days).
- **Platform:** relays encrypted content and AI requests, reminds the specialist 30 days after acceptance, and **purges by deleting the ciphertext and the keys** a week after closing ([`docs/data-lifecycle.md`](docs/data-lifecycle.md)).

> **Synthetic (fake) patient data only. Not for clinical use.** The institution names are used only as source-system names; nothing comes from those organisations.

| Document | Where |
|---|---|
| **Architecture spec v4 (end-to-end encryption)**, how it maps onto the code, and its status | [`docs/e2e-architecture-spec-v4.md`](docs/e2e-architecture-spec-v4.md), [`docs/e2e-mapping.md`](docs/e2e-mapping.md) |
| **Security model:** what is protected, the limits, and the acceptance tests | [`docs/security-model.md`](docs/security-model.md) |
| Cryptography and machine-to-machine authentication | [`docs/crypto.md`](docs/crypto.md), [`docs/auth.md`](docs/auth.md) |
| Approvals, and decisions awaiting the owner's confirmation | [`docs/approvals.md`](docs/approvals.md) |
| What changed in version 2, and differences from the SRS | [`docs/v2-changes.md`](docs/v2-changes.md) |
| Medication flags: DDInter interactions, drug-label rules, sources and coverage | [`docs/medication-flagging.md`](docs/medication-flagging.md) |
| Requirements (SRS) | [`docs/requirements/FYP SRS.pdf`](docs/requirements/FYP%20SRS.pdf) |
| Development roadmap | [`docs/requirements/FYP Development Roadmap.pdf`](docs/requirements/FYP%20Development%20Roadmap.pdf) |
| Seed patients (5 synthetic Karachi patients) and their expected results | [`seed-data/README.md`](seed-data/README.md) |
| **Software Design Specification** (full, versioned design; regenerated from the code) | [`docs/sds/SDS.md`](docs/sds/SDS.md) |
| Short architecture overview: boundaries, roles, flows, data lifecycle, AI and privacy | [`docs/architecture.md`](docs/architecture.md) |
| SRS evaluation report | [`docs/srs-evaluation-report.md`](docs/srs-evaluation-report.md) |
| Every decision, with its reasons and approval status | [`docs/decisions/`](docs/decisions/) |
| Supervisor demo script (25 min) | [`docs/demo-script.md`](docs/demo-script.md) |
| Tests: how to run and what they cover | [`docs/testing.md`](docs/testing.md) |
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
| `worker` | Background jobs: OCR, the AI recommendation, sending referrals and orders, removing expired records, closing access | none |
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

# 4. Pin every institution's signing key (once per installation; writes infra/participants/participants.json)
python scripts/onboard_participants.py

# 5. Load the five synthetic patients into every institution's database
.\scripts\reset-and-seed.ps1 -Force   # macOS/Linux: sh scripts/reset-and-seed.sh --force
```

**Device keys are automatic:** the first time a doctor or patient signs in on a browser, it creates their keys (no set-up step, no passphrase), and every later sign-in loads them. The private keys never leave that browser. Signing in on another browser creates a new key that replaces the old one: records from institutions can be requested again, while items that existed only on the platform stay readable only with the old key (or from the patient's copy).

Open **http://localhost:3000**, click **Sign in with your institution account**, and use an account from section 3.

**Coming from version 2?** Add the five `*_KEYSTORE_SECRET` lines from `.env.example` to your `.env` (each service seals its own private keys with one), run `docker compose up -d --build`, `python scripts/onboard_participants.py` and `python scripts/sync_keycloak_realm.py` (adds the patient accounts), then reset the demo data.

### Every day after that

| What | Command (in the project folder) |
|---|---|
| Start | Open Docker Desktop, then `docker compose up -d` |
| Stop (data is kept) | `docker compose stop` |
| Reset to clean demo data (before a demo) | `.\scripts\reset-and-seed.ps1 -Force` |
| Add demo referrals for the patient view | `.\.venv\Scripts\python scripts/seed_demo_referrals.py` (after a reset) |
| See errors | `docker compose logs -f central` (or `web`, `worker`, `akuh`, …) |
| After pulling new code | `git pull` then `docker compose up -d --build` |
| Delete everything including data | `docker compose down -v` (**permanent**) |

---

## 3. Access: logins, addresses, databases

### Demo accounts (password for all: `demo1234`)

| Username | Person | Institution, department | What they do |
|---|---|---|---|
| `dr.ali` | Dr Ali Raza | Dr Ali's Clinic, General practice | **Doctor**: makes referrals and test requests, reviews the packet (papers, medicines, flags, records, letter), sees results, closes the referral |
| `staff.ali` | Hina Raza | Dr Ali's Clinic | **Staff**: retrieves records, uploads papers, sends referrals and test orders, tells the patient, closes; takes in referrals sent to the clinic. Sees titles and statuses, not clinical content |
| `tech.ali` | Bilal Ahmed | Dr Ali's Clinic, in-clinic tests (ECG) | Test orders done at the clinic |
| `admin.ali` | Adeel Shah | Dr Ali's Clinic | Administrator: accounts and roles, record sharing, audit (no patient records) |
| `dr.asma` | Dr Asma Rauf | Ziauddin, Cardiology | Accepts or declines cardiology referrals and marks them complete; can also refer |
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

**Patient accounts** (same password). A patient signs in on the same page and gets a phone-style view: the places that hold their records, their referrals and tests, and their history read directly from each place ([decision](docs/decisions/2026-10-29-patient-view.md)).

| Username | Patient | Demo journey (`scripts/seed_demo_referrals.py`) |
|---|---|---|
| `rubina.akhtar` | Rubina Akhtar (P1) | Referral to AKUH Dentistry, accepted |
| `muhammad.tariq.mahmood` | Muhammad Tariq Mahmood (P2) | Referral to Ziauddin Cardiology, sent |
| `abdul.rehman.gondal` | Abdul Rehman Gondal (P3) | Test request: liver tests reported, knee MRI booked |
| `shazia.parveen` | Shazia Parveen (P4) | Referral to Ziauddin Gastroenterology, being prepared |
| `imtiaz.ali.soomro` | Imtiaz Ali Soomro (P5) | Referral to AKUH General Surgery, closed |

After pulling this change on an existing install, re-import the Keycloak realm so the patient accounts exist (see Troubleshooting, the `rad.chughtai` row).

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

### AI and handwriting (optional)
Everything works without these. Change `.env`, then `docker compose up -d central worker`.

| Feature | Settings in `.env` | Without it |
|---|---|---|
| **AI record suggestions and AI flag suggestions** (only when the doctor clicks, after a preview of the de-identified text) | Groq's free tier: `LLM_PROVIDER=openai_compatible`, `LLM_BASE_URL=https://api.groq.com/openai/v1`, `LLM_MODEL=openai/gpt-oss-120b`, `LLM_REASONING_EFFORT=low`, `LLM_API_KEY=<key from console.groq.com>`, `LLM_EXTERNAL_ALLOWED=true` (or Ollama or Anthropic, see `.env.example`) | The deterministic floor and Layer 1 flags work; the screen says "AI check not available" |

**Privacy:** the browser removes the patient's name, ID numbers, record numbers, places, doctors' names and dates, and shows the doctor exactly what will be sent; the relay refuses anything that still identifies the patient, and stores and logs no text. A model outside this computer is used only with `LLM_EXTERNAL_ALLOWED=true`, over https. **Papers are read on the device** (Tesseract.js, served by this application): no image or text leaves it. **Synthetic data only.**

---

## 4. Try the full workflow

**P1 Rubina Akhtar → Aga Khan, Dentistry, surgical removal of a wisdom tooth.** Use a separate private window per person.

1. **Sign in** as `dr.faisal` (Aga Khan dentistry) once before Dr Ali signs: his first sign-in creates his device key automatically, which also creates the dentistry department's key. Doctors and the patient never set up keys by hand.
2. **Dr Ali**: **New request** → **Refer to a doctor or department** → *Rubina* → Aga Khan University Hospital, Dentistry → reason → **A procedure is planned** → *Surgical removal of impacted lower wisdom tooth* → **Submit request**.
3. **Hina** (`staff.ali`): **Consent & records** → **Ask the patient for consent**.
4. **Rubina** (patient app): **Permissions** → open the request → **Agree and sign** (signed on her phone).
5. **Hina**: **Request records**. Each institution answers under its own policy: records (encrypted), or a refusal with its reason (her psychiatric record is held back without specific consent). Hina sees titles only.
6. **Dr Ali**:
   - **Consent & records**: the records are decrypted on his device, and the ticks start from the default selection. **Suggest with AI** (optional) shows exactly what is sent first.
   - **Medicines & flags**: enter what the patient takes (e.g. *Disprin 75mg*, *Plavix 75 mg*; *Glare* asks which company's product it is). Flags from DDInter appear, checked on the device; choose **Ignore** or **Research**, then **Save the list**.
   - **Papers**: add a photo, **Read it on this device**, and correct the medicines.
   - **Approve & sign**: write notes for the specialist (share them with the patient or not), then **Approve and sign**.
7. **Hina**: **Check & send** → **Send to Aga Khan University Hospital**. A notice with titles goes; the content stays encrypted.
8. **Mariam** (`staff.aku`): **Incoming referrals** → **Acknowledge receipt** → **Confirm the patient** → **Assign to doctor**: Dr Faisal. Optionally **Add our records** (encrypted for the department).
9. **Dr Faisal**: **Incoming referrals** → open it → unlock. It is decrypted with the department's key and checked against Dr Ali's signature. **Accept referral**, and later **Close referral** (or **Extend by 30 days**). It is purged a week after closing.
10. **Rubina**: **Referrals** → the referral → **Save a copy on this phone** → **Open my copy**. It is verified against Dr Ali's signature, and it still opens after the purge.

**A test or scan request**, e.g. P3 *Abdul Rehman Gondal*:
1. **Dr Ali**: **New request** → **Request a test or scan** → *Gondal* → Imaging or scan, *MRI knee*, Where: Aga Khan University Hospital → **Submit request**.
2. **Hina**: **Tests & results** → **Send to Aga Khan University Hospital**.
3. **Dr Sana** (`rad.aku`): **Test and scan orders** → open it → **Confirm the patient** (register as new) → **Accept order** → findings, impression, and **Choose files**: `seed-data/documents/imaging/synthetic_mri-knee-coronal.png` → **Send report**. A report needs findings, an impression and the images; a laboratory report needs each result with its value.
4. **Dr Ali**: **Tests & results** shows the report with the image → **I have seen the result**. **Hina**: **Record that the patient was told** → **Close request**.

**Medicine names:** sign in as `dr.reviewer` → **Medicine names** to add a brand name (DRAP register names are marked "DRAP register").

**Roles:** sign in as `admin.ali` → **Accounts and roles** → pick a role for an account (it applies at that user's next sign-in).

---

## 5. Automated tests

See [`docs/testing.md`](docs/testing.md) for every suite and what it covers (the spec's acceptance tests T-DB-1 to T-PERF-1).

```powershell
python -m venv .venv
.\.venv\Scripts\pip install httpx pytest "pyjwt[crypto]" cryptography

.\.venv\Scripts\python -m pytest tests -q              # integration checks against the stack (reseeds first)
.\.venv\Scripts\python -m pytest libs/common/tests -q  # crypto suite, Python and browser interop, Layer 1 flags (needs Node.js)
docker compose run --rm --no-deps -v ${PWD}/services/central/tests:/srv/tests central python -m pytest tests -q
cd web; npm ci; npx playwright install chromium; npx playwright test; cd ..   # browser journeys (reseed first)
```

---

## 6. Troubleshooting

| Problem | Fix |
|---|---|
| Login page says **"We are sorry… An internal server error has occurred"** | Run `docker compose restart keycloak`, wait about 1 minute, refresh. |
| `rad.chughtai` cannot sign in after pulling | The login accounts are imported only once. Delete the realm and restart Keycloak: `docker compose exec keycloak sh -c '/opt/keycloak/bin/kcadm.sh config credentials --server http://localhost:8080 --realm master --user admin --password "$KC_BOOTSTRAP_ADMIN_PASSWORD" && /opt/keycloak/bin/kcadm.sh delete realms/referral'` then `docker compose restart keycloak` and reseed. |
| **Accounts** → changing a role says "The sign-in service did not accept the role change" | Keycloak was set up before the platform was allowed to assign roles. Run once: `docker compose exec keycloak sh -c '/opt/keycloak/bin/kcadm.sh config credentials --server http://localhost:8080 --realm master --user admin --password "$KC_BOOTSTRAP_ADMIN_PASSWORD" && /opt/keycloak/bin/kcadm.sh add-roles -r referral --uusername service-account-central-api --cclientid realm-management --rolename view-realm'` |
| Login works but every page errors after switching from version 1 | The old database volume is still there. Run `docker compose down -v`, then the first-time steps. |
| `docker compose` can't connect, or hangs | Docker Desktop isn't running, or its WSL backend froze. Quit Docker Desktop, run `wsl --shutdown`, start Docker Desktop again. |
| `ERR_CONNECTION_RESET` / "connection aborted" on localhost:3000 or 8080, while `docker compose ps` shows everything healthy | Docker Desktop's port forwarding is stuck. Run `docker compose up -d --force-recreate web keycloak`. If that doesn't help, `wsl --shutdown`, reopen Docker Desktop and `docker compose up -d`. |
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
docs/                   Documentation (see the table at the top); docs/decisions/ holds every decision
docker-compose.yml      Defines all 11 containers
.env.example            Settings template; copy to .env (never commit .env)
```

## 8. Known limitations (be upfront in demos)

- **Synthetic data, unreviewed clinical content.** Brand mappings and interaction data are not clinically reviewed; flags are "automatically generated, not clinically reviewed".
- **What end-to-end encryption does not cover** ([`docs/security-model.md`](docs/security-model.md)):
  - a compromised doctor's device;
  - the platform serves the browser code;
  - metadata and the patient's demographics are visible to the platform;
  - the AI relay sees de-identified text in memory;
  - decrypt events are reported by the client.
- **Keys live in the browser.** Losing a key (or clearing the browser's data) without a backup means the records are fetched again from the institutions; items that existed only on the platform are lost unless the patient has a copy.
- **Not done yet:** the RQ1, RQ2 and RQ4 evaluations, a handwriting benchmark, and T-PERF-1 on a phone ([`docs/evaluation.md`](docs/evaluation.md)).
- **Handwriting:** Tesseract on the device reads printed text well and handwriting poorly; the doctor checks every field against the image.
- **Test and scan orders** keep the v2 flow (not encrypted end to end); they are out of scope for v4.
- **Not production-hardened:** HTTP on localhost with demo passwords. See [`docs/operations.md`](docs/operations.md).
