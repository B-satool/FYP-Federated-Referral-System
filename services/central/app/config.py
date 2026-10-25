from __future__ import annotations

import os
from pathlib import Path


def _bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    return default if raw is None else raw.strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    database_url = os.environ.get("DATABASE_URL", "postgresql+psycopg://central:central@postgres/central_db")
    redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
    storage_root = Path(os.environ.get("STORAGE_ROOT", "/data/documents"))
    repo_root = Path(os.environ.get("REPO_ASSETS", "/srv/assets"))

    source_timeout_seconds = float(os.environ.get("SOURCE_TIMEOUT_SECONDS", "10"))
    source_max_retries = int(os.environ.get("SOURCE_MAX_RETRIES", "2"))
    # Visits, results and imaging older than this are not retrieved for a referral.
    referral_window_days = int(os.environ.get("REFERRAL_WINDOW_DAYS", "183"))

    llm_provider = os.environ.get("LLM_PROVIDER", "anthropic")
    llm_model = os.environ.get("LLM_MODEL", "claude-opus-5-5")
    anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    extraction_mode = os.environ.get("EXTRACTION_MODE", "auto")  # auto | llm | rules
    llm_timeout_seconds = float(os.environ.get("LLM_TIMEOUT_SECONDS", "120"))

    max_upload_bytes = int(os.environ.get("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))
    max_pages = int(os.environ.get("MAX_PAGES", "10"))
    document_retention_days = int(os.environ.get("DOCUMENT_RETENTION_DAYS", "365"))

    run_jobs_inline = _bool("RUN_JOBS_INLINE", False)

    @property
    def llm_configured(self) -> bool:
        return self.llm_provider == "anthropic" and bool(self.anthropic_api_key)


settings = Settings()

# --------------------------------------------------------------------------- departments
# kind: clinical (receives referrals) | laboratory | imaging | cardiac (receive test/scan orders)
DEPARTMENTS: dict[str, dict] = {
    "general_practice": {"name": "General practice", "kind": "clinical"},
    "cardiology": {"name": "Cardiology", "kind": "clinical"},
    "gastro_hepatology": {"name": "Gastroenterology and Hepatology", "kind": "clinical"},
    "general_surgery": {"name": "General Surgery", "kind": "clinical"},
    "orthopaedics": {"name": "Orthopaedics", "kind": "clinical"},
    "dentistry": {"name": "Dentistry (Oral and Maxillofacial Surgery)", "kind": "clinical"},
    "nephrology": {"name": "Nephrology", "kind": "clinical"},
    "urology": {"name": "Urology", "kind": "clinical"},
    "neurology": {"name": "Neurology", "kind": "clinical"},
    "pulmonology": {"name": "Pulmonology", "kind": "clinical"},
    "endocrinology": {"name": "Endocrinology and Diabetes", "kind": "clinical"},
    "obgyn": {"name": "Obstetrics and Gynaecology", "kind": "clinical"},
    "ent": {"name": "ENT (Ear, Nose and Throat)", "kind": "clinical"},
    "ophthalmology": {"name": "Ophthalmology", "kind": "clinical"},
    "dermatology": {"name": "Dermatology", "kind": "clinical"},
    "oncology": {"name": "Oncology", "kind": "clinical"},
    "paediatrics": {"name": "Paediatrics", "kind": "clinical"},
    "psychiatry": {"name": "Psychiatry", "kind": "clinical"},
    "laboratory": {"name": "Clinical laboratory", "kind": "laboratory"},
    "radiology": {"name": "Radiology and imaging", "kind": "imaging"},
    "cardiac_diagnostics": {"name": "Cardiac diagnostics (ECG, echo)", "kind": "cardiac"},
    "clinic_tests": {"name": "In-clinic tests (ECG)", "kind": "cardiac"},
}
HOSPITAL_CLINICAL = ["cardiology", "gastro_hepatology", "general_surgery", "orthopaedics", "dentistry", "nephrology",
                     "urology", "neurology", "pulmonology", "endocrinology", "obgyn", "ent", "ophthalmology",
                     "dermatology", "oncology", "paediatrics", "psychiatry"]
HOSPITAL_DIAGNOSTIC = ["laboratory", "radiology", "cardiac_diagnostics"]

# Institutions in the demonstration (synthetic data; names are used only as source-system names).
INSTITUTIONS: dict[str, dict] = {
    "drali": {"name": "Dr Ali's Clinic, Clifton", "kind": "clinic", "url_env": "DRALI_URL",
              "departments": ["general_practice", "clinic_tests"]},
    "ziauddin": {"name": "Ziauddin Hospital", "kind": "hospital", "url_env": "ZIAUDDIN_URL",
                 "departments": HOSPITAL_CLINICAL + HOSPITAL_DIAGNOSTIC},
    "akuh": {"name": "Aga Khan University Hospital", "kind": "hospital", "url_env": "AKUH_URL",
             "departments": HOSPITAL_CLINICAL + HOSPITAL_DIAGNOSTIC},
    "chughtai": {"name": "Chughtai Lab", "kind": "laboratory", "url_env": "CHUGHTAI_URL",
                 "departments": ["laboratory"]},
    "central-platform": {"name": "Central referral platform", "kind": "platform", "departments": []},
}
SOURCES = {k for k, v in INSTITUTIONS.items() if v.get("url_env")}
KIND_LABELS = {"clinic": "clinic", "hospital": "hospital", "laboratory": "laboratory"}


def institution_url(institution_id: str) -> str:
    cfg = INSTITUTIONS[institution_id]
    return os.environ.get(cfg["url_env"], f"http://{institution_id}:8000").rstrip("/")


def institution_name(institution_id: str | None) -> str | None:
    if not institution_id:
        return None
    return INSTITUTIONS.get(institution_id, {}).get("name", institution_id)


def department_name(code: str | None) -> str | None:
    if not code:
        return None
    return DEPARTMENTS.get(code, {}).get("name", code)


# --------------------------------------------------------------------------- urgency (clinician-selected)
URGENCIES = {
    "urgent": {"label": "Urgent", "detail": "Patient should be seen within 1 week"},
    "soon": {"label": "Soon", "detail": "Patient should be seen within 2 weeks"},
    "routine": {"label": "Routine", "detail": "Patient should be seen within 4 to 6 weeks"},
}
URGENCY_NOTE = "For an emergency, send the patient to the emergency department now. Do not use a referral."

# --------------------------------------------------------------------------- procedures
# Tags describe what about a procedure can make a medicine relevant. Medication rules
# match a drug class against these tags, so a rule covers every procedure with the tag.
PROCEDURE_TAGS = {
    "oral_surgery": "Oral or dental surgery",
    "major_surgery": "Major or elective surgery",
    "minor_surgery": "Minor surgery",
    "general_anaesthesia": "General anaesthesia",
    "prolonged_fasting": "Fasting before and after the procedure",
    "iodinated_contrast": "Iodinated contrast media",
    "arterial_access": "Arterial puncture",
    "gi_endoscopy": "Gastrointestinal endoscopy",
    "sedation": "Sedation",
    "bleeding_risk": "Procedure with bleeding risk",
}
PROCEDURES: dict[str, dict] = {
    "surgical_tooth_extraction": {"label": "Surgical extraction of a tooth", "departments": ["dentistry"],
                                  "tags": ["oral_surgery", "bleeding_risk"]},
    "simple_tooth_extraction": {"label": "Simple tooth extraction", "departments": ["dentistry"],
                                "tags": ["oral_surgery", "bleeding_risk"]},
    "dental_implant": {"label": "Dental implant placement", "departments": ["dentistry"], "tags": ["oral_surgery"]},
    "coronary_angiography": {"label": "Coronary angiography", "departments": ["cardiology"],
                             "tags": ["iodinated_contrast", "arterial_access"]},
    "pci": {"label": "Coronary angioplasty and stenting (PCI)", "departments": ["cardiology"],
            "tags": ["iodinated_contrast", "arterial_access"]},
    "upper_gi_endoscopy": {"label": "Upper gastrointestinal endoscopy", "departments": ["gastro_hepatology"],
                           "tags": ["gi_endoscopy", "sedation"]},
    "colonoscopy": {"label": "Colonoscopy", "departments": ["gastro_hepatology"], "tags": ["gi_endoscopy", "sedation"]},
    "ercp": {"label": "ERCP", "departments": ["gastro_hepatology"],
             "tags": ["gi_endoscopy", "sedation", "iodinated_contrast", "bleeding_risk"]},
    "laparoscopic_cholecystectomy": {"label": "Laparoscopic cholecystectomy", "departments": ["general_surgery"],
                                     "tags": ["major_surgery", "general_anaesthesia", "prolonged_fasting", "bleeding_risk"]},
    "hernia_repair": {"label": "Hernia repair", "departments": ["general_surgery"],
                      "tags": ["major_surgery", "general_anaesthesia", "prolonged_fasting", "bleeding_risk"]},
    "total_knee_replacement": {"label": "Total knee replacement", "departments": ["orthopaedics"],
                               "tags": ["major_surgery", "general_anaesthesia", "prolonged_fasting", "bleeding_risk"]},
    "knee_arthroscopy": {"label": "Knee arthroscopy", "departments": ["orthopaedics"],
                         "tags": ["minor_surgery", "general_anaesthesia", "prolonged_fasting"]},
    "joint_injection": {"label": "Joint injection", "departments": ["orthopaedics"], "tags": []},
    "kidney_biopsy": {"label": "Kidney biopsy", "departments": ["nephrology"], "tags": ["bleeding_risk"]},
    "cystoscopy": {"label": "Cystoscopy", "departments": ["urology"], "tags": ["sedation"]},
    "pcnl": {"label": "Percutaneous nephrolithotomy (PCNL)", "departments": ["urology"],
             "tags": ["major_surgery", "general_anaesthesia", "prolonged_fasting", "bleeding_risk", "iodinated_contrast"]},
    "lumbar_puncture": {"label": "Lumbar puncture", "departments": ["neurology"], "tags": ["bleeding_risk"]},
    "bronchoscopy": {"label": "Bronchoscopy", "departments": ["pulmonology"], "tags": ["sedation"]},
    "hysteroscopy": {"label": "Hysteroscopy", "departments": ["obgyn"], "tags": ["sedation"]},
    "tonsillectomy": {"label": "Tonsillectomy", "departments": ["ent"],
                      "tags": ["major_surgery", "general_anaesthesia", "prolonged_fasting", "bleeding_risk"]},
    "cataract_surgery": {"label": "Cataract surgery", "departments": ["ophthalmology"], "tags": ["minor_surgery"]},
    "skin_biopsy": {"label": "Skin biopsy", "departments": ["dermatology"], "tags": ["minor_surgery"]},
    "tissue_biopsy": {"label": "Tissue biopsy", "departments": ["oncology"], "tags": ["bleeding_risk"]},
    "thyroid_fna": {"label": "Thyroid fine-needle aspiration", "departments": ["endocrinology"], "tags": []},
}
# none = consultation only (no procedure planned); unknown = the specialist will decide;
# other = a procedure not in the list (procedure-dependent rules cannot be checked).
PROCEDURE_STATUSES = {"known", "none", "unknown", "other"}


def procedure_label(status: str, code: str | None, other: str | None) -> str:
    if status == "known" and code:
        return PROCEDURES.get(code, {}).get("label", code)
    if status == "other":
        return f"{other or 'Other procedure'} (not in the procedure list)"
    if status == "none":
        return "No procedure planned (consultation only)"
    return "Not known yet (the specialist will decide)"


# --------------------------------------------------------------------------- doctor directory
# Picked in the referral form: the referring doctor (from the clinic's own staff) and,
# optionally, the doctor the patient should see. "username" marks demo sign-in accounts.
PRACTITIONERS = [
    {"name": "Dr Ali Raza", "institution": "drali", "department": "general_practice", "username": "dr.ali"},
    {"name": "Dr Asma Rauf", "institution": "ziauddin", "department": "cardiology", "username": "dr.asma"},
    {"name": "Dr Aamir Hussain", "institution": "ziauddin", "department": "cardiology"},
    {"name": "Dr Irfan Siddiqui", "institution": "ziauddin", "department": "gastro_hepatology", "username": "dr.irfan"},
    {"name": "Dr Kashif Mehmood", "institution": "ziauddin", "department": "orthopaedics"},
    {"name": "Dr Sadia Imran", "institution": "ziauddin", "department": "general_surgery"},
    {"name": "Dr Bilal Qadir", "institution": "ziauddin", "department": "nephrology"},
    {"name": "Dr Rehana Kausar", "institution": "ziauddin", "department": "neurology"},
    {"name": "Dr Faisal Haider", "institution": "akuh", "department": "dentistry", "username": "dr.faisal"},
    {"name": "Dr Salman Akhtar", "institution": "akuh", "department": "orthopaedics", "username": "dr.salman"},
    {"name": "Dr Naveed Baig", "institution": "akuh", "department": "general_surgery", "username": "dr.naveed"},
    {"name": "Dr Ayesha Siddiqa", "institution": "akuh", "department": "gastro_hepatology"},
    {"name": "Dr Hamid Raza", "institution": "akuh", "department": "cardiology"},
    {"name": "Dr Saima Zafar", "institution": "akuh", "department": "pulmonology"},
]

# --------------------------------------------------------------------------- test and scan suggestions
TEST_SUGGESTIONS = [
    {"test": "Complete blood count", "category": "laboratory"},
    {"test": "Liver function tests", "category": "laboratory"},
    {"test": "Renal function (creatinine, eGFR)", "category": "laboratory"},
    {"test": "HbA1c", "category": "laboratory"},
    {"test": "Lipid profile", "category": "laboratory"},
    {"test": "Coagulation (PT/INR)", "category": "laboratory"},
    {"test": "Serum lipase", "category": "laboratory"},
    {"test": "Thyroid function (TSH)", "category": "laboratory"},
    {"test": "Urine routine examination", "category": "laboratory"},
    {"test": "Chest X-ray", "category": "imaging", "body_area": "Chest"},
    {"test": "Ultrasound abdomen", "category": "imaging", "body_area": "Abdomen"},
    {"test": "CT abdomen with contrast", "category": "imaging", "body_area": "Abdomen"},
    {"test": "MRI knee", "category": "imaging", "body_area": "Knee"},
    {"test": "MRI brain", "category": "imaging", "body_area": "Head"},
    {"test": "MRCP", "category": "imaging", "body_area": "Abdomen"},
    {"test": "CBCT (cone-beam CT) of the jaw", "category": "imaging", "body_area": "Jaw"},
    {"test": "Transient elastography (FibroScan)", "category": "imaging", "body_area": "Liver"},
    {"test": "Resting ECG", "category": "cardiac"},
    {"test": "Transthoracic echocardiogram", "category": "cardiac", "body_area": "Heart"},
]
DRUG_CLASSES = {
    "anticoagulant": "Anticoagulant",
    "antiplatelet": "Antiplatelet",
    "nsaid": "NSAID (anti-inflammatory painkiller)",
    "biguanide": "Biguanide (metformin)",
    "sulfonylurea": "Sulfonylurea",
    "sglt2_inhibitor": "SGLT2 inhibitor",
    "insulin": "Insulin",
    "bisphosphonate": "Bisphosphonate",
    "systemic_corticosteroid": "Systemic corticosteroid",
    "statin": "Statin",
    "beta_blocker": "Beta blocker",
    "ace_inhibitor": "ACE inhibitor",
    "arb": "Angiotensin receptor blocker",
    "calcium_channel_blocker": "Calcium channel blocker",
    "proton_pump_inhibitor": "Proton pump inhibitor",
    "analgesic": "Analgesic",
    "opioid": "Opioid analgesic",
    "antibiotic": "Antibiotic",
    "antiviral": "Antiviral",
    "antispasmodic": "Antispasmodic",
    "iron_supplement": "Iron supplement",
    "calcium_vitamin_d": "Calcium and vitamin D",
    "thyroid_hormone": "Thyroid hormone",
    "bronchodilator": "Bronchodilator",
}
DIAGNOSTIC_CATEGORIES = {"laboratory": "Laboratory test", "imaging": "Imaging or scan", "cardiac": "Cardiac test"}
CATEGORY_DEPARTMENT_KIND = {"laboratory": "laboratory", "imaging": "imaging", "cardiac": "cardiac"}
