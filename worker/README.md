# Background worker

The worker shares the central platform's image and code (`services/central/app/tasks.py`) so job handlers and workflow logic cannot drift apart. Compose runs it as:

```
celery -A app.tasks worker -B --concurrency=2 -Q referral
```

| Task | Trigger | Notes |
|---|---|---|
| `process_document` | upload / reprocess | Embedded-text or Tesseract OCR, then field extraction; re-checks requester authorization first |
| `generate_brief` | "Draft with AI" | Language model behind `LLMProvider`; strict schema and evidence-ID validation; failures are visible on the job |
| `deliver_outbox` | every 5 s (beat) and after submit | Idempotent delivery to the specialist service with bounded exponential retry |
| `retention_sweep` | hourly (beat) | Deletes document copies of closed referrals after the retention period |

Redis is only the broker. Job state (`jobs` table), outbox state and all results live in PostgreSQL. A lost Redis message is recovered by the next beat run for delivery, or by "Retry extraction" for documents.
