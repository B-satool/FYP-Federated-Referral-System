"""Brief drafting and editing. Every save is a new immutable brief version."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from refcommon.auth import Principal
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import Brief, EvidenceItem, Job
from ..referrals.state import ensure_clinical_edit_allowed, mark_clinical_change
from ..security import audit, check_version, error, get_principal, load_referral
from ..serializers import brief_out, job_out
from ..tasks import enqueue
from . import brief as brief_mod

router = APIRouter(tags=["referral brief"])


@router.get("/referrals/{referral_id}/brief")
def get_brief(referral_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    r = load_referral(db, referral_id, principal, "view")
    versions = db.scalars(select(Brief).where(Brief.referral_id == r.id).order_by(Brief.version.desc())).all()
    return {"latest": brief_out(versions[0]) if versions else None,
            "versions": [{"version": b.version, "kind": b.kind, "model": b.model, "created_by": b.created_by,
                          "created_at": b.created_at} for b in versions],
            "llm_configured": settings.llm_configured, "llm_model": settings.llm_model if settings.llm_configured else None,
            "section_titles": brief_mod.SECTION_TITLES}


@router.get("/referrals/{referral_id}/brief/versions/{version}")
def get_brief_version(referral_id: int, version: int, db: Session = Depends(get_db),
                      principal: Principal = Depends(get_principal)):
    r = load_referral(db, referral_id, principal, "view")
    b = db.scalars(select(Brief).where(Brief.referral_id == r.id, Brief.version == version)).first()
    if b is None:
        raise error(404, "not_found", "Brief version not found")
    return brief_out(b)


@router.post("/referrals/{referral_id}/brief/generate", status_code=202)
def generate(referral_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    r = load_referral(db, referral_id, principal, "generate_brief")
    ensure_clinical_edit_allowed(r)
    if not brief_mod.permitted_evidence(db, r):
        raise error(409, "no_evidence", "Select at least one evidence item before generating a brief")
    job = Job(id=uuid.uuid4().hex, kind="generate_brief", referral_id=r.id, created_by=principal.display_name,
              created_by_id=principal.subject, institution_id=principal.institution_id)
    db.add(job)
    audit(db, principal, "brief.generate_requested", "referral", r.reference, "success", r.id)
    db.commit()
    enqueue("generate_brief", job.id)
    return job_out(job)


@router.post("/referrals/{referral_id}/brief/template", status_code=201)
def from_template(referral_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """Non-AI evidence template so preparation never depends on the model (FR-58)."""
    r = load_referral(db, referral_id, principal, "edit_brief")
    ensure_clinical_edit_allowed(r)
    out = brief_mod.template(db, r, principal.display_name)
    prev = brief_mod.latest_brief(db, r.id)
    b = Brief(referral_id=r.id, version=brief_mod.next_version(db, r.id), kind="template", sections=out["sections"],
              limitations=out["limitations"], evidence_ids=out["evidence_ids"], prompt_version=None,
              based_on_version=prev.version if prev else None, created_by=principal.display_name)
    db.add(b)
    if r.current_package_version:
        mark_clinical_change(db, r, principal.display_name, "brief replaced from template", principal)
    audit(db, principal, "brief.template", "brief", f"{r.reference}:v{b.version}", "success", r.id)
    db.commit()
    return brief_out(b)


class StatementIn(BaseModel):
    id: str | None = None
    text: str
    evidence_ids: list[int] = []


class SectionIn(BaseModel):
    key: str
    statements: list[StatementIn]


class BriefSaveIn(BaseModel):
    based_on_version: int | None
    expected_version: int
    sections: list[SectionIn]
    limitations: list[str] = []


@router.put("/referrals/{referral_id}/brief")
def save_brief(referral_id: int, body: BriefSaveIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """Clinician/staff edit. Changed or new statements record their author (FR-44)."""
    r = load_referral(db, referral_id, principal, "edit_brief")
    check_version(r, body.expected_version)
    ensure_clinical_edit_allowed(r)
    prev = brief_mod.latest_brief(db, r.id)
    if (prev.version if prev else None) != body.based_on_version:
        raise error(409, "stale_brief", "The brief changed since you opened it; reload before saving",
                    current_version=prev.version if prev else None)
    prev_statements = {}
    if prev:
        for sec in prev.sections:
            for st in sec["statements"]:
                prev_statements[st["id"]] = st
    allowed_ids = set(db.scalars(select(EvidenceItem.id).where(EvidenceItem.referral_id == r.id)))
    by_id = {e.id: e for e in db.scalars(select(EvidenceItem).where(EvidenceItem.referral_id == r.id))}
    sections = []
    for sec in body.sections:
        if sec.key not in brief_mod.SECTION_TITLES:
            raise error(422, "invalid_section", f"Unknown section {sec.key}")
        statements = []
        for st in sec.statements:
            text = st.text.strip()
            if not text:
                continue
            bad = set(st.evidence_ids) - allowed_ids
            if bad:
                raise error(422, "invalid_reference", f"Evidence {sorted(bad)} does not belong to this referral")
            old = prev_statements.get(st.id or "")
            if old and old["text"] == text and old.get("evidence_ids", []) == st.evidence_ids:
                statements.append(old)
                continue
            usable = [i for i in st.evidence_ids if i in by_id]
            verification = brief_mod._statement_verification(usable, by_id) if usable else "none"
            if old:
                statements.append({**old, "text": text, "evidence_ids": st.evidence_ids,
                                   "edited_by": principal.display_name, "verification": verification})
            else:
                statements.append({"id": uuid.uuid4().hex[:10], "text": text, "evidence_ids": st.evidence_ids,
                                   "author_kind": "clinician", "author_name": principal.display_name, "edited_by": None,
                                   "verification": verification})
        sections.append({"key": sec.key, "title": brief_mod.SECTION_TITLES[sec.key], "statements": statements})
    b = Brief(referral_id=r.id, version=brief_mod.next_version(db, r.id), kind="edited", sections=sections,
              limitations=[x.strip() for x in body.limitations if x.strip()],
              evidence_ids=sorted({i for s in sections for st in s["statements"] for i in st["evidence_ids"]}),
              model=prev.model if prev else None, prompt_version=prev.prompt_version if prev else None,
              based_on_version=prev.version if prev else None, created_by=principal.display_name)
    db.add(b)
    if r.current_package_version:
        mark_clinical_change(db, r, principal.display_name, "brief edited", principal)
    else:
        from ..security import bump
        bump(r)
    audit(db, principal, "brief.edit", "brief", f"{r.reference}:v{b.version}", "success", r.id)
    db.commit()
    return {"brief": brief_out(b), "referral_version": r.row_version}
