# Supervisor demonstration script (about 25 minutes)

**Preparation (5 minutes before):**
1. `docker compose up -d` and wait until `docker compose ps` shows every service healthy.
2. `.\scripts\reset-and-seed.ps1 -Force`.
3. Open http://localhost:3000 in **four browser profiles or private windows**, one per role.
4. All passwords are `demo1234`.

Each step lists the SRS acceptance criterion (§11) it demonstrates.

## 0. Governance first: rules start as drafts (FR-61, NFR 10.6)

1. Sign in as `admin.a` and open **Medication rules**. The admin can view the rules but cannot approve them.
2. Sign in as `dr.reviewer` and open **Medication rules**. Point out:
   - Each rule has its class, procedure contexts, rationale, reference and content hash.
   - Every rule is *draft*.
3. Approve each rule, recording the reference checked.

> *Talking point:* rules were drafted with AI assistance, so they never activate automatically. A real clinical reviewer must confirm the references before any real use.

## 1. Independent systems and identity (Acceptance: Independent systems, Identity, Authorization)

1. As `staff.a`, click **New referral**, search "Khan" and select **Ayesha Khan (clinic-a / MR-102)**.
2. Enter a reason, choose procedure **Tooth extraction** and click **Create draft**.
3. Open **Sources & evidence** and click **Retrieve permitted records**. Show:
   - Clinic A and Lab B are **successful**. Lab B returns record **LB-5531** through *verified link #1*.
   - Specialist C shows **No verified patient link**, so it is not requested.
   - Clinic A reports *partial*: clinic staff are not permitted the `conditions` category, and the source itself enforces this.
4. Open **Patient links**. Lab B also has a patient **MR-102** (Bilal Ahmed). It is *not linked* and never imported: identical local IDs stay separate.
5. Link the specialist record:
   - Propose **Specialist C / SP-7781** with basis "appointment card + national ID". The identity check shows ✓ family, ✓ given, ✓ DOB.
   - As `dr.malik`, **Verify** it, then re-run retrieval. Specialist C now returns the 2024 consultation.

## 2. Clinician review of medications and flags (FR-30, FR-61 to FR-70)

1. As `dr.malik`, open the referral and use **Assign me as referring clinician** and **Priority = routine** (clinician-selected).
2. Open **Medications & flags** and set current use for each entry:
   - Warfarin → *Confirmed current*.
   - Alendronate (stopped in 2023) → *Historical / stopped*. No flag appears: a past prescription is not current use.
   - Ecosprin (patient-reported) → *Uncertain*, which shows **"Possible medication use—please confirm"**.
   - Calcium D → stays *ambiguous mapping* and asks for clarification.
3. Show the confirmed flag **"Medication requires review: anticoagulant recorded"** with its medication, class, source record, current-use status and rule `ORTHO-ANTICOAG-SURG v1`.
4. Open the evidence chip to show the original record.
5. On **Overview**, change the procedure to *Fixed appliance*. The anticoagulant flag disappears, because the procedure rule doesn't match. Change it back to *Tooth extraction*.
6. Set the procedure to *Explicitly unknown* to show **"Procedure context required"**: the rule is not guessed. Restore it afterwards.
7. Click **Mark reviewed** on each flag. *Reviewed is acknowledgment, not treatment clearance.*

## 3. Paper records: OCR, correction, verification (Acceptance: OCR review, Data integrity, Conflicting information)

1. Open **Documents** and upload `samples/documents/prescription_cardiology_digital.pdf`. The status moves from *queued* to *extracted*.
2. Open the document. The original page sits beside the proposed fields, and hovering a field highlights its region on the page.
3. The Warfarin 7.5 mg field is *proposed / unverified*. Click **Correct**, add a note, then **Verify (clinician)**.
4. Open the evidence chip to show the history: original extracted value kept, plus editor and time.
5. Open **Checklist & clarifications**. A **discrepancy** shows the Clinic A record (5 mg, 2021-06-01) versus the uploaded document (7.5 mg, 2026-09-01). Resolve it with a rationale.
6. Point out that INR 3.1 (July) versus 2.6 (September) is *not* flagged as a conflict, because the values come from different dates.
7. Upload `unreadable_scan.png`. The status shows **unreadable**. Use **Transcribe manually** with a page reference.
8. Upload `rejected_not_a_pdf.pdf`. It is **rejected** because the declared type doesn't match the file content.

