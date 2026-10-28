"""Institution service: one instance per clinic, laboratory or hospital.

It owns this institution's patient records and makes every access decision
itself (own staff and role, or an access grant created by its own staff when
they approved a patient-link request). Clinics and hospitals receive referrals
here (staff take them in, confirm the patient and assign a doctor), and
laboratory/imaging departments receive diagnostic orders here.
"""
from __future__ import annotations

import base64
import binascii
import logging
import os
import threading
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from typing import Any, Literal

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from refcommon.auth import KeycloakConfig, Principal, ServiceTokenProvider, TokenVerifier, forbid, make_principal_dependency
from refcommon.db import make_session_factory, session_dependency, utcnow
from refcommon.exchange import ClarificationAnswer, DiagnosticOrder, ProviderEvent, ResultForward
from refcommon.sourcekit import (
    ALL_CATEGORIES,
    DEFAULT_GRANT_DAYS,
    build_admin_router,
    build_grant_service_router,
    decide_access,
    grant_expiry,
    grant_is_live,
    health_router,
    normalize_cnic,
    record_audit,
    records_bundle,
)
from sqlalchemy import func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import adapter
from .config import (ACCEPTED_HOLD_DAYS, AUDIENCE, CENTRAL_URL, DEFAULT_WINDOW_DAYS, GRACE_HOURS, INSTITUTION, INSTITUTION_NAME,
                     LOCAL_ID_PREFIX)
from .models import (
    AccessGrant,
    AuditEvent,
    Case,
    Condition,
    ConsultationResponse,
    ForwardedResult,
    ImagingReport,
    IncomingPackage,
    InfoRequest,
    LabResult,
    Medication,
    Order,
    OrderAttachment,
    Outbox,
    Patient,
    SentCopy,
    Surgery,
    Visit,
)

log = logging.getLogger("provider")
OUTBOX_MAX_ATTEMPTS = 12
STAFF_ROLES = ("clinic_staff", "clinician", "institution_admin")
INTAKE_ROLES = ("clinic_staff", "institution_admin")  # take in referrals and assign a doctor
IDENTITY_ROLES = ("clinic_staff", "institution_admin", "diagnostics_staff")  # confirm who an arriving patient is
MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024
ATTACHMENT_TYPES = {"image/png", "image/jpeg", "application/pdf"}

engine, SessionLocal = make_session_factory(os.environ["DATABASE_URL"])
get_db = session_dependency(SessionLocal)
kc = KeycloakConfig()
verifier = TokenVerifier(kc, audience=AUDIENCE)
get_principal = make_principal_dependency(verifier)
service_tokens = ServiceTokenProvider(kc)
_stop = threading.Event()


# --------------------------------------------------------------------------- outbox delivery
def _deliver_once() -> int:
    sent = 0
    with SessionLocal() as db:
        due = db.scalars(select(Outbox).where(Outbox.status == "pending", Outbox.next_attempt_at <= utcnow())
                         .order_by(Outbox.id).limit(20)).all()
        for item in due:
            item.attempts += 1
            try:
                token = service_tokens.get()
                resp = httpx.post(f"{CENTRAL_URL}/inbound/provider-events", json=item.payload,
                                  headers={"Authorization": f"Bearer {token}"}, timeout=10.0)
                if resp.status_code < 300:
                    item.status, item.sent_at, item.last_error = "sent", utcnow(), None
                    sent += 1
                elif 400 <= resp.status_code < 500 and resp.status_code not in (401, 408, 409, 429):
                    item.status = "failed"
                    item.last_error = f"rejected by central ({resp.status_code}): {resp.text[:300]}"
                else:
                    raise httpx.HTTPStatusError(f"central returned {resp.status_code}", request=resp.request, response=resp)
            except httpx.HTTPError as exc:
                item.last_error = str(exc)[:500]
                if item.attempts >= OUTBOX_MAX_ATTEMPTS:
                    item.status = "failed"
                else:
                    item.next_attempt_at = utcnow() + timedelta(seconds=min(60, 2 ** item.attempts))
            db.commit()
    return sent


def _outbox_loop() -> None:
    while not _stop.is_set():
        try:
            _deliver_once()
        except Exception:  # noqa: BLE001 - keep the loop alive; errors are stored per item
            log.exception("outbox loop error")
        _stop.wait(3)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    thread = threading.Thread(target=_outbox_loop, name="outbox", daemon=True)
    thread.start()
    yield
    _stop.set()


app = FastAPI(
    title=f"{INSTITUTION_NAME} institution service",
    version="2.0.0",
    description=("One institution's own system: patient records, access decisions, received referrals and "
                 "diagnostic orders. Custom endpoints return FHIR R4 4.0.1 content."),
    lifespan=lifespan,
)


def _check_db() -> None:
    with engine.connect() as conn:
        conn.execute(text("select 1"))


app.include_router(health_router(_check_db))
app.include_router(build_admin_router(INSTITUTION, AccessGrant, AuditEvent,
                                      lambda db, pid: db.get(Patient, pid) is not None, get_db, get_principal))
app.include_router(build_grant_service_router(INSTITUTION, AccessGrant, AuditEvent, get_db, get_principal))


# --------------------------------------------------------------------------- helpers
def _not_found(message: str) -> HTTPException:
    return HTTPException(404, {"code": "not_found", "message": message})


def _conflict(code: str, message: str) -> HTTPException:
    return HTTPException(409, {"code": code, "message": message})


def require_own(principal: Principal, *roles: str, what: str = "do this") -> None:
    if principal.institution_id != INSTITUTION or not principal.has_any(*roles):
        raise forbid(f"Only {INSTITUTION_NAME} staff with the right role can {what}")


def _require_central(principal: Principal) -> None:
    if "svc_central" not in principal.roles:
        raise forbid("Only the central referral platform may deliver to this endpoint")


def _plain(name: str | None) -> str:
    return (name or "").lower().replace("dr ", "").replace("dr. ", "").strip()


def _demographics(p: Patient) -> dict:
    return {"institution_id": INSTITUTION, "local_patient_id": p.local_id, "given": p.given, "family": p.family,
            "name": f"{p.given} {p.family}", "birth_date": p.birth_date.isoformat(), "sex": p.sex, "cnic": p.cnic,
            "phone": p.phone, "city": p.city, "synthetic": p.synthetic}


