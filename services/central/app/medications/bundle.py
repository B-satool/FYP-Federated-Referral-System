"""The medication data bundle for the browser's Layer 1 check (spec v4 9.1, 9.3; approval A10).

Doctors' browsers download this once per version and check it themselves, so no medicine name leaves the device for
Layer 1. It is reference data, not patient data: the medicine names (hand-checked names and the DRAP register,
strict-start matching), the components of combination products, and the DDInter interaction pairs with their
severity, identifier and any drug-label quote. The bundle is versioned and its SHA-256 over canonical JSON is
published with it; the browser recomputes it before use.

There is no drug-procedure table here or anywhere else (T-FLAG-2): drug-procedure risks come only from the AI layer,
labelled "AI suggestion, not verified".
"""
from __future__ import annotations

import hashlib

from fastapi import APIRouter, Depends, Response
from refcommon import e2e
from refcommon.auth import Principal
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import DrugInteraction, Ingredient, MedicineName
from ..security import get_principal

router = APIRouter(tags=["medication data bundle"])
BUNDLE_TYPE = "refx.med-bundle/v1"
DDINTER = {"name": "DDInter 2.0", "url": "https://ddinter.scbdd.com", "licence": "CC BY-NC-SA 4.0 (re-check at download)"}
_cache: dict[tuple, dict] = {}


def _stamp(db: Session) -> tuple:
    return (db.scalar(select(func.count()).select_from(MedicineName)), db.scalar(select(func.max(MedicineName.id))),
            db.scalar(select(func.count()).select_from(DrugInteraction)), db.scalar(select(func.max(DrugInteraction.id))))


def build(db: Session) -> dict:
    names, options = [], {}
    for n in db.scalars(select(MedicineName).where(MedicineName.status == "active").order_by(MedicineName.name)):
        names.append([n.name, n.display, n.ingredient, n.drug_class, n.kind])
        if n.options:
            options[n.name] = [{k: o.get(k) for k in ("ingredient", "company", "drap_reg_no", "strength", "dosage_form")}
                               for o in n.options]
    components, in_source = {}, []
    for i in db.scalars(select(Ingredient).order_by(Ingredient.name)):
        if i.components:
            components[i.name] = list(i.components)
        if i.in_interaction_source:
            in_source.append(i.name)
    pairs, version = [], None
    for d in db.scalars(select(DrugInteraction).order_by(DrugInteraction.ingredient_a, DrugInteraction.ingredient_b)):
        pairs.append([d.ingredient_a, d.ingredient_b, d.severity, d.source_ref, d.label_quote, d.label_source])
        version = version or d.source_version
    content = {"type": BUNDLE_TYPE, "names": names, "options": options, "components": components,
               "in_source": in_source, "interactions": pairs, "interaction_source": {**DDINTER, "version": version}}
    digest = hashlib.sha256(e2e.canonical(content)).hexdigest()
    return {"version": digest[:12], "sha256": digest, "content": content}


@router.get("/med-bundle")
def med_bundle(response: Response, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """The current bundle; clients keep it until the version changes."""
    stamp = _stamp(db)
    if stamp not in _cache:
        _cache.clear()
        _cache[stamp] = build(db)
    out = _cache[stamp]
    response.headers["ETag"] = f'"{out["sha256"]}"'
    response.headers["Cache-Control"] = "private, max-age=300"
    return out
