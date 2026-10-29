# 9. AI and machine-learning design

The system uses AI in three places, each optional and each kept outside the safety-critical path:

| Use | Technique | Runs | Can it change flags or remove records? |
|---|---|---|---|
| Packet selection recommendation | Language model, structured JSON | Worker, after retrieval | No. It may add records and mark relevance; defaults and staff choices always stand |
| Reading fields from uploaded papers | Language model, structured JSON with line-id citations | Worker, per document | No. Proposals are unverified until staff check them against the page image |
| Possible drug–drug clashes not in DDInter | Logistic regression trained offline | Offline script; the app only looks results up | No. Labelled "AI suggestion, not verified"; never a flag |

Handwriting OCR through Google Cloud Vision is a service call, not a model the project trains or prompts (Section 6.4).

## 9.1 Provider abstraction (`generation/provider.py`)

Workflow code depends only on `LLMProvider.structured(system, user_payload, schema, max_tokens) -> dict`. Choose the implementation with `LLM_PROVIDER`:

| Provider | Configuration | Structured output |
|---|---|---|
| `anthropic` | `ANTHROPIC_API_KEY`, `LLM_MODEL` (default `claude-opus-5-5`) | JSON-schema output format enforced by the API; server-side refusal fallback; `refusal` and `max_tokens` stops are rejected |
| `ollama` | `OLLAMA_HOST` (default `http://host.docker.internal:11434`), `LLM_MODEL` (for example `gemma4:cloud`), optional `OLLAMA_API_KEY` for ollama.com | Local models get the schema as `format`. Ollama's cloud does not enforce schemas, so for `:cloud` models and ollama.com the schema goes in the prompt and the reply is checked by `check_schema` |
| `openai_compatible` | `LLM_BASE_URL` (…/v1), `LLM_API_KEY`, `LLM_MODEL`, optional `LLM_REASONING_EFFORT` (sent only when set). Demo setting: Groq, `openai/gpt-oss-120b`, effort `low` | Chat completions with a JSON response format; reply checked by `check_schema` |
| `disabled` | none configured | Raises `ProviderUnavailable`; rule-based paths apply |

**Error handling.**

- **`ProviderUnavailable`:** no model, unreachable server, 401 or 403, 429 or other status errors, or a refused destination.
- **`ProviderOutputInvalid`:** truncated output, invalid JSON, schema mismatch, or failed reference validation.

Callers treat both as "AI unavailable" and keep the deterministic result. Every answer goes through `check_schema()`, which checks the JSON Schema subset the project uses (type, properties, required, additionalProperties, items, enum), whatever the provider.

## 9.2 Packet selection prompt and validation (`selection/selection.py`)

**Prompt.** The system prompt (versioned by `PROMPT_VERSION`, fingerprinted by `PROMPT_HASH` over the version, prompt and schema) asks the model to return, for every record id:

- `recommendation`: include, exclude or optional;
- `relevance`: high, medium or low;
- `reason`: at most 25 words, describing why the specialist needs the record, never what should be done.

It also asks for at most 5 "missing" phrases, and forbids treatment, dosing or medicine advice and invented ids. It names words to avoid (stop, hold, continue, resume, manage, adjust, dose, clearance, must, should).

**Payload** (after de-identification):

- **Referral:** kind, reason, the doctor's consultation notes (at most 2,000 characters), department, planned procedure, procedure status and urgency, with age and sex. Prompt version `packet-selection/4`.
- **Each record:** id, category, relative date, default flag and text, cut to 300 characters.

**Validation** rejects the whole answer when:

- the keys aren't exactly `items` and `missing`;
- an id is unknown, a boolean or repeated;
- a value isn't in its allowed set;
- a reason is empty or longer than 25 words.

**Withheld, not fatal:**

