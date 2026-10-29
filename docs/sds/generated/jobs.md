## Background jobs (`services/central/app/tasks.py`, Celery worker with beat)

Redis is the queue only; job state lives in PostgreSQL (`jobs` table).

| Task | Schedule | Purpose | Function |
|---|---|---|---|
| `process_document` | on demand | Process document. | `process_document` |
| `deliver_outbox` | every 5 s | Deliver outbox. | `deliver_outbox` |
| `retention_sweep` | every 3600 s | Delete uploaded document copies of closed referrals after the retention period. Approved package snapshots and audit history are retained by policy. | `retention_sweep` |
| `purge_working_sets` | every 600 s | Crypto-shred referrals whose time is up (see lifecycle/working_set.py); a failure is retried next run. | `purge_working_sets` |
| `seal_audit` | every 60 s | Add the audit events written since the last run to the hash chain (spec v4 11.5). | `seal_audit` |
| `close_reminders` | every 3600 s | Close reminders 30 days after acceptance, weekly repeats and escalation (spec v4 7). | `close_reminders` |
