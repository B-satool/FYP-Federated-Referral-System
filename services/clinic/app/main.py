"""Clinic A source service (independent service, own database, own access decisions)."""
from __future__ import annotations

import os

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from refcommon.auth import KeycloakConfig, Principal, TokenVerifier, forbid, make_principal_dependency
from refcommon.db import make_session_factory, session_dependency
from refcommon.sourcekit import (
    MatchIn,
    build_admin_router,
    decide_access,
    health_router,
    identity_match,
    record_audit,
    records_bundle,
)
from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session

from . import adapter
from .models import (
    AccessGrant,
    AuditEvent,
    Condition,
    Encounter,
    Patient,
    Prescription,
    ReportedMedication,
    SourceDocument,
)

INSTITUTION = "clinic-a"
CATEGORIES = {"demographics", "encounters", "conditions", "medications", "documents"}

engine, SessionLocal = make_session_factory(os.environ["DATABASE_URL"])
get_db = session_dependency(SessionLocal)
verifier = TokenVerifier(KeycloakConfig(), audience="clinic-api")
get_principal = make_principal_dependency(verifier)

app = FastAPI(
    title="Clinic A source service",
    version="1.0.0",
    description="Example referring-clinic system. Returns custom endpoints carrying FHIR R4 4.0.1 content.",
)


def _check_db() -> None:
    with engine.connect() as conn:
        conn.execute(text("select 1"))


app.include_router(health_router(_check_db))
app.include_router(build_admin_router(
    INSTITUTION, AccessGrant, AuditEvent,
    lambda db, pid: db.get(Patient, pid) is not None,
    get_db, get_principal,
))


def _demographics(p: Patient) -> dict:
    return {
        "institution_id": INSTITUTION,
        "local_patient_id": p.local_id,
        "given": p.given,
        "family": p.family,
        "birth_date": p.birth_date.isoformat(),
        "sex": p.sex,
        "city": p.city,
        "synthetic": p.synthetic,
    }


@app.get("/patients", tags=["patients"])
def search_patients(q: str = Query("", max_length=100), db: Session = Depends(get_db),
                    principal: Principal = Depends(get_principal)):
    """Local patient index; only this clinic's own staff may search it."""
    if principal.institution_id != INSTITUTION or not principal.has_any("clinic_staff", "clinician"):
        record_audit(db, AuditEvent, principal, "patients.search", "patient_index", "*", "denied")
        db.commit()
        raise forbid("Only Clinic A staff can search the Clinic A patient index")
    stmt = select(Patient).order_by(Patient.local_id)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Patient.local_id.ilike(like), Patient.given.ilike(like), Patient.family.ilike(like)))
    rows = db.scalars(stmt.limit(50)).all()
    record_audit(db, AuditEvent, principal, "patients.search", "patient_index", "*", "success", detail={"q": q, "count": len(rows)})
    db.commit()
    return [_demographics(p) for p in rows]


@app.post("/identity/match", tags=["identity"])
def match_identity(body: MatchIn, request: Request, db: Session = Depends(get_db),
                   principal: Principal = Depends(get_principal)):
    if not principal.has_any("clinic_staff", "clinician", "institution_admin", "specialist"):
        raise forbid("Role may not request identity verification checks")
    result = identity_match(db.get(Patient, body.local_patient_id), body)
    record_audit(db, AuditEvent, principal, "identity.match", "patient", body.local_patient_id, "success",
                 referral_context=request.headers.get("x-referral-id"), detail=result)
    db.commit()
    return result


@app.get("/fhir/patients/{local_id}/records", tags=["fhir"])
def patient_records(local_id: str, request: Request, categories: str | None = None,
                    db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """Custom project endpoint returning a FHIR searchset Bundle for one local patient."""
    referral_ctx = request.headers.get("x-referral-id")
    requested = set(categories.split(",")) & CATEGORIES if categories else set(CATEGORIES)
    patient = db.get(Patient, local_id)
    if patient is None:
        record_audit(db, AuditEvent, principal, "records.read", "patient", local_id, "not_found", referral_ctx)
        db.commit()
        raise HTTPException(404, {"code": "patient_not_found", "message": "No such patient at Clinic A"})
    decision = decide_access(db, AccessGrant, principal, INSTITUTION, local_id, requested)
    if not decision.allowed:
        record_audit(db, AuditEvent, principal, "records.read", "patient", local_id, "denied", referral_ctx,
                     {"reason": decision.reason})
        db.commit()
        raise forbid(f"Clinic A denied access: {decision.reason}", code="access_denied")

    resources: list[dict] = []
    if "demographics" in decision.allowed:
        resources.append(adapter.patient(patient))
    if "encounters" in decision.allowed:
        resources += [adapter.encounter(e) for e in db.scalars(select(Encounter).where(Encounter.patient_id == local_id))]
    if "conditions" in decision.allowed:
        resources += [adapter.condition(c) for c in db.scalars(select(Condition).where(Condition.patient_id == local_id))]
    if "medications" in decision.allowed:
        resources += [adapter.medication_request(m) for m in db.scalars(select(Prescription).where(Prescription.patient_id == local_id))]
        resources += [adapter.medication_statement(m) for m in db.scalars(select(ReportedMedication).where(ReportedMedication.patient_id == local_id))]
    if "documents" in decision.allowed:
        resources += [adapter.document_reference(d) for d in db.scalars(select(SourceDocument).where(SourceDocument.patient_id == local_id))]

    record_audit(db, AuditEvent, principal, "records.read", "patient", local_id,
                 "partial" if decision.denied else "success", referral_ctx,
                 {"categories": sorted(decision.allowed), "withheld": sorted(decision.denied), "count": len(resources)})
    db.commit()
    return records_bundle(resources, decision.denied)
