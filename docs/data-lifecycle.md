# Data lifecycle (architecture spec v4, sections 7 and 11)

## In one paragraph

The source institutions keep their records in their own databases. For a referral, a records request carries the
patient's signed consent, and each institution's adapter answers under its own policy with titles and ciphertext
encrypted for the referring doctor. The platform stores that ciphertext only while the referral is open. The doctor
decrypts on their device, chooses what goes in, and signs the package; the data keys are re-wrapped for the receiving
department and the patient. When the specialist closes the referral (or it is declined, denied, cancelled, or reaches
its maximum lifetime), the platform deletes the ciphertext and the wrapped keys and keeps a receipt. The patient's
copy on their phone is the only copy of the referral that lasts (D16).

## What is stored where (spec v4 11.1)

| Data | Central platform | Institutions | Patient's phone |
|---|---|---|---|
| Referral metadata, status, reason, timestamps | Kept | The receiving hospital's own case (its decision and questions) | Summary |
| Record titles | Only while open (deleted with the ciphertext, O6) | The receiving hospital keeps the notice's titles until the purge notice | Yes |
| Record content | Ciphertext, only while open | The original stays in the source institution's database; never copied to another | Yes, kept, encrypted with the patient's key |
| Wrapped data keys | Only while open | None | The patient's own |
| Signed package manifest | Kept (no plaintext) | The notice holds its hash | Yes |
| Consent | Kept | Each adapter checks it when asked | Yes |
| Audit | Kept: ids, actors, reason codes, hashes | Each institution's own audit | None |

## Lifecycle (spec v4 7)

| When | What happens |
|---|---|
| Open, not yet accepted | No time limit |
| Accepted by the specialist | A close reminder to the receiving department's doctors after `ACCEPTED_HOLD_DAYS` (30), then every `REMINDER_INTERVAL_DAYS` (7). After `ESCALATE_AFTER_REMINDERS` (3) reminders, the receiving staff are told too. Never closed silently (O4). |
| The specialist extends | 30 more days, with a reason, at most `MAX_REFERRAL_DAYS` (180) after acceptance. The reminder moves with it. |
| The specialist closes | Purged after `CLOSE_GRACE_DAYS` (7). The patient is told to save their copy. |
| Declined, denied or cancelled | Purged after `DECLINE_GRACE_DAYS` (1) |
| Maximum lifetime reached, after escalation | Everyone is told (both hospitals' doctors and staff, and the referring side); purged after the close grace period |
| Test and scan orders | Unchanged from v2 (out of scope for v4): results are kept `WORKING_SET_GRACE_HOURS` (72) after they are back |

## Purge by crypto-shredding (spec v4 5.9, 11.2)

`lifecycle/working_set.py`, run every 10 minutes by the worker. It is idempotent and resumable:

1. It waits until every delivery carrying the referral is confirmed (or failed for good).
2. It deletes the referral's ciphertext items, their titles, the batches and every wrapped data key.
3. It writes a purge receipt: when, how many items and wrapped keys, the latest signed manifest's hash, and the
   trigger (closed by the specialist, declined, cancelled, maximum lifetime).
4. It tells the receiving hospital, whose system drops its notice and keeps only identifiers and the hash.

A second run finds nothing to delete and keeps the first receipt. After the purge the platform answers "purged" (HTTP
410), never "no records", and `POST /e2e/verify-manifest` still confirms a holder's copy against the recorded hash.

**Backups:** a backup taken while the referral was open holds ciphertext and wrapped keys. It becomes unreadable once
no backup still holding the wrapped keys is kept, so the backup retention window must not exceed what the institution
accepts for referral data. See `operations.md`.

## The patient's copy (spec v4 11.3)

The patient saves the signed package on their phone (`GET /patient-access/referrals/{reference}/copy`): ciphertext, the
data keys wrapped to their key, the manifest and the signer's directory entry. The app opens it with the patient's
device key and checks it against the referring doctor's signature, also after the purge. The download is the same
encrypted copy. The doctor's notes for the specialist are in it only if the doctor chose to share them. If the phone
is lost, so is the copy; the institutions still hold the originals.

## No sender-side copy (D16)

Nothing is written back to the sending hospital's system. The v2 "sender's own copy" and the receiving hospital's
stored package were removed: the receiving hospital gets a titles-only notice, and its doctors open the ciphertext from
the platform.
