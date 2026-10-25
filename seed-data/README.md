# Seed data: five synthetic patients (Karachi, five departments)

SYNTHETIC. Every patient, CNIC-style number, phone number and clinician is invented. Do not add real patient data here.

The institutions are named after real Karachi organisations so the demo looks familiar. They are used only as source-system names. The documents carry no logos or letterhead styling and all say they are synthetic, and nothing here comes from those organisations. Show that wording if you present the demo.

| Role | Name in the data |
|---|---|
| Referring clinic (all patients) | Dr Ali's Clinic, Clifton, Karachi |
| Laboratory | Chughtai Lab |
| Hospitals (receiving specialist, earlier visits, radiology) | Ziauddin Hospital, Aga Khan University Hospital |

Reference date for the data is **26 October 2026**, so "last 6 months" means on or after **26 April 2026**.

| Key | Patient | Department (receiving hospital) | Planned procedure | Expected medication flag (drug against procedure) |
|---|---|---|---|---|
| P1 | Rubina Akhtar, 52 F | Dentistry (Aga Khan) | Surgical extraction of impacted tooth 38 | Alendronate (bisphosphonate) with oral surgery |
| P2 | Muhammad Tariq Mahmood, 58 M | Cardiology (Ziauddin) | Coronary angiography | Metformin with contrast media, eGFR 56 |
| P3 | Abdul Rehman Gondal, 66 M | Orthopaedics (Aga Khan) | Right total knee replacement | Aspirin and diclofenac before major joint surgery |
| P4 | Shazia Parveen, 44 F | Hepatology (Ziauddin) | Upper GI endoscopy (variceal screening) | Ibuprofen with portal hypertension |
| P5 | Imtiaz Ali Soomro, 45 M | General Surgery (Aga Khan) | Laparoscopic cholecystectomy | Clopidogrel and aspirin (stent 2025); insulin and metformin around fasting |

## What is in each patient file (`patients/*.json`)

- `demographics`, `local_ids` (a different ID at each institution, never merged by name or ID).
- `referral`: from clinic and doctor, to hospital and department, optional requested doctor, reason, urgency, planned procedure, and `diagnostic_requests` (tests, scans and equipment the clinic does not have, sent inside the same referral).
- `brought_by_patient`: papers the patient carried (prescriptions as photos, a discharge summary). These go through OCR.
- `sources`: records split by institution (referring clinic, another hospital, laboratory, radiology centre): conditions, surgeries, visits, medications (active, stopped and completed), lab results with LOINC codes, imaging reports.
- `scenario`: what the case is meant to test, which flags should fire, which source records conflict, and which records fall outside the 6-month window.
- `expected_retrieval_view`: what the platform should show by default, so the seed is also an expected result. It lists conditions, surgeries, visits from the last 6 months, and **current** medications only (stopped and completed medicines are excluded).

`index.json` is a one-line summary per patient.

## Documents (`documents/`, 18 files)

| Type | Files | Use |
|---|---|---|
| Prescription photos (OCR) | `P1_prescription_dentist_*`, `P2_prescription_clinic_*`, `P3_prescription_orthopaedic_*`, `P4_prescription_hospital_2019-*`, `P4_prescription_clinic_*`, `P5_prescription_cardiology_*` | Upload as patient-brought documents. Three are handwriting-style, three are printed. They carry tilt, uneven light and grain. Tesseract reads the printed ones almost exactly and the handwriting-style ones with small errors, which is deliberate. |
| Discharge summary | `P2_discharge_summary_AKUH_2026-08-31.pdf` | Lists metformin 500 mg and atorvastatin 20 mg, which differ from the clinic record (850 mg and 40 mg). |
| Lab reports | `P*_lab_report_*.pdf` | Same values as the JSON. `P2_lab_report_2025-09-02.pdf` is outside the 6-month window. |
| Radiology reports | `P*_radiology_report_*.pdf` | Text reports only. No X-ray or scan images are included. |

## Rebuild

    python3 seed-data/generate.py

Needs Pillow and reportlab (both are in the central image). Edit `data.py`, not the JSON.

## Limits

- This folder **is the seed** for version 2. Each institution service loads only its own blocks (`clinic-ali` → Dr Ali's Clinic, `lab-b` → Chughtai Lab, `zia`/`rad-zia` → Ziauddin, `aku`/`rad-aku` → Aga Khan), and the central seed creates the earlier patient links. Edit `data.py`, regenerate, then run `scripts/reset-and-seed.ps1 -Force`.
- Brand names (Brufen, Panadol, Glucophage, Plavix and so on) are common in Pakistan but are used here only as examples. Check dose forms against a pharmacist before showing the data to anyone.
- The clinical content is plausible, not clinically reviewed. Have a clinician supervisor check it before a formal demo.
