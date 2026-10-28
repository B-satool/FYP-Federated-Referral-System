## Configuration

### Environment variables read by the code

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

### `.env.example` (installation settings)

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

_PyYAML is not installed, so the Compose inventory was not generated._
