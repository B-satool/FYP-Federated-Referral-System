## Background jobs (`services/central/app/tasks.py`, Celery worker with beat)

Redis is the queue only; job state lives in PostgreSQL (`jobs` table).

| Task | Schedule | Purpose | Function |
|---|---|---|---|
| `process_document` | on demand | Process document. | `process_document` |
| `deliver_outbox` | every 5 s | Deliver outbox. | `deliver_outbox` |
| `retention_sweep` | every 3600 s | Delete uploaded document copies of closed referrals after the retention period. Approved package snapshots and audit history are retained by policy. | `retention_sweep` |
| `close_referral_grants` | every 60 s | For finished referrals, ask each institution to revoke the access grants opened for them. | `close_referral_grants` |
| `purge_working_sets` | every 600 s | Remove the clinical content of working sets whose time is up (see lifecycle/working_set.py). | `purge_working_sets` |
| `recommend_selection` | on demand | AI packet-selection recommendation, run in the background after retrieval (it can take a minute). | `recommend_selection` |
