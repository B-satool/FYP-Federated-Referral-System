"""Patient links confirmed by the other institution, and account administration.

Flow: staff at the requesting institution send a link request (name, date of birth,
sex and CNIC from their own record). Staff at the target institution look the
patient up in their own index, then approve with the matching record (or register
the patient as new) or reject it. Approval also creates the target institution's
access grant, so records open only after that institution's staff have checked.
"""
from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from refcommon.auth import Principal
from refcommon.db import utcnow
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import INSTITUTIONS, SOURCES, institution_name
from ..db import get_db
from ..integration import sources
from ..models import (DiagnosticRequest, EvidenceItem, PatientLink, PatientLinkEvent, Referral, ReferralEvent,
                      ReferralPackage, User)
from ..notifications import notify
from ..security import audit, error, get_principal, kc_config, require_roles, service_tokens, verifier
from . import role_templates
from .links import link_out, links_for, open_request

router = APIRouter(tags=["patient links"])
LINK_ROLES = ("clinic_staff", "clinician", "institution_admin", "diagnostics_staff")
DECIDE_ROLES = ("clinic_staff", "institution_admin", "diagnostics_staff")


def _event(db: Session, link: PatientLink, action: str, principal: Principal, note: str = "", detail: dict | None = None):
    db.add(PatientLinkEvent(link_id=link.id, action=action, actor=principal.display_name, actor_id=principal.subject,
                            institution_id=principal.institution_id, note=note, detail=detail or {}))


def create_request(db: Session, principal: Principal, *, local_id: str, target: str, name: str, birth_date: str | None,
                   sex: str | None, cnic: str | None, referral: Referral | None, purpose: str,
                   kind: str = "records") -> PatientLink:
    """records: staff ask a place the patient visited for their records.
    intake: sent with a referral or test order; the receiver confirms the patient when it arrives
    (their incoming referral or order screen shows the request, so no separate notice is sent)."""
    if target not in SOURCES or target == principal.institution_id:
        raise error(422, "invalid_institution", "Choose another participating institution")
    existing = open_request(db, principal.institution_id, local_id, target)
    if existing:
        if kind == "intake" and existing.status == "requested":
            existing.kind = "intake"  # the patient is now being sent there, so they may register them as new
            existing.referral_id = existing.referral_id or (referral.id if referral else None)
        return existing
    link = PatientLink(requester_institution=principal.institution_id, requester_local_id=local_id,
                       target_institution=target, patient_name=name, patient_birth_date=birth_date, patient_sex=sex,
                       patient_cnic=cnic, referral_id=referral.id if referral else None, purpose=purpose, kind=kind,
                       requested_by=principal.display_name, requested_by_id=principal.subject)
    db.add(link)
    db.flush()
    _event(db, link, "requested", principal, purpose)
    audit(db, principal, "patient_link.request", "patient_link", link.id, "success", referral.id if referral else None,
          {"target": target, "local_id": local_id, "kind": kind})
    if kind == "records":
        notify(db, "link_request", f"Patient record request from {institution_name(principal.institution_id)}",
               institution=target, role="clinic_staff",
               body=f"Confirm which of your patient records is {name} (born {birth_date or 'not recorded'}), "
                    "or say you have no record of them.",
               link="/patient-links")
    return link


def _load_link(db: Session, link_id: int, principal: Principal) -> PatientLink:
    link = db.get(PatientLink, link_id)
    if link is None:
        raise error(404, "not_found", "Link not found")
    if principal.institution_id not in (link.requester_institution, link.target_institution):
        raise error(403, "forbidden", "Link does not involve your institution")
    return link


