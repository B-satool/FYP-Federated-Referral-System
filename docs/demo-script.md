# Supervisor demonstration script (about 25 minutes)

**Preparation (5 minutes before):**
1. `docker compose up -d`, then wait until `docker compose ps` shows every service healthy.
2. `.\scripts\reset-and-seed.ps1 -Force` (the five synthetic patients, nothing else).
3. Open http://localhost:3000 in **four private windows or browser profiles**, one per person:
   - Dr Ali (`dr.ali`) and Hina (`staff.ali`) at Dr Ali's Clinic;
   - Mariam (`staff.aku`) and Dr Naveed (`dr.naveed`) at Aga Khan.
4. All passwords are `demo1234`.
5. Say up front: **synthetic data only; the clinical rules and brand mappings are not clinically reviewed.**

Each step names the SRS requirement it shows.

## 1. The doctor asks, staff prepare (8 min)

1. **Dr Ali**: **Work queue** → **New request** → **Refer to a doctor or department**.
   - Patient *Imtiaz Ali Soomro*; Aga Khan University Hospital, General Surgery; urgency *Routine*.
   - Reason; **A procedure is planned**: *Laparoscopic cholecystectomy*. Point out that its features tick themselves
     (surgery, anaesthesia, fasting, bleeding risk). FR-11, FR-12.
   - **Submit request**. The Medicines tab says staff are still gathering.
2. **Hina**: open it from her **Work queue**.
   - **Records** → **Retrieve records**. Show where each record came from (own clinic, Ziauddin, Chughtai Lab) and
     the "held until the referral is finished" note.
   - The **default selection**: the last 6 months are ticked, older records are offered but unticked. Staff decide.
     FR-16, FR-21.
   - **Papers** → upload `seed-data/documents/P5_prescription_cardiology_2025-06-18.jpg`, open it, and confirm the
     medicines against the photo. Each merges with the clinic's record. FR-22 to FR-28.
   - **Medicines & flags** → **Add a medicine**: *Panadol*, over the counter. Then add *Glare 80 mg*: it asks
     "Which Glare is it?" and lists gliclazide (Mass Pharma) and ibuprofen (Shrooq). Pick one; the flags are checked
     again. FR-33, FR-62.
   - **I asked the patient about all their medicines** → **Check & send** → **Ready for the doctor's review**.

## 2. The doctor reviews the flags (4 min)

3. **Dr Ali**: **Medicines & flags**.
   - Rule flags: aspirin and clopidogrel before surgery; insulin and metformin around fasting.
   - DDInter interactions and drug-label warnings, each with its source and quote.
   - Mark each **Reviewed**, **Ignore** (with a note) or **Research**.
   - Say: a decision means "seen", never a treatment change; the model can never create or hide a flag.
     FR-61 to FR-71.

## 3. Send and receive (6 min)

4. **Hina**: **Check & send** → read the referral letter → **Send to Aga Khan University Hospital**. It carries the
   name, date of birth, sex and CNIC, and a fingerprint (SHA-256) is stored. FR-47 to FR-49.
5. **Mariam** (`staff.aku`): **Incoming referrals** → open it:
   - **Acknowledge receipt**;
   - **Confirm the patient**: he is new there, so write how you checked and **Register as a new patient**;
   - **Assign** Dr Naveed Baig.
6. **Dr Naveed**: **Incoming referrals** shows only referrals assigned to him. Open it → **Accept referral**.
   - Show the **Shared records** panel: kept 30 days after acceptance; he can keep them longer, with a reason.
   - **Mark as complete**: the records are removed in 72 hours. FR-50, FR-51.

## 4. Follow-through and close (3 min)

7. **Hina**: **Outcome & follow-up** → **Record that the patient was told**.
8. **Dr Ali**: the outcome shows "Accepted … Marked complete by Dr Naveed Baig" → **Close referral**. FR-52, FR-53.
9. **History** shows every step, with who and when. FR-59.

## 5. Optional extras (if time allows)

- **Test request:**
  - Dr Ali requests an *MRI knee* for *Abdul Rehman Gondal* at Aga Khan radiology, and Hina sends it.
  - `rad.aku` confirms the patient, accepts, and reports with the image
    `seed-data/documents/imaging/synthetic_mri-knee-coronal.png`.
  - Dr Ali sees the result with the image.
- **Roles:** `admin.ali` → **Accounts and roles** → change `tech.ali` to *Staff*. After signing in again, his menu
  changes. Change him back.
- **Rules:** `dr.reviewer` → **Medication rules** (a change becomes a new draft for approval) and **Medicine names**
  (hand-checked names, plus thousands of DRAP register names marked "DRAP register").
- **Expiry rules:** decline a referral and the shared records are removed straight away
  ([decision](decisions/2026-10-28-referral-expiry.md)).

## What to say about AI (be accurate)

- The AI packet recommendation and the paper reader are built for Gemma 4 through Ollama's cloud, with de-identified
  input, explicit permission and an audit trail (`docs/decisions/2026-10-28-cloud-model-privacy.md`). Until the
  Ollama account has credits, the screen shows **"AI recommendation unavailable"**, and the rule-based selection is
  what you are seeing.
- Handwriting OCR with Google Cloud Vision is built and needs an API key. Without one, papers are read with
  Tesseract (printed text).