## 4. Missing information with the laboratory (Acceptance: Missing information)

1. In **Checklist & clarifications**, choose **New request**, assign it to **Lab B** and set a due date.
2. As `lab.b`, open the **Work queue**. The request shows **your patient record LB-5531**, not the clinic's record, and the lab user cannot open the referral.
3. Answer the request. As `staff.a`, mark it resolved.

## 5. Brief, approval and versioning (Acceptance: Brief approval)

1. As `dr.malik`, open **Brief & approval** and click **Draft with AI** (if an API key is configured) or **Start from evidence template**.
   - Every statement carries evidence chips and a verification label.
   - Medication flags render below from the rules, not from the model.
2. On **Overview**, click **Send for clinician approval**. Back in **Brief & approval**, the approval panel lists any blockers.
3. Click **Approve this exact version** to create **v1** with its SHA-256 hash.
4. Edit a statement and save. The status returns to **Draft** and v1 is marked *superseded*: approved content cannot be silently changed.
5. Approve again to create v2, then click **Send approved version to specialist**. The status changes to **Submitted** once the specialist system confirms receipt.

## 6. Specialist (Acceptance: Follow-through, Duplicate prevention)

1. As `dr.ortho`, open **Specialist inbox** and the referral. Show:
   - The approved package, approver and hash.
   - Structured flags.
   - Evidence chips from the package snapshot.
   - "Our records" (prior consultation via the verified link).
2. Click **Acknowledge receipt**. Click **Reviewed** on each flag, or **Request clarification** on one, which arrives in the clinic's clarifications to answer. Then click **Accept referral**.
3. Write the response, then **Save draft**, **Approve response** and **Return to referring clinic**.
4. As `dr.malik`, open **Specialist & follow-up**. The response is received; **Record receipt** and **Record clinician review** are separate actions.
5. Add a follow-up task, record its outcome and click **Close referral**. Closing marks the workflow as complete; it does not claim the condition resolved.

## 7. Changed medication flag after submission (FR-70)

On a submitted referral, change Ecosprin to *Confirmed current*:
- An **amendment banner** appears, with a new *antiplatelet* flag that needs review.
- Approve and send **v2**. The specialist sees v2 and must review the new flag version. v1 and its acknowledgments remain traceable.

## 8. Failure handling (Acceptance: Failure recovery)

1. Run `docker compose stop lab`, then retrieve on any referral. Lab B shows **unavailable**, distinct from **denied**, after bounded retries, and the clinic evidence remains.
2. On **Fatima Noor (MR-330)**, Lab B shows **denied**: Lab B has no grant for Clinic A.
3. Run `docker compose start lab` and click **Retry**.
4. Without an API key, **Draft with AI** fails visibly and the manual path continues.

## 9. Security and audit (Acceptance: Authorization, Audit)

1. As `staff.x` (another clinic), the referral list is empty. Opening a Clinic A referral URL gives *403*.
2. As `admin.a`, open **Accounts** and disable `dr.locum`. That user's open session is rejected immediately.
3. As `admin.a`, open **Audit log**. The denied access attempts and every action appear with actor, institution, action, target, time and outcome.
4. As `admin.b`, open **Source access** to see Lab B's own grants, then revoke one.
5. Open the referral's **Audit trail** tab to show the referral journey end to end.

## Backup and restore (NFR 10.2)

Run `.\scripts\backup.ps1`, then `.\scripts\restore-check.ps1 -BackupDir backups\<ts>`. The restore check shows *"approved package … restored; N documents reopened, 0 checksum mismatches"*.
