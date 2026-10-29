# Testing (architecture spec v4, as of 2026-10-30)

## How to run

```powershell
docker compose up -d --build
python scripts/onboard_participants.py          # once per installation: pins every institution's signing key
python scripts/sync_keycloak_realm.py           # adds demo and patient accounts a local realm is missing
.\scripts\reset-and-seed.ps1 -Force
python -m venv .venv; .\.venv\Scripts\pip install httpx pytest "pyjwt[crypto]" cryptography

# Integration tests against the running stack (reseeds first; SKIP_RESET=1 keeps the data)
.\.venv\Scripts\python -m pytest tests -q

# Unit tests: the central image, the institution adapter, the shared library (Python and browser crypto, Layer 1 flags)
docker compose run --rm --no-deps -v ${PWD}/services/central/tests:/srv/tests central python -m pytest tests -q
docker compose run --rm --no-deps -v ${PWD}/services/provider:/prov -w /prov -e INSTITUTION_ID=chughtai central python -m pytest tests -q
.\.venv\Scripts\python -m pytest libs/common/tests -q          # needs Node.js for the browser checks

# Browser journeys (reseed first)
cd web; npx playwright install chromium; npx playwright test; cd ..

# Web type check and build
cd web; npm run typecheck; npm run build; cd ..
```

**With a model configured** (`LLM_PROVIDER` and its key in `.env`), `test_e2e_ai.py` and `test_e2e_flags.py` call it
once each. Without one, they check that "AI check not available" is said instead. The Groq free tier allows about two
calls a minute; a rate-limited call is skipped, not failed.

## What is covered

| Suite | Covers (spec v4 acceptance tests in brackets) |
|---|---|
| `tests/test_e2e_keys.py` | Doctor and patient keys, hospital signatures, a forged or unsigned entry refused (T-DIR-1), group join, leave and rotation (T-GROUP-1) |
| `tests/test_e2e_consent.py` | Consent signed by the patient only (T-CONSENT-1); request assertions (T-TOKEN-1); each institution's policy and refusal codes (T-POLICY-1, T-REFUSAL-1) |
| `tests/test_e2e_retrieval.py` | Records arrive encrypted; staff see titles; the database holds no plaintext, data key or private key (T-STAFF-1, T-DOC-1, T-DB-1); lost-key recovery (T-REC-1) |
| `tests/test_e2e_package.py` | Approve and sign on the device, send a titles-only notice, the department's doctor decrypts and verifies; tampered or foreign signatures refused; versions (T-APPROVE-1); the receiving hospital adds its own records (step 8) |
| `tests/test_e2e_ai.py` | The relay refuses identifiers, logs no text, only the referring doctor may ask, answers are checked (T-AI-1, T-AI-2) |
| `tests/test_e2e_flags.py` | The hash-checked bundle with DRAP brands and DDInter pairs; the browser library on the real bundle; Ignore/Research audited by hash; Layer 2 names only (T-FLAG-1 to 3) |
| `tests/test_e2e_patient.py` | Papers from the patient app, readable only by the doctor and the patient; the plaintext upload path refuses referrals (T-OCR-1); the patient's copy opens and verifies after the purge (T-LIFE-2) |
| `tests/test_e2e_lifecycle.py` | Reminders, escalation, capped extension, the specialist closes, grace period, purge with a receipt, idempotent; decline purges after a day (T-LIFE-1, T-NOCOPY-1) |
| `tests/test_e2e_audit.py` | The audit table is append-only; the hash chain verifies and finds an altered entry; no content in audit (T-AUDIT-1) |
| `tests/test_patient_access.py`, `test_roles.py`, `test_test_requests.py` | The patient view; role menus and template assignment; test and scan orders (unchanged by v4) |
| `libs/common/tests` | The crypto suite; Python and browser interoperability; the Layer 1 library under Node; no drug-procedure table anywhere (T-FLAG-2) |
| `services/provider/tests` | Each institution's release policy |
| `services/central/tests` | Unit tests of the central modules (lifecycle timing, role templates, selection validation, privacy, the server evaluator kept for tests) |
| `web/e2e/smoke.spec.ts` | The full v4 referral in a real browser across six sessions (two doctors, two staff, the patient), and a test request |
| `web/e2e/admin.spec.ts` | An administrator changes a role; the menu follows on the next sign-in |
| `web/scripts/perf-decrypt.ts` | T-PERF-1 measurement |

## Latest results (2026-10-30, branch `e2e-v4/wp5-approval`, fresh seed)

| Suite | Result |
|---|---|
| Integration (`tests/`) | **41 passed** (4 min 31 s), with the Groq model configured |
| Central unit (`services/central/tests`) | **120 passed** |
| Institution adapter unit (`services/provider/tests`) | **6 passed** |
| Shared library (`libs/common/tests`, including the Node checks) | **13 passed** |
| Web type check | Clean |
| Browser journeys (`web/e2e`) | **3 passed**: the v4 referral across six sessions (37 s), the test request, and the role change |

Test order matters in one way: the integration tests run in file order, and `test_patient_access.py` and
`test_test_requests.py` expect Rubina and Gondal never to have been registered at Aga Khan. So the e2e tests that take
a referral in send Rubina's referrals to Ziauddin (where she is already a patient), and step 8 uses Tariq (already an
Aga Khan patient).

## Not covered by automatic tests

- RQ1, RQ2, RQ4 and the handwriting benchmark (planned; see `evaluation.md`).
- T-PERF-1 on a phone.
- **If browser or API tests fail with `ERR_CONNECTION_RESET` on Windows:** Docker Desktop's port forwarding can get
  stuck. Recreate the affected containers (`docker compose up -d --force-recreate web keycloak`), or restart WSL
  (`wsl --shutdown`) and Docker Desktop.
