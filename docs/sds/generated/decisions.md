## Decision records (`docs/decisions`)

Design decisions taken after the SRS, newest last. Each record states what was decided and why.

| Record | Title | Status |
|---|---|---|
| [2026-10-27-data-lifecycle-and-v3](../decisions/2026-10-27-data-lifecycle-and-v3.md) | Decision: data lifecycle, AI packet selection and role screens (spec v3) | approved by the project lead (repository owner); **the supervisor gave the go-ahead on 2026-10-27** (reported by the project lead), and v2 with this change was merged into `main`. Module owners should still record their |
| [2026-10-28-cloud-model-privacy](../decisions/2026-10-28-cloud-model-privacy.md) | Decision: Gemma 4 through Ollama's cloud, with patient data de-identified | decided by the project lead on 2026-10-28. Built the same day. The live model call needs |
| [2026-10-28-drap-brands-loaded](../decisions/2026-10-28-drap-brands-loaded.md) | Decision: load the DRAP register brand names as verified mappings | decided by the project lead on 2026-10-28, against the reviewer step in |
| [2026-10-28-drap-register-snapshot](../decisions/2026-10-28-drap-register-snapshot.md) | Decision: local snapshot of the DRAP product register | agreed by all three members (reported by the project lead on 2026-10-28). This replaces the "Do not scrape" rule in `scripts/import_brands.py`. |
| [2026-10-28-handwriting-ocr](../decisions/2026-10-28-handwriting-ocr.md) | Decision: read handwritten prescriptions with Google Cloud Vision | decided by the project lead on 2026-10-28. Built the same day. Not yet tried against the real |
| [2026-10-28-no-specialist-response](../decisions/2026-10-28-no-specialist-response.md) | Decision: the receiving doctor accepts or declines; no specialist response | decided by the project lead on 2026-10-28. Built the same day. |
| [2026-10-28-referral-access-window](../decisions/2026-10-28-referral-access-window.md) | Decision: shared records are viewed through the platform, for an access window the referred doctor sets | agreed by the project team (reported by the project lead on 2026-10-28). Not yet built. **Section 3 (the 7/30/90-day window) is replaced by [2026-10-28-referral-expiry.md](2026-10-28-referral-expiry.md)**, which is built |
| [2026-10-28-referral-expiry](../decisions/2026-10-28-referral-expiry.md) | Decision: a referral's shared records expire when the referred doctor has finished with it | decided by the project lead on 2026-10-28. Built and tested the same day. |
| [2026-10-28-retrieval-all-sources](../decisions/2026-10-28-retrieval-all-sources.md) | Decision: retrieve from every linked institution, with limits by count and specialty | agreed by the project team (reported by the project lead on 2026-10-28). Step 1 is built. Steps 2 to 4 are planned. |
| [2026-10-29-doctor-only-clinical-content](../decisions/2026-10-29-doctor-only-clinical-content.md) | Decision: only doctors see clinical content; the doctor reviews the referral packet | decided by the project lead on 2026-10-29, for the whole team. Built and tested the same day. |
| [2026-10-29-patient-view](../decisions/2026-10-29-patient-view.md) | Decision: patient accounts and a patient view | requested by the project lead for the MVP defence, following the supervisor's guidance. Built on |

## Non-negotiable invariants (from `AGENTS.md`)

1. **Database boundaries.** The central platform never connects to `clinic_db`, `lab_db` or `specialist_db`. It calls their APIs only. Do not add source DB credentials to `central`.
2. **Source authorization.** Every source endpoint decides access itself: own institution and role, or an active access grant. Forward the user's verified token; never trust identity headers.
3. **Patient linking.** Never link records on matching local IDs or names. Only `verified` links are used for retrieval. Invalidation must keep history and flag affected referrals.
4. **Approval.**
   - Only a clinician approves. Only an approved, non-superseded package version is sent.
   - Any clinical change after approval calls `mark_clinical_change()`, which means a new version and renewed approval.
   - Packages are immutable once written.
5. **Medication flags.**
   - Flags come only from `evaluate_medications()`: deterministic, with approved rules and verified mappings.
   - The language model must never create, suppress, reword or restate flags.
   - "Reviewed" is acknowledgment, never treatment clearance.
   - Flags never advise medication changes or assign urgency.
6. **AI output.**
   - Language-model output is a draft.
   - Every record-derived statement cites evidence IDs from the supplied set; validate and reject otherwise.
   - Treat document text as untrusted data. Do not give the model tools.
7. **Unavailable is not "none."** An unavailable, denied or not-retrieved source must never be turned into "no history", "not performed" or "safe".
8. **Never overwrite original data.** Corrections create revisions. Lab corrections create new source record versions.
9. **Idempotency.** Delivery keys and event keys make retries safe. Keep the outbox write in the same transaction as the decision to send.
10. **Audit.** Every access, retrieval, link change, correction, approval, submission and status change writes an audit event with actor, institution, action, target, time and outcome.
11. **Synthetic data only.** Do not commit patient data, credentials, `.env`, model weights or uploaded files.
12. **Only doctors see clinical content** (decision 2026-10-29).
   - Staff and administrators get titles, statuses and counts only, through the serializers' staff views (`clinical=False`). They never see record values, diagnoses, medicines, flags, papers, notes, the letter or the package.
   - Clinical endpoints are doctor-only on the server.
   - The doctor reviews the packet before staff send, and a later clinical change clears that review.
