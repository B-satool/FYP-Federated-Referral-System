# Decision: only doctors see clinical content; the doctor reviews the referral packet

- **Date:** 2026-10-29
- **Status:** decided by the project lead on 2026-10-29, for the whole team. Built and tested the same day.

## What changed

1. **Staff never see a patient's clinical content.** That covers record values and findings, diagnoses, medicines, flags, papers and their read fields, the letter, the reason, the consultation notes, the procedure, clarification questions and answers, test questions and results, and the sent package.
   - **What staff see:** each record's **title** (for example "Lab result: HbA1c", "Imaging report: MRI knee", "Visit: Clinic visit"), its source, date and whether it is in the packet. Also counts and statuses (for example "6 current medicines", "2 flags waiting for the doctor").
   - **Generic titles only:** a diagnosis, surgery or medicine name is itself clinical, so its title is only "Diagnosis", "Previous surgery" or "Medicine".
   - **Enforced on the server.** Serializers have a staff view: `evidence_out`, `referral_out`, `diagnostic_out` with `clinical=False`, and the medicines summary. Clinical endpoints are doctor-only (`load_referral(..., roles=("clinician",))`, `require_doctor`). The screens follow, but they are not the enforcement.
2. **The doctor reviews the packet.** The new order is:
   1. The doctor requests.
   2. **Staff** retrieve the records, upload the patient's papers and mark it ready.
   3. **The doctor** checks the papers' fields against the page images, confirms the medicine list with the patient (including over-the-counter medicines), resolves different doses, decides on every flag, reviews the records ticked for the packet and the letter, then marks the **packet reviewed** (`POST /referrals/{id}/packet-reviewed`).
   4. **Staff** send.
   - **A later change clears the review.** A clinical change after the review (records, papers, medicines, the procedure, or an AI recommendation that changes the selection) clears it, so the doctor reviews again.
   - **Labels:** "With the doctor for review", then "Ready to send".
3. **The same at the receiving institution.**
   - **Intake staff** see who the patient is, where the referral comes from, the urgency, the department and the records attached **by title**.
   - **The assigned doctor** sees the referral itself.
   - **Sender's own copies:** the sending clinic's copies (`sent_copies`) are shown to its doctors only.
4. **Administrators** see audit records without the detail fields that can hold clinical text (`changes`, `note`).

## Also decided the same day

- **Consultation notes.** The doctor writes consultation notes (symptoms, history, examination) under the reason, which acts as the headline.
  - **Where they go:** the letter (section "Consultation notes"), the package (`consultation_notes`, hashed when present so older packages keep their fingerprint) and, de-identified, the AI recommendation (prompt `packet-selection/3`).
  - **Edits after sending** open an amendment, like the reason.
- **Interaction explanations quoted from drug labels.** `scripts/extract_label_rules.py interactions` finds, for each DDInter pair, a sentence in either drug's US label that names the other drug and talks about the combination.
  - **Selection:** the drug-interactions section is preferred, and the sentence is kept verbatim (`rules/labels/interaction-quotes.json`).
  - **Display:** the interaction flag shows it as a quoted source sentence, naming the label and section.
  - **Coverage:** 37 of 342 pairs have one. Otherwise nothing is shown; no explanation is ever written by a model.
  - **Precision over coverage:** drug-class mentions ("calcium channel blockers") and fragments are excluded, and pairs read and found irrelevant are listed in the script (`REVIEWED_NOT_RELEVANT`).
- **Seed wording.** Two visit summaries that read like test notes ("Older than 6 months, should not appear…") were replaced with realistic text.
- **Speech-to-text for consultations** (Whisper locally, then the language model drafting notes) is deferred.

## Accepted risk and limits

- **Staff with database or log access could still see content.** The control is in the application. Operators must keep database access to administrators of the platform.
- **The doctor does more work.** Papers and medicines that staff used to check now wait for the doctor.
- **A few label quotes are only loosely about the interaction** (for example a trial sentence). They are labelled as the label's wording, automatically extracted and not clinically reviewed.