def _emit(db: Session, key: str, event_type: str, referral_id: str, principal: Principal, data: dict | None = None,
          case: Case | None = None, order: Order | None = None, package_version: int | None = None) -> None:
    if db.scalars(select(Outbox).where(Outbox.event_key == key)).first():
        return
    event = ProviderEvent(event_key=key, referral_id=referral_id, order_ref=order.order_ref if order else None,
                          package_version=package_version or (case.latest_version if case else None), type=event_type,
                          actor_id=principal.subject, actor_name=principal.display_name, institution_id=INSTITUTION,
                          occurred_at=utcnow(), data=data or {})
    db.add(Outbox(event_key=key, event_type=event_type, case_id=case.id if case else None,
                  order_id=order.id if order else None, payload=event.model_dump(mode="json")))


# --------------------------------------------------------------------------- patient index (own staff)
@app.get("/patients", tags=["patients"])
def search_patients(q: str = Query("", max_length=100), db: Session = Depends(get_db),
                    principal: Principal = Depends(get_principal)):
    """Own patient index (name, local ID or CNIC)."""
    require_own(principal, *STAFF_ROLES, "diagnostics_staff", what="search the patient index")
    stmt = select(Patient).order_by(Patient.family, Patient.given)
    if q.strip():
        like = f"%{q.strip()}%"
        digits = normalize_cnic(q)
        conds = [Patient.local_id.ilike(like), Patient.given.ilike(like), Patient.family.ilike(like),
                 func.concat(Patient.given, " ", Patient.family).ilike(like)]
        if len(digits) >= 5:
            conds.append(Patient.cnic.like(f"%{digits}%"))
        stmt = stmt.where(or_(*conds))
    rows = db.scalars(stmt.limit(50)).all()
    record_audit(db, AuditEvent, principal, "patients.search", "patient_index", "*", "success", detail={"q": q, "count": len(rows)})
    db.commit()
    return [_demographics(p) for p in rows]


