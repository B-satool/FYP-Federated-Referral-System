## Configuration

### Environment variables read by the code

Every variable read with `os.environ.get`, `os.getenv` or a boolean helper, with its default and where it is read.

| Variable | Default | Meaning | Read in |
|---|---|---|---|
| `ACCEPTED_HOLD_DAYS` | `'30'` | a received referral's shared records: kept ACCEPTED_HOLD_DAYS after acceptance (extendable by the referred doctor), and removed GRACE_HOURS after they mark it complete (the platform applies the same rules) | services/central/app/config.py:56, services/provider/app/config.py:17 |
| `ANTHROPIC_API_KEY` | `''` |  | services/central/app/config.py:25 |
| `CENTRAL_URL` | `'http://central:8000'` |  | services/provider/app/config.py:9 |
| `CLOSE_GRACE_DAYS` | `'7'` | spec v4 7: the specialist closes (purged CLOSE_GRACE_DAYS later) or extends, at most MAX_REFERRAL_DAYS after accepting | services/central/app/config.py:60, services/provider/app/config.py:20 |
| `DATABASE_URL` | `'postgresql+psycopg://central:central@postgres/central_db'` |  | services/central/app/config.py:13, services/provider/app/main.py:72, services/provider/app/seed.py:114 |
| `DECLINE_GRACE_DAYS` | `'1'` |  | services/central/app/config.py:61 |
| `DOCTOR_KEY_VALID_DAYS` | `'365'` |  | services/provider/app/config.py:27 |
| `DOCUMENT_RETENTION_DAYS` | `'365'` |  | services/central/app/config.py:50 |
| `ESCALATE_AFTER_REMINDERS` | `'3'` |  | services/central/app/config.py:58 |
| `EXTRACTION_MODE` | `'auto'` | auto \| llm \| rules | services/central/app/config.py:39 |
| `GOOGLE_VISION_API_KEY` | `''` |  | services/central/app/config.py:43 |
| `GOOGLE_VISION_ENDPOINT` | `'https://vision.googleapis.com/v1/images:annotate'` |  | services/central/app/config.py:44 |
| `HUB_URL` | `CENTRAL_URL` |  | services/provider/app/config.py:26 |
| `INSTITUTION_ID` | `(required)` | drali \| chughtai \| ziauddin \| akuh | services/provider/app/config.py:6 |
| `INSTITUTION_NAME` | `INSTITUTION` |  | services/provider/app/config.py:7 |
| `INTROSPECT_TOKENS` | `True` |  | libs/common/refcommon/auth.py:70 |
| `KEYCLOAK_INTERNAL_URL` | `'http://keycloak:8080'` |  | libs/common/refcommon/auth.py:65 |
| `KEYCLOAK_PUBLIC_URL` | `'http://localhost:8080'` |  | libs/common/refcommon/auth.py:66 |
| `KEYCLOAK_REALM` | `'referral'` |  | libs/common/refcommon/auth.py:67 |
| `KEYSTORE_SECRET` | `''` | End-to-end encryption (spec v4): the platform's own signing key is sealed with this secret | services/central/app/config.py:73, services/provider/app/config.py:25 |
| `LLM_API_KEY` | `''` |  | services/central/app/config.py:36 |
| `LLM_BASE_URL` | `''` | openai_compatible: vLLM, Kimi or any other chat-completions server (…/v1) | services/central/app/config.py:35 |
| `LLM_CONTEXT_TOKENS` | `'16384'` | local Ollama models | services/central/app/config.py:30 |
| `LLM_EXTERNAL_ALLOWED` | `False` | Patient data (always de-identified) may go to a model outside this computer (an Ollama ":cloud" model, ollama.com, Anthropic, any remote server) only if this is true: docs/decisions/2026-10-28-cloud-model-privacy.md | services/central/app/config.py:33 |
| `LLM_MODEL` | `'claude-opus-5-5'` |  | services/central/app/config.py:24 |
| `LLM_PROVIDER` | `'anthropic'` | anthropic \| ollama \| openai_compatible | services/central/app/config.py:23 |
| `LLM_REASONING_EFFORT` | `''` | sent only when set: low \| medium \| high for reasoning models such as gpt-oss on Groq | services/central/app/config.py:38 |
| `LLM_TIMEOUT_SECONDS` | `'120'` |  | services/central/app/config.py:46 |
| `LOCAL_ID_PREFIX` | `'PT'` |  | services/provider/app/config.py:8 |
| `MAX_PAGES` | `'10'` |  | services/central/app/config.py:49 |
| `MAX_REFERRAL_DAYS` | `'180'` |  | services/central/app/config.py:59, services/provider/app/config.py:21 |
| `MAX_RETRIEVAL_SOURCES` | `'5'` | Retrieval asks every linked institution, up to this many besides the referring one (most recently visited first), so the AI recommendation stays within what it can read. The rest are listed as not retrieved, never as "no records". | services/central/app/config.py:68 |
| `MAX_UPLOAD_BYTES` | `str(10 * 1024 * 1024)` |  | services/central/app/config.py:48 |
| `OCR_ENGINE` | `'tesseract'` | Reading papers: tesseract (printed text, on this computer) \| google_vision (printed and handwritten; the page image is sent to Google Cloud Vision) | services/central/app/config.py:42 |
| `OCR_TIMEOUT_SECONDS` | `'60'` |  | services/central/app/config.py:45 |
| `OLLAMA_API_KEY` | `''` |  | services/central/app/config.py:29 |
| `OLLAMA_HOST` | `'http://host.docker.internal:11434'` | Ollama: a local server (which also serves ":cloud" models once `ollama signin` has run on that computer), or https://ollama.com directly with OLLAMA_API_KEY. | services/central/app/config.py:28 |
| `PARTICIPANTS_FILE` | `'/etc/refx/participants/participants.json'` |  | libs/common/refcommon/participants.py:39 |
| `REDIS_URL` | `'redis://redis:6379/0'` |  | services/central/app/config.py:14 |
| `REFERRAL_HISTORY_YEARS` | `'3'` | How far back retrieval asks each source (the 6-month window is the default selection, not a fetch limit), for a destination with no entry in SPECIALTY_HISTORY_YEARS | services/central/app/config.py:64 |
| `REFERRAL_WINDOW_DAYS` | `'183'` | Visits, results and imaging older than this are not retrieved for a referral. | services/central/app/config.py:21, services/provider/app/config.py:14 |
| `REMINDER_INTERVAL_DAYS` | `'7'` |  | services/central/app/config.py:57 |
| `REPO_ASSETS` | `'/srv/assets'` |  | services/central/app/config.py:16 |
| `RUN_JOBS_INLINE` | `False` |  | services/central/app/config.py:70 |
| `SEED_DATA_DIR` | `'/srv/seed-data/patients'` |  | services/provider/app/seed.py:24 |
| `SERVICE_CLIENT_ID` | (none) |  | libs/common/refcommon/auth.py:68 |
| `SERVICE_CLIENT_SECRET` | (none) |  | libs/common/refcommon/auth.py:69 |
| `SOURCE_MAX_RETRIES` | `'2'` |  | services/central/app/config.py:19 |
| `SOURCE_TIMEOUT_SECONDS` | `'10'` |  | services/central/app/config.py:18 |
| `STORAGE_ROOT` | `'/data/documents'` |  | services/central/app/config.py:15 |
| `TOKEN_AUDIENCE` | `f'{INSTITUTION}-api'` |  | services/provider/app/config.py:10 |
| `WORKING_SET_GRACE_HOURS` | `'72'` | test requests | services/central/app/config.py:55, services/provider/app/config.py:18 |

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
| `PLATFORM_KEYSTORE_SECRET` | secret: set per installation | End-to-end encryption (spec v4): each service seals its own private keys (hospital signing key, department group keys, the platform signing key) with its key-store secret. At least 16 characters; different per service. |
| `DRALI_KEYSTORE_SECRET` | secret: set per installation |  |
| `CHUGHTAI_KEYSTORE_SECRET` | secret: set per installation |  |
| `ZIAUDDIN_KEYSTORE_SECRET` | secret: set per installation |  |
| `AKUH_KEYSTORE_SECRET` | secret: set per installation |  |
| `LLM_PROVIDER` | `anthropic` | Language model (optional; used only to read uploaded papers). Leave ANTHROPIC_API_KEY empty to use the rule-based reader instead. |
| `ANTHROPIC_API_KEY` | secret: set per installation |  |
| `LLM_MODEL` | `claude-opus-5-5` |  |
| `OLLAMA_HOST` |  | Open models through Ollama instead: LLM_PROVIDER=ollama LLM_MODEL=gemma4:31b-cloud   (run `ollama signin` on the computer running Ollama; the free plan covers only some cloud models, listed at https://ollama.com/settings, and gemma4:cloud is not one) OLLAMA_HOST=http://host.docker.internal:11434   (Ollama on this computer, as seen from the containers) or call Ollama's cloud directly: OLLAMA_HOST=https://ollama.com, OLLAMA_API_KEY=<key from https://ollama.com/settings/keys>, and the model's API name (e.g. gemma4:31b) as LLM_MODEL. |
| `OLLAMA_API_KEY` | secret: set per installation |  |
| `LLM_BASE_URL` |  | Or any OpenAI-style server (Groq, vLLM, Kimi). Groq's free tier (8,000 tokens a minute, 1,000 requests a day): LLM_PROVIDER=openai_compatible LLM_BASE_URL=https://api.groq.com/openai/v1 LLM_MODEL=openai/gpt-oss-120b LLM_API_KEY=<key from https://console.groq.com/keys> LLM_REASONING_EFFORT=low   (gpt-oss: less thinking, so the answer fits and stays within the limit) |
| `LLM_API_KEY` | secret: set per installation |  |
| `LLM_REASONING_EFFORT` |  |  |
| `LLM_EXTERNAL_ALLOWED` | `false` | Privacy: patient data (always de-identified first) may go to a model outside this computer (a ":cloud" model, ollama.com, Anthropic) only when this is true. Synthetic data only until the operating institution has agreed (docs/decisions/2026-10-28-cloud-model-privacy.md). Remote servers must use https. |
| `LLM_TIMEOUT_SECONDS` | `120` |  |
| `EXTRACTION_MODE` | `auto` | Extraction: "llm" uses the language model when configured, otherwise "rules" |
| `OCR_ENGINE` | `tesseract` | Reading uploaded papers. "tesseract" reads printed text on this computer. "google_vision" also reads handwriting (doctors' prescriptions) with Google Cloud Vision: the page image is sent to Google. Key: Google Cloud console > APIs & Services > Credentials > API key, restricted to the Cloud Vision API. Synthetic data only until the operating institution has agreed to this (docs/decisions/2026-10-28-handwriting-ocr.md). |
| `GOOGLE_VISION_API_KEY` | secret: set per installation |  |
| `DOCUMENT_RETENTION_DAYS` | `365` | Retention (days) for uploaded document copies after referral closure |

### `docker-compose.yml`

| Service | Image / build | Ports | Depends on | Environment keys | Volumes | Command | Health check |
|---|---|---|---|---|---|---|---|
| `postgres` | postgres:16-alpine |  |  | AKUH_DB_PASSWORD, CENTRAL_DB_PASSWORD, CHUGHTAI_DB_PASSWORD, DRALI_DB_PASSWORD, KEYCLOAK_DB_PASSWORD, POSTGRES_PASSWORD, POSTGRES_USER, ZIAUDDIN_DB_PASSWORD | pgdata:/var/lib/postgresql/data, ./infra/postgres/init:/docker-entrypoint-initdb.d:ro |  | yes |
| `redis` | redis:7-alpine |  |  |  |  |  | yes |
| `keycloak` | quay.io/keycloak/keycloak:26.0 | 8080:8080 | postgres | AKUH_CLIENT_SECRET, CENTRAL_CLIENT_SECRET, CHUGHTAI_CLIENT_SECRET, DEMO_USER_PASSWORD, DRALI_CLIENT_SECRET, JAVA_OPTS_KC_HEAP, KC_BOOTSTRAP_ADMIN_PASSWORD, KC_BOOTSTRAP_ADMIN_USERNAME, KC_DB, KC_DB_PASSWORD, KC_DB_URL, KC_DB_USERNAME, KC_HEALTH_ENABLED, KC_HOSTNAME, KC_HTTP_ENABLED, WEB_ORIGIN, ZIAUDDIN_CLIENT_SECRET | ./infra/keycloak/import:/opt/keycloak/data/import:ro | `start-dev --import-realm` | yes |
| `drali` | build: services/provider/Dockerfile | 8001:8000 | keycloak, postgres | CENTRAL_URL, DATABASE_URL, INSTITUTION_ID, INSTITUTION_NAME, INTROSPECT_TOKENS, KEYCLOAK_INTERNAL_URL, KEYCLOAK_PUBLIC_URL, KEYCLOAK_REALM, KEYSTORE_SECRET, LOCAL_ID_PREFIX, SERVICE_CLIENT_ID, SERVICE_CLIENT_SECRET | ./infra/participants:/etc/refx/participants:ro |  | yes |
| `chughtai` | build: services/provider/Dockerfile | 8002:8000 | keycloak, postgres | CENTRAL_URL, DATABASE_URL, INSTITUTION_ID, INSTITUTION_NAME, INTROSPECT_TOKENS, KEYCLOAK_INTERNAL_URL, KEYCLOAK_PUBLIC_URL, KEYCLOAK_REALM, KEYSTORE_SECRET, LOCAL_ID_PREFIX, SERVICE_CLIENT_ID, SERVICE_CLIENT_SECRET | ./infra/participants:/etc/refx/participants:ro |  | yes |
| `ziauddin` | build: services/provider/Dockerfile | 8003:8000 | keycloak, postgres | CENTRAL_URL, DATABASE_URL, INSTITUTION_ID, INSTITUTION_NAME, INTROSPECT_TOKENS, KEYCLOAK_INTERNAL_URL, KEYCLOAK_PUBLIC_URL, KEYCLOAK_REALM, KEYSTORE_SECRET, LOCAL_ID_PREFIX, SERVICE_CLIENT_ID, SERVICE_CLIENT_SECRET | ./infra/participants:/etc/refx/participants:ro |  | yes |
| `akuh` | build: services/provider/Dockerfile | 8004:8000 | keycloak, postgres | CENTRAL_URL, DATABASE_URL, INSTITUTION_ID, INSTITUTION_NAME, INTROSPECT_TOKENS, KEYCLOAK_INTERNAL_URL, KEYCLOAK_PUBLIC_URL, KEYCLOAK_REALM, KEYSTORE_SECRET, LOCAL_ID_PREFIX, SERVICE_CLIENT_ID, SERVICE_CLIENT_SECRET | ./infra/participants:/etc/refx/participants:ro |  | yes |
| `central` | build: services/central/Dockerfile | 8000:8000 | keycloak, postgres, redis | AKUH_URL, ANTHROPIC_API_KEY, CHUGHTAI_URL, DATABASE_URL, DOCUMENT_RETENTION_DAYS, DRALI_URL, EXTRACTION_MODE, GOOGLE_VISION_API_KEY, INTROSPECT_TOKENS, KEYCLOAK_INTERNAL_URL, KEYCLOAK_PUBLIC_URL, KEYCLOAK_REALM, KEYSTORE_SECRET, LLM_API_KEY, LLM_BASE_URL, LLM_CONTEXT_TOKENS, LLM_EXTERNAL_ALLOWED, LLM_MODEL, LLM_PROVIDER, LLM_REASONING_EFFORT, LLM_TIMEOUT_SECONDS, OCR_ENGINE, OLLAMA_API_KEY, OLLAMA_HOST, REDIS_URL, SERVICE_CLIENT_ID, SERVICE_CLIENT_SECRET, STORAGE_ROOT, ZIAUDDIN_URL | documents:/data/documents, ./infra/participants:/etc/refx/participants:ro |  | yes |
| `worker` | build: services/central/Dockerfile |  | central, redis | AKUH_URL, ANTHROPIC_API_KEY, CHUGHTAI_URL, DATABASE_URL, DOCUMENT_RETENTION_DAYS, DRALI_URL, EXTRACTION_MODE, GOOGLE_VISION_API_KEY, INTROSPECT_TOKENS, KEYCLOAK_INTERNAL_URL, KEYCLOAK_PUBLIC_URL, KEYCLOAK_REALM, KEYSTORE_SECRET, LLM_API_KEY, LLM_BASE_URL, LLM_CONTEXT_TOKENS, LLM_EXTERNAL_ALLOWED, LLM_MODEL, LLM_PROVIDER, LLM_REASONING_EFFORT, LLM_TIMEOUT_SECONDS, OCR_ENGINE, OLLAMA_API_KEY, OLLAMA_HOST, REDIS_URL, SERVICE_CLIENT_ID, SERVICE_CLIENT_SECRET, STORAGE_ROOT, ZIAUDDIN_URL | documents:/data/documents, ./infra/participants:/etc/refx/participants:ro | `celery -A app.tasks worker -B --loglevel=info --concurrency=2 -Q referral` |  |
| `web` | build: Dockerfile | 3000:80 | central |  | ./infra/participants:/etc/refx/participants:ro |  |  |

Named volumes: `documents`, `pgdata`

### `docker-compose.prod.yml`

| Service | Image / build | Ports | Depends on | Environment keys | Volumes | Command | Health check |
|---|---|---|---|---|---|---|---|
| `caddy` | caddy:2-alpine | 80:80, 443:443 | keycloak, web | SITE_HOST | ./infra/caddy/Caddyfile:/etc/caddy/Caddyfile:ro, caddy_data:/data, caddy_config:/config |  |  |
| `keycloak` |  |  |  | KC_HOSTNAME, KC_HTTP_ENABLED, KC_HTTP_MANAGEMENT_RELATIVE_PATH, KC_HTTP_RELATIVE_PATH, KC_PROXY_HEADERS, WEB_ORIGIN |  | `start --import-realm` |  |
| `web` | build: Dockerfile |  |  |  |  |  |  |
| `postgres` |  |  |  |  |  |  |  |
| `drali` |  |  |  | KEYCLOAK_INTERNAL_URL, KEYCLOAK_PUBLIC_URL |  |  |  |
| `chughtai` |  |  |  | KEYCLOAK_INTERNAL_URL, KEYCLOAK_PUBLIC_URL |  |  |  |
| `ziauddin` |  |  |  | KEYCLOAK_INTERNAL_URL, KEYCLOAK_PUBLIC_URL |  |  |  |
| `akuh` |  |  |  | KEYCLOAK_INTERNAL_URL, KEYCLOAK_PUBLIC_URL |  |  |  |
| `central` |  |  |  | KEYCLOAK_INTERNAL_URL, KEYCLOAK_PUBLIC_URL |  |  |  |
| `worker` |  |  |  | KEYCLOAK_INTERNAL_URL, KEYCLOAK_PUBLIC_URL |  |  |  |

Named volumes: `caddy_config`, `caddy_data`

### `docker-compose.dbaccess.yml`

| Service | Image / build | Ports | Depends on | Environment keys | Volumes | Command | Health check |
|---|---|---|---|---|---|---|---|
| `postgres` |  | 127.0.0.1:5432:5432 |  |  |  |  |  |
