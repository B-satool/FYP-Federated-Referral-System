# Decision: patient accounts and a patient view

- **Date:** 2026-10-29
- **Status:** requested by the project lead for the MVP defence, following the supervisor's guidance. Built on
  `feature/patient-view`. Needs agreement from the owners of `libs/common` (auth), `infra/` (Keycloak realm) and
  the institution service before merging (AGENTS.md, "Module ownership").

## What was decided

1. **Patients get their own accounts.** One per seed patient (username from the seed file, e.g. `rubina.akhtar`,
   demo password). They have the `patient` realm role and belong to no institution.
2. **What a patient sees:**
   - the places that hold records about them (each institution is asked, using their CNIC);
   - the referrals and test requests made for them, with status and a plain-language timeline;
   - their medical history at each place: conditions, medicines (current and past), visits, test results,
     scans and operations.
3. **The history stays local to the patient** (the supervisor's requirement). Each institution answers the
   patient's device directly. The central platform never relays, caches or stores it, and responses are marked
   `no-store`. For the MVP the "device" is a phone-shaped screen in the website; a real phone app would keep it
   on the phone the same way.
4. **Identity is the CNIC**, held as a Keycloak user attribute that only administrators can see or edit, and
   sent in the token's `cnic` claim. A patient cannot change it, and services never take it from a request
   header or body.
5. **What the patient does not see:** medication flags, the retrieved working set, papers and the referral letter.
   Flags are for the reviewing doctor (they are acknowledgments, not advice) and could alarm without context.

## Change to the AGENTS.md invariants

- **Invariant 2 (source authorization)** gains a third basis: the patient reading their own records, matched on
  the verified CNIC claim. Each institution still decides access itself, and every read is audited at the
  institution. The wording of AGENTS.md should be updated once the owners agree.

## Not built

- **Self-registration and identity proofing.** Accounts are created by an administrator. A real deployment would
  need the patient to prove who they are (for example at a hospital desk, or through NADRA) before a CNIC is set.
- **Consent management** from the patient's side (approving or refusing a records request). The view shows what
  happened; it does not yet let the patient decide.
- **Corrections requested by the patient.** The view tells them to ask the institution.
- **A native phone app** that keeps the history on the device between sessions.

## Demo data

`scripts/seed_demo_referrals.py` creates one journey per seed patient through the real APIs (accepted, sent,
tests reported and booked, being prepared, closed). Run it after `scripts/reset-and-seed.ps1 -Force`.
