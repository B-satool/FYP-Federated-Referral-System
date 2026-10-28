# Decision: a referral's shared records expire when the referred doctor has finished with it

- **Date:** 2026-10-28
- **Status:** decided by the project lead on 2026-10-28. Built and tested the same day.
- **Replaces:** section 3 ("The referred doctor sets the access window") of
  [2026-10-28-referral-access-window.md](2026-10-28-referral-access-window.md), which was never built,
  and the 60-day maximum of [2026-10-27-data-lifecycle-and-v3.md](2026-10-27-data-lifecycle-and-v3.md).

## Rules

"Shared records" means the records retrieved for the referral, the papers, the medicine list, the flags, the letter
and the sent package. They are held on the platform and in the receiving hospital's copy.

| When | Shared records |
| --- | --- |
| Sent, not yet accepted | Kept, with no time limit |
| Receiving doctor **accepts** | Kept, with a safety limit of 30 days after acceptance (`ACCEPTED_HOLD_DAYS`) |
| Receiving doctor **extends** (with a reason; any number of times) | The limit becomes 30 days from then (never shorter) |
| Receiving doctor **marks it complete** (only after sending their response) | Removed 72 hours later (`WORKING_SET_GRACE_HOURS`) |
| Receiving doctor **declines** | Removed straight away |
| Referring doctor **cancels** | Removed 72 hours later |
| Test request (lab, radiology, ECG) | Removed 72 hours after all results are back, or after it is closed or cancelled |

Answering or closing a referral no longer starts the clock by itself. The safety limit covers a doctor who never
presses "Mark as complete".

## What is removed, and where

- **On the platform:** the content of the working set, as before (`lifecycle/working_set.py`). The reference,
  status, audit trail, package manifest and SHA-256 fingerprint stay.
- **At the receiving hospital:** the platform sends `expire_shared` to `POST /inbound/referral-expired`. The
  hospital's system then removes its copy of the packages and the results forwarded with them. Its own decision,
  questions and response are its record and are kept. Its screen says when the records were removed.
- **Not changed:** the sending clinic's own copy (`sent_copies`) is kept, as decided on 2026-10-27. The access-window
  decision's plan to send the receiver a notification instead of the package (its parts B, C and D) is not built.
  The receiving hospital still gets the package, and removes it at expiry as described above.

## Changes to exchange contracts (owner review)

- `ProviderEventType` gains `completed` and `hold_extended` (`libs/common/refcommon/exchange.py`).
- New institution endpoints: `POST /cases/{id}/complete`, `POST /cases/{id}/extend-hold` and
  `POST /inbound/referral-expired`.
- Migrations: `referrals.receiver_completed_at` and `referrals.receiver_completed_by` (central), and
  `cases.completed_by`, `cases.completed_at`, `cases.hold_until` and `cases.shared_removed_at` (institution service).

## Tests

- `services/central/tests/test_lifecycle.py`: each rule.
- `tests/test_referral_expiry.py`: accept → extend → complete → expiry. This checks that both the platform's copy
  and the receiving hospital's copy are removed, and that the hospital's response is kept. It also checks that a
  decline removes the records straight away.
- `web/e2e/smoke.spec.ts`: the surgeon presses "Mark as complete", and the referring doctor sees it.