@app.get("/patients/{local_id}", tags=["patients"])
def get_patient(local_id: str, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    require_own(principal, *STAFF_ROLES, "diagnostics_staff", what="view patient details")
    p = db.get(Patient, local_id)
    if p is None:
        raise _not_found("No such patient")
    return _demographics(p)


# --------------------------------------------------------------------------- identity (link approval)
class LookupIn(BaseModel):
    cnic: str | None = None
    name: str | None = None
    birth_date: str | None = None
    sex: str | None = None


@app.post("/identity/lookup", tags=["identity"])
def identity_lookup(body: LookupIn, request: Request, db: Session = Depends(get_db),
                    principal: Principal = Depends(get_principal)):
    """Own staff look up who a link request refers to. Candidates are shown to a person,
    with each field compared; nothing is linked automatically."""
    require_own(principal, *STAFF_ROLES, "diagnostics_staff", what="look up a patient for a link request")
    cnic = normalize_cnic(body.cnic)
    cands: list[Patient] = []
    if cnic:
        cands = list(db.scalars(select(Patient).where(Patient.cnic == cnic)))
    if not cands and body.name and body.birth_date:
        family = body.name.split()[-1]
        cands = [p for p in db.scalars(select(Patient).where(Patient.family.ilike(family)))
                 if p.birth_date.isoformat() == body.birth_date]
    out = []
    for p in cands:
        out.append({**_demographics(p), "compare": {
            "cnic": bool(cnic) and p.cnic == cnic,
            "name": _plain(f"{p.given} {p.family}") == _plain(body.name),
            "birth_date": p.birth_date.isoformat() == (body.birth_date or ""),
            "sex": (p.sex or "").upper() == (body.sex or "").upper(),
        }})
    record_audit(db, AuditEvent, principal, "identity.lookup", "patient_index", "*", "success",
                 referral_context=request.headers.get("x-referral-id"), detail={"candidates": len(out)})
    db.commit()
    return out


class RegisterIn(BaseModel):
    cnic: str
    given: str
    family: str
    birth_date: date
    sex: str
    phone: str | None = None
    city: str | None = None


@app.post("/identity/register", status_code=201, tags=["identity"])
def register_patient(body: RegisterIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """Register a patient who is new to this institution (first referral or test here)."""
    require_own(principal, *IDENTITY_ROLES, what="register a new patient")
    cnic = normalize_cnic(body.cnic)
    if len(cnic) != 13:
        raise HTTPException(422, {"code": "invalid_cnic", "message": "CNIC must have 13 digits"})
    if db.scalars(select(Patient).where(Patient.cnic == cnic)).first():
        raise _conflict("already_registered", "A patient with this CNIC is already registered here; choose that record")
    n = (db.scalar(select(func.count()).select_from(Patient)) or 0) + 1
    local_id = f"{LOCAL_ID_PREFIX}-{900000 + n}"
    while db.get(Patient, local_id):
        n += 1
        local_id = f"{LOCAL_ID_PREFIX}-{900000 + n}"
    p = Patient(local_id=local_id, cnic=cnic, given=body.given.strip(), family=body.family.strip(),
                birth_date=body.birth_date, sex=body.sex, phone=body.phone, city=body.city,
                registered_by=principal.display_name)
    db.add(p)
    record_audit(db, AuditEvent, principal, "patient.register", "patient", local_id, "success")
    db.commit()
    return _demographics(p)


class ShareIn(BaseModel):
    grantee_institution: str
    local_patient_id: str
    basis: str = Field(min_length=5)
    duration_days: int = DEFAULT_GRANT_DAYS
    referral_ref: str | None = None


@app.post("/sharing/grants", status_code=201, tags=["sharing"])
def share_records(body: ShareIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """Created when this institution's own staff approve a patient-link request:
    the requesting institution may then read this patient's referral-relevant records."""
    require_own(principal, "clinic_staff", "institution_admin", what="share patient records")
    if db.get(Patient, body.local_patient_id) is None:
        raise _not_found("No such patient")
    if body.grantee_institution == INSTITUTION:
        raise HTTPException(422, {"code": "self_grant", "message": "An institution does not need a grant for itself"})
    expires = grant_expiry(body.duration_days)
    existing = [g for g in db.scalars(select(AccessGrant).where(AccessGrant.grantee_institution == body.grantee_institution,
                                                                AccessGrant.local_patient_id == body.local_patient_id,
                                                                AccessGrant.status == "active"))
                if grant_is_live(g)]
    if existing:
        g = existing[0]
        return {"id": g.id, "status": g.status, "categories": g.categories, "expires_at": g.expires_at}
    g = AccessGrant(grantee_institution=body.grantee_institution, local_patient_id=body.local_patient_id,
                    categories=list(ALL_CATEGORIES), basis=body.basis, granted_by=principal.display_name,
                    expires_at=expires, referral_ref=body.referral_ref)
    db.add(g)
    db.flush()
    record_audit(db, AuditEvent, principal, "grant.create", "access_grant", str(g.id), "success",
                 referral_context=body.referral_ref,
                 detail={"grantee": g.grantee_institution, "patient": g.local_patient_id, "basis": body.basis,
                         "expires_at": g.expires_at.isoformat()})
    db.commit()
    return {"id": g.id, "status": g.status, "categories": g.categories, "expires_at": g.expires_at}


# --------------------------------------------------------------------------- referral-relevant records
def _since(raw: str | None) -> date:
    if raw:
        return date.fromisoformat(raw)
    return date.today() - timedelta(days=DEFAULT_WINDOW_DAYS)


def _last_activity(db: Session, local_id: str) -> date | None:
    dates = [
        db.scalar(select(func.max(Visit.visit_date)).where(Visit.patient_id == local_id)),
        db.scalar(select(func.max(LabResult.collected)).where(LabResult.patient_id == local_id)),
        db.scalar(select(func.max(ImagingReport.study_date)).where(ImagingReport.patient_id == local_id)),
    ]
    dates = [d for d in dates if d]
    return max(dates) if dates else None


@app.get("/patients/{local_id}/activity", tags=["records"])
def patient_activity(local_id: str, request: Request, db: Session = Depends(get_db),
                     principal: Principal = Depends(get_principal)):
    """When the patient was last seen here (visit, test or scan). Used to choose the most
    recently visited institution of each kind."""
    patient = db.get(Patient, local_id)
    if patient is None:
        raise _not_found(f"No such patient at {INSTITUTION_NAME}")
    decision = decide_access(db, AccessGrant, principal, INSTITUTION, local_id, {"demographics"})
    if not decision.allowed:
        record_audit(db, AuditEvent, principal, "records.activity", "patient", local_id, "denied",
                     request.headers.get("x-referral-id"), {"reason": decision.reason})
        db.commit()
        raise forbid(f"{INSTITUTION_NAME} denied access: {decision.reason}", code="access_denied")
    last = _last_activity(db, local_id)
    return {"institution_id": INSTITUTION, "local_patient_id": local_id, "last_activity": last.isoformat() if last else None}


@app.get("/fhir/patients/{local_id}/records", tags=["fhir"])
def patient_records(local_id: str, request: Request, categories: str | None = None, since: str | None = None,
                    db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """Referral profile, kept to what a referral needs: conditions, surgeries, current
    medications only, and visits, results and imaging since the window start
    (latest result per test). Returned as a FHIR searchset Bundle."""
    referral_ctx = request.headers.get("x-referral-id")
    requested = set(categories.split(",")) & set(ALL_CATEGORIES) if categories else set(ALL_CATEGORIES)
    patient = db.get(Patient, local_id)
    if patient is None:
        record_audit(db, AuditEvent, principal, "records.read", "patient", local_id, "not_found", referral_ctx)
        db.commit()
        raise _not_found(f"No such patient at {INSTITUTION_NAME}")
    decision = decide_access(db, AccessGrant, principal, INSTITUTION, local_id, requested)
    if not decision.allowed:
        record_audit(db, AuditEvent, principal, "records.read", "patient", local_id, "denied", referral_ctx,
                     {"reason": decision.reason})
        db.commit()
        raise forbid(f"{INSTITUTION_NAME} denied access: {decision.reason}", code="access_denied")
    start = _since(since)
    allowed = decision.allowed
    res: list[dict] = []
    if "demographics" in allowed:
        res.append(adapter.patient(INSTITUTION, patient))
    if "conditions" in allowed:
        res += [adapter.condition(INSTITUTION, c) for c in db.scalars(
            select(Condition).where(Condition.patient_id == local_id, Condition.clinical_status != "entered-in-error"))]
    if "surgeries" in allowed:
        res += [adapter.procedure(INSTITUTION, s) for s in db.scalars(select(Surgery).where(Surgery.patient_id == local_id))]
    if "visits" in allowed:
        res += [adapter.encounter(INSTITUTION, v) for v in db.scalars(
            select(Visit).where(Visit.patient_id == local_id, Visit.visit_date >= start).order_by(Visit.visit_date.desc()))]
    if "medications" in allowed:
        res += [adapter.medication_request(INSTITUTION, m) for m in db.scalars(
            select(Medication).where(Medication.patient_id == local_id, Medication.status == "active"))]
    if "labs" in allowed:
        latest: dict[str, LabResult] = {}
        for r in db.scalars(select(LabResult).where(LabResult.patient_id == local_id, LabResult.collected >= start)
                            .order_by(LabResult.collected.desc(), LabResult.id)):
            latest.setdefault((r.loinc or r.test).lower(), r)
        res += [adapter.observation(INSTITUTION, r) for r in latest.values()]
    if "imaging" in allowed:
        res += [adapter.imaging_report(INSTITUTION, i) for i in db.scalars(
            select(ImagingReport).where(ImagingReport.patient_id == local_id, ImagingReport.study_date >= start))]
    record_audit(db, AuditEvent, principal, "records.read", "patient", local_id,
                 "partial" if decision.denied else "success", referral_ctx,
                 {"categories": sorted(allowed), "withheld": sorted(decision.denied), "count": len(res),
                  "since": start.isoformat()})
    db.commit()
    return records_bundle(res, decision.denied, INSTITUTION, str(request.url))


# --------------------------------------------------------------------------- inbound from central
@app.post("/inbound/referrals", tags=["inbound (central platform)"])
def receive_package(raw: dict, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """Idempotent receipt of a sent referral version (keyed by delivery key)."""
    _require_central(principal)
    delivery_key = raw.get("delivery_key")
    existing = db.scalars(select(IncomingPackage).where(IncomingPackage.delivery_key == delivery_key)).first()
    if existing:
        return {"status": "already_received", "case_id": existing.case_id, "version": existing.version}
    try:
        env, fields = adapter.translate_package(INSTITUTION, raw)
    except adapter.PackageRejected as exc:
        record_audit(db, AuditEvent, principal, "package.receive", "referral", str(raw.get("referral_id")), "rejected",
                     detail={"reason": str(exc)})
        db.commit()
        raise HTTPException(422, {"code": "package_rejected", "message": str(exc)}) from exc
    except Exception as exc:  # noqa: BLE001 - pydantic validation errors
        raise HTTPException(422, {"code": "invalid_envelope", "message": str(exc)[:500]}) from exc
    case = db.scalars(select(Case).where(Case.central_referral_id == env.referral_id)).first()
    if case is None:
        case = Case(latest_version=env.package_version, **fields)
        db.add(case)
        db.flush()
    else:
        case.latest_version = max(case.latest_version, env.package_version)
        case.urgency = fields["urgency"]
        case.local_patient_id = fields["local_patient_id"] or case.local_patient_id
    db.add(IncomingPackage(case_id=case.id, version=env.package_version, delivery_key=env.delivery_key,
                           envelope=env.model_dump(mode="json"), content_hash=env.content_hash))
    record_audit(db, AuditEvent, principal, "package.receive", "referral", env.referral_id, "success",
                 detail={"version": env.package_version, "hash": env.content_hash})
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalars(select(IncomingPackage).where(IncomingPackage.delivery_key == delivery_key)).one()
        return {"status": "already_received", "case_id": existing.case_id, "version": existing.version}
    return {"status": "received", "case_id": case.id, "version": env.package_version}


class ExpiredIn(BaseModel):
    expire_key: str
    referral_id: str
    expired_at: datetime


@app.post("/inbound/referral-expired", tags=["inbound (central platform)"])
def referral_expired(body: ExpiredIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """The referral's time is up: remove this institution's copy of the shared records (the packages and the
    results forwarded with them). Its own decision, questions and response are its record and are kept."""
    _require_central(principal)
    case = db.scalars(select(Case).where(Case.central_referral_id == body.referral_id)).first()
    if case is None:
        return {"status": "no_case"}
    if case.shared_removed_at is None:
        for p in db.scalars(select(IncomingPackage).where(IncomingPackage.case_id == case.id)):
            p.envelope = {"referral_id": case.central_referral_id, "package_version": p.version,
                          "content_hash": p.content_hash, "purged": True,
                          "note": "shared records removed: the referral's time ended"}
        for f in db.scalars(select(ForwardedResult).where(ForwardedResult.case_id == case.id)):
            f.content = {"purged": True}
        case.shared_removed_at = body.expired_at
        record_audit(db, AuditEvent, principal, "case.shared_records_removed", "referral", case.central_referral_id,
                     "success", detail={"expire_key": body.expire_key})
        db.commit()
    return {"status": "removed", "case_id": case.id}


@app.post("/inbound/orders", tags=["inbound (central platform)"])
def receive_order(body: DiagnosticOrder, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    _require_central(principal)
    existing = db.scalars(select(Order).where(Order.order_key == body.order_key)).first()
    if existing:
        return {"status": "already_received", "order_id": existing.id}
    if body.destination_institution != INSTITUTION:
        raise HTTPException(422, {"code": "wrong_destination", "message": "Order is addressed to another institution"})
    o = Order(order_key=body.order_key, order_ref=body.order_ref, central_referral_id=body.referral_id,
              sender_institution=body.sender_institution, sender_name=body.patient.get("sender_name", body.sender_institution),
              department=body.destination_department, category=body.category, test=body.test, body_area=body.body_area,
              clinical_question=body.clinical_question, urgency=body.urgency, patient_name=body.patient.get("name", "Unknown"),
              patient_birth_date=body.patient.get("birth_date"), patient_sex=body.patient.get("sex"),
              patient_cnic=body.patient.get("cnic"), local_patient_id=body.patient.get("local_patient_id"),
              link_request_id=body.patient.get("link_request_id"), requested_by=body.requested_by,
              history=[{"status": "requested", "by": body.requested_by, "at": body.requested_at.isoformat()}])
    db.add(o)
    record_audit(db, AuditEvent, principal, "order.receive", "order", body.order_ref, "success",
                 referral_context=body.referral_id)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        o = db.scalars(select(Order).where(Order.order_key == body.order_key)).one()
        return {"status": "already_received", "order_id": o.id}
    return {"status": "received", "order_id": o.id}


@app.post("/inbound/results", tags=["inbound (central platform)"])
def receive_result(body: ResultForward, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    _require_central(principal)
    if db.scalars(select(ForwardedResult).where(ForwardedResult.forward_key == body.forward_key)).first():
        return {"status": "already_received"}
    case = db.scalars(select(Case).where(Case.central_referral_id == body.referral_id)).first()
    if case is None:
        raise _not_found("No referral case for this result")
    db.add(ForwardedResult(forward_key=body.forward_key, case_id=case.id, content=body.model_dump(mode="json")))
    record_audit(db, AuditEvent, principal, "result.receive", "referral", body.referral_id, "success",
                 detail={"order_ref": body.order_ref})
    db.commit()
    return {"status": "received"}


class SentCopyIn(BaseModel):
    copy_key: str
    referral_id: str
    kind: Literal["package", "response"]
    version: int = 0
    content: dict


@app.post("/outbound-copies", tags=["inbound (central platform)"])
def receive_sent_copy(body: SentCopyIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """Store our own copy of a referral we sent, or of the response to it (idempotent by key)."""
    _require_central(principal)
    existing = db.scalars(select(SentCopy).where(SentCopy.copy_key == body.copy_key)).first()
    if existing:
        return {"status": "already_received", "id": existing.id}
    c = SentCopy(copy_key=body.copy_key, central_referral_id=body.referral_id, kind=body.kind, version=body.version,
                 content=body.content)
    db.add(c)
    record_audit(db, AuditEvent, principal, "sent_copy.store", "referral", body.referral_id, "success",
                 referral_context=body.referral_id, detail={"kind": body.kind, "version": body.version})
    db.commit()
    return {"status": "received", "id": c.id}


@app.get("/outbound-copies", tags=["records"])
def list_sent_copies(referral_id: str, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """Our own copies for one referral (doctors and staff here)."""
    require_own(principal, "clinician", "clinic_staff", what="read our copies of sent referrals")
    rows = db.scalars(select(SentCopy).where(SentCopy.central_referral_id == referral_id).order_by(SentCopy.id)).all()
    record_audit(db, AuditEvent, principal, "sent_copy.read", "referral", referral_id, "success", referral_context=referral_id)
    db.commit()
    return [{"kind": c.kind, "version": c.version, "received_at": c.received_at, "content": c.content} for c in rows]


class IntakeIn(BaseModel):
    referral_id: str
    local_patient_id: str


@app.post("/intake/patient", tags=["intake"])
def intake_patient(body: IntakeIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """Staff here confirmed who an arriving patient is (through the central link request): the
    incoming referral and test orders for that request now point at this record."""
    require_own(principal, *IDENTITY_ROLES, what="confirm an arriving patient")
    if db.get(Patient, body.local_patient_id) is None:
        raise _not_found("No such patient")
    cases = db.scalars(select(Case).where(Case.central_referral_id == body.referral_id)).all()
    orders = db.scalars(select(Order).where(Order.central_referral_id == body.referral_id)).all()
    for item in [*cases, *orders]:
        item.local_patient_id = body.local_patient_id
    record_audit(db, AuditEvent, principal, "intake.patient_confirmed", "patient", body.local_patient_id, "success",
                 referral_context=body.referral_id, detail={"cases": len(cases), "orders": len(orders)})
    db.commit()
    return {"cases": len(cases), "orders": len(orders), "local_patient_id": body.local_patient_id}


@app.post("/inbound/clarification-answers", tags=["inbound (central platform)"])
def receive_answer(body: ClarificationAnswer, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    _require_central(principal)
    ir = db.get(InfoRequest, body.provider_clarification_id)
    if ir is None:
        raise _not_found("Information request not found")
    if ir.answer_key == body.answer_key:
        return {"status": "already_received", "id": ir.id}
    ir.answer, ir.answered_by, ir.answered_at, ir.answer_key = body.answer, body.answered_by, body.answered_at, body.answer_key
    ir.status = "answered"
    record_audit(db, AuditEvent, principal, "info_request.answer_received", "info_request", str(ir.id), "success",
                 referral_context=body.referral_id)
    db.commit()
    return {"status": "received", "id": ir.id}


# --------------------------------------------------------------------------- incoming referrals
# Staff take every incoming referral in: acknowledge receipt, confirm the patient and assign a
# doctor. The doctor sees the referrals assigned to them and accepts, declines or responds.
def _require_doctor(principal: Principal) -> None:
    require_own(principal, "clinician", what="act on incoming referrals")


def _is_intake(principal: Principal) -> bool:
    return principal.institution_id == INSTITUTION and principal.has_any(*INTAKE_ROLES)


def _visible(case: Case, principal: Principal) -> bool:
    if _is_intake(principal):
        return True
    return "clinician" in principal.roles and bool(case.assigned_doctor) and \
        _plain(case.assigned_doctor) == _plain(principal.display_name)


def _get_case(db: Session, case_id: int, principal: Principal) -> Case:
    case = db.get(Case, case_id)
    if case is None or not _visible(case, principal):
        raise _not_found("Referral not found, or not assigned to you")
    return case


def _case_out(c: Case, db: Session) -> dict:
    return {
        "id": c.id, "central_referral_id": c.central_referral_id, "sender_institution": c.sender_institution,
        "sender_name": c.sender_name, "department": c.department, "requested_doctor": c.requested_doctor,
        "patient_name": c.patient_name, "patient_birth_date": c.patient_birth_date, "patient_sex": c.patient_sex,
        "patient_cnic": c.patient_cnic, "local_patient_id": c.local_patient_id, "link_request_id": c.link_request_id,
        "urgency": c.urgency, "status": c.status, "latest_version": c.latest_version,
        "acknowledged_by": c.acknowledged_by, "acknowledged_at": c.acknowledged_at,
        "assigned_doctor": c.assigned_doctor, "assigned_by": c.assigned_by, "assigned_at": c.assigned_at,
        "assign_note": c.assign_note, "decision": c.decision,
        "decision_by": c.decision_by, "decision_at": c.decision_at, "decline_reason": c.decline_reason,
        "completed_by": c.completed_by, "completed_at": c.completed_at, "hold_until": c.hold_until,
        "shared_removed_at": c.shared_removed_at,
        "received_at": c.received_at, "updated_at": c.updated_at,
        "open_info_requests": db.scalar(select(func.count()).select_from(InfoRequest).where(
            InfoRequest.case_id == c.id, InfoRequest.status == "open")) or 0,
    }


@app.get("/cases", tags=["incoming referrals"])
def list_cases(db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    require_own(principal, "clinician", *INTAKE_ROLES, what="see incoming referrals")
    cases = [c for c in db.scalars(select(Case).order_by(Case.updated_at.desc())) if _visible(c, principal)]
    return [_case_out(c, db) for c in cases]


@app.post("/cases/{case_id}/acknowledge", tags=["incoming referrals"])
def acknowledge(case_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """Staff confirm the referral has been received here."""
    require_own(principal, *INTAKE_ROLES, what="acknowledge a referral")
    case = _get_case(db, case_id, principal)
    if case.acknowledged_at is None:
        case.acknowledged_by, case.acknowledged_at = principal.display_name, utcnow()
        if case.status == "received":
            case.status = "acknowledged"
        _emit(db, f"{INSTITUTION}:{case.central_referral_id}:acknowledged", "acknowledged", case.central_referral_id,
              principal, case=case)
        record_audit(db, AuditEvent, principal, "case.acknowledge", "referral", case.central_referral_id, "success")
        db.commit()
    return _case_out(case, db)


class AssignIn(BaseModel):
    doctor: str = Field(min_length=3)
    note: str = ""


@app.post("/cases/{case_id}/assign", tags=["incoming referrals"])
def assign(case_id: int, body: AssignIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """Staff send the referral to the doctor who will see the patient (can be changed until they decide)."""
    require_own(principal, *INTAKE_ROLES, what="assign a referral")
    case = _get_case(db, case_id, principal)
    if case.acknowledged_at is None:
        raise _conflict("not_acknowledged", "Acknowledge the referral first")
    if not case.local_patient_id:
        raise _conflict("patient_not_confirmed", "Confirm the patient (match your record or register them) first")
    if case.decision:
        raise _conflict("already_decided", f"The doctor has already {case.decision} it")
    case.assigned_doctor, case.assigned_by, case.assigned_at = body.doctor.strip(), principal.display_name, utcnow()
    case.assign_note = body.note.strip() or None
    case.status = "assigned"
    record_audit(db, AuditEvent, principal, "case.assign", "referral", case.central_referral_id, "success",
                 detail={"doctor": case.assigned_doctor})
    db.commit()
    return _case_out(case, db)


@app.get("/cases/{case_id}", tags=["incoming referrals"])
def get_case(case_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    require_own(principal, "clinician", *INTAKE_ROLES, what="see incoming referrals")
    case = _get_case(db, case_id, principal)
    packages = db.scalars(select(IncomingPackage).where(IncomingPackage.case_id == case.id)
                          .order_by(IncomingPackage.version.desc())).all()
    infos = db.scalars(select(InfoRequest).where(InfoRequest.case_id == case.id).order_by(InfoRequest.id)).all()
    responses = db.scalars(select(ConsultationResponse).where(ConsultationResponse.case_id == case.id)
                           .order_by(ConsultationResponse.id)).all()
    results = db.scalars(select(ForwardedResult).where(ForwardedResult.case_id == case.id).order_by(ForwardedResult.id)).all()
    record_audit(db, AuditEvent, principal, "case.view", "referral", case.central_referral_id, "success")
    db.commit()
    return {
        "case": _case_out(case, db),
        "packages": [{"version": p.version, "received_at": p.received_at, "content_hash": p.content_hash,
                      "envelope": p.envelope} for p in packages],
        "info_requests": [{"id": i.id, "package_version": i.package_version, "question": i.question, "status": i.status,
                           "created_by": i.created_by, "created_at": i.created_at, "answer": i.answer,
                           "answered_by": i.answered_by, "answered_at": i.answered_at} for i in infos],
        "responses": [{"id": r.id, "package_version": r.package_version, "content": r.content, "status": r.status,
                       "drafted_by": r.drafted_by, "row_version": r.row_version, "returned_by": r.returned_by,
                       "returned_at": r.returned_at} for r in responses],
        "results": [{"id": r.id, "received_at": r.received_at, **r.content} for r in results],
    }


class DecisionIn(BaseModel):
    decision: Literal["accept", "decline"]
    reason: str | None = None


@app.post("/cases/{case_id}/decision", tags=["receiving doctor"])
def decide(case_id: int, body: DecisionIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    _require_doctor(principal)
    case = _get_case(db, case_id, principal)
    if case.acknowledged_at is None or not case.assigned_doctor:
        raise _conflict("not_assigned", "Staff have not assigned this referral yet")
    target = "accepted" if body.decision == "accept" else "declined"
    if case.decision:
        if case.decision == target:
            return _case_out(case, db)
        raise _conflict("already_decided", f"Referral already {case.decision}")
    if body.decision == "decline" and not (body.reason or "").strip():
        raise HTTPException(422, {"code": "reason_required", "message": "Give a reason so the clinic can act on it"})
    case.decision, case.decision_by, case.decision_at = target, principal.display_name, utcnow()
    case.decline_reason = body.reason.strip() if body.decision == "decline" else None
    case.status = target
    if target == "accepted":
        case.hold_until = case.decision_at + timedelta(days=ACCEPTED_HOLD_DAYS)
    _emit(db, f"{INSTITUTION}:{case.central_referral_id}:{target}", target, case.central_referral_id, principal,
          {"reason": case.decline_reason} if case.decline_reason else {}, case=case)
    record_audit(db, AuditEvent, principal, f"case.{target}", "referral", case.central_referral_id, "success")
    db.commit()
    return _case_out(case, db)


class InfoIn(BaseModel):
    question: str = Field(min_length=3)


@app.post("/cases/{case_id}/info-requests", tags=["receiving doctor"])
def request_info(case_id: int, body: InfoIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    _require_doctor(principal)
    case = _get_case(db, case_id, principal)
    if case.acknowledged_at is None:
        raise _conflict("not_acknowledged", "Acknowledge the referral first")
    ir = InfoRequest(case_id=case.id, package_version=case.latest_version, question=body.question.strip(),
                     created_by=principal.display_name)
    db.add(ir)
    db.flush()
    _emit(db, f"{INSTITUTION}:{case.central_referral_id}:info:{ir.id}", "info_requested", case.central_referral_id,
          principal, {"provider_clarification_id": ir.id, "question": ir.question}, case=case)
    record_audit(db, AuditEvent, principal, "info_request.create", "referral", case.central_referral_id, "success")
    db.commit()
    return {"id": ir.id, "status": ir.status}


class ResponseIn(BaseModel):
    assessment: str = ""
    plan: str = ""
    instructions_for_clinic: str = ""
    appointment: str = ""
    expected_row_version: int | None = None


def _current_response(db: Session, case: Case) -> ConsultationResponse | None:
    return db.scalars(select(ConsultationResponse).where(ConsultationResponse.case_id == case.id)
                      .order_by(ConsultationResponse.id.desc())).first()


def _response_out(r: ConsultationResponse) -> dict:
    return {"id": r.id, "package_version": r.package_version, "content": r.content, "status": r.status,
            "drafted_by": r.drafted_by, "row_version": r.row_version, "returned_by": r.returned_by,
            "returned_at": r.returned_at}


@app.put("/cases/{case_id}/response", tags=["receiving doctor"])
def save_response(case_id: int, body: ResponseIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    _require_doctor(principal)
    case = _get_case(db, case_id, principal)
    if case.decision != "accepted":
        raise _conflict("not_accepted", "Accept the referral before writing a response")
    content = body.model_dump(exclude={"expected_row_version"})
    resp = _current_response(db, case)
    if resp and resp.status == "returned":
        raise _conflict("response_locked", "A sent response cannot be edited")
    if resp:
        if body.expected_row_version is not None and body.expected_row_version != resp.row_version:
            raise _conflict("stale_version", "Response changed since you opened it; reload")
        resp.content, resp.row_version = content, resp.row_version + 1
        resp.drafted_by, resp.drafted_at = principal.display_name, utcnow()
    else:
        resp = ConsultationResponse(case_id=case.id, package_version=case.latest_version, content=content,
                                    drafted_by=principal.display_name)
        db.add(resp)
    record_audit(db, AuditEvent, principal, "response.save_draft", "referral", case.central_referral_id, "success")
    db.commit()
    return _response_out(resp)


class SendIn(BaseModel):
    expected_row_version: int


@app.post("/cases/{case_id}/response/send", tags=["receiving doctor"])
def send_response(case_id: int, body: SendIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """The receiving doctor signs off and returns the response in one step."""
    _require_doctor(principal)
    case = _get_case(db, case_id, principal)
    resp = _current_response(db, case)
    if resp is None:
        raise _conflict("no_draft", "Write the response first")
    if resp.status == "returned":
        return _response_out(resp)
    if resp.row_version != body.expected_row_version:
        raise _conflict("stale_version", "Response changed since you opened it; reload")
    if not any(str(v).strip() for v in resp.content.values()):
        raise HTTPException(422, {"code": "empty_response", "message": "The response is empty"})
    now = utcnow()
    resp.status, resp.returned_by, resp.returned_by_id, resp.returned_at = "returned", principal.display_name, principal.subject, now
    resp.return_key = f"{INSTITUTION}:{case.central_referral_id}:response:{resp.id}"
    case.status = "responded"
    _emit(db, resp.return_key, "response_returned", case.central_referral_id, principal, {
        "response_id": resp.id, "content": resp.content, "returned_by": resp.returned_by, "returned_at": now.isoformat(),
        "package_version": resp.package_version,
        "fhir_task": adapter.response_task(INSTITUTION_NAME, case.central_referral_id, resp.id, resp.content,
                                           resp.returned_by, now.isoformat()),
    }, case=case)
    record_audit(db, AuditEvent, principal, "response.return", "referral", case.central_referral_id, "success")
    db.commit()
    return _response_out(resp)


class ExtendHoldIn(BaseModel):
    reason: str = Field(min_length=3)


@app.post("/cases/{case_id}/complete", tags=["receiving doctor"])
def complete_case(case_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """The referred doctor has finished with the referral. The shared records are removed 72 hours later."""
    _require_doctor(principal)
    case = _get_case(db, case_id, principal)
    if case.completed_at:
        return _case_out(case, db)
    if case.decision != "accepted":
        raise _conflict("not_accepted", "Only an accepted referral can be marked complete")
    resp = _current_response(db, case)
    if resp is None or resp.status != "returned":
        raise _conflict("no_response", "Send your response to the referring clinic first")
    now = utcnow()
    case.completed_by, case.completed_at, case.status = principal.display_name, now, "completed"
    case.hold_until = now + timedelta(hours=GRACE_HOURS)
    _emit(db, f"{INSTITUTION}:{case.central_referral_id}:completed", "completed", case.central_referral_id, principal,
          {"records_removed_at": case.hold_until.isoformat()}, case=case)
    record_audit(db, AuditEvent, principal, "case.complete", "referral", case.central_referral_id, "success",
                 detail={"records_removed_at": case.hold_until.isoformat()})
    db.commit()
    return _case_out(case, db)


@app.post("/cases/{case_id}/extend-hold", tags=["receiving doctor"])
def extend_hold(case_id: int, body: ExtendHoldIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """The referred doctor needs the shared records for longer: kept for another 30 days from now."""
    _require_doctor(principal)
    case = _get_case(db, case_id, principal)
    if case.decision != "accepted" or case.completed_at or case.shared_removed_at:
        raise _conflict("not_extendable", "Only an accepted referral that is not complete can be extended")
    now = utcnow()
    case.hold_until = max(case.hold_until or now, now + timedelta(days=ACCEPTED_HOLD_DAYS))
    _emit(db, f"{INSTITUTION}:{case.central_referral_id}:extend:{int(now.timestamp())}", "hold_extended",
          case.central_referral_id, principal, {"until": case.hold_until.isoformat(), "reason": body.reason.strip()}, case=case)
    record_audit(db, AuditEvent, principal, "case.extend_hold", "referral", case.central_referral_id, "success",
                 detail={"until": case.hold_until.isoformat(), "reason": body.reason.strip()})
    db.commit()
    return _case_out(case, db)


# --------------------------------------------------------------------------- laboratory / imaging department
def _require_diagnostics(principal: Principal) -> None:
    require_own(principal, "diagnostics_staff", what="act on test and scan orders")


def _get_order(db: Session, order_id: int, principal: Principal) -> Order:
    o = db.get(Order, order_id)
    if o is None or o.department != principal.department:
        raise _not_found("Order not found in your department")
    return o


def _order_out(o: Order, db: Session | None = None) -> dict:
    files = [] if db is None else [
        {"id": a.id, "filename": a.filename, "content_type": a.content_type, "size": len(a.data)}
        for a in db.scalars(select(OrderAttachment).where(OrderAttachment.order_id == o.id).order_by(OrderAttachment.id))]
    return {
        "id": o.id, "order_ref": o.order_ref, "central_referral_id": o.central_referral_id,
        "sender_institution": o.sender_institution, "sender_name": o.sender_name, "department": o.department,
        "category": o.category, "test": o.test, "body_area": o.body_area, "clinical_question": o.clinical_question,
        "urgency": o.urgency, "patient_name": o.patient_name, "patient_birth_date": o.patient_birth_date,
        "patient_sex": o.patient_sex, "patient_cnic": o.patient_cnic, "local_patient_id": o.local_patient_id,
        "link_request_id": o.link_request_id, "requested_by": o.requested_by, "status": o.status,
        "reject_reason": o.reject_reason, "scheduled_for": o.scheduled_for, "report_text": o.report_text,
        "findings": o.findings, "impression": o.impression,
        "values": o.values, "reported_by": o.reported_by, "reported_at": o.reported_at, "history": o.history,
        "attachments": files, "received_at": o.received_at, "updated_at": o.updated_at,
    }


def _order_step(db: Session, o: Order, principal: Principal, status: str, event: str, data: dict) -> dict:
    o.status = status
    o.history = list(o.history or []) + [{"status": status, "by": principal.display_name, "at": utcnow().isoformat(),
                                         **{k: v for k, v in data.items() if k in ("reason", "scheduled_for")}}]
    _emit(db, f"{INSTITUTION}:{o.order_ref}:{event}", event, o.central_referral_id, principal, data, order=o)
    record_audit(db, AuditEvent, principal, f"order.{status}", "order", o.order_ref, "success",
                 referral_context=o.central_referral_id)
    db.commit()
    return _order_out(o, db)


@app.get("/orders", tags=["laboratory and imaging"])
def list_orders(db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    _require_diagnostics(principal)
    rows = db.scalars(select(Order).where(Order.department == principal.department).order_by(Order.updated_at.desc()))
    return [_order_out(o) for o in rows]


@app.get("/orders/{order_id}", tags=["laboratory and imaging"])
def get_order(order_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    _require_diagnostics(principal)
    return _order_out(_get_order(db, order_id, principal), db)


@app.get("/orders/{order_id}/attachments/{attachment_id}", tags=["laboratory and imaging"])
def order_attachment(order_id: int, attachment_id: int, db: Session = Depends(get_db),
                     principal: Principal = Depends(get_principal)):
    _require_diagnostics(principal)
    o = _get_order(db, order_id, principal)
    a = db.get(OrderAttachment, attachment_id)
    if a is None or a.order_id != o.id:
        raise _not_found("Attachment not found")
    return Response(a.data, media_type=a.content_type, headers={"Content-Disposition": f'inline; filename="{a.filename}"'})


@app.post("/orders/{order_id}/accept", tags=["laboratory and imaging"])
def accept_order(order_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    _require_diagnostics(principal)
    o = _get_order(db, order_id, principal)
    if o.status != "requested":
        raise _conflict("invalid_step", f"Order is already {o.status}")
    if not o.local_patient_id or db.get(Patient, o.local_patient_id) is None:
        raise _conflict("patient_not_linked", "Confirm the patient first: match your record or register them as new")
    return _order_step(db, o, principal, "accepted", "order_accepted", {})


class RejectIn(BaseModel):
    reason: str = Field(min_length=3)


@app.post("/orders/{order_id}/reject", tags=["laboratory and imaging"])
def reject_order(order_id: int, body: RejectIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """A rejection always carries a reason (wrong test, preparation needed, no capacity)."""
    _require_diagnostics(principal)
    o = _get_order(db, order_id, principal)
    if o.status not in ("requested", "accepted", "scheduled"):
        raise _conflict("invalid_step", f"Order is already {o.status}")
    o.reject_reason = body.reason.strip()
    return _order_step(db, o, principal, "rejected", "order_rejected", {"reason": o.reject_reason})


class ScheduleIn(BaseModel):
    scheduled_for: datetime


@app.post("/orders/{order_id}/schedule", tags=["laboratory and imaging"])
def schedule_order(order_id: int, body: ScheduleIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    _require_diagnostics(principal)
    o = _get_order(db, order_id, principal)
    if o.status not in ("accepted", "scheduled"):
        raise _conflict("invalid_step", "Accept the order before scheduling it")
    o.scheduled_for = body.scheduled_for
    return _order_step(db, o, principal, "scheduled", "order_scheduled", {"scheduled_for": body.scheduled_for.isoformat()})


@app.post("/orders/{order_id}/done", tags=["laboratory and imaging"])
def order_done(order_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    _require_diagnostics(principal)
    o = _get_order(db, order_id, principal)
    if o.status not in ("accepted", "scheduled"):
        raise _conflict("invalid_step", "Only an accepted or scheduled order can be marked done")
    return _order_step(db, o, principal, "done", "order_done", {})


class ValueIn(BaseModel):
    test: str
    value: str
    unit: str | None = None
    reference: str | None = None
    flag: str | None = None


class AttachmentIn(BaseModel):
    filename: str = Field(min_length=1, max_length=200)
    content_type: str
    data: str  # base64


class ReportIn(BaseModel):
    findings: str = ""
    impression: str = ""
    values: list[ValueIn] = Field(default_factory=list)
    attachments: list[AttachmentIn] = Field(default_factory=list, max_length=6)


def _unprocessable(code: str, message: str) -> HTTPException:
    return HTTPException(422, {"code": code, "message": message})


def _check_report(o: Order, body: ReportIn) -> list[tuple[AttachmentIn, bytes]]:
    """A report must say what was found: every laboratory result with its value; a scan or
    cardiac test with findings, an impression and the images (or trace) themselves."""
    if o.category == "laboratory":
        if not body.values or any(not v.test.strip() or not v.value.strip() for v in body.values):
            raise _unprocessable("values_required", "Enter every result with its test name and value")
    else:
        if len(body.findings.strip()) < 10 or len(body.impression.strip()) < 5:
            raise _unprocessable("findings_required", "Write the findings and the impression")
        if not body.attachments:
            what = "scan images" if o.category == "imaging" else "ECG trace or echo images"
            raise _unprocessable("images_required", f"Attach the {what} (PNG, JPEG or PDF)")
    files = []
    for a in body.attachments:
        if a.content_type not in ATTACHMENT_TYPES:
            raise _unprocessable("file_type", f"{a.filename}: only PNG, JPEG or PDF files")
        try:
            raw = base64.b64decode(a.data, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise _unprocessable("file_unreadable", f"{a.filename} could not be read") from exc
        if not raw or len(raw) > MAX_ATTACHMENT_BYTES:
            raise _unprocessable("file_size", f"{a.filename}: each file must be under 5 MB")
        files.append((a, raw))
    return files


@app.post("/orders/{order_id}/report", tags=["laboratory and imaging"])
def report_order(order_id: int, body: ReportIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """Return the report (with images for scans). It is also filed in this institution's own records."""
    _require_diagnostics(principal)
    o = _get_order(db, order_id, principal)
    if o.status not in ("accepted", "scheduled", "done"):
        raise _conflict("invalid_step", "Accept the order before reporting it")
    files = _check_report(o, body)
    now = utcnow()
    values: list[dict[str, Any]] = [v.model_dump() for v in body.values]
    o.findings, o.impression = body.findings.strip() or None, body.impression.strip() or None
    o.report_text = "\n".join(x for x in [body.findings.strip() and f"Findings: {body.findings.strip()}",
                                          body.impression.strip() and f"Impression: {body.impression.strip()}"] if x)
    o.values, o.reported_by, o.reported_at = values, principal.display_name, now
    for a, raw in files:
        db.add(OrderAttachment(order_id=o.id, filename=a.filename, content_type=a.content_type, data=raw,
                               uploaded_by=principal.display_name))
    n = db.scalar(select(func.count()).select_from(LabResult)) or 0
    if o.category == "laboratory":
        for i, v in enumerate(values):
            try:
                num, txt = float(v["value"]), None
            except (TypeError, ValueError):
                num, txt = None, v["value"]
            db.add(LabResult(id=f"OBS-{o.local_patient_id}-o{o.id}-{n + i + 1}", patient_id=o.local_patient_id,
                             panel=o.test, collected=now.date(), test=v["test"], value_num=num, value_text=txt,
                             unit=v.get("unit"), reference_range=v.get("reference"), abnormal_flag=v.get("flag")))
    else:
        db.add(ImagingReport(id=f"IMG-{o.local_patient_id}-o{o.id}", patient_id=o.local_patient_id, study_date=now.date(),
                             study=o.test, body_part=o.body_area, findings=body.findings.strip(),
                             impression=body.impression.strip(), reporter=principal.display_name))
    return _order_step(db, o, principal, "reported", "order_reported", {
        "test": o.test, "report_text": o.report_text, "findings": body.findings.strip(),
        "impression": body.impression.strip(), "values": values, "reported_by": principal.display_name,
        "reported_at": now.isoformat(), "local_patient_id": o.local_patient_id,
        "attachments": [{"filename": a.filename, "content_type": a.content_type, "data": a.data} for a, _ in files]})


@app.post("/outbox/{item_id}/retry", tags=["receiving doctor"])
def retry_outbox(item_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    require_own(principal, "clinician", "diagnostics_staff", "institution_admin", what="retry delivery")
    item = db.get(Outbox, item_id)
    if item is None:
        raise _not_found("Outbox item not found")
    if item.status == "failed":
        item.status, item.attempts, item.next_attempt_at = "pending", 0, utcnow()
        db.commit()
    return {"id": item.id, "status": item.status}
