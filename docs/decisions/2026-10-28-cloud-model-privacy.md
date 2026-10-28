# Decision: Gemma 4 through Ollama's cloud, with patient data de-identified

- **Date:** 2026-10-28
- **Status:** decided by the project lead on 2026-10-28. Built the same day. The live model call needs
  `ollama signin` on the computer running Ollama (not done yet).

## What the model does

`gemma4:cloud` is reached through the Ollama on this computer (`LLM_PROVIDER=ollama`,
`OLLAMA_HOST=http://host.docker.internal:11434`). It:
- recommends which retrieved records go in the referral packet (`selection/selection.py`);
- reads the medicine and lab fields of uploaded papers when `EXTRACTION_MODE=auto` (`documents/processing.py`).

Its output is a suggestion only. It is checked in code, staff decide, and record text is treated as data. The model
has no tools.

## How patient data is protected (`app/generation/privacy.py`)

| Measure | Detail |
| --- | --- |
| Explicit permission | A model that runs outside this computer is used only if `LLM_EXTERNAL_ALLOWED=true` (default `false`). This covers `:cloud` models even through a local Ollama, ollama.com, Anthropic and any remote server. Otherwise the call is refused before anything is sent, and the rule-based selection applies. |
| Encrypted transport | A remote model server must use `https`. The local Ollama forwards `:cloud` requests to ollama.com over TLS. |
| De-identification, always | Never sent: name, CNIC, record numbers, date of birth, referral reference. Patient name parts, ID and phone numbers, doctors' names and institution names are removed from the text. Calendar dates become "N days before the referral" (paper reading keeps dates, because a medicine's start date is one of its fields). The model receives age, sex, the reason, the department, the procedure, and each record's category and text. |
| Minimum necessary | At most 150 records, each cut to 300 characters. Only the fields the task needs. |
| Audit, not logs | Each call records the model, prompt version, record count, destination and `deidentified: true` in the audit trail (`selection.recommend`). Record content is never logged. Keys stay in `.env`, and the Google key travels in a header, never in a URL. |
| Fallback | If the model is refused, unreachable or gives an answer that fails the checks, nothing is applied and the screen says "AI recommendation unavailable". |

## Limits to state plainly in the report

- De-identification uses patterns. A name written unusually, or a rare detail in free text, could still identify
  someone. That is why this stays on **synthetic data only** until the operating institution agrees.
- Once data reaches Ollama's cloud, its handling follows Ollama's terms and privacy policy. Check the current
  terms before any real use. Alternatively, run a local model (`medgemma:4b`, kept on the local branch
  `medgemma-local`), so nothing leaves the computer.
- Uploaded paper images sent to Google Cloud Vision cannot be de-identified the same way
  (see `2026-10-28-handwriting-ocr.md`).
