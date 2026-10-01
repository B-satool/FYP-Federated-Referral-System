"""Patient-link verification/correction (FR-06 to FR-10) and account administration (FR-05)."""
from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from refcommon.auth import Principal
from refcommon.db import utcnow
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import INSTITUTIONS, SOURCES
from ..db import get_db
from ..integration import sources
from ..models import EvidenceItem, PatientLink, PatientLinkEvent, Referral, ReferralPackage, ReviewItem, User
from ..referrals.state import CLINICAL_LOCKED, TERMINAL, mark_clinical_change
from ..security import audit, error, get_principal, kc_config, require_roles, service_tokens, verifier
from ..workflow import after_change
from .links import link_out, links_for

router = APIRouter(tags=["identity"])
LINK_ROLES = ("clinic_staff", "clinician", "institution_admin")


def _event(db: Session, link: PatientLink, action: str, principal: Principal, note: str = "", detail: dict | None = None):
    db.add(PatientLinkEvent(link_id=link.id, action=action, actor=principal.display_name, actor_id=principal.subject,
                            note=note, detail=detail or {}))
    audit(db, principal, f"patient_link.{action}", "patient_link", link.id, "success",
          detail={"a": f"{link.a_institution}/{link.a_local_id}", "b": f"{link.b_institution}/{link.b_local_id}",
                  "note": note, **(detail or {})})


def _load_link(db: Session, link_id: int, principal: Principal) -> PatientLink:
    link = db.get(PatientLink, link_id)
    if link is None:
        raise error(404, "not_found", "Link not found")
    if principal.institution_id not in (link.a_institution, link.b_institution):
        raise error(403, "forbidden", "Link does not involve your institution")
    return link


