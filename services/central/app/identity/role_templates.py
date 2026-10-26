"""Role templates: named bundles of realm roles, each with a home screen and a menu.

Templates live in rules/roles/templates.v1.json. Applying a template to a user replaces the
template-managed roles they hold with the template's roles; roles outside the templates
(service roles, Keycloak defaults) are never touched. Keycloak stays the authority and every
access check in the services is unchanged: the menu only hides screens a role cannot use.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache

from ..config import INSTITUTIONS, settings

# Roles a template may contain. Service roles are deliberately absent.
ASSIGNABLE_ROLES = frozenset({"clinic_staff", "clinician", "diagnostics_staff", "institution_admin", "rule_reviewer"})


@dataclass(frozen=True)
class RoleTemplate:
    template_id: str
    name: str
    description: str
    roles: tuple[str, ...]
    institution_kinds: tuple[str, ...]
    default_grant_days: int
    home: str
    menu: tuple[str, ...]

    def as_dict(self) -> dict:
        return {"template_id": self.template_id, "name": self.name, "description": self.description,
                "roles": list(self.roles), "institution_kinds": list(self.institution_kinds),
                "default_grant_days": self.default_grant_days, "home": self.home, "menu": list(self.menu)}


@lru_cache
def _raw() -> dict:
    return json.loads((settings.repo_root / "rules" / "roles" / "templates.v1.json").read_text(encoding="utf-8"))


def screens() -> dict[str, dict]:
    return _raw()["screens"]


@lru_cache
def templates() -> dict[str, RoleTemplate]:
    out: dict[str, RoleTemplate] = {}
    for t in _raw()["templates"]:
        bad = set(t["roles"]) - ASSIGNABLE_ROLES
        if bad or not t["roles"]:
            raise ValueError(f"template {t['template_id']} has non-assignable or no roles: {sorted(bad)}")
        missing = (set(t["menu"]) | {t["home"]}) - set(screens())
        if missing:
            raise ValueError(f"template {t['template_id']} names unknown screens: {sorted(missing)}")
        out[t["template_id"]] = RoleTemplate(t["template_id"], t["name"], t["description"], tuple(t["roles"]),
                                             tuple(t["institution_kinds"]), int(t["default_grant_days"]), t["home"],
                                             tuple(t["menu"]))
    return out


def managed_roles() -> frozenset[str]:
    return frozenset(r for t in templates().values() for r in t.roles)


def templates_for_institution(institution_id: str | None) -> list[RoleTemplate]:
    kind = INSTITUTIONS.get(institution_id or "", {}).get("kind")
    return [t for t in templates().values() if kind in t.institution_kinds]


def plan_change(current_roles: set[str], template: RoleTemplate) -> tuple[list[str], list[str]]:
    """Return (roles to add, roles to remove). Only template-managed roles are ever removed."""
    wanted = set(template.roles)
    return sorted(wanted - current_roles), sorted((managed_roles() & current_roles) - wanted)


def navigation(roles: set[str], institution_id: str | None) -> dict:
    """Templates a user holds (all their roles), their home screen and their menu.

    A screen is offered only if the user has one of the roles the screen needs, so a menu never
    links to something the API would refuse."""
    kind = INSTITUTIONS.get(institution_id or "", {}).get("kind")
    held = [t for t in templates().values() if set(t.roles) <= roles and kind in t.institution_kinds]
    keys: list[str] = []
    for t in held:
        keys += [k for k in t.menu if k not in keys]
    allowed = [k for k in keys if set(screens()[k]["roles"]) & roles]
    home = next((t.home for t in held if t.home in allowed), allowed[0] if allowed else None)
    return {"templates": [t.template_id for t in held], "home": screens()[home]["route"] if home else None,
            "menu": [{"key": k, **{f: screens()[k][f] for f in ("route", "label", "group")}} for k in allowed]}
