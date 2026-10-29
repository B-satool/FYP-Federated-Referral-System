"""Role templates (spec v4 4.1): named bundles of realm roles, each with screens, API scopes, a record-visibility
level and whether the role holds keys.

Templates live in rules/roles/templates.v2.json. Applying a template to a user replaces the template-managed roles
they hold with the template's roles; roles outside the templates (service roles, Keycloak defaults) are never
touched. Keycloak stays the authority for roles; the services enforce the scopes and visibility derived from them
(security.require_scope, security.sees_clinical). The menu only hides what the API would refuse.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache

from ..config import INSTITUTIONS, settings

# Roles a template applied by an institution may contain. Service roles and the patient role are deliberately absent.
ASSIGNABLE_ROLES = frozenset({"clinic_staff", "clinician", "diagnostics_staff", "institution_admin", "rule_reviewer"})
VISIBILITY = ("none", "titles_only", "content")  # ordered: a user holding several templates gets the highest
TEMPLATE_FILE = "templates.v2.json"


@dataclass(frozen=True)
class RoleTemplate:
    template_id: str
    name: str
    description: str
    roles: tuple[str, ...]
    institution_kinds: tuple[str, ...]
    record_visibility: str
    holds_keys: bool
    api_scopes: tuple[str, ...]
    home: str | None
    menu: tuple[str, ...]
    assignable: bool = True

    def as_dict(self) -> dict:
        return {"template_id": self.template_id, "name": self.name, "description": self.description,
                "roles": list(self.roles), "institution_kinds": list(self.institution_kinds),
                "record_visibility": self.record_visibility, "holds_keys": self.holds_keys,
                "api_scopes": list(self.api_scopes), "home": self.home, "menu": list(self.menu)}


@lru_cache
def _raw() -> dict:
    return json.loads((settings.repo_root / "rules" / "roles" / TEMPLATE_FILE).read_text(encoding="utf-8"))


def screens() -> dict[str, dict]:
    return _raw()["screens"]


def scopes() -> dict[str, str]:
    return _raw()["scopes"]


@lru_cache
def templates() -> dict[str, RoleTemplate]:
    out: dict[str, RoleTemplate] = {}
    for t in _raw()["templates"]:
        assignable = t.get("assignable", True)
        bad = set(t["roles"]) - ASSIGNABLE_ROLES if assignable else set()
        if bad or not t["roles"]:
            raise ValueError(f"template {t['template_id']} has non-assignable or no roles: {sorted(bad)}")
        missing = (set(t["menu"]) | ({t["home"]} if t["home"] else set())) - set(screens())
        if missing:
            raise ValueError(f"template {t['template_id']} names unknown screens: {sorted(missing)}")
        if t["record_visibility"] not in VISIBILITY:
            raise ValueError(f"template {t['template_id']} has an unknown record visibility")
        unknown = set(t["api_scopes"]) - set(scopes())
        if unknown:
            raise ValueError(f"template {t['template_id']} names unknown scopes: {sorted(unknown)}")
        out[t["template_id"]] = RoleTemplate(
            t["template_id"], t["name"], t["description"], tuple(t["roles"]), tuple(t["institution_kinds"]),
            t["record_visibility"], bool(t["holds_keys"]), tuple(t["api_scopes"]), t["home"], tuple(t["menu"]),
            assignable)
    return out


def managed_roles() -> frozenset[str]:
    return frozenset(r for t in templates().values() if t.assignable for r in t.roles)


def templates_for_institution(institution_id: str | None) -> list[RoleTemplate]:
    kind = INSTITUTIONS.get(institution_id or "", {}).get("kind")
    return [t for t in templates().values() if t.assignable and kind in t.institution_kinds]


def plan_change(current_roles: set[str], template: RoleTemplate) -> tuple[list[str], list[str]]:
    """Return (roles to add, roles to remove). Only template-managed roles are ever removed."""
    wanted = set(template.roles)
    return sorted(wanted - current_roles), sorted((managed_roles() & current_roles) - wanted)


def held(roles: set[str], institution_id: str | None) -> list[RoleTemplate]:
    """Templates whose roles the user has all of (patients: the patient template, which belongs to no institution)."""
    kind = INSTITUTIONS.get(institution_id or "", {}).get("kind")
    return [t for t in templates().values() if set(t.roles) <= roles
            and (kind in t.institution_kinds or (not t.assignable and institution_id is None))]


def profile(roles: set[str], institution_id: str | None) -> dict:
    """What the user's templates allow: the highest record visibility, whether they hold keys, and the scopes."""
    ts = held(roles, institution_id)
    visibility = max((t.record_visibility for t in ts), key=VISIBILITY.index, default="none")
    return {"record_visibility": visibility, "holds_keys": any(t.holds_keys for t in ts),
            "scopes": sorted({s for t in ts for s in t.api_scopes})}


def navigation(roles: set[str], institution_id: str | None) -> dict:
    """Templates a user holds (all their roles), their home screen and their menu.

    A screen is offered only if the user has one of the roles the screen needs, so a menu never
    links to something the API would refuse."""
    ts = held(roles, institution_id)
    keys: list[str] = []
    for t in ts:
        keys += [k for k in t.menu if k not in keys]
    allowed = [k for k in keys if set(screens()[k]["roles"]) & roles]
    home = next((t.home for t in ts if t.home in allowed), allowed[0] if allowed else None)
    return {"templates": [t.template_id for t in ts], "home": screens()[home]["route"] if home else None,
            "menu": [{"key": k, **{f: screens()[k][f] for f in ("route", "label", "group")}} for k in allowed],
            **profile(roles, institution_id)}