@router.get("/patient-links")
def list_links(institution: str, local_id: str, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    require_roles(principal, *LINK_ROLES, action="patient_link.view")
    if principal.institution_id != institution:
        raise error(403, "forbidden", "You can only view links for your institution's patient records")
    out = []
    for link in links_for(db, institution, local_id):
        item = link_out(link)
        item["events"] = [{"action": e.action, "actor": e.actor, "note": e.note, "detail": e.detail, "created_at": e.created_at}
                          for e in db.scalars(select(PatientLinkEvent).where(PatientLinkEvent.link_id == link.id)
                                              .order_by(PatientLinkEvent.id))]
        out.append(item)
    return out


class Demographics(BaseModel):
    family: str
    given: str
    birth_date: str


class LinkIn(BaseModel):
    a_local_id: str
    b_institution: str
    b_local_id: str
    basis: str = Field(min_length=5)
    check_demographics: Demographics | None = None
    referral_reference: str | None = None


@router.post("/patient-links", status_code=201)
def propose_link(body: LinkIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    require_roles(principal, "clinic_staff", "clinician", action="patient_link.propose")
    if body.b_institution not in SOURCES or body.b_institution == principal.institution_id:
        raise error(422, "invalid_institution", "Choose another participating institution")
    current = [x for x in links_for(db, principal.institution_id, body.a_local_id, ("pending", "verified"))
               if body.b_institution in (x.a_institution, x.b_institution)]
    if current:
        raise error(409, "link_exists", f"A {current[0].status} link to {sources.source_name(body.b_institution)} already "
                                        "exists for this patient; invalidate it first")
    link = PatientLink(a_institution=principal.institution_id, a_local_id=body.a_local_id, b_institution=body.b_institution,
                       b_local_id=body.b_local_id.strip(), basis=body.basis.strip(), proposed_by=principal.display_name,
                       proposed_by_id=principal.subject)
    if body.check_demographics:
        link.match_check = {**sources.identity_match(body.b_institution, {"local_patient_id": link.b_local_id,
                                                                          **body.check_demographics.model_dump()},
                                                     principal, body.referral_reference), "checked_at": utcnow().isoformat()}
    db.add(link)
    db.flush()
    _event(db, link, "proposed", principal, body.basis, {"match_check": link.match_check})
    db.commit()
    return link_out(link)


class CheckIn(Demographics):
    referral_reference: str | None = None


@router.post("/patient-links/{link_id}/check")
def check_link(link_id: int, body: CheckIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    require_roles(principal, *LINK_ROLES, action="patient_link.check")
    link = _load_link(db, link_id, principal)
    other_inst, other_id = (link.b_institution, link.b_local_id) if link.a_institution == principal.institution_id \
        else (link.a_institution, link.a_local_id)
    result = sources.identity_match(other_inst, {"local_patient_id": other_id, **body.model_dump(exclude={"referral_reference"})},
                                    principal, body.referral_reference)
    link.match_check = {**result, "checked_at": utcnow().isoformat()}
    _event(db, link, "checked", principal, detail={"match_check": link.match_check})
    db.commit()
    return link_out(link)


class DecisionIn(BaseModel):
    note: str = Field(min_length=5)


@router.post("/patient-links/{link_id}/verify")
def verify_link(link_id: int, body: DecisionIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """Records verifier, timestamp and basis (FR-08). Only clinicians or administrators verify."""
    require_roles(principal, "clinician", "institution_admin", action="patient_link.verify",
                  message="Only a clinician or institution administrator can verify a patient link")
    link = _load_link(db, link_id, principal)
    if link.status != "pending":
        raise error(409, "not_pending", f"Link is {link.status}")
    mc = link.match_check or {}
    if mc and not mc.get("record_exists", True):
        raise error(409, "record_missing", "The identity check found no such record at the other institution")
    link.status, link.verified_by, link.verified_by_id, link.verified_at = "verified", principal.display_name, principal.subject, utcnow()
    link.basis = f"{link.basis}\nVerification: {body.note.strip()}"
    _event(db, link, "verified", principal, body.note)
    db.commit()
    return link_out(link)


@router.post("/patient-links/{link_id}/reject")
def reject_link(link_id: int, body: DecisionIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    require_roles(principal, *LINK_ROLES, action="patient_link.reject")
    link = _load_link(db, link_id, principal)
    if link.status != "pending":
        raise error(409, "not_pending", f"Link is {link.status}")
    link.status, link.status_key = "rejected", f"rejected-{link.id}"
    link.invalidated_by, link.invalidated_at, link.invalidation_reason = principal.display_name, utcnow(), body.note
    _event(db, link, "rejected", principal, body.note)
    db.commit()
    return link_out(link)


@router.post("/patient-links/{link_id}/invalidate")
def invalidate_link(link_id: int, body: DecisionIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """Prevents future use and identifies affected drafts/packages; history is kept, not rewritten (FR-10)."""
    require_roles(principal, "clinician", "institution_admin", action="patient_link.invalidate",
                  message="Only a clinician or institution administrator can invalidate a patient link")
    link = _load_link(db, link_id, principal)
    if link.status != "verified":
        raise error(409, "not_verified", "Only a verified link can be invalidated")
    link.status, link.status_key = "invalidated", f"invalidated-{link.id}"
    link.invalidated_by, link.invalidated_at, link.invalidation_reason = principal.display_name, utcnow(), body.note
    affected = []
    items = db.scalars(select(EvidenceItem).where(EvidenceItem.link_id == link.id)).all()
    by_referral: dict[int, list[EvidenceItem]] = {}
    for ev in items:
        by_referral.setdefault(ev.referral_id, []).append(ev)
    for ref_id, evs in by_referral.items():
        r = db.get(Referral, ref_id)
        ids = {e.id for e in evs}
        packages = [p.version for p in db.scalars(select(ReferralPackage).where(ReferralPackage.referral_id == r.id))
                    if ids & {x["evidence_id"] for x in p.envelope.get("evidence", [])}]
        if r.status not in TERMINAL and r.status not in CLINICAL_LOCKED:
            for e in evs:
                e.verification_status, e.selected = "invalidated", False
        key = f"link_invalidated:{link.id}"
        if not db.scalars(select(ReviewItem).where(ReviewItem.referral_id == r.id, ReviewItem.item_key == key)).first():
            db.add(ReviewItem(referral_id=r.id, item_key=key, kind="link_invalidated", title=
                              f"Patient link to {sources.source_name(link.b_institution if link.a_institution == r.patient_institution else link.a_institution)} was invalidated",
                              detail=(f"Reason: {body.note}. {len(evs)} evidence item(s) from that link can no longer be used."
                                      + (f" Approved package version(s) {packages} contained this evidence and are kept for history; review required."
                                         if packages else "")),
                              evidence_ids=sorted(ids), blocking=True, override_allowed=True, clinical=True))
        if packages and r.status not in TERMINAL and r.status not in CLINICAL_LOCKED:
            mark_clinical_change(db, r, principal.display_name, "patient link invalidated", principal)
        if r.status not in TERMINAL and r.status not in CLINICAL_LOCKED:
            after_change(db, r, "patient_link_invalidated", principal)
        affected.append({"referral_id": r.id, "reference": r.reference, "status": r.status,
                         "evidence_items": len(evs), "packages_containing_evidence": packages})
    _event(db, link, "invalidated", principal, body.note, {"affected": affected})
    db.commit()
    return {**link_out(link), "affected": affected}


# ------------------------------------------------------------------ account administration
def _kc_headers() -> dict:
    return {"Authorization": f"Bearer {service_tokens.get()}"}


def _kc_user(user_id: str) -> tuple[dict, list[str]]:
    base = kc_config.admin_url
    u = httpx.get(f"{base}/users/{user_id}", headers=_kc_headers(), timeout=10)
    if u.status_code == 404:
        raise error(404, "not_found", "User not found")
    u.raise_for_status()
    groups = httpx.get(f"{base}/users/{user_id}/groups", headers=_kc_headers(), timeout=10).json()
    return u.json(), [g["name"] for g in groups]


@router.get("/admin/users")
def list_users(db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    require_roles(principal, "institution_admin", action="admin.users")
    base = kc_config.admin_url
    groups = httpx.get(f"{base}/groups", params={"search": principal.institution_id}, headers=_kc_headers(), timeout=10).json()
    group = next((g for g in groups if g["name"] == principal.institution_id), None)
    if group is None:
        return []
    members = httpx.get(f"{base}/groups/{group['id']}/members", params={"max": 200}, headers=_kc_headers(), timeout=10).json()
    out = []
    for m in members:
        local = db.get(User, m["id"])
        roles = httpx.get(f"{base}/users/{m['id']}/role-mappings/realm", headers=_kc_headers(), timeout=10).json()
        out.append({"id": m["id"], "username": m["username"], "name": f"{m.get('firstName', '')} {m.get('lastName', '')}".strip(),
                    "enabled": m.get("enabled", True), "central_status": local.account_status if local else "never_signed_in",
                    "roles": sorted(r["name"] for r in roles if not r["name"].startswith("default-roles")),
                    "last_seen_at": local.last_seen_at if local else None})
    return out


class StatusIn(BaseModel):
    reason: str = Field(min_length=3)


def _set_status(db: Session, principal: Principal, user_id: str, enabled: bool, reason: str) -> dict:
    require_roles(principal, "institution_admin", action="admin.user_status")
    kc_user, groups = _kc_user(user_id)
    if principal.institution_id not in groups:
        raise error(403, "forbidden", "You can only manage accounts of your own institution")
    if user_id == principal.subject:
        raise error(409, "self", "You cannot change your own account status")
    base = kc_config.admin_url
    httpx.put(f"{base}/users/{user_id}", json={"enabled": enabled}, headers=_kc_headers(), timeout=10).raise_for_status()
    if not enabled:
        httpx.post(f"{base}/users/{user_id}/logout", headers=_kc_headers(), timeout=10)
    local = db.get(User, user_id)
    if local is None:
        local = User(id=user_id, username=kc_user["username"], display_name=kc_user["username"],
                     institution_id=principal.institution_id, roles=[])
        db.add(local)
    local.account_status = "active" if enabled else "disabled"
    local.status_changed_by, local.status_changed_at = principal.display_name, utcnow()
    verifier.invalidate_cache()
    audit(db, principal, "admin.enable_user" if enabled else "admin.disable_user", "user", kc_user["username"], "success",
          detail={"reason": reason})
    db.commit()
    return {"id": user_id, "username": kc_user["username"], "central_status": local.account_status, "enabled": enabled}


@router.post("/admin/users/{user_id}/disable")
def disable_user(user_id: str, body: StatusIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    return _set_status(db, principal, user_id, False, body.reason)


@router.post("/admin/users/{user_id}/enable")
def enable_user(user_id: str, body: StatusIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    return _set_status(db, principal, user_id, True, body.reason)


@router.get("/institutions")
def institutions(principal: Principal = Depends(get_principal)):
    return [{"id": k, **v} for k, v in INSTITUTIONS.items() if k != "central-platform"]
