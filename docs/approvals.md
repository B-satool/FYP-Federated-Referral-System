# Approvals

Changes that touch schemas, authentication, packages or the AGENTS.md invariants need the project owner's approval (AGENTS.md). This file records them.

| Date | Approved by | Scope | Reference |
|---|---|---|---|
| 2026-10-29 | Project owner (project lead), for the team | Every change in section 13 of the architecture spec v4 (A1 to A11). New tables and columns: key directory, wrapped keys, signed package manifests, consent, adapter policy, purge receipts, reminders and extensions, patient keys. Machine-to-machine authentication between the platform and the institution adapters, the hospital-signed key directory and patient login. Consent and adapter policy replace per-patient sharing grants. Encrypted packages with signed manifests (no plaintext at the platform). New and changed AGENTS.md invariants. Purge of package content and wrapped keys on close. Medication flags evaluated in the browser. Doctor, staff and patient clients hold keys. | `e2e-architecture-spec-v4.md` (2026-10-29), sections 0.2 and 13 |
| 2026-10-29 | Project owner | Only doctors see clinical content; the doctor reviews the packet | `docs/decisions/2026-10-29-doctor-only-clinical-content.md` |
| 2026-10-29 | Project owner | Patient accounts and a patient view | `docs/decisions/2026-10-29-patient-view.md` |

Anything not in this table still needs the owner's approval first.

## Decisions taken while finishing WP5 to WP11 (2026-10-30), awaiting the owner's confirmation

Each one follows the spec's default or its stated intent. They are listed so the owner can confirm or reverse them.

| Decision | Why | Where |
|---|---|---|
| Two exactly pinned npm packages for on-device OCR: `tesseract.js` 5.1.1 and `@tesseract.js-data/eng` 1.0.0. The engine and the English model are served by this application from `public/ocr`, never a CDN. | Spec 10 lists on-device OCR. A CDN would run third-party code next to the image, so the files are self-hosted. AGENTS.md asks before changing packages. | `web/package.json`, `web/scripts/copy-ocr-assets.mjs` |
| `rules/medication/seed-rules.json` (11 drug-class-by-procedure rules) and the 29 drug-procedure label rules were deleted. The extractor now builds drug-condition rules only. | Spec 9.1 and T-FLAG-2 forbid a hardcoded drug-procedure table (A6). | `rules/labels/label-rules.json`, `scripts/extract_label_rules.py` |
| The v2 and v3 integration tests that used the removed plaintext retrieval were retired. The test-request journey and the role tests were kept, in their own files. | They tested behaviour v4 removed (plaintext records at the platform, server-side flags, the sender's copy). | `tests/` |
| A declined, denied or cancelled referral is purged after 1 day. A closed referral is purged after 7 days. The maximum lifetime is 180 days. | These are the spec 7 and O10 defaults. | `services/central/app/config.py` |
| The doctor's notes reach the patient's copy only if the doctor ticks "Share these notes with the patient". | Spec 4: the doctor's private notes are not shown to the patient unless marked shareable. | `web/src/features/referrals/SendTab.tsx` |
| Patient notices (accepted, closed) appear on the referral's timeline in the patient app. | Patient accounts belong to no institution, so institution notifications cannot reach them. | `services/central/app/notifications.py` |
| Any doctor of the receiving department who holds its group key may open a sent referral; the platform logs which member opened it. | Spec D4 and 5.5. The platform does not know the assigned doctor's account (assignment is by name at the hospital). | `services/central/app/records/router.py` |
