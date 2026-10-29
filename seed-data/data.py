"""Synthetic patients for the referral platform (five departments, Pakistan).

Everything here is invented for the FYP prototype. Names, CNIC-style numbers,
phone numbers, institutions and clinicians are fictional. Reference "today"
is 2026-10-26, so "last 6 months" means on or after 2026-04-26.

Each patient is split by SOURCE, because the platform never holds one merged
record: every institution keeps its own local ID and its own records.
"""

TODAY = "2026-10-26"
SIX_MONTHS_AGO = "2026-04-26"

INSTITUTIONS = {
    "clinic-ali": "Dr Ali's Clinic, Clifton, Karachi",
    "lab-b": "Chughtai Lab",
    "zia": "Ziauddin Hospital",
    "aku": "Aga Khan University Hospital",
    "rad-zia": "Ziauddin Hospital, Radiology",
    "rad-aku": "Aga Khan University Hospital, Radiology",
}


def med(name, generic, dose, freq, since, status="active", brand=None, prescriber=None, note=None, route="oral"):
    return {"name": name, "generic": generic, "brand_as_written": brand, "dose": dose, "route": route,
            "frequency": freq, "start": since, "status": status, "prescriber": prescriber, "note": note}


def cond(display, snomed, onset, status="active"):
    return {"display": display, "snomed": snomed, "onset": onset, "status": status}


def visit(date, setting, doctor, reason, summary):
    return {"date": date, "setting": setting, "doctor": doctor, "reason": reason, "summary": summary}


def lab(date, panel, results, issued_note=None):
    # results: (test, loinc, value, unit, reference, flag)
    return {"date": date, "panel": panel, "note": issued_note,
            "results": [{"test": t, "loinc": l, "value": v, "unit": u, "reference": r, "flag": f}
                        for t, l, v, u, r, f in results]}


def img(date, study, body, findings, impression, radiologist):
    return {"date": date, "study": study, "body_part": body, "findings": findings,
            "impression": impression, "radiologist": radiologist}


