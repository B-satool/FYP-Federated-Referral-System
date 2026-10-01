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

    clinic_url = os.environ.get("CLINIC_URL", "http://clinic:8000").rstrip("/")
    lab_url = os.environ.get("LAB_URL", "http://lab:8000").rstrip("/")
    specialist_url = os.environ.get("SPECIALIST_URL", "http://specialist:8000").rstrip("/")
    source_timeout_seconds = float(os.environ.get("SOURCE_TIMEOUT_SECONDS", "10"))
    source_max_retries = int(os.environ.get("SOURCE_MAX_RETRIES", "2"))

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

# Institutions participating in the demonstration (reference data).
INSTITUTIONS = {
    "clinic-a": {"name": "Clinic A - Green Valley Family Clinic", "kind": "clinic"},
    "clinic-x": {"name": "Clinic X - Riverside Medical Centre", "kind": "clinic"},
    "lab-b": {"name": "Lab B - CityLab Diagnostics", "kind": "laboratory"},
    "spec-c": {"name": "Specialist C - Smile Orthodontic Centre", "kind": "specialist"},
    "central-platform": {"name": "Central referral platform", "kind": "platform"},
}

# Source services the central platform may call (never their databases).
SOURCES = {
    "clinic-a": {"url_attr": "clinic_url", "categories": "demographics,encounters,conditions,medications,documents",
                 "path": "/fhir/patients/{id}/records", "medication_source": True},
    "lab-b": {"url_attr": "lab_url", "categories": "demographics,labs", "path": "/fhir/patients/{id}/results",
              "medication_source": False},
    "spec-c": {"url_attr": "specialist_url", "categories": "demographics,consultations,conditions",
               "path": "/fhir/patients/{id}/records", "medication_source": False},
}

SPECIALTIES = {"orthodontics": "Orthodontics"}
PROCEDURES = {
    "orthodontic_assessment": "Orthodontic assessment only",
    "fixed_appliance": "Fixed appliance treatment",
    "tooth_extraction": "Tooth extraction (as part of orthodontic plan)",
    "mini_implant_placement": "Temporary anchorage device (mini-implant) placement",
    "orthognathic_surgery": "Orthognathic surgery (combined care)",
}
PRIORITIES = ("routine", "soon", "urgent")