- **A reason with advice or action words** (patterns `ADVICE`, `DOSING`): `DOSING` covers dose, adjust, hold, cessation, continue, resume, manage, clearance, must and should. The reason is never shown or stored, and that record keeps its default. The run notes how many were withheld.
- **A missing phrase with those words, or longer than 15 words,** is dropped.

Until 2026-10-29 a single such reason rejected the whole answer. gpt-oss-120b wrote borderline phrases ("relevant for medication dosing") in nearly every answer, and also real advice that the older, narrower `DOSING` pattern missed ("must be managed before surgery", "requires cessation", "generally continued").

**Applying the answer.**

- Staff choices are never overridden.
- Items in the default floor stay selected; the model's "exclude" on them is shown as a low-relevance hint only.
- Non-default items the model includes become selected with `selection_source=ai`.

The run is recorded in `selection_runs`, and the package's `selection` field records each item's source (default, AI or staff), the model and the prompt version.

**Observed behaviour:**

- **`gemma4:cloud`** (integration test run, 2026-10-28): 12 of 15 runs completed. 3 were rejected by the dosing-word check. In every rejected case the default selection stood, as designed.
- **Groq `openai/gpt-oss-120b`, effort `low`** (2026-10-29, P5 referral, 29 records): 3 of 3 runs completed in about 4 s, each with 1 to 3 reasons withheld. The answer used about 3,500 tokens, so the free tier (8,000 tokens a minute) allows about two referrals a minute; a 429 leaves the default in place.
- **The same model at the default effort** used the whole token budget thinking, and the reply was cut off.

## 9.3 Paper field extraction (`documents/processing.py`)

**Input.** The model receives the paper's OCR lines (`i`, page, text), de-identified with dates kept.

**Output.** It must return, under `extraction_schema()`:

- **medicines:** name, strength, dose, route, frequency, start date, line ids;
- **labs:** test, value, unit, date, line ids;
- the document date.

**Checks and fallback.** Any field that cites an unknown line id, or no line id, rejects the answer. With `EXTRACTION_MODE=auto` the deterministic `rules-extractor/2` then runs instead, and the run notes say so. With `llm` the failure is reported. The extractor version is recorded on each `extraction_runs` row (`llm:<model>` or `rules`).

## 9.4 AI suggestions (offline logistic regression)

`scripts/train_ai_suggestions.py` trains a logistic regression on DDInter 2.0. The positives are 160,235 known pairs; pairs absent from DDInter are unlabelled background, not negatives. Features:

- shared ATC group;
- how often each drug's ATC class-mates interact with the other drug;
- each drug's interaction count;
- the ATC main groups involved.

It scores every pair among the project's ingredients that has no DDInter entry and writes those scoring 0.8 or more to `rules/ai/suggestions.json`. The evaluation is in `rules/ai/evaluation.json`: at 0.8, 73% of held-out known interactions are found, with about 3.4 suggestions per 100 random pairs that DDInter doesn't cover.

The app only looks these up (`medications/suggestions.py`, `ai_view.py`). A pair that DDInter covers is never suggested. The evaluator has no input from this model: unit tests force every score to 0 and to 1 and check that the flags are identical. None of these figures is clinical accuracy.

## 9.5 Guardrails summary

| Guardrail | Where |
|---|---|
| Model output is a draft; people decide | Staff selection always wins; paper fields unverified until checked |
| Output validated in code; a structural failure rejects the whole answer, and advice wording is withheld | `check_schema`, `selection.validate`, extraction line-id check |
| Every record-derived statement cites supplied ids | Selection ids, extraction line ids; the letter itself is deterministic and cites evidence ids |
| Document and record text is untrusted data | Marked as data in the prompt; no tools; schema-only output |
| Never creates, changes or restates flags | The evaluator has no model input; flags are not in the model's output schema |
| Privacy | De-identification, external-model switch, https only, audit without content (Section 8.6) |
| Graceful absence | Without a model, or on any failure, deterministic defaults apply and the screen says "AI recommendation unavailable" |
