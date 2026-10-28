# Decision: retrieve from every linked institution, with limits by count and specialty

- **Date:** 2026-10-28
- **Status:** agreed by the project team (reported by the project lead on 2026-10-28). Step 1 is built. Steps 2 to 4 are planned.
- **Why:** Retrieval used only the most recently visited hospital, clinic and laboratory. A patient seen at two hospitals got one hospital's records. The other was listed as skipped, though it could hold the history the specialist needs.

## What was decided

1. **Every linked institution is read** (verified links only, as before), in parallel, up to **5 besides the referring one** (`MAX_RETRIEVAL_SOURCES`), most recently visited first.
   - The limit keeps the AI recommendation within what it can read.
   - Institutions beyond the limit are listed as skipped, with the date the patient was last seen there. They are never shown as "no records".
2. **History depends on the specialty** (`SPECIALTY_HISTORY_YEARS` in `services/central/app/config.py`):
   - Visits, results and imaging go back 5 years for cardiology, endocrinology, nephrology, oncology and neurology. Most others get 3 years; obstetrics, ENT, ophthalmology and dentistry get 2, and dermatology 1.
   - **These are placeholders until a clinician confirms them.**
   - Conditions, surgeries and current medicines are retrieved whatever their date. The 6-month default selection is unchanged.
3. **One summary per institution (FHIR IPS) is not adopted now.** Sources already return what an IPS covers. It is noted as future work.

## Planned next steps

| Step | What | Notes |
|---|---|---|
| 2 | **Clean the data before the AI sees it.** <br>- Medicines are already grouped across institutions by ingredient and strength (`medications/service.py`). The AI selection should receive one entry per group, citing every source record. <br>- Lab names map to LOINC and units to UCUM, with values converted where the conversion is exact (e.g. mmol/L ↔ mg/dL for glucose). | Merged entries keep every source record and its evidence ID (invariant 6). Disagreements, such as different doses or results, are shown side by side, never resolved silently. An unmapped lab name or unit is shown as received and marked "not standardised". |
| 3 | **List first, then fetch selected.** Each source lists what it holds (type, date, title). Specialty rules and the AI choose from the list. Only the chosen records are fetched. | A source endpoint for listing records. Listed but not fetched shows "available, not fetched", never "none" (invariant 7). Fits the access-window decision: unchosen records never reach the platform. |
| 4 | **Start retrieval when the draft has a patient and a specialty**, not when the form is opened. | Abandoned drafts are cleared by the working-set rules. |
