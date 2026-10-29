# 12. Reliability and error handling

## 12.1 Failure semantics

| Failure | Behaviour | What the user sees |
|---|---|---|
| Institution slow or down during retrieval | Timeout `SOURCE_TIMEOUT_SECONDS` (10 s), up to `SOURCE_MAX_RETRIES` (2) retries for transient errors; other sources continue in parallel | Source marked "unavailable" (retryable); `records_incomplete` flag; letter lists it as a limitation |
| Access denied or grant expired | No retry; centrally held copies from that source become `access_revoked` and deselected | "Denied" or "access expired", never "no records" |
| Invalid FHIR from a source | Invalid resources counted and listed; the rest imported | "Partial" with the reasons |
| Delivery to an institution fails | Outbox retry with the same key, backoff 2^n s up to 120 s, 8 attempts | Delivery problem in the staff work queue; manual retry (`POST /referrals/{id}/retry-delivery`) |
| Institution cannot reach the platform | Institution outbox thread retries with the same event key | Event applied once when the platform is back |
| Model unavailable, refused or invalid | Rule-based default selection or rules extractor | "AI recommendation unavailable" with the reason |
| OCR engine failure | Google Vision falls back to Tesseract; processing errors fail the job visibly | Document status `failed` with the error; reprocess available |
| Keycloak admin call fails | No partial role change | `502 identity_provider_refused` |
| Worker down | Jobs stay queued (Redis); outbox rows stay pending; purges wait | Jobs pending; nothing lost, because job state is in PostgreSQL |
| Purge while a delivery is unconfirmed | Purge deferred and audited with reasons | Content kept until delivery is confirmed |
| Concurrent edits | Optimistic concurrency | "Changed by someone else, reload" (409) |

## 12.2 Consistency model

- **Within a service:** one PostgreSQL transaction per request. Domain changes, audit rows, events, notifications and outbox rows commit together.
- **Between services:** eventual consistency through outboxes with idempotent receivers. Statuses reflect confirmed facts only:
  - a referral becomes `submitted` only when the receiving service confirms receipt;
  - acknowledgement, acceptance and completion come only from the receiver's events.
- **Out-of-order events:** an `accepted` event arriving while the referral is still `submitted` first applies `acknowledged`, so the state machine stays valid.

## 12.3 Background job safety

- **Delivery semantics:** `task_acks_late=True` and `worker_prefetch_multiplier=1` mean a task is acknowledged only after it finishes. A worker crash re-delivers it, and every task is idempotent.
- **Permission re-check:** document jobs re-check the requester's account and institution before running.
- **Scheduled sweeps** (beat):
  - outbox: every 5 s;
  - grant close-out: every 60 s;
  - working-set purge: every 10 min;
  - document retention: hourly.

  Each sweep only does work that is due, so a missed run is caught up by the next.
