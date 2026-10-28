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

    llm_provider = os.environ.get("LLM_PROVIDER", "anthropic")  # anthropic | ollama
    llm_model = os.environ.get("LLM_MODEL", "claude-opus-5-5")
    anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    # Ollama: a local server (which also serves ":cloud" models once `ollama signin` has run on that
    # computer), or https://ollama.com directly with OLLAMA_API_KEY.
    ollama_host = os.environ.get("OLLAMA_HOST", "http://host.docker.internal:11434").rstrip("/")
    ollama_api_key = os.environ.get("OLLAMA_API_KEY", "")
    extraction_mode = os.environ.get("EXTRACTION_MODE", "auto")  # auto | llm | rules
    llm_timeout_seconds = float(os.environ.get("LLM_TIMEOUT_SECONDS", "120"))

    max_upload_bytes = int(os.environ.get("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))
    max_pages = int(os.environ.get("MAX_PAGES", "10"))
    document_retention_days = int(os.environ.get("DOCUMENT_RETENTION_DAYS", "365"))
    # How long a referral's shared records are kept (docs/decisions/2026-10-28-referral-expiry.md):
    # no limit until the receiving doctor accepts; then a safety limit of ACCEPTED_HOLD_DAYS, which that
    # doctor can extend by the same again; removed WORKING_SET_GRACE_HOURS after they mark the referral
    # complete (or it is cancelled), and straight away if they decline it.
    working_set_grace_hours = int(os.environ.get("WORKING_SET_GRACE_HOURS", "72"))
    accepted_hold_days = int(os.environ.get("ACCEPTED_HOLD_DAYS", "30"))
    # How far back retrieval asks each source (the 6-month window is the default selection, not a fetch limit),
    # for a destination with no entry in SPECIALTY_HISTORY_YEARS
    history_years = int(os.environ.get("REFERRAL_HISTORY_YEARS", "3"))
    # Retrieval asks every linked institution, up to this many besides the referring one (most recently
    # visited first), so the AI recommendation stays within what it can read. The rest are listed as
    # not retrieved, never as "no records".
    max_retrieval_sources = int(os.environ.get("MAX_RETRIEVAL_SOURCES", "5"))

    run_jobs_inline = _bool("RUN_JOBS_INLINE", False)

    @property
    def llm_configured(self) -> bool:
        if self.llm_provider == "ollama":
            return bool(self.llm_model and self.ollama_host)
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

# Years of visits, results and imaging retrieved for a referral to each specialty. Conditions, surgeries
# and current medicines are retrieved whatever their date. Placeholders until a clinician confirms them
# (docs/decisions/2026-10-28-retrieval-all-sources.md); others use REFERRAL_HISTORY_YEARS.
SPECIALTY_HISTORY_YEARS: dict[str, int] = {
    "cardiology": 5, "endocrinology": 5, "nephrology": 5, "oncology": 5, "neurology": 5,
    "gastro_hepatology": 3, "general_surgery": 3, "orthopaedics": 3, "pulmonology": 3, "urology": 3,
    "psychiatry": 3, "paediatrics": 3, "general_practice": 3,
    "obgyn": 2, "ent": 2, "ophthalmology": 2, "dentistry": 2,
    "dermatology": 1,
}


def history_years_for(department: str | None) -> int:
    return SPECIALTY_HISTORY_YEARS.get(department or "", settings.history_years)

# Institutions in the demonstration (synthetic data; names are used only as source-system names).
INSTITUTIONS: dict[str, dict] = {
    "drali": {"name": "Dr Ali's Clinic, Clifton", "kind": "clinic", "url_env": "DRALI_URL",
              "departments": ["general_practice", "clinic_tests"]},
    "ziauddin": {"name": "Ziauddin Hospital", "kind": "hospital", "url_env": "ZIAUDDIN_URL",
                 "departments": HOSPITAL_CLINICAL + HOSPITAL_DIAGNOSTIC},
    "akuh": {"name": "Aga Khan University Hospital", "kind": "hospital", "url_env": "AKUH_URL",
             "departments": HOSPITAL_CLINICAL + HOSPITAL_DIAGNOSTIC},
    "chughtai": {"name": "Chughtai Lab", "kind": "laboratory", "url_env": "CHUGHTAI_URL",
                 "departments": ["laboratory", "radiology"]},
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
# The doctor writes the procedure in their own words and ticks what it involves. Words in
# the name pre-tick likely features (the doctor can change them); nothing is guessed silently.
PROCEDURE_HINTS: dict[str, list[str]] = {
    "ectomy": ["major_surgery", "general_anaesthesia", "prolonged_fasting", "bleeding_risk"],
    "replacement": ["major_surgery", "general_anaesthesia", "prolonged_fasting", "bleeding_risk"],
    "repair": ["major_surgery", "general_anaesthesia", "prolonged_fasting", "bleeding_risk"],
    "surgery": ["major_surgery", "general_anaesthesia", "prolonged_fasting", "bleeding_risk"],
    "laparoscopic": ["major_surgery", "general_anaesthesia", "prolonged_fasting", "bleeding_risk"],
    "extraction": ["oral_surgery", "bleeding_risk"],
    "tooth": ["oral_surgery", "bleeding_risk"],
    "dental": ["oral_surgery"],
    "implant": ["oral_surgery"],
    "endoscopy": ["gi_endoscopy", "sedation"],
    "colonoscopy": ["gi_endoscopy", "sedation"],
    "ercp": ["gi_endoscopy", "sedation", "iodinated_contrast", "bleeding_risk"],
    "angiography": ["iodinated_contrast", "arterial_access"],
    "angioplasty": ["iodinated_contrast", "arterial_access"],
    "contrast": ["iodinated_contrast"],
    "biopsy": ["bleeding_risk"],
    "arthroscopy": ["minor_surgery", "general_anaesthesia", "prolonged_fasting"],
    "bronchoscopy": ["sedation"],
    "cystoscopy": ["sedation"],
    "puncture": ["bleeding_risk"],
}
# planned = a procedure is planned (name + features); none = consultation only;
# unknown = the specialist will decide (procedure-dependent rules are not checked).
PROCEDURE_STATUSES = {"planned", "none", "unknown"}


def procedure_label(status: str, text: str | None) -> str:
    if status == "planned" and text:
        return text
    if status == "none":
        return "No procedure planned (consultation only)"
    return "Not known yet (the specialist will decide)"

# Shown beside medication flags. Wording to be confirmed by the supervisor (see docs/medication-flagging.md).
FLAG_DISCLAIMER = (
    "Medication flags are information for the clinician, produced automatically from approved rules, the DDInter "
    "interaction database and US drug labels. Imported flags are not clinically reviewed and may be incomplete or "
    "wrong. They are not medical advice, never mean a medicine is safe, and do not replace the clinician's judgement "
    "or a pharmacist's review."
)

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
