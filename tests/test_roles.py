"""Role templates (spec v4 4.1): the menu follows the user's roles, and an administrator assigns a role by template
(the change reaches Keycloak and the next sign-in)."""
from __future__ import annotations

from helpers import central, ok, token

DOCTOR, STAFF = central("dr.ali"), central("staff.ali")


def test_role_menus():
    staff_menu = {m["key"] for m in ok(STAFF.get("/me"))["menu"]}
    doctor = ok(DOCTOR.get("/me"))
    reviewer_menu = {m["key"] for m in ok(central("dr.reviewer").get("/me"))["menu"]}
    assert doctor["home"] and {"rules", "medicine_names"}.isdisjoint({m["key"] for m in doctor["menu"]})
    assert {"rules", "accounts"}.isdisjoint(staff_menu)
    assert "rules" in reviewer_menu
    # a screen outside the menu is refused by the API as well
    assert STAFF.get("/rules").status_code == 403


def test_admin_assigns_a_role_by_template():
    """An institution administrator turns a lab account into front-desk staff and back. The change is
    made in Keycloak, so it applies on the user's next sign-in, and it is audited."""
    admin = central("admin.ali")
    users = {u["username"]: u for u in ok(admin.get("/admin/users"))}
    tech = users["tech.ali"]
    assert {t["template_id"] for t in ok(admin.get("/admin/role-templates"))} >= {"front_desk", "doctor"}
    try:
        out = ok(admin.post(f"/admin/users/{tech['id']}/apply-template",
                            {"template_id": "front_desk", "reason": "Moved to the front desk"}))
        assert out["added"] == ["clinic_staff"] and out["removed"] == ["diagnostics_staff"]
        token("tech.ali", fresh=True)
        me = ok(central("tech.ali").get("/me"))
        assert me["roles"] == ["clinic_staff"] and me["home"] == "/work-queue"
        assert central("tech.ali").get("/work-queue").status_code == 200
    finally:
        ok(admin.post(f"/admin/users/{tech['id']}/apply-template", {"template_id": "lab_radiology", "reason": "Test finished"}))
    token("tech.ali", fresh=True)
    assert ok(central("tech.ali").get("/me"))["roles"] == ["diagnostics_staff"]
    # guards: not oneself, not another institution's account, not by non-administrators
    assert admin.post(f"/admin/users/{users['admin.ali']['id']}/apply-template",
                      {"template_id": "doctor", "reason": "test"}).status_code == 409
    other = next(u for u in ok(central("admin.aku").get("/admin/users")) if u["username"] == "staff.aku")
    assert admin.post(f"/admin/users/{other['id']}/apply-template", {"template_id": "doctor", "reason": "test"}).status_code == 403
    assert STAFF.post(f"/admin/users/{tech['id']}/apply-template", {"template_id": "doctor", "reason": "test"}).status_code == 403
