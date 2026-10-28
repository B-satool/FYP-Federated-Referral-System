# Decision: the receiving doctor accepts or declines; no specialist response

- **Date:** 2026-10-28
- **Status:** decided by the project lead on 2026-10-28. Built the same day.

## What changes

- The receiving doctor **accepts or declines** the referral. A decline needs a reason. Either way the requesting
  doctor is notified, and staff are notified too because they tell the patient. There is no assessment or plan
  form, and the referring clinic has no "review the specialist's response" step.
- **Mark as complete** stays a separate, deliberate action by the receiving doctor. It is available any time after
  accepting and never happens by itself. It starts the 72-hour removal of the shared records
  ([2026-10-28-referral-expiry.md](2026-10-28-referral-expiry.md)).
- **Referring clinic:** once the referral is accepted, staff record that the patient was told. Follow-up tasks are
  optional. Then the **doctor or staff** close it. Closing no longer waits for a response.
- Test requests are unchanged: results still come back from the laboratory or radiology department.

## Kept for compatibility

- The response endpoints (`PUT /cases/{id}/response`, `POST /cases/{id}/response/send`, `POST /responses/{id}/review`)
  and the `response_returned` event still exist. A response sent before this change is still shown, read-only.
- The referral status `response_returned` is still used by test requests (results back).
