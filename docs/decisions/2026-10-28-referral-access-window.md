# Decision: shared records are viewed through the platform, for an access window the referred doctor sets

- **Date:** 2026-10-28
- **Status:** agreed by the project team (reported by the project lead on 2026-10-28). Not yet built. **Section 3 (the 7/30/90-day window) is replaced by [2026-10-28-referral-expiry.md](2026-10-28-referral-expiry.md)**, which is built: records are kept until the referred doctor marks the referral complete (then 72 hours), with a 30-day safety limit after acceptance that they can extend; a decline removes them straight away. Builds on `2026-10-27-data-lifecycle-and-v3.md`, which made the platform's own copy temporary.
- **Why:** After v3 the platform deletes its copy, but the receiving institution keeps the full package in its own database (`incoming_packages.envelope`), and the sending clinic keeps a full copy (`/outbound-copies`). So patient records from other institutions stay with B after the referral has ended.

## What was decided

1. **Shared records are never copied to the receiving institution.**
   - Delivery to B becomes a **notification**: referral ID, version, urgency, specialty, B's local patient ID, the package manifest and its SHA-256. It holds no clinical content.
   - B's staff and doctors read the package, forwarded results and clarification answers **from the central platform**, with their own login, while the access window is open. Each view is audited.
2. **Each institution keeps what it wrote itself.**
   - **B keeps permanently:** its accept or decline decision, its questions and its consultation response. These are B's medical record.
   - **A keeps permanently:** what it wrote for the referral (reason, letter, medication review decisions) and the manifest. Its sender copy no longer contains other institutions' records, whose originals stay in their source systems.
   - **Temporary:** records retrieved from other institutions (clinics, hospitals, labs) exist only on the platform, and only for the window.
3. **The referred doctor sets the access window.**
   - **Until the referral is accepted, it does not expire.** The content stays available for B to triage and decide. The referring clinic can still cancel it at any time.
   - **On acceptance, a 30-day window starts automatically.**
   - **The referred doctor** can instead pick **7, 30 or 90 days**, counted from when they pick. They can change it at any time, shorter or longer.
   - **Hard limit:** content is never held more than **90 days after acceptance**. This replaces `WORKING_SET_MAX_DAYS` (60).
   - **Answered, cancelled or closed:** the existing **72-hour** grace applies if it ends sooner.
   - **Declined:** the shared content is deleted straight away, with no grace period. The referring doctor and staff are notified with B's reason (this notification exists already, `delivery/inbound.py`). The decline and its reason stay with both sides as authored records.
   - **Warning:** **3 days** before expiry, the referred doctor and the referring clinic are told.
4. **After the window ends:**
   - The platform deletes the content as it does now (identifiers, status, audit, manifest and hash stay).
   - Both sides see "Access window ended on <date>", never an empty record (invariant 7).
   - If more is needed, the referring clinic retrieves again, which starts a new working set and a new version.
5. **Viewing controls:**
   - Content is shown view-only, with no download, export or print button.
   - Each page is watermarked with the viewer's name and the time.
   - These controls discourage copying but cannot prevent it (screenshots, manual typing). The rest is covered by the data-sharing agreement between institutions and the audit trail. This must be stated plainly in the report.
6. **Patient consent is not added.** The team's view: by attending the referring clinic and accepting the referral, the patient expects the clinicians involved to see the records needed for their care. Recorded here as a design assumption to defend in the report.

## Changes to the AGENTS.md invariants

- **4 (packages immutable and kept):**
  - Immutable as before: the SHA-256 and manifest never change.
  - **No institution keeps another institution's records after the window.** What lasts is each institution's own authored work, and the fingerprint.
- **8 (never overwrite original data):** unchanged for sources. Copies on the platform are deleted at window end, as in v3.
- **9 (idempotency):** delivery keys still make notifications safe to retry. A purge no longer waits for the sending clinic to confirm a full copy.

## Implementation plan

| # | Work | Main files |
|---|---|---|
| A | **Window on the referral.** `access_window_days`, `access_window_set_by/at`, `accepted_at`. Before acceptance there is no expiry. Acceptance sets 30 days. `POST /referrals/{id}/access-window` (7, 30 or 90; destination-institution clinician only; audited). The expiry is the earliest of: the chosen window, 90 days after acceptance, and 72 h after the referral is answered, cancelled or closed. A decline purges at once. Migration. | `central/app/lifecycle/working_set.py`, `referrals/router.py`, `models.py`, migration |
| B | **Read-through API for B.** `GET /referrals/{id}/shared-content`: package content, forwarded results and clarification answers. The destination institution only, window open only, an audit event per view, `410 window_ended` after. | `central/app/referrals/` (new route), `security.py` |
| C | **Notification instead of package.** The exchange envelope is split into a notification without clinical content. The receiver stores only the notification. Existing synthetic rows are cleared by migration. `get_case` returns B's own data plus the manifest. | `libs/common/refcommon/exchange.py`, `contracts/`, `provider/app/main.py`, `adapter.py`, `models.py`, migration |
| D | **Sender copy.** Only A-authored parts and the manifest. Remove the "sending clinic has not confirmed its copy" purge blocker. | `central/app/sending/packages.py`, `delivery/inbound.py`, `lifecycle/working_set.py` |
| E | **Warnings.** A scheduled job finds windows ending within 3 days and notifies both sides once (event key). | `central/app/tasks.py`, `lifecycle/` |
| F | **Screens.** Incoming case reads content from the platform. Window picker (7/30/90) with the expiry date. Expired state. Watermark. No print or download. The referring side shows the expiry. | `web/src/features/incoming`, `web/src/features/referrals` |
| G | **Tests.** Window rules (each limit, changes, the 90-day cap). B can view inside the window and gets 410 after. The receiver database holds no clinical content after delivery. Purge without the sender-copy blocker. Audit on every view. | `services/central/tests`, `tests/` |
| H | **Docs.** Architecture (§ data lifecycle), traceability, AGENTS.md invariants 4 and 9, this record. | `docs/`, `AGENTS.md` |

Order: A and B first (the platform can serve content), then C and D (stop copying), then E, F, G, H. Orders sent to laboratories and imaging (`deliver_order`) are out of scope: the lab keeps the order it performs as its own record.

## Accepted risk

- After the window, B has only its own notes. If B later needs the original records, the referring clinic has to send again.
- If the platform is unavailable during the window, B cannot read the records. They have no local copy to fall back on.
- A referral nobody accepts keeps its shared content on the platform indefinitely. It is still only on the platform (not at B), and the referring clinic can cancel it.