PATIENTS = [
    # ------------------------------------------------------------------ 1 DENTAL
    {
        "key": "P1",
        "department": "Dentistry (Oral and Maxillofacial Surgery)",
        "demographics": {
            "name": "Rubina Akhtar", "sex": "F", "dob": "1974-02-09", "age": 52,
            "cnic": "35202-0000011-4", "phone": "0300-0000011", "city": "Karachi",
            "language": "Punjabi, Urdu", "blood_group": "B+", "marital_status": "Married", "occupation": "Homemaker",
            "allergies": [],
        },
        "local_ids": {"clinic-ali": "DA-20411", "lab-b": "MD-771203", "rad-zia": "MI-55120", "aku": None},
        "referral": {
            "from_institution": "clinic-ali", "from_department": "General practice",
            "requested_by_doctor": "Dr Ali", "referred_doctor_requested": "Dr Faisal Haider",
            "to_institution": "aku", "to_department": "Dentistry (Oral and Maxillofacial Surgery)",
            "date": "2026-10-20", "urgency": "Routine (within 2 weeks)",
            "reason": "Recurrent pain and swelling, lower left wisdom tooth (38), three episodes of pericoronitis since July. OPG shows 38 mesio-angular impaction close to the inferior alveolar canal. Surgical extraction advised.",
            "planned_procedure": "Surgical extraction of impacted tooth 38 under local anaesthesia",
            "diagnostic_requests": [
                {"type": "Imaging", "test": "CBCT, lower left jaw", "reason": "Relation of 38 roots to the inferior alveolar canal; clinic has no CBCT",
                 "send_to": "zia", "urgency": "Routine", "status": "requested"},
            ],
        },
        "brought_by_patient": [
            {"file": "P1_prescription_dentist_2026-10-05.jpg", "kind": "Handwritten-style prescription from a local dentist", "date": "2026-10-05"},
        ],
        "sources": {
            "clinic-ali": {
                "conditions": [
                    cond("Type 2 diabetes mellitus", "44054006", "2016-04"),
                    cond("Essential hypertension", "59621000", "2019-08"),
                    cond("Osteoporosis", "64859006", "2022-02"),
                ],
                "surgeries": [
                    {"procedure": "Caesarean section", "date": "2003-05", "where": "Private hospital, Karachi"},
                    {"procedure": "Caesarean section", "date": "2006-09", "where": "Private hospital, Karachi"},
                ],
                "visits": [
                    visit("2026-10-14", "Clinic visit", "Dr Ali", "Review of tooth pain after dentist visit", "Third pericoronitis episode since July. Referred for surgical opinion. BP 132/84."),
                    visit("2026-09-12", "Clinic visit", "Dr Ali", "Toothache and facial swelling", "Pericoronitis, lower left. Augmentin 5 days. Advised dental review."),
                    visit("2026-07-18", "Clinic visit", "Dr Ali", "Diabetes and blood pressure review", "Stable. Continue medicines."),
                    visit("2026-02-10", "Clinic visit", "Dr Ali", "Routine review", "Diabetes and blood pressure stable. HbA1c due. Continue current medicines."),
                ],
                "medications": [
                    med("Alendronate 70 mg tablet", "alendronic acid", "70 mg", "once weekly", "2022-03-01", brand="Fosamax", prescriber="Dr Ali", note="Taken on an empty stomach on Sundays"),
                    med("Metformin 500 mg tablet", "metformin", "500 mg", "twice daily with meals", "2016-06-01", brand="Glucophage", prescriber="Dr Ali"),
                    med("Amlodipine 5 mg tablet", "amlodipine", "5 mg", "once daily", "2019-09-01", brand="Norvasc", prescriber="Dr Ali"),
                    med("Calcium with vitamin D3 tablet", "calcium carbonate / colecalciferol", "1 tablet", "once daily", "2022-03-01", prescriber="Dr Ali"),
                    med("Amoxicillin + clavulanic acid 625 mg tablet", "co-amoxiclav", "625 mg", "twice daily for 5 days", "2026-09-12", status="completed", brand="Augmentin", prescriber="Dr Ali", note="Course finished 2026-09-17"),
                ],
            },
            "lab-b": {
                "labs": [
                    lab("2026-10-12", "HbA1c and renal function", [
                        ("HbA1c", "4548-4", 7.6, "%", "4.0-5.6", "high"),
                        ("Creatinine", "2160-0", 0.8, "mg/dL", "0.5-1.1", ""),
                        ("eGFR", "62238-1", 88, "mL/min/1.73m2", ">=60", ""),
                    ]),
                    lab("2026-10-12", "Complete blood count", [
                        ("Haemoglobin", "718-7", 12.4, "g/dL", "12.0-15.5", ""),
                        ("Platelets", "777-3", 268, "10*9/L", "150-400", ""),
                        ("WBC", "6690-2", 10.9, "10*9/L", "4.0-11.0", ""),
                    ]),
                    lab("2026-10-12", "Vitamin D (25-OH)", [
                        ("25-OH vitamin D", "1989-3", 24, "ng/mL", "30-100", "low"),
                    ]),
                ],
            },
            "rad-zia": {
                "imaging": [
                    img("2026-10-08", "Orthopantomogram (OPG)", "Jaws and teeth",
                        "Mesio-angular impaction of 38 with a pericoronal radiolucency. Root apices lie close to the superior margin of the inferior alveolar canal. Caries in 36 (occlusal). Generalised mild horizontal bone loss. Right side: 48 erupted, no abnormality.",
                        "Impacted 38, close relation to the inferior alveolar canal. Suggest CBCT before surgery.", "Dr Hira Anwar, Consultant Radiologist"),
                ],
            },
        },
        "scenario": {
            "tests": "Drug against procedure: alendronate (a bisphosphonate, 4.5 years) with a tooth extraction, which carries a jaw-osteonecrosis risk, so the flag should fire. Metformin and amlodipine need no flag for this procedure. Brought-by-patient prescription lists Brufen and Panadol, which should be read by OCR.",
            "should_flag": ["Alendronate with planned oral surgery (bisphosphonate and jaw osteonecrosis)"],
            "records_outside_6_months": ["Clinic visit 2026-02-10"],
        },
    },

    # ------------------------------------------------------------- 2 CARDIOLOGY
    {
        "key": "P2",
        "department": "Cardiology",
        "demographics": {
            "name": "Muhammad Tariq Mahmood", "sex": "M", "dob": "1968-07-21", "age": 58,
            "cnic": "37405-0000022-7", "phone": "0300-0000022", "city": "Karachi",
            "language": "Urdu, Pothwari", "blood_group": "O+", "marital_status": "Married", "occupation": "Retired government clerk",
            "allergies": [],
        },
        "local_ids": {"clinic-ali": "DA-8842", "aku": "AK-319077", "lab-b": "MD-771874", "rad-zia": "MI-55307", "zia": None},
        "referral": {
            "from_institution": "clinic-ali", "from_department": "General practice",
            "requested_by_doctor": "Dr Ali", "referred_doctor_requested": "Dr Asma Rauf",
            "to_institution": "zia", "to_department": "Cardiology",
            "date": "2026-10-21", "urgency": "Urgent (within 1 week)",
            "reason": "Exertional chest tightness for 6 weeks, relieved by rest, now on walking one flight of stairs. ECG at the clinic shows non-specific T-wave flattening in V4 to V6. Diabetic and hypertensive. Needs cardiology assessment for suspected stable angina.",
            "planned_procedure": "Coronary angiography",
            "diagnostic_requests": [
                {"type": "Imaging", "test": "Transthoracic echocardiogram", "reason": "Left ventricular function; clinic has no echo machine",
                 "send_to": "zia", "urgency": "Urgent", "status": "requested"},
                {"type": "Laboratory", "test": "Lipid profile and HbA1c (repeat)", "reason": "Last lipid profile over a year old",
                 "send_to": "lab-b", "urgency": "Routine", "status": "requested"},
            ],
        },
        "brought_by_patient": [
            {"file": "P2_prescription_clinic_2026-10-08.jpg", "kind": "Printed clinic prescription (patient's copy)", "date": "2026-10-08"},
            {"file": "P2_discharge_summary_AKUH_2026-08-31.pdf", "kind": "Discharge summary from Aga Khan University Hospital emergency visit", "date": "2026-08-31"},
        ],
        "sources": {
            "clinic-ali": {
                "conditions": [
                    cond("Type 2 diabetes mellitus", "44054006", "2012-03"),
                    cond("Essential hypertension", "59621000", "2015-06"),
                    cond("Dyslipidaemia", "55822004", "2019-01"),
                    cond("Exertional chest pain, under investigation", "29857009", "2026-09"),
                ],
                "surgeries": [
                    {"procedure": "Right inguinal hernia repair", "date": "2009-11", "where": "Private hospital, Karachi"},
                ],
                "visits": [
                    visit("2026-10-20", "Clinic visit", "Dr Ali", "Chest tightness, follow-up", "Symptoms worsening with stairs. ECG repeated, T-wave flattening V4 to V6. Referral to cardiology."),
                    visit("2026-10-08", "Clinic visit", "Dr Ali", "Chest tightness on walking", "First visit for this complaint. Aspirin continued. Chest X-ray requested."),
                    visit("2026-06-15", "Clinic visit", "Dr Ali", "Diabetes review", "HbA1c above target. Glimepiride added."),
                ],
                "medications": [
                    med("Metformin 850 mg tablet", "metformin", "850 mg", "twice daily with meals", "2014-01-01", brand="Glucophage", prescriber="Dr Ali", note="Clinic record says 850 mg. The hospital discharge summary says 500 mg (discrepancy to resolve)."),
                    med("Glimepiride 2 mg tablet", "glimepiride", "2 mg", "once daily before breakfast", "2026-06-15", brand="Amaryl", prescriber="Dr Ali"),
                    med("Aspirin 75 mg tablet", "aspirin", "75 mg", "once daily after lunch", "2019-01-10", brand="Cardiprin", prescriber="Dr Ali"),
                    med("Atorvastatin 40 mg tablet", "atorvastatin", "40 mg", "once daily at night", "2019-01-10", brand="Lipitor", prescriber="Dr Ali"),
                    med("Enalapril 10 mg tablet", "enalapril", "10 mg", "once daily", "2015-07-01", brand="Renitec", prescriber="Dr Ali"),
                    med("Diclofenac sodium 50 mg tablet", "diclofenac", "50 mg", "twice daily as needed", "2025-03-01", status="stopped", brand="Voltral", prescriber="Dr Ali", note="Stopped 2026-08 after the emergency visit"),
                ],
            },
            "aku": {
                "conditions": [cond("Chest pain, non-cardiac cause not excluded", "29857009", "2026-08")],
                "surgeries": [],
                "visits": [
                    visit("2026-08-30", "Emergency department, Aga Khan University Hospital", "Dr Nida Iqbal (medical officer)", "Chest pain at rest, 40 minutes", "ECG normal sinus rhythm. Troponin negative at 0 and 3 hours. Treated as musculoskeletal. Discharged with advice to see a physician."),
                ],
                "medications": [
                    med("Metformin 500 mg tablet", "metformin", "500 mg", "twice daily", "2014-01-01", status="active", note="As written in the discharge summary"),
                    med("Aspirin 75 mg tablet", "aspirin", "75 mg", "once daily", "2019-01-10"),
                    med("Atorvastatin 20 mg tablet", "atorvastatin", "20 mg", "once daily", "2019-01-10", note="Discharge summary lists 20 mg, the clinic lists 40 mg (discrepancy)"),
                ],
            },
            "lab-b": {
                "labs": [
                    lab("2026-10-10", "Renal function", [
                        ("Creatinine", "2160-0", 1.4, "mg/dL", "0.7-1.3", "high"),
                        ("eGFR", "62238-1", 56, "mL/min/1.73m2", ">=60", "low"),
                        ("Urea", "3091-6", 38, "mg/dL", "15-45", ""),
                    ]),
                    lab("2026-10-10", "HbA1c", [("HbA1c", "4548-4", 8.2, "%", "4.0-5.6", "high")]),
                    lab("2026-10-10", "Cardiac markers", [
                        ("Troponin I (high sensitivity)", "89579-7", 8, "ng/L", "<34", ""),
                        ("CK-MB", "13969-1", 14, "U/L", "<25", ""),
                    ]),
                    lab("2025-09-02", "Lipid profile", [
                        ("Total cholesterol", "2093-3", 214, "mg/dL", "<200", "high"),
                        ("LDL cholesterol", "13457-7", 138, "mg/dL", "<100", "high"),
                        ("HDL cholesterol", "2085-9", 38, "mg/dL", ">40", "low"),
                        ("Triglycerides", "2571-8", 192, "mg/dL", "<150", "high"),
                    ], issued_note="Older than 6 months"),
                ],
            },
            "rad-zia": {
                "imaging": [
                    img("2026-10-10", "Chest X-ray, PA view", "Chest",
                        "Lung fields clear. Cardiothoracic ratio about 0.52, upper limit of normal. No effusion. Aortic knuckle prominent.",
                        "No acute chest disease. Borderline cardiac size.", "Dr Hira Anwar, Consultant Radiologist"),
                ],
            },
        },
        "scenario": {
            "tests": "Drug against procedure: metformin with iodinated contrast at angiography and eGFR 56 (flag). Aspirin continues for angiography (informational). Source conflict: metformin 850 mg (clinic) vs 500 mg (hospital) and atorvastatin 40 mg vs 20 mg, to be resolved by a person. Stopped diclofenac must not appear as a current medicine.",
            "should_flag": ["Metformin with contrast media, reduced eGFR"],
            "conflicts": ["Metformin dose clinic vs hospital", "Atorvastatin dose clinic vs hospital"],
            "records_outside_6_months": ["Clinic visit 2026-06-15 is inside 6 months", "Lipid profile 2025-09-02 is outside 6 months"],
        },
    },

    # ----------------------------------------------------------- 3 ORTHOPAEDICS
    {
        "key": "P3",
        "department": "Orthopaedics",
        "demographics": {
            "name": "Abdul Rehman Gondal", "sex": "M", "dob": "1959-11-30", "age": 66,
            "cnic": "36302-0000033-5", "phone": "0300-0000033", "city": "Karachi",
            "language": "Saraiki, Urdu", "blood_group": "A+", "marital_status": "Married", "occupation": "Retired schoolteacher",
            "allergies": [],
        },
        "local_ids": {"clinic-ali": "DA-3306", "lab-b": "MD-772455", "rad-zia": "MI-55611", "aku": None},
        "referral": {
            "from_institution": "clinic-ali", "from_department": "General practice",
            "requested_by_doctor": "Dr Ali", "referred_doctor_requested": None,
            "to_institution": "aku", "to_department": "Orthopaedics",
            "date": "2026-10-19", "urgency": "Routine (within 4 weeks)",
            "reason": "Progressive right knee pain for 4 years, now worse on walking 100 metres and at night. Painkillers no longer help. Standing X-ray shows advanced osteoarthritis. Please assess for knee replacement.",
            "planned_procedure": "Right total knee replacement (to be decided by orthopaedic surgeon)",
            "diagnostic_requests": [
                {"type": "Imaging", "test": "MRI right knee", "reason": "Rule out other internal derangement; clinic has no MRI",
                 "send_to": "zia", "urgency": "Routine", "status": "requested"},
                {"type": "Cardiac", "test": "Resting ECG", "reason": "Pre-operative fitness, age 66",
                 "send_to": "clinic-ali", "urgency": "Routine", "status": "requested"},
            ],
        },
        "brought_by_patient": [
            {"file": "P3_prescription_orthopaedic_2026-07-22.jpg", "kind": "Handwritten-style prescription from a private orthopaedic clinic", "date": "2026-07-22"},
        ],
        "sources": {
            "clinic-ali": {
                "conditions": [
                    cond("Osteoarthritis of knee, bilateral, right worse", "239873007", "2022-05"),
                    cond("Essential hypertension", "59621000", "2010-03"),
                    cond("Gastro-oesophageal reflux disease", "235595009", "2020-02"),
                    cond("Mild anaemia", "271737000", "2026-07"),
                ],
                "surgeries": [
                    {"procedure": "Appendicectomy", "date": "1982-08", "where": "Private hospital, Karachi"},
                    {"procedure": "Left eye cataract surgery with lens implant", "date": "2023-02", "where": "Eye hospital, Karachi"},
                ],
                "visits": [
                    visit("2026-10-15", "Clinic visit", "Dr Ali", "Knee pain review", "Pain 8 out of 10 on walking. Painkillers not controlling. Referral to orthopaedics."),
                    visit("2026-07-22", "Private orthopaedic clinic, Karachi (outside)", "Dr Naveed Qureshi", "Right knee pain", "Advised diclofenac, physiotherapy, weight loss. Prescription brought by patient."),
                    visit("2026-07-02", "Clinic visit", "Dr Ali", "Tiredness and joint pain", "Mild anaemia on blood test. Advised iron."),
                    visit("2026-01-20", "Clinic visit", "Dr Ali", "Blood pressure review", "BP 138/86. Advised low-salt diet and regular walking. Recheck in 3 months."),
                ],
                "medications": [
                    med("Diclofenac sodium 50 mg tablet", "diclofenac", "50 mg", "twice daily after food", "2026-07-22", brand="Voltral", prescriber="Dr Naveed Qureshi", note="From the outside orthopaedic prescription"),
                    med("Aspirin 75 mg tablet", "aspirin", "75 mg", "once daily", "2018-05-01", brand="Loprin", prescriber="Dr Ali", note="Primary prevention"),
                    med("Losartan 50 mg tablet", "losartan", "50 mg", "once daily", "2016-04-01", brand="Cozaar", prescriber="Dr Ali"),
                    med("Esomeprazole 20 mg capsule", "esomeprazole", "20 mg", "once daily before breakfast", "2020-03-01", brand="Nexum", prescriber="Dr Ali"),
                    med("Ferrous sulfate 200 mg tablet", "ferrous sulfate", "200 mg", "once daily", "2026-07-02", prescriber="Dr Ali"),
                    med("Tramadol 50 mg capsule", "tramadol", "50 mg", "as needed, up to twice daily", "2025-11-01", status="stopped", prescriber="Dr Naveed Qureshi", note="Stopped 2026-03 for dizziness"),
                ],
            },
            "lab-b": {
                "labs": [
                    lab("2026-10-16", "Complete blood count", [
                        ("Haemoglobin", "718-7", 11.4, "g/dL", "13.5-17.5", "low"),
                        ("MCV", "787-2", 76, "fL", "80-100", "low"),
                        ("Platelets", "777-3", 302, "10*9/L", "150-400", ""),
                        ("WBC", "6690-2", 7.2, "10*9/L", "4.0-11.0", ""),
                    ]),
                    lab("2026-10-16", "Renal function and inflammation", [
                        ("Creatinine", "2160-0", 1.2, "mg/dL", "0.7-1.3", ""),
                        ("eGFR", "62238-1", 66, "mL/min/1.73m2", ">=60", ""),
                        ("ESR", "4537-7", 34, "mm/hr", "0-20", "high"),
                        ("CRP", "1988-5", 6, "mg/L", "<5", "high"),
                    ]),
                    lab("2026-10-16", "HbA1c", [("HbA1c", "4548-4", 5.8, "%", "4.0-5.6", "high")]),
                ],
            },
            "rad-zia": {
                "imaging": [
                    img("2026-09-30", "X-ray both knees, standing AP and lateral", "Knees",
                        "Right: marked medial joint space narrowing with bone-on-bone contact, large marginal osteophytes, subchondral sclerosis and cysts, varus alignment. Left: moderate medial narrowing and osteophytes. No fracture. No effusion calcification.",
                        "Right knee Kellgren-Lawrence grade 4. Left knee grade 2 to 3.", "Dr Hira Anwar, Consultant Radiologist"),
                ],
            },
        },
        "scenario": {
            "tests": "Drug against procedure: aspirin and diclofenac (NSAID) before major joint replacement (bleeding risk), flag should fire for both. Losartan and an NSAID with eGFR 66 is a drug-against-drug topic and is out of scope for the procedure rules. Anaemia and raised inflammatory markers appear as results. Stopped tramadol must not appear as a current medicine.",
            "should_flag": ["Aspirin before major orthopaedic surgery", "NSAID (diclofenac) before major orthopaedic surgery"],
            "records_outside_6_months": ["Clinic visit 2026-01-20"],
        },
    },

    # -------------------------------------------------------------- 4 HEPATOLOGY
    {
        "key": "P4",
        "department": "Gastroenterology and Hepatology",
        "demographics": {
            "name": "Shazia Parveen", "sex": "F", "dob": "1982-04-17", "age": 44,
            "cnic": "42101-0000044-2", "phone": "0300-0000044", "city": "Karachi",
            "language": "Urdu", "blood_group": "AB+", "marital_status": "Married", "occupation": "Schoolteacher",
            "allergies": [{"substance": "Sulfonamide antibiotics", "reaction": "Rash", "source": "Patient reported"}],
        },
        "local_ids": {"clinic-ali": "DA-12908", "aku": "AK-204118", "lab-b": "MD-773019", "rad-aku": "MI-55902", "zia": None},
        "referral": {
            "from_institution": "clinic-ali", "from_department": "General practice",
            "requested_by_doctor": "Dr Ali", "referred_doctor_requested": "Dr Irfan Siddiqui",
            "to_institution": "zia", "to_department": "Gastroenterology and Hepatology",
            "date": "2026-10-22", "urgency": "Urgent (within 2 weeks)",
            "reason": "Treated hepatitis C in 2019. Now abdominal swelling and fatigue for 2 months, platelets low at 92, ultrasound suggests chronic liver disease with splenomegaly. Needs hepatology assessment and screening for oesophageal varices.",
            "planned_procedure": "Upper gastrointestinal endoscopy (variceal screening)",
            "diagnostic_requests": [
                {"type": "Imaging", "test": "Transient elastography (FibroScan)", "reason": "Liver stiffness; clinic has no elastography",
                 "send_to": "zia", "urgency": "Routine", "status": "requested"},
            ],
        },
        "brought_by_patient": [
            {"file": "P4_prescription_hospital_2019-03-11.jpg", "kind": "Old hepatitis C treatment prescription (photo of paper)", "date": "2019-03-11"},
            {"file": "P4_prescription_clinic_2026-10-20.jpg", "kind": "Recent clinic prescription (photo of paper)", "date": "2026-10-20"},
        ],
        "sources": {
            "clinic-ali": {
                "conditions": [
                    cond("Chronic hepatitis C, treated (sustained virological response 2019)", "128302006", "2016-09", status="resolved"),
                    cond("Suspected chronic liver disease with splenomegaly", "235856003", "2026-10"),
                    cond("Iron deficiency anaemia", "87522002", "2025-03"),
                    cond("Chronic low back pain", "161891005", "2024-01"),
                ],
                "surgeries": [
                    {"procedure": "Caesarean section", "date": "2008-12", "where": "Private hospital, Karachi"},
                ],
                "visits": [
                    visit("2026-10-20", "Clinic visit", "Dr Ali", "Review of blood tests and ultrasound", "Ultrasound shows chronic liver disease with splenomegaly. Propranolol started. Patient says she still takes Brufen for back pain, advised to stop. Referral to hepatology."),
                    visit("2026-10-02", "Clinic visit", "Dr Ali", "Fatigue, abdominal swelling and swollen ankles", "Mild ascites on examination. Blood tests and ultrasound requested. Advised to avoid painkillers other than paracetamol."),
                    visit("2026-05-20", "Clinic visit", "Dr Ali", "Back pain", "Brufen as needed. Advised physiotherapy."),
                ],
                "medications": [
                    med("Propranolol 20 mg tablet", "propranolol", "20 mg", "twice daily", "2026-10-20", brand="Inderal", prescriber="Dr Ali"),
                    med("Omeprazole 20 mg capsule", "omeprazole", "20 mg", "once daily before breakfast", "2025-03-10", brand="Risek", prescriber="Dr Ali"),
                    med("Ferrous fumarate 200 mg tablet", "ferrous fumarate", "200 mg", "once daily", "2025-03-10", prescriber="Dr Ali"),
                    med("Paracetamol 500 mg tablet", "paracetamol", "500 mg", "as needed, maximum 3 per day", "2024-01-15", brand="Panadol", prescriber="Dr Ali"),
                    med("Ibuprofen 400 mg tablet", "ibuprofen", "400 mg", "as needed for back pain", "2026-05-20", brand="Brufen", prescriber="Dr Ali", note="Patient still takes it from a previous supply despite advice (reported 2026-10-20). Marked active because the patient reports taking it."),
                    med("Sofosbuvir 400 mg + daclatasvir 60 mg", "sofosbuvir / daclatasvir", "400 mg + 60 mg", "once daily for 12 weeks", "2019-03-11", status="completed", prescriber="Aga Khan University Hospital", note="Completed 2019-06"),
                ],
            },
            "aku": {
                "conditions": [cond("Chronic hepatitis C genotype 3", "128302006", "2016-09", status="resolved")],
                "surgeries": [],
                "visits": [
                    visit("2019-03-11", "Outpatient hepatology clinic", "Dr Tahir Mehmood", "Start of hepatitis C treatment", "Genotype 3. Sofosbuvir and daclatasvir for 12 weeks."),
                    visit("2019-10-04", "Outpatient hepatology clinic", "Dr Tahir Mehmood", "SVR12 check", "HCV RNA not detected 12 weeks after treatment. Sustained response."),
                ],
                "medications": [],
            },
            "lab-b": {
                "labs": [
                    lab("2026-10-13", "Liver function tests", [
                        ("ALT", "1742-6", 58, "U/L", "7-35", "high"),
                        ("AST", "1920-8", 74, "U/L", "8-33", "high"),
                        ("Total bilirubin", "1975-2", 1.7, "mg/dL", "0.2-1.2", "high"),
                        ("Albumin", "1751-7", 3.0, "g/dL", "3.5-5.0", "low"),
                        ("ALP", "6768-6", 112, "U/L", "44-147", ""),
                    ]),
                    lab("2026-10-13", "Coagulation", [("INR", "6301-6", 1.4, "{INR}", "0.8-1.2", "high")]),
                    lab("2026-10-13", "Complete blood count", [
                        ("Haemoglobin", "718-7", 10.6, "g/dL", "12.0-15.5", "low"),
                        ("Platelets", "777-3", 92, "10*9/L", "150-400", "low"),
                        ("WBC", "6690-2", 3.9, "10*9/L", "4.0-11.0", "low"),
                    ]),
                    lab("2026-10-13", "Hepatitis C RNA (PCR)", [("HCV RNA", "11011-4", "Not detected", "", "Not detected", "")]),
                    lab("2026-10-13", "Alpha-fetoprotein", [("AFP", "1834-1", 5.2, "ng/mL", "<10", "")]),
                ],
            },
            "rad-aku": {
                "imaging": [
                    img("2026-10-16", "Ultrasound abdomen and pelvis", "Abdomen",
                        "Liver is mildly shrunken with coarse echotexture and nodular contour. Portal vein 13 mm. Spleen enlarged, 14.5 cm. Mild free fluid in the abdomen. Gallbladder, pancreas and both kidneys appear normal. No focal liver lesion seen.",
                        "Features of chronic liver disease with portal hypertension (splenomegaly, mild ascites).", "Dr Hira Anwar, Consultant Radiologist"),
                ],
            },
        },
        "scenario": {
            "tests": "Drug against procedure: ibuprofen reported by the patient with liver disease and portal hypertension before endoscopy (bleeding risk, flag). Propranolol is expected and needs no flag for variceal screening. Source difference: the hospital record shows hepatitis C resolved in 2019 while the clinic now has new liver findings. Completed sofosbuvir course must not appear as a current medicine. Sulfonamide allergy is recorded.",
            "should_flag": ["NSAID (ibuprofen) with portal hypertension before endoscopy"],
            "records_outside_6_months": ["Hospital visits 2019-03-11 and 2019-10-04"],
        },
    },

    # ------------------------------------------------------------ 5 GENERAL SURGERY
    {
        "key": "P5",
        "department": "General Surgery",
        "demographics": {
            "name": "Imtiaz Ali Soomro", "sex": "M", "dob": "1981-01-05", "age": 45,
            "cnic": "41304-0000055-9", "phone": "0300-0000055", "city": "Karachi",
            "language": "Sindhi, Urdu", "blood_group": "O-", "marital_status": "Married", "occupation": "Shopkeeper",
            "allergies": [],
        },
        "local_ids": {"clinic-ali": "DA-6120", "lab-b": "MD-773640", "rad-zia": "MI-56188", "aku": None},
        "referral": {
            "from_institution": "clinic-ali", "from_department": "General practice",
            "requested_by_doctor": "Dr Ali", "referred_doctor_requested": None,
            "to_institution": "aku", "to_department": "General Surgery",
            "date": "2026-10-23", "urgency": "Routine (within 4 weeks)",
            "reason": "Repeated right upper abdominal pain after fatty meals, two episodes needing injections at a local hospital. Ultrasound shows multiple gallstones with a thickened gallbladder wall. Diabetic with a coronary stent in 2025. Needs surgical assessment for gallbladder removal.",
            "planned_procedure": "Laparoscopic cholecystectomy",
            "diagnostic_requests": [
                {"type": "Imaging", "test": "MRCP", "reason": "Liver enzymes mildly raised; exclude a common bile duct stone. Clinic has no MRI",
                 "send_to": "zia", "urgency": "Routine", "status": "requested"},
                {"type": "Laboratory", "test": "Serum lipase and repeat HbA1c", "reason": "Pre-operative, HbA1c 8.9",
                 "send_to": "lab-b", "urgency": "Routine", "status": "requested"},
            ],
        },
        "brought_by_patient": [
            {"file": "P5_prescription_cardiology_2025-06-18.jpg", "kind": "Cardiologist prescription after stent (photo of paper)", "date": "2025-06-18"},
        ],
        "sources": {
            "clinic-ali": {
                "conditions": [
                    cond("Type 2 diabetes mellitus", "44054006", "2018-02"),
                    cond("Coronary artery disease, drug-eluting stent to LAD", "53741008", "2025-06"),
                    cond("Obesity (BMI 33)", "414916001", "2020-01"),
                    cond("Cholelithiasis (gallstones)", "235919008", "2026-09"),
                ],
                "surgeries": [
                    {"procedure": "Percutaneous coronary intervention with one drug-eluting stent (LAD)", "date": "2025-06", "where": "Ziauddin Hospital"},
                    {"procedure": "Appendicectomy", "date": "2002-07", "where": "Civil hospital, Karachi"},
                ],
                "visits": [
                    visit("2026-10-20", "Clinic visit", "Dr Ali", "Abdominal pain, ultrasound review", "Gallstones with thick wall. Referral to surgery. Advised to continue heart medicines."),
                    visit("2026-09-19", "Clinic visit", "Dr Ali", "Severe right upper abdominal pain", "Biliary colic. Given injections, advised ultrasound."),
                    visit("2026-08-02", "Clinic visit", "Dr Ali", "Diabetes review", "Insulin dose increased."),
                ],
                "medications": [
                    med("Insulin glargine 100 units/mL", "insulin glargine", "24 units", "once daily at night", "2024-05-01", route="subcutaneous", brand="Basalog", prescriber="Dr Ali", note="Increased from 20 units on 2026-08-02"),
                    med("Metformin 1000 mg tablet", "metformin", "1000 mg", "twice daily with meals", "2018-03-01", brand="Glucophage", prescriber="Dr Ali"),
                    med("Aspirin 75 mg tablet", "aspirin", "75 mg", "once daily", "2025-06-18", brand="Disprin Cardio", prescriber="Dr Aamir Hussain (Ziauddin cardiology)"),
                    med("Clopidogrel 75 mg tablet", "clopidogrel", "75 mg", "once daily", "2025-06-18", brand="Plavix", prescriber="Dr Aamir Hussain (Ziauddin cardiology)", note="Planned 12 months after the stent; cardiologist has not yet advised stopping"),
                    med("Atorvastatin 40 mg tablet", "atorvastatin", "40 mg", "once daily at night", "2025-06-18", brand="Lipitor", prescriber="Dr Aamir Hussain (Ziauddin cardiology)"),
                    med("Bisoprolol 2.5 mg tablet", "bisoprolol", "2.5 mg", "once daily", "2025-06-18", brand="Concor", prescriber="Dr Aamir Hussain (Ziauddin cardiology)"),
                    med("Hyoscine butylbromide 10 mg tablet", "hyoscine butylbromide", "10 mg", "as needed for pain", "2026-09-19", status="stopped", brand="Buscopan", prescriber="Dr Ali", note="Short course, finished"),
                ],
            },
            "lab-b": {
                "labs": [
                    lab("2026-10-19", "HbA1c and glucose", [
                        ("HbA1c", "4548-4", 8.9, "%", "4.0-5.6", "high"),
                        ("Glucose (fasting)", "2345-7", 168, "mg/dL", "70-99", "high"),
                    ]),
                    lab("2026-10-19", "Liver function tests", [
                        ("ALT", "1742-6", 62, "U/L", "7-56", "high"),
                        ("AST", "1920-8", 48, "U/L", "10-40", "high"),
                        ("ALP", "6768-6", 168, "U/L", "44-147", "high"),
                        ("Total bilirubin", "1975-2", 1.3, "mg/dL", "0.2-1.2", "high"),
                    ]),
                    lab("2026-10-19", "Complete blood count", [
                        ("Haemoglobin", "718-7", 14.1, "g/dL", "13.5-17.5", ""),
                        ("Platelets", "777-3", 231, "10*9/L", "150-400", ""),
                        ("WBC", "6690-2", 9.4, "10*9/L", "4.0-11.0", ""),
                    ]),
                    lab("2026-10-19", "Renal function", [
                        ("Creatinine", "2160-0", 0.9, "mg/dL", "0.7-1.3", ""),
                        ("eGFR", "62238-1", 102, "mL/min/1.73m2", ">=60", ""),
                    ]),
                ],
            },
            "rad-zia": {
                "imaging": [
                    img("2026-10-15", "Ultrasound abdomen", "Abdomen",
                        "Gallbladder contains multiple echogenic stones, largest 11 mm, with posterior shadowing. Wall thickness 4.5 mm. Common bile duct 6 mm. No pericholecystic fluid. Liver is mildly bright (fatty change). Pancreas and both kidneys are normal.",
                        "Cholelithiasis with a thickened gallbladder wall. Fatty liver. CBD at the upper limit of normal.", "Dr Hira Anwar, Consultant Radiologist"),
                ],
            },
        },
        "scenario": {
            "tests": "Drug against procedure: clopidogrel and aspirin before elective laparoscopic surgery with a stent placed 16 months ago (flag; surgeon and cardiologist decide, the system must not tell the patient to stop). Insulin and metformin around surgery and fasting (flag). Liver enzymes raised: shows a result that the requested MRCP should explain. Stopped hyoscine must not appear as current.",
            "should_flag": ["Clopidogrel before elective surgery", "Aspirin before elective surgery", "Insulin and metformin around fasting for surgery"],
            "records_outside_6_months": [],
        },
    },
]
