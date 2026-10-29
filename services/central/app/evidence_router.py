"""Records and paper fields: selection, correction, exclusion, manual entry and checking.

Only the doctor sees record content and changes it (decision 2026-10-29). Staff see each record's title,
source, date and whether it is in the packet.
Every change is an append-only EvidenceRevision; raw extraction is never overwritten."""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from refcommon.auth import Principal
from refcommon.db import utcnow
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .integration.importer import _parse_time
from .models import Document, EvidenceItem, EvidenceRevision
from .referrals.state import ensure_clinical_edit_allowed, mark_clinical_change
from .security import audit, error, get_principal, load_referral, sees_clinical
from .selection.selection import floor, staff_select
from .serializers import evidence_out
from .workflow import after_change

router = APIRouter(tags=["evidence"])

EDITABLE_FIELDS = {
    "medication": {"medication", "strength", "dosage_text", "route", "frequency", "start", "end"},
    "lab": {"test", "value", "unit", "value_text", "collected", "reference_range", "specimen"},
    "condition": {"condition", "onset", "clinical_status"},
    "note": {"text"},
}


def _load(db: Session, evidence_id: int, principal: Principal, action: str,
          roles: tuple[str, ...] = ("clinician",)) -> EvidenceItem:
    ev = db.get(EvidenceItem, evidence_id)
    if ev is None:
        raise error(404, "not_found", "Evidence not found")
    load_referral(db, ev.referral_id, principal, action, roles=roles)
    return ev


def _revise(db: Session, ev: EvidenceItem, principal: Principal, action: str, note: str = "",
            prior: dict | None = None, new: dict | None = None, prior_state: str | None = None) -> None:
    db.add(EvidenceRevision(evidence_id=ev.id, action=action, prior_value=prior, new_value=new,
                            prior_state=prior_state, new_state=ev.review_state, editor=principal.display_name,
                            editor_id=principal.subject, note=note))
    ev.row_version += 1
    audit(db, principal, f"evidence.{action}", "evidence", ev.id, "success", ev.referral_id, {"note": note})


def _finish(db: Session, ev: EvidenceItem, principal: Principal, what: str) -> dict:
    from .models import Referral

    referral = db.get(Referral, ev.referral_id)
    if referral.current_package_version:
        mark_clinical_change(db, referral, principal.display_name, what, principal)
    after_change(db, referral, f"evidence_{what}", principal)
    db.commit()
    return evidence_out(ev)


