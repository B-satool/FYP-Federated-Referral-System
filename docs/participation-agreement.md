# Participation agreement: how the system enforces or records each clause (spec v4 6.1)

The agreement itself is a legal document. Its text is a team and supervisor deliverable and is not drafted here. This page lists what the software does for each clause. Version `PA-1.0`, dated 2026-10-29, is recorded for every institution at onboarding.

| Clause | System behaviour | Where |
|---|---|---|
| **Allowed purposes:** referral and treatment, emergency, patient's own access | The request assertion's `purpose` must be `TREAT`, `ETREAT` or `PATRQT`. Anything else is refused with `request_incomplete_or_invalid`. | `refcommon/participants.py` (`PURPOSES`); `services/provider/app/release.py` (`check_claims`) |
| **Duty to respond** to referral requests with valid consent unless an exception applies | Every request is logged at both ends. Requests waiting for staff appear in the institution's queue, with the reason `pending_manual_review` shown to the requester. | `GET /e2e/record-requests` at each adapter; `record_requests` at the platform |
| **Allowed refusals:** prohibited by law; too sensitive without specific consent; incomplete or invalid request | The adapter answers with a **structured refusal** carrying one of the reason codes. It never answers with an empty list. "Could not be reached" and "holds no matching records" are separate outcomes from a refusal. | `services/provider/app/policy.py` (`REFUSAL_REASONS`) |
| **Security duties:** encryption, audit logs, breach reporting | Encryption per spec v4 section 5 (`docs/crypto.md`). Audit at every service. Breach procedure below. | |
| **Liability** if data is misused after it is shared | Documentation only. | This page |
| **Retention:** the receiver deletes data when the referral packet expires | The platform purges ciphertext and wrapped keys when the referral is closed (spec v4 section 11). | WP9 |
| **Onboarding record** | Each institution's id, name, pinned signing key, adapter URL, agreement version and date | `infra/participants/participants.json` (`scripts/onboard_participants.py`) |
| **Suspension** | Set `status: suspended` (`--suspend <id>`). The platform stops calling that institution and refuses its signed requests. The other adapters refuse requests on its behalf. | `refcommon/participants.py` (`in_good_standing`) |

## Breach-report procedure (draft)

1. The person who notices a suspected breach tells their institution's administrator and the platform operator the same day.
2. The operator preserves the audit trail (it is append-only) and records what was exposed. Ciphertext without keys is not a disclosure of content. Titles, demographics and metadata are.
3. If a hospital signing key or the platform key may be compromised: revoke and re-key, re-run onboarding, and tell every participant to compare the new fingerprints.
4. Notify the affected institutions and, through them, the patients, within the period the law requires.

> **Not verified:** the draft Personal Data Protection Bill is said to require notification within 72 hours. Check the actual bill text before citing this figure. Until then the procedure says "within the period the law requires".
