"""Central referral platform (modular monolith).

Feature modules: referrals (the doctor's request), identity (patient links confirmed
by the other institution), integration (retrieval from the most recently visited
institutions), documents and records, medicines (rules edited in the app), sending,
tests and scans, response and follow-through, notifications and the work queue.
It calls the institution services' APIs and never their databases.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text

from . import audit_router, evidence_router, notifications, workqueue
from .db import engine
from .delivery import inbound
from .diagnostics import router as diagnostics
from .documents import router as documents
from .followup import router as followup
from .identity import router as identity
from .medications import router as medications
from .referrals import router as referrals
from .sending import router as sending

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(
    title="Referral Preparation and Follow-through Platform - central API",
    version="2.0.0",
    description=("Central workflow API. Patient records are retrieved through each institution's own API, which "
                 "makes its own access decisions. FHIR content follows the pinned R4 4.0.1 project subset; "
                 "envelopes marked 'Project API contract' are not standard FHIR resources."),
)

for module in (referrals, identity, evidence_router, documents, medications, sending, diagnostics, followup, inbound,
               notifications, workqueue, audit_router):
    app.include_router(module.router)


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}


@app.get("/ready", tags=["health"])
def ready():
    try:
        with engine.connect() as conn:
            conn.execute(text("select 1"))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(503, {"code": "not_ready", "message": str(exc)}) from exc
    return {"status": "ready"}


@app.exception_handler(RequestValidationError)
async def validation_handler(_request: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    field = ".".join(str(x) for x in first.get("loc", [])[1:]) or "request"
    return JSONResponse(status_code=422, content={"detail": {
        "code": "validation_error", "message": f"{field}: {first.get('msg', 'invalid value')}"}},
    )