@router.get("/referrals/{referral_id}/evidence")
def list_evidence(referral_id: int, category: str | None = None, include_superseded: bool = False,
                  db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    r = load_referral(db, referral_id, principal, "view")
    stmt = select(EvidenceItem).where(EvidenceItem.referral_id == r.id)
    if category:
        stmt = stmt.where(EvidenceItem.category.in_(category.split(",")))
    if not include_superseded:
        stmt = stmt.where(EvidenceItem.superseded_by.is_(None))
    clinical = sees_clinical(principal)
    return [evidence_out(e, clinical) for e in db.scalars(stmt.order_by(EvidenceItem.category, EvidenceItem.clinical_time.desc().nulls_last(), EvidenceItem.id))]


@router.get("/evidence/{evidence_id}")
def get_evidence(evidence_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    ev = _load(db, evidence_id, principal, "view", roles=("clinic_staff", "clinician"))
    if not sees_clinical(principal):
        return {**evidence_out(ev, False), "fhir": None, "revisions": [], "versions": [], "document": None}
    revisions = db.scalars(select(EvidenceRevision).where(EvidenceRevision.evidence_id == ev.id).order_by(EvidenceRevision.id))
    history = []
    if ev.source_record_id:
        history = [{"id": h.id, "version": h.source_record_version, "superseded_by": h.superseded_by,
                    "display": h.display, "retrieved_at": h.retrieved_at}
                   for h in db.scalars(select(EvidenceItem).where(
                       EvidenceItem.referral_id == ev.referral_id, EvidenceItem.source_institution == ev.source_institution,
                       EvidenceItem.source_record_id == ev.source_record_id).order_by(EvidenceItem.id))]
    doc = db.get(Document, ev.document_id) if ev.document_id else None
    return {**evidence_out(ev),
            "fhir": None if ev.verification_status == "access_revoked" else ev.fhir,
            "revisions": [{"id": x.id, "action": x.action, "prior_value": x.prior_value, "new_value": x.new_value,
                           "prior_state": x.prior_state, "new_state": x.new_state, "editor": x.editor, "note": x.note,
                           "created_at": x.created_at} for x in revisions],
            "versions": history,
            "document": {"id": doc.id, "filename": doc.original_filename, "doc_type": doc.doc_type} if doc else None}


class SelectIn(BaseModel):
    selected: bool


@router.post("/evidence/{evidence_id}/select")
def select_evidence(evidence_id: int, body: SelectIn, db: Session = Depends(get_db),
                    principal: Principal = Depends(get_principal)):
    """The doctor finalises the packet: their choice overrides the default and the AI recommendation."""
    ev = _load(db, evidence_id, principal, "edit")
    from .models import Referral
    ensure_clinical_edit_allowed(db.get(Referral, ev.referral_id))
    if body.selected and ev.verification_status in ("invalidated", "access_revoked"):
        raise error(409, "evidence_unusable", "This evidence can no longer be used (link invalidated or access revoked)")
    if body.selected and ev.review_state == "excluded":
        raise error(409, "evidence_excluded", "Restore the excluded field before selecting it")
    if ev.selected == body.selected and ev.selection_source == "staff":
        return evidence_out(ev)
    staff_select(ev, body.selected, principal.display_name)
    _revise(db, ev, principal, "select" if body.selected else "deselect", prior_state=ev.review_state,
            new={"selected": body.selected, "ai_recommendation": ev.ai_recommendation, "default": floor(ev)})
    return _finish(db, ev, principal, "selection")


class CorrectIn(BaseModel):
    fields: dict[str, Any]
    note: str = ""
    expected_row_version: int


@router.post("/evidence/{evidence_id}/correct")
def correct(evidence_id: int, body: CorrectIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    ev = _load(db, evidence_id, principal, "edit")
    if ev.row_version != body.expected_row_version:
        raise error(409, "stale_version", "This field changed since you opened it; reload")
    if ev.origin == "source":
        raise error(409, "source_record_readonly",
                    "Source records cannot be edited centrally; request a correction from the source institution")
    allowed = EDITABLE_FIELDS.get(ev.category, set())
    bad = set(body.fields) - allowed
    if bad:
        raise error(422, "invalid_fields", f"Fields not editable for {ev.category}: {sorted(bad)}")
    prior = dict(ev.current)
    new = {**ev.current, **body.fields}
    ev.current = new
    prior_state = ev.review_state
    ev.review_state = "corrected" if ev.origin == "document" else ev.review_state
    if ev.verification_status == "verified":
        ev.verification_status = "unverified"  # a corrected value needs fresh clinical verification
        ev.verified_by = ev.verified_at = None
    ev.display = _display(ev)
    if ev.category in ("medication", "lab"):
        when = new.get("start") or new.get("collected")
        ev.clinical_time = _parse_time(when) if isinstance(when, str) else ev.clinical_time
    _revise(db, ev, principal, "correct", body.note, prior, new, prior_state)
    return _finish(db, ev, principal, "correction")


class StateIn(BaseModel):
    note: str = ""


def _set_state(db, evidence_id, principal, state: str, note: str) -> dict:
    ev = _load(db, evidence_id, principal, "edit")
    if ev.origin == "source" and state in ("unresolved",):
        raise error(409, "source_record_readonly", "Mark source records for clarification through a review item instead")
    prior_state = ev.review_state
    if state == "restore":
        ev.review_state = "proposed" if ev.origin == "document" else ("manual" if ev.origin == "manual" else "imported")
    else:
        ev.review_state = state
    if state == "excluded":
        ev.selected = False
    _revise(db, ev, principal, state if state != "restore" else "restore", note, prior_state=prior_state)
    return _finish(db, ev, principal, state)


@router.post("/evidence/{evidence_id}/unresolve")
def mark_unresolved(evidence_id: int, body: StateIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    return _set_state(db, evidence_id, principal, "unresolved", body.note)


@router.post("/evidence/{evidence_id}/exclude")
def exclude(evidence_id: int, body: StateIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    return _set_state(db, evidence_id, principal, "excluded", body.note)


@router.post("/evidence/{evidence_id}/restore")
def restore(evidence_id: int, body: StateIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    return _set_state(db, evidence_id, principal, "restore", body.note)


class VerifyIn(BaseModel):
    note: str = ""
    expected_row_version: int


@router.post("/evidence/{evidence_id}/verify")
def verify(evidence_id: int, body: VerifyIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """The doctor checks a field read from a paper against the page image; a checked medicine joins the
    current-medicine list."""
    ev = _load(db, evidence_id, principal, "verify")
    if ev.row_version != body.expected_row_version:
        raise error(409, "stale_version", "This field changed since you opened it; reload")
    if ev.origin == "source":
        raise error(409, "not_applicable", "Source records are already documented at an authorized source")
    if ev.review_state in ("excluded",):
        raise error(409, "evidence_excluded", "Excluded fields cannot be verified")
    if ev.review_state == "unresolved":
        raise error(409, "evidence_unresolved", "Correct or restore the field before verifying it")
    ev.verification_status = "verified"
    ev.verified_by, ev.verified_at = principal.display_name, utcnow()
    _revise(db, ev, principal, "verify", body.note, prior_state=ev.review_state)
    return _finish(db, ev, principal, "verification")


class ManualIn(BaseModel):
    category: Literal["medication", "lab", "condition", "note"]
    fields: dict[str, Any]
    document_id: int | None = None
    page: int | None = None
    note: str = ""


@router.post("/referrals/{referral_id}/evidence/manual", status_code=201)
def manual_entry(referral_id: int, body: ManualIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """Manual transcription by the doctor, with an optional source reference; works without OCR (FR-58)."""
    r = load_referral(db, referral_id, principal, "edit", roles=("clinician",))
    ensure_clinical_edit_allowed(r)
    bad = set(body.fields) - EDITABLE_FIELDS[body.category]
    if bad:
        raise error(422, "invalid_fields", f"Fields not supported for {body.category}: {sorted(bad)}")
    if body.document_id:
        doc = db.get(Document, body.document_id)
        if doc is None or doc.referral_id != r.id:
            raise error(422, "invalid_document", "Document is not attached to this referral")
    fields = dict(body.fields)
    if body.category == "medication":
        fields.setdefault("record_kind", "document" if body.document_id else "manual")
    when = fields.get("start") or fields.get("collected") or fields.get("onset")
    ev = EvidenceItem(
        referral_id=r.id, patient_institution=r.patient_institution, patient_local_id=r.patient_local_id,
        origin="manual", source_institution=r.source_institution, category=body.category, display="",
        original=fields, current=dict(fields), clinical_time=_parse_time(when) if isinstance(when, str) else None,
        document_id=body.document_id, page=body.page,
        source_text=f"Manual transcription by {principal.display_name}" + (f" from document #{body.document_id} page {body.page}" if body.document_id else ""),
        review_state="manual", verification_status="unverified", selected=True, author=principal.display_name,
    )
    ev.display = _display(ev)
    db.add(ev)
    db.flush()
    _revise(db, ev, principal, "manual_entry", body.note, None, fields)
    return _finish(db, ev, principal, "manual_entry")


def _display(ev: EvidenceItem) -> str:
    c = ev.current
    suffix = {"document": " (uploaded document)", "manual": f" (entered by {ev.author})"}.get(ev.origin, "")
    if ev.category == "medication":
        return f"{c.get('medication') or 'Unnamed medication'} - {c.get('dosage_text') or 'dose not recorded'}{suffix}"
    if ev.category == "lab":
        val = c.get("value") if c.get("value") is not None else c.get("value_text")
        unit = c.get("unit") or "(unit not recorded)"
        return f"{c.get('test') or 'Test'}: {val if val is not None else 'value not recorded'} {unit if val is not None else ''}".strip() + suffix
    if ev.category == "condition":
        return f"{c.get('condition') or 'Condition'} ({c.get('clinical_status') or 'status not recorded'}){suffix}"
    return (c.get("text") or "Note") + suffix
