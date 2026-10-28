# 11. Interfaces

## 11.1 Interface catalogue

| Interface | From → to | Protocol | Contract |
|---|---|---|---|
| Central REST API | Web app → `central` (`/api/central/*`) | HTTPS (production), JSON, user token | Appendix F; OpenAPI at `/docs` and `/openapi.json` on the service |
| Institution REST API (own staff) | Web app → institution (`/api/<institution>/*`) | JSON, user token | Appendix F (institution section) |
| Record retrieval | `central` → institution | JSON and FHIR R4 Bundle, forwarded user token, `X-Referral-Id` | Section 5.6, `docs/fhir-subset.md` |
| Identity lookup, registration, intake, grants | `central` → institution | JSON, user token | Appendix F |
| Package, order, copy, clarification answer, expiry delivery | `central` (worker) → institution `inbound/*` | JSON envelopes, `central-api` service token | Appendix G (`PackageEnvelope`, `DiagnosticOrder`, `ClarificationAnswer`, …) |
| Provider events | institution → `central` `POST /inbound/provider-events` | `ProviderEvent` envelope, institution service token | Appendix G |
| Grant close-out | `central` (worker) → institution `POST /grants/revoke-by-referral` | JSON, `central-api` service token | Appendix F |
| Identity provider | all → Keycloak | OIDC, JWKS, token introspection, client credentials, admin REST API (role templates, account status) | Appendix K |
| Language models | `central`, worker → Ollama, Anthropic, OpenAI-compatible | HTTPS (or local HTTP to Ollama) | Section 9.1 |
| OCR service | worker → Google Cloud Vision `images:annotate` | HTTPS, key in the `X-Goog-Api-Key` header | Section 6.4 |

## 11.2 API conventions

- **Resources** are referral-centred (`/referrals/{id}/...`), with sub-resources for evidence, documents, medicines, flags, links, retrievals, selection, packages, diagnostics, tasks and responses.
- **Writes** that change a referral carry `expected_row_version`. A stale version returns `409 stale_version` with `current_version`.
- **Errors** share one shape: `{"detail": {"code": "<machine code>", "message": "<sentence for a person>", ...}}`. Validation errors return `422 validation_error` naming the first failing field.

| Status | Codes |
|---|---|
| 401 | `account_disabled`, invalid or expired token |
| 403 | `forbidden` (audited), `access_denied` at sources, `wrong_institution`, `wrong_destination` |
| 404 | `not_found`, `unknown_referral` |
| 409 | `invalid_transition`, `stale_version`, `clinical_content_locked`, `record_linked_elsewhere`, `not_accepted`, `patient_not_informed`, `tasks_open`, `outcome_not_seen`, `already_closed` |
| 410 | `deleted` (document removed under retention) |
| 415 | `unsupported_type` (upload is not PDF, PNG or JPEG by content) |
| 422 | `too_large`, `too_many_pages`, `validation_error`; every upload rejection is audited |
| 502 | `identity_provider_refused` (Keycloak admin call failed) |
| 503 | `not_ready` |

- **Health:** every service exposes `GET /health` (process up) and `GET /ready` (database reachable). Compose health checks use `/ready`.
- **Lists** are bounded (for example 100 notifications, 500 medicine names, 150 AI candidates). There is no general pagination.

## 11.3 Envelope versioning

Envelopes carry an `envelope_version`:

- `referral-package/2.0`
- `diagnostic-order/1.0`
- `provider-event/1.0`

They also carry `contract_note = "Project API contract (not a standard FHIR resource)"`.

**Changing a contract.** Contract changes (`libs/common/refcommon/exchange.py`, `contracts/`) need the consuming owner's approval (AGENTS.md). Additive fields keep the version. A breaking change bumps it, and the receiver must reject versions it does not understand. `contracts/examples/` holds example payloads exported by `scripts/export_contract_examples.py`, and `contracts/fhir-samples/` holds FHIR samples validated by the official validator (`scripts/fhir-validate.ps1`).

## 11.4 Idempotency keys

| Message | Key | Receiver behaviour on repeat |
|---|---|---|
| Package delivery | `delivery_key` = `<source>:<reference>:v<version>` | `incoming_packages.delivery_key` unique: returns `already_received` with the original case |
| Sender copy | `copy_key` | `sent_copies.copy_key` unique |
| Diagnostic order | `order_key` = `<source>:<DX reference>` | `orders.order_key` unique |
| Provider event | `event_key` | `inbound_messages.message_key` unique: returns `duplicate` |
| Clarification answer | `answer_key` | `info_requests.answer_key` unique |
| Forwarded result (not built) | `forward_key` | `forwarded_results.forward_key` unique |
| Response (legacy) | `return_key` and event key | unique |

Retries always reuse the key, so a request that timed out but succeeded is never applied twice (invariant 9). The outbox row is written in the same transaction as the decision to send.
