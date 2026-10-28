# Data lifecycle: temporary access, temporary working set, minimal storage

This page covers the supervisor's suggestions (`data-lifecycle.patch`) and spec v3, both ported onto v2. The decision and its approval status are in [decisions/2026-10-27-data-lifecycle-and-v3.md](decisions/2026-10-27-data-lifecycle-and-v3.md). For each kind of content, [data-inventory.md](data-inventory.md) says where it is held and for how long.

## In one paragraph

Each institution keeps its own database. For a referral, the platform asks each linked institution's API for the patient's records, using the user's own token and an access grant. The institution decides whether to answer. The records become a temporary **working set** for that referral. A rule-based default, plus an AI recommendation when a model is configured, proposes which records go in the packet, and staff decide. The packet goes to the specialist, who keeps it as part of their own record, and the sending clinic's system keeps its own copy. When the working set ends, the platform deletes the clinical content. It keeps the reference, the status, the audit trail, a manifest (which record and version, from where, and which flags and rules) and the SHA-256 fingerprint.

## Temporary access (grants)

- Every grant has `expires_at` (14 days by default, at most 30) and optionally `referral_ref`. An expired grant is refused with "access grant expired", and the referral shows that source as **expired**, never as "no records".
- An institution's administrator chooses the duration, can extend it with a reason (counted from now, up to 30 days), revokes it, and can filter for "ending within 3 days" (**Source access** screen).
- When a referral is finished, the worker asks every institution to revoke the grants opened for it (`close_referral_grants`, every minute, central service token, `POST /grants/revoke-by-referral`). The institution revokes its own grants: central never writes to an institution's database. If the call fails, the expiry date is the backstop.
- Seed grants and grants made before expiry existed show as `legacy_no_expiry`.

## Temporary working set

| When | What happens |
| --- | --- |
| First retrieval, paper or manual entry | `working_set_expires_at` = now + 60 days |
| Specialist's answer returned, referral closed, declined or cancelled | End moves forward to now + 72 hours (never later than before) |
| End reached (worker `purge_working_sets`, every 10 minutes) | If every package, order and the clinic's own copy has been delivered, the content is removed (see the inventory). Otherwise the purge waits, and each wait is audited as `deferred`. |
| Retrieved again later (an amendment) | A new working set begins and fresh copies are fetched. Removed content is never reused. |

The screens show "Held for this referral until …". After removal they show "Content has been removed. Reference and fingerprint kept." and "These records are no longer held", never an empty list read as "no history".

## Copies that outlive the working set

- **Receiving institution:** the package it received is part of its own record and follows its own retention policy. The platform never deletes it.
- **Sending clinic:** each sent package and each response it receives is also delivered to the clinic's own system (`POST /outbound-copies`, outbox kind `sender_copy`). The purge waits until that delivery is confirmed.
- **Checking a copy:** `POST /referrals/{id}/packages/{v}/verify` checks any copy against the kept fingerprint, and `.../verify-own-copy` fetches the clinic's copy from its own system and checks it. The sent letter offers this as a button, and shows the copy once it matches.

## Role templates

`rules/roles/templates.v1.json` defines named bundles of the existing realm roles (front desk, doctor, laboratory and radiology, institution administrator, rule reviewer), with each one's home screen and menu. `GET /me` returns the user's templates, home and menu. The web app builds its navigation from that and opens the home screen after sign-in. Hiding a screen is only a convenience: every API still checks the role itself. An administrator can change a user's role by applying a template (**Accounts** screen). This replaces only the template-managed roles, never service roles, never on oneself, and is audited as `role.assign` (a refused change is audited as `failed`). The change is made in Keycloak, so it reaches the user at their next sign-in, or within about 5 minutes when their token renews. The platform's Keycloak service account needs `view-realm` for this (in the realm file since 2026-10-28; older installs: see the README troubleshooting table).

## Not built (and why)

- **Receiver-side retention settings and export** (the missing `data-lifecycle-and-roles-spec.md` section 4) need a schema change in the receiving institution's module.
- **Refetching the exact record version to verify after purge.** The manifest has what is needed, but sources only serve the current version through the referral API.
- **Refetch blocked by an expired grant** shows the source as "expired" with the reason. There is no separate "amendment blocked" message.
- The placeholder numbers need an institutional or legal source (not verified for Pakistan).