@router.get("/patient-links")
def list_links(institution: str | None = None, local_id: str | None = None, db: Session = Depends(get_db),
               principal: Principal = Depends(get_principal)):
    """Links of one of your own patient records (all states, with history)."""
    require_roles(principal, *LINK_ROLES, action="patient_link.view")
    institution = institution or principal.institution_id
    if institution != principal.institution_id:
        raise error(403, "forbidden", "You can only view links for your own institution's patient records")
    if not local_id:
        raise error(422, "local_id_required", "Choose a patient")
    out = []
    for link in links_for(db, institution, local_id):
        item = link_out(link)
        item["events"] = [{"action": e.action, "actor": e.actor, "institution_id": e.institution_id, "note": e.note,
                           "created_at": e.created_at}
                          for e in db.scalars(select(PatientLinkEvent).where(PatientLinkEvent.link_id == link.id)
                                              .order_by(PatientLinkEvent.id))]
        out.append(item)
    return out


@router.get("/patient-links/incoming")
def incoming(status: str = "requested", db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """Requests from other institutions for your staff to check."""
    require_roles(principal, *LINK_ROLES, action="patient_link.incoming")
    stmt = select(PatientLink).where(PatientLink.target_institution == principal.institution_id)
    if status != "all":
        stmt = stmt.where(PatientLink.status.in_(status.split(",")))
    return [link_out(x) for x in db.scalars(stmt.order_by(PatientLink.requested_at.desc()).limit(200))]


@router.get("/patient-links/outgoing")
def outgoing(status: str = "requested", db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    require_roles(principal, *LINK_ROLES, action="patient_link.outgoing")
    stmt = select(PatientLink).where(PatientLink.requester_institution == principal.institution_id)
    if status != "all":
        stmt = stmt.where(PatientLink.status.in_(status.split(",")))
    return [link_out(x) for x in db.scalars(stmt.order_by(PatientLink.requested_at.desc()).limit(200))]


class LinkIn(BaseModel):
    local_id: str
    target_institution: str
    purpose: str = Field(min_length=5)


@router.post("/patient-links", status_code=201)
def request_link(body: LinkIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """Ask another institution to confirm their record of one of your patients."""
    require_roles(principal, "clinic_staff", "clinician", action="patient_link.request")
    p = sources.call(principal.institution_id, "GET", f"/patients/{body.local_id}", principal)
    link = create_request(db, principal, local_id=body.local_id, target=body.target_institution, name=p["name"],
                          birth_date=p["birth_date"], sex=p["sex"], cnic=p.get("cnic"), referral=None, purpose=body.purpose)
    db.commit()
    return link_out(link)


@router.post("/patient-links/{link_id}/lookup")
def lookup(link_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """Target staff search their own patient index for the person in the request."""
    link = _load_link(db, link_id, principal)
    if principal.institution_id != link.target_institution:
        raise error(403, "forbidden", "Only the institution asked to confirm the link can look the patient up")
    require_roles(principal, *DECIDE_ROLES, action="patient_link.lookup")
    candidates = sources.call(link.target_institution, "POST", "/identity/lookup", principal,
                              json={"cnic": link.patient_cnic, "name": link.patient_name,
                                    "birth_date": link.patient_birth_date, "sex": link.patient_sex})
    link.match_check = {"candidates": len(candidates), "checked_by": principal.display_name,
                        "checked_at": utcnow().isoformat()}
    _event(db, link, "looked_up", principal, detail={"candidates": len(candidates)})
    db.commit()
    return {"link": link_out(link), "candidates": candidates}


class ApproveIn(BaseModel):
    local_patient_id: str | None = None
    register_new: bool = False
    note: str = Field(min_length=3)


@router.post("/patient-links/{link_id}/approve")
def approve_link(link_id: int, body: ApproveIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """Only staff at the target institution approve. Approval records the basis and shares
    the patient's referral-relevant records with the requesting institution."""
    link = _load_link(db, link_id, principal)
    if principal.institution_id != link.target_institution:
        raise error(403, "forbidden", "Only the institution asked to confirm the link can approve it")
    require_roles(principal, *DECIDE_ROLES, action="patient_link.approve",
                  message="Only staff or an administrator at this institution can approve a patient link")
    if link.status != "requested":
        raise error(409, "not_pending", f"This link is already {link.status}")
    if body.register_new == bool(body.local_patient_id):
        raise error(422, "choose_one", "Choose the matching record, or register the patient as new")
    if body.register_new and link.kind != "intake":
        raise error(422, "records_request",
                    "This is a request for records. If you have no record of this patient, answer 'No record here'.")
    local_id = body.local_patient_id
    if body.register_new:
        *given, family = link.patient_name.split()
        created = sources.call(link.target_institution, "POST", "/identity/register", principal, json={
            "cnic": link.patient_cnic or "", "given": " ".join(given) or family, "family": family,
            "birth_date": link.patient_birth_date, "sex": link.patient_sex or "U"})
        local_id = created["local_patient_id"]
        link.registered_new = True
    taken = db.scalars(select(PatientLink).where(
        PatientLink.target_institution == link.target_institution, PatientLink.target_local_id == local_id,
        PatientLink.requester_institution == link.requester_institution, PatientLink.status == "verified",
        PatientLink.requester_local_id != link.requester_local_id)).first()
    if taken:
        raise error(409, "record_linked_elsewhere",
                    "That record is already linked to a different patient at the requesting institution")
    referral = db.get(Referral, link.referral_id) if link.referral_id else None
    if link.kind == "records":
        # temporary access, tied to the referral it was asked for (closed when that referral finishes)
        sources.call(link.target_institution, "POST", "/sharing/grants", principal, json={
            "grantee_institution": link.requester_institution, "local_patient_id": local_id,
            "basis": f"Patient link #{link.id} approved by {principal.display_name}: {body.note.strip()}",
            "referral_ref": referral.reference if referral else None})
    elif referral is not None:
        # the incoming referral and test orders for this patient now point at the confirmed record
        sources.call(link.target_institution, "POST", "/intake/patient", principal, json={
            "referral_id": referral.reference, "local_patient_id": local_id})
        for dx in db.scalars(select(DiagnosticRequest).where(DiagnosticRequest.referral_id == referral.id,
                                                             DiagnosticRequest.destination_institution == link.target_institution)):
            dx.local_patient_id = local_id
    link.target_local_id = local_id
    link.status = "verified"
    link.decided_by, link.decided_by_id, link.decided_at = principal.display_name, principal.subject, utcnow()
    link.decision_note = body.note.strip()
    _event(db, link, "verified", principal, body.note, {"local_id": local_id, "registered_new": link.registered_new})
    audit(db, principal, "patient_link.approve", "patient_link", link.id, "success", link.referral_id,
          {"target_local_id": local_id, "registered_new": link.registered_new})
    target = institution_name(link.target_institution)
    if link.kind == "records":
        title, text = f"{target} confirmed {link.patient_name}", "Records from there can now be retrieved."
    elif link.registered_new:
        title, text = (f"{target} registered {link.patient_name} as a new patient",
                       f"They had no earlier record of this patient. New record: {local_id}.")
    else:
        title, text = f"{target} matched {link.patient_name} to their record", f"Their record: {local_id}."
    notify(db, "link_verified", title, institution=link.requester_institution, role="clinic_staff", body=text,
           link=f"/referrals/{link.referral_id}" if link.referral_id else "/patient-links")
    if link.referral_id:
        db.add(ReferralEvent(referral_id=link.referral_id, event_type="patient_link_verified", actor=principal.display_name,
                             institution_id=principal.institution_id,
                             detail={"institution": link.target_institution, "local_id": local_id, "kind": link.kind,
                                     "registered_new": link.registered_new}))
    db.commit()
    return link_out(link)


class DecisionIn(BaseModel):
    note: str = Field(min_length=3)


@router.post("/patient-links/{link_id}/reject")
def reject_link(link_id: int, body: DecisionIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    link = _load_link(db, link_id, principal)
    if principal.institution_id != link.target_institution:
        raise error(403, "forbidden", "Only the institution asked to confirm the link can reject it")
    require_roles(principal, *DECIDE_ROLES, action="patient_link.reject")
    if link.status != "requested":
        raise error(409, "not_pending", f"This link is already {link.status}")
    link.status, link.status_key = "rejected", f"rejected-{link.id}"
    link.decided_by, link.decided_by_id, link.decided_at = principal.display_name, principal.subject, utcnow()
    link.decision_note = body.note.strip()
    _event(db, link, "rejected", principal, body.note)
    audit(db, principal, "patient_link.reject", "patient_link", link.id, "success", link.referral_id)
    notify(db, "link_rejected", f"{institution_name(link.target_institution)} could not confirm {link.patient_name}",
           institution=link.requester_institution, role="clinic_staff", body=f"Reason: {body.note.strip()}",
           link=f"/referrals/{link.referral_id}?tab=links" if link.referral_id else "/patient-links")
    db.commit()
    return link_out(link)


@router.post("/patient-links/{link_id}/invalidate")
def invalidate_link(link_id: int, body: DecisionIn, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    """Stops future use. History is kept, and referrals that used it are flagged for review."""
    from ..referrals.state import CLINICAL_LOCKED, TERMINAL, event, mark_clinical_change
    from ..workflow import after_change

    require_roles(principal, "clinician", "institution_admin", "clinic_staff", action="patient_link.invalidate")
    link = _load_link(db, link_id, principal)
    if link.status != "verified":
        raise error(409, "not_verified", "Only a verified link can be invalidated")
    link.status, link.status_key = "invalidated", f"invalidated-{link.id}"
    link.invalidated_by, link.invalidated_at, link.invalidation_reason = principal.display_name, utcnow(), body.note
    affected = []
    by_referral: dict[int, list[EvidenceItem]] = {}
    for ev in db.scalars(select(EvidenceItem).where(EvidenceItem.link_id == link.id)):
        by_referral.setdefault(ev.referral_id, []).append(ev)
    for ref_id, evs in by_referral.items():
        r = db.get(Referral, ref_id)
        ids = {e.id for e in evs}
        packages = [p.version for p in db.scalars(select(ReferralPackage).where(ReferralPackage.referral_id == r.id))
                    if ids & {x["evidence_id"] for x in p.envelope.get("evidence", [])}]
        open_referral = r.status not in TERMINAL and r.status not in CLINICAL_LOCKED
        if open_referral:
            for e in evs:
                e.verification_status, e.selected = "invalidated", False
        event(db, r, "patient_link_invalidated", principal.display_name, principal.institution_id,
              {"link_id": link.id, "reason": body.note, "evidence_items": len(evs), "sent_versions_affected": packages})
        if open_referral:
            if packages:
                mark_clinical_change(db, r, principal.display_name, "patient link invalidated", principal)
            after_change(db, r, "patient_link_invalidated", principal)
        affected.append({"referral_id": r.id, "reference": r.reference, "evidence_items": len(evs),
                         "sent_versions_affected": packages})
    _event(db, link, "invalidated", principal, body.note, {"affected": affected})
    audit(db, principal, "patient_link.invalidate", "patient_link", link.id, "success", detail={"affected": affected})
    db.commit()
    return {**link_out(link), "affected": affected}


@router.get("/patients/search")
def search_patients(q: str = "", principal: Principal = Depends(get_principal)):
    """Search your own institution's patient index (name, local ID or CNIC)."""
    require_roles(principal, *LINK_ROLES, action="patients.search")
    if principal.institution_id not in SOURCES:
        raise error(404, "no_patient_index", "Your institution has no connected patient index")
    return sources.call(principal.institution_id, "GET", "/patients", principal, params={"q": q})


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
    # group paths look like "/ziauddin/cardiology"; the first segment is the institution
    return u.json(), [g.get("path", "/" + g["name"]).strip("/").split("/")[0] for g in groups]


@router.get("/admin/users")
def list_users(db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    require_roles(principal, "institution_admin", action="admin.users")
    base = kc_config.admin_url
    groups = httpx.get(f"{base}/groups", params={"search": principal.institution_id}, headers=_kc_headers(), timeout=10).json()
    group = next((g for g in groups if g["name"] == principal.institution_id), None)
    if group is None:
        return []
    children = httpx.get(f"{base}/groups/{group['id']}/children", params={"max": 100}, headers=_kc_headers(),
                         timeout=10).json()
    members: list[tuple[dict, str | None]] = []
    for g, dept in [(group, None)] + [(c, c["name"]) for c in children]:
        for m in httpx.get(f"{base}/groups/{g['id']}/members", params={"max": 200}, headers=_kc_headers(), timeout=10).json():
            members.append((m, dept))
    out = []
    for m, dept in members:
        local = db.get(User, m["id"])
        roles = httpx.get(f"{base}/users/{m['id']}/role-mappings/realm", headers=_kc_headers(), timeout=10).json()
        out.append({"id": m["id"], "username": m["username"], "name": f"{m.get('firstName', '')} {m.get('lastName', '')}".strip(),
                    "department": dept,
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
    return [{"id": k, **{x: y for x, y in v.items() if x != "url_env"}} for k, v in INSTITUTIONS.items()
            if k != "central-platform"]


# ------------------------------------------------------------------ role templates
class ApplyTemplateIn(BaseModel):
    template_id: str
    reason: str = Field(min_length=3)


def _kc_realm_roles(user_id: str) -> set[str]:
    resp = httpx.get(f"{kc_config.admin_url}/users/{user_id}/role-mappings/realm", headers=_kc_headers(), timeout=10)
    resp.raise_for_status()
    return {r["name"] for r in resp.json()}


def _kc_role_reps(names: list[str]) -> list[dict]:
    reps = []
    for n in names:
        resp = httpx.get(f"{kc_config.admin_url}/roles/{n}", headers=_kc_headers(), timeout=10)
        resp.raise_for_status()
        reps.append(resp.json())
    return reps


@router.get("/admin/role-templates")
def list_role_templates(principal: Principal = Depends(get_principal)):
    """Templates this institution's administrator may apply."""
    require_roles(principal, "institution_admin", action="admin.role_templates")
    return [t.as_dict() for t in role_templates.templates_for_institution(principal.institution_id)]


@router.post("/admin/users/{user_id}/apply-template")
def apply_role_template(user_id: str, body: ApplyTemplateIn, db: Session = Depends(get_db),
                        principal: Principal = Depends(get_principal)):
    """Replace the user's template-managed realm roles with the template's (never service roles, never oneself)."""
    require_roles(principal, "institution_admin", action="admin.apply_template")
    template = role_templates.templates().get(body.template_id)
    if template is None or template not in role_templates.templates_for_institution(principal.institution_id):
        raise error(404, "template_not_available", "That template is not available for this institution")
    kc_user, groups = _kc_user(user_id)
    if principal.institution_id not in groups:
        raise error(403, "forbidden", "You can only manage accounts of your own institution")
    if user_id == principal.subject:
        raise error(409, "self", "You cannot change your own roles")
    before = _kc_realm_roles(user_id)
    add, remove = role_templates.plan_change(before, template)
    base = kc_config.admin_url
    if add:
        httpx.post(f"{base}/users/{user_id}/role-mappings/realm", json=_kc_role_reps(add),
                   headers=_kc_headers(), timeout=10).raise_for_status()
    if remove:
        httpx.request("DELETE", f"{base}/users/{user_id}/role-mappings/realm", json=_kc_role_reps(remove),
                      headers=_kc_headers(), timeout=10).raise_for_status()
    verifier.invalidate_cache()  # applies on the user's next request
    audit(db, principal, "role.assign", "user", kc_user["username"], "success",
          detail={"template": template.template_id, "added": add, "removed": remove, "reason": body.reason})
    db.commit()
    return {"id": user_id, "username": kc_user["username"], "template": template.template_id,
            "added": add, "removed": remove, "default_grant_days": template.default_grant_days}
