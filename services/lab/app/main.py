"""Lab B source service (independent service, own database, own access decisions)."""
from __future__ import annotations

import os

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel
from refcommon.auth import KeycloakConfig, Principal, TokenVerifier, forbid, make_principal_dependency
from refcommon.db import make_session_factory, session_dependency, utcnow
from refcommon.sourcekit import (
    MatchIn,
    build_admin_router,
    decide_access,
    health_router,
    identity_match,
    record_audit,
    records_bundle,
)
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from . import adapter
from .models import AccessGrant, AuditEvent, Patient, Report, Result, ResultRevision

INSTITUTION = "lab-b"
CATEGORIES = {"demographics", "labs"}

engine, SessionLocal = make_session_factory(os.environ["DATABASE_URL"])
get_db = session_dependency(SessionLocal)
verifier = TokenVerifier(KeycloakConfig(), audience="lab-api")
get_principal = make_principal_dependency(verifier)

app = FastAPI(
    title="Lab B source service",
    version="1.0.0",
    description="Example laboratory system. Returns custom endpoints carrying FHIR R4 4.0.1 content.",
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


def _result_out(r: Result) -> dict:
    return {
        "id": r.id, "patient_id": r.patient_id, "report_id": r.report_id, "loinc": r.loinc, "test_name": r.test_name,
        "value_num": r.value_num, "value_text": r.value_text, "unit": r.unit, "reference_range": r.reference_range,
        "specimen": r.specimen, "collected_at": r.collected_at, "resulted_at": r.resulted_at, "status": r.status,
        "version": r.version,
    }


def _require_lab_staff(principal: Principal) -> None:
    if principal.institution_id != INSTITUTION or "lab_staff" not in principal.roles:
        raise forbid("Only Lab B laboratory staff can use the laboratory workspace")


@app.get("/lab/patients", tags=["laboratory workspace"])
def lab_patients(db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    _require_lab_staff(principal)
    return [{"local_patient_id": p.local_id, "given": p.given, "family": p.family,
             "birth_date": p.birth_date.isoformat(), "sex": p.sex, "synthetic": p.synthetic}
            for p in db.scalars(select(Patient).order_by(Patient.local_id))]


@app.get("/lab/patients/{local_id}/results", tags=["laboratory workspace"])
def lab_patient_results(local_id: str, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    _require_lab_staff(principal)
    rows = db.scalars(select(Result).where(Result.patient_id == local_id).order_by(Result.collected_at.desc())).all()
    out = []
    for r in rows:
        item = _result_out(r)
        item["revisions"] = [{"version": rv.version, "snapshot": rv.snapshot, "reason": rv.reason,
                              "changed_by": rv.changed_by, "changed_at": rv.changed_at}
                             for rv in db.scalars(select(ResultRevision).where(ResultRevision.result_id == r.id)
                                                  .order_by(ResultRevision.version))]
        out.append(item)
    return out


class CorrectionIn(BaseModel):
    value_num: float | None = None
    value_text: str | None = None
    unit: str | None = None
    reason: str
    expected_version: int


@app.post("/lab/results/{result_id}/correct", tags=["laboratory workspace"])
def correct_result(result_id: str, body: CorrectionIn, db: Session = Depends(get_db),
                   principal: Principal = Depends(get_principal)):
    """Publish a corrected result as a new record version; the prior version is retained."""
    _require_lab_staff(principal)
    r = db.get(Result, result_id)
    if not r:
        raise HTTPException(404, {"code": "not_found", "message": "Result not found"})
    if r.version != body.expected_version:
        raise HTTPException(409, {"code": "stale_version", "message": "Result changed since you opened it; reload"})
    if not body.reason.strip():
        raise HTTPException(422, {"code": "reason_required", "message": "A correction reason is required"})
    db.add(ResultRevision(result_id=r.id, version=r.version, snapshot=_result_out(r) | {"collected_at": str(r.collected_at), "resulted_at": str(r.resulted_at)},
                          reason=body.reason, changed_by=principal.display_name))
    r.value_num = body.value_num
    r.value_text = body.value_text
    if body.unit is not None:
        r.unit = body.unit
    r.status = "corrected"
    r.version += 1
    r.resulted_at = utcnow()
    record_audit(db, AuditEvent, principal, "result.correct", "result", r.id, "success",
                 detail={"new_version": r.version, "reason": body.reason})
    db.commit()
    return _result_out(r)


@app.post("/identity/match", tags=["identity"])
def match_identity(body: MatchIn, request: Request, db: Session = Depends(get_db),
                   principal: Principal = Depends(get_principal)):
    if not principal.has_any("clinic_staff", "clinician", "institution_admin", "specialist", "lab_staff"):
        raise forbid("Role may not request identity verification checks")
    result = identity_match(db.get(Patient, body.local_patient_id), body)
    record_audit(db, AuditEvent, principal, "identity.match", "patient", body.local_patient_id, "success",
                 referral_context=request.headers.get("x-referral-id"), detail=result)
    db.commit()
    return result


@app.get("/fhir/patients/{local_id}/results", tags=["fhir"])
@app.get("/fhir/patients/{local_id}/records", tags=["fhir"])
def patient_results(local_id: str, request: Request, categories: str | None = None,
                    db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """Custom project endpoint returning a FHIR searchset Bundle (Observation + DiagnosticReport)."""
    referral_ctx = request.headers.get("x-referral-id")
    requested = set(categories.split(",")) & CATEGORIES if categories else set(CATEGORIES)
    patient = db.get(Patient, local_id)
    if patient is None:
        record_audit(db, AuditEvent, principal, "records.read", "patient", local_id, "not_found", referral_ctx)
        db.commit()
        raise HTTPException(404, {"code": "patient_not_found", "message": "No such patient at Lab B"})
    decision = decide_access(db, AccessGrant, principal, INSTITUTION, local_id, requested)
    if not decision.allowed:
        record_audit(db, AuditEvent, principal, "records.read", "patient", local_id, "denied", referral_ctx,
                     {"reason": decision.reason})
        db.commit()
        raise forbid(f"Lab B denied access: {decision.reason}", code="access_denied")
    resources: list[dict] = []
    if "demographics" in decision.allowed:
        resources.append(adapter.patient(patient))
    if "labs" in decision.allowed:
        results = db.scalars(select(Result).where(Result.patient_id == local_id)).all()
        resources += [adapter.observation(r) for r in results]
        for rep in db.scalars(select(Report).where(Report.patient_id == local_id)):
            resources.append(adapter.diagnostic_report(rep, [r.id for r in results if r.report_id == rep.id]))
    record_audit(db, AuditEvent, principal, "records.read", "patient", local_id,
                 "partial" if decision.denied else "success", referral_ctx,
                 {"categories": sorted(decision.allowed), "withheld": sorted(decision.denied), "count": len(resources)})
    db.commit()
    return records_bundle(resources, decision.denied)
