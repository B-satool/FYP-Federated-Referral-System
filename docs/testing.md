# Testing (version 2, as of 2026-10-29)

## How to run

```powershell
docker compose up -d --build
python -m venv .venv; .\.venv\Scripts\pip install httpx pytest

# API tests against the running stack (reseed first; SKIP_RESET=1 keeps the data)
.\.venv\Scripts\python -m pytest tests -q

# Unit tests inside the central image (no network, no keys, no cost)
docker compose run --rm --no-deps -v ${PWD}/services/central/tests:/srv/tests central python -m pytest tests -q

# Browser journeys (reseed first)
cd web; npx playwright install chromium; npx playwright test; cd ..

# Web type check and build
cd web; npm run typecheck; npm run build; cd ..
```

**With a cloud model configured**, every test referral queues an AI recommendation. The tests pass either way, but
for quick runs switch the model off: `$env:LLM_PROVIDER="anthropic"; docker compose up -d central worker`.

**Test order matters a little:** API tests run in alphabetical file order. `test_referral_expiry.py` uses Rubina and
Dr Salman, so that the patients and doctor `test_v2_flow.py` expects to be new at Aga Khan (Imtiaz, Gondal,
Dr Naveed) stay untouched.

## What is covered

| Suite | Covers |
|---|---|
| `tests/test_v2_flow.py` | P5 referral end to end: roles, linking on arrival, accept, the doctor closes. P3 test request with an image. |
| `tests/test_v2_scenarios.py` | Each seed patient's expected flags; DDInter and label flags with sources; Ignore and Research logged; a procedure without features is not checked; every linked hospital and a stopped medicine; a paper merging with the recorded medicines |
| `tests/test_v3_lifecycle.py` | Temporary grants; role menus; an admin assigning a role in Keycloak; packet selection, manifest, the clinic's own copy, removal and refetch; the default selection matching each seed patient's expected view |
| `tests/test_referral_expiry.py` | Accept → 30-day limit → extend → mark complete → 72 h → removal on the platform and at the hospital; decline removes straight away |
| `tests/test_drap_brands.py` | A DRAP brand maps and is checked against DDInter; an ambiguous name is chosen by company (staff and doctor); a wrong choice is refused |
| `services/central/tests` (unit) | Evaluator and flags; mapping and DRAP register names; AI suggestions never change flags; AI selection validation and application; model providers (Anthropic, Ollama local and cloud, OpenAI-compatible) against fake servers; de-identification and the external-model switch; Google Vision against a fake server; grant expiry and close-out; working-set timing; manifests; role templates |
| `web/e2e/smoke.spec.ts` | Referral across seven accounts (staff retrieve and upload, the doctor confirms medicines, decides flags and marks the packet reviewed, staff send, intake, accept, mark complete, tell the patient, the doctor closes); test request with an MRI image |
| `web/e2e/admin.spec.ts` | An administrator changes a role; the menu follows on the next sign-in |

## Latest results (2026-10-29, after merging the doctor-only change and the patient view)

- Unit: **136 passed**
- API: **25 passed** (including `test_patient_access.py`)
- Browser: **3 passed**
- Type check and build: clean

**If browser or API tests fail with `ERR_CONNECTION_RESET` or "connection aborted" on Windows:** Docker Desktop's
port forwarding can get stuck, especially when memory is low. Check from inside Docker
(`docker compose exec central python -c "import httpx; print(httpx.get('http://web:80/').status_code)"`). If that
works, recreate the affected containers (`docker compose up -d --force-recreate web keycloak`); if not, restart WSL
(`wsl --shutdown`) and Docker Desktop.

## Not covered by automatic tests

- **Live model and live Vision calls:** these need Ollama credits and a Vision key. The request shapes and failure
  handling are tested against fake servers.
- **Some v1 tests were not ported:** disabled-account revocation at the sources, link invalidation, load test and
  backup/restore check. The scripts still exist (`scripts/loadtest.py`, `scripts/restore-check.ps1`) but have not
  been re-run on v2.
- **OCR accuracy on real handwriting:** not measured. `evaluation/` covers machine-rendered samples only.
