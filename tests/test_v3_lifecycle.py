"""Architecture spec v3 and the data-lifecycle change, against the running stack:
temporary grants, role menus, packet selection, the package manifest, the clinic's own copy and the purge."""
from __future__ import annotations

import json

import pytest
from conftest import SURGERY, compose, doctor_review, new_referral
from helpers import central, institution, ok, token, wait_for

DOCTOR, STAFF = central("dr.ali"), central("staff.ali")


def _ref(rid):
    return ok(STAFF.get(f"/referrals/{rid}"))


def test_grants_are_temporary():
    admin = institution("drali", "admin.ali")
    body = {"grantee_institution": "akuh", "local_patient_id": "DA-6120", "categories": ["medications"],
            "basis": "synthetic test", "referral_ref": "REF-TEST-GRANT"}
    assert admin.post("/admin/grants", {**body, "duration_days": 0}).status_code == 422
    assert admin.post("/admin/grants", {**body, "duration_days": 31}).status_code == 422
    g = ok(admin.post("/admin/grants", {**body, "duration_days": 3}), 201)
    assert g["state"] == "active" and g["expires_at"] and g["referral_ref"] == "REF-TEST-GRANT"
    assert admin.post(f"/admin/grants/{g['id']}/extend", {"days": 5, "reason": ""}).status_code == 422
    ok(admin.post(f"/admin/grants/{g['id']}/extend", {"days": 5, "reason": "appointment moved"}))
    # only the central service closes grants by referral
    assert institution("drali", "staff.ali").post("/grants/revoke-by-referral",
                                                  {"referral_ref": "REF-TEST-GRANT"}).status_code == 403
    ok(admin.post(f"/admin/grants/{g['id']}/revoke"))


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


def test_selection_manifest_own_copy_and_purge():
    r = new_referral("Gondal", "akuh", "orthopaedics", "Total knee replacement (right)", SURGERY)
    rid = r["id"]
    retrieved = ok(STAFF.post(f"/referrals/{rid}/retrieve"))
    assert _ref(rid)["working_set_expires_at"] is None  # no time limit until the receiving doctor accepts

    # Packet selection: without a model the default stands and the page can say so.
    sel = ok(STAFF.get(f"/referrals/{rid}/selection"))
    if not sel["llm_configured"]:
        assert retrieved["selection"]["run"]["status"] == "unavailable"
    else:
        sel = wait_for(lambda: (s := ok(STAFF.get(f"/referrals/{rid}/selection")))["run"] and s, 180, 3, "AI selection")
        assert sel["run"]["status"] in ("completed", "rejected", "unavailable")
    ev = ok(DOCTOR.get(f"/referrals/{rid}/evidence"))
    assert all(e["selected"] for e in ev if e["in_default"])  # the AI never removes a default item
    item = next(e for e in ev if e["selected"] and e["origin"] == "source")
    # only the doctor finalises the packet; staff see titles only (decision 2026-10-29)
    assert STAFF.post(f"/evidence/{item['id']}/select", {"selected": False}).status_code == 403
    ok(DOCTOR.post(f"/evidence/{item['id']}/select", {"selected": False}))
    ok(DOCTOR.post(f"/evidence/{item['id']}/select", {"selected": True}))
    after = next(e for e in ok(DOCTOR.get(f"/referrals/{rid}/evidence")) if e["id"] == item["id"])
    assert after["selection_source"] == "staff" and after["selected_by"]  # "staff" = a person's choice

    # Send.
    ok(STAFF.post(f"/referrals/{rid}/prepared", {"expected_version": _ref(rid)["row_version"]}))
    doctor_review(rid)
    ok(STAFF.post(f"/referrals/{rid}/send", {"expected_version": _ref(rid)["row_version"]}))
    wait_for(lambda: _ref(rid)["status"] == "submitted", 60, what="delivery")
    wait_for(lambda: all(b["status"] == "sent" for b in ok(STAFF.get(f"/referrals/{rid}/delivery"))), 60,
             what="package and the clinic's copy delivered")
    kinds = {b["kind"] for b in ok(STAFF.get(f"/referrals/{rid}/delivery"))}
    assert {"deliver_package", "sender_copy"} <= kinds

    pkg = ok(DOCTOR.get(f"/referrals/{rid}/packages/1"))
    env, manifest = pkg["envelope"], pkg["manifest"]
    assert manifest["content_hash"] == pkg["content_hash"] and manifest["evidence"]
    assert env["selection"]["counts"]["selected"] == len(env["evidence"])
    assert all(s["label"] == "AI suggestion, not verified" for s in env["ai_suggestions"])
    assert "display" not in json.dumps(manifest["evidence"])  # references only, no clinical values

    # The clinic's own system holds a copy, which matches the fingerprint.
    own = ok(DOCTOR.post(f"/referrals/{rid}/packages/1/verify-own-copy"))
    assert own["result"] == "match"
    tampered = {**own["copy"], "reason": "changed"}
    assert ok(STAFF.post(f"/referrals/{rid}/packages/1/verify", {"package": tampered}))["result"] == "mismatch"

    # Purge (normally run by the worker once the time is up): content goes, reference and fingerprint stay.
    script = ("from app.db import SessionLocal\nfrom app.models import Referral\n"
              "from app.lifecycle.working_set import blockers, purge\n"
              f"db = SessionLocal()\nr = db.get(Referral, {rid})\nassert not blockers(db, r), blockers(db, r)\n"
              "purge(db, r)\ndb.commit()\n")
    compose("exec", "-T", "central", "python", "-c", script)
    ref = _ref(rid)
    assert ref["working_set_purged_at"] and ref["reference"]
    pkg = ok(DOCTOR.get(f"/referrals/{rid}/packages/1"))
    assert pkg["content_purged_at"] and pkg["envelope"]["purged"] and "evidence" not in pkg["envelope"]
    assert pkg["manifest"]["evidence"] and pkg["content_hash"] == manifest["content_hash"]
    assert all(e["display"] != item["display"] for e in ok(DOCTOR.get(f"/referrals/{rid}/evidence")))
    # the clinic's own copy still verifies against the kept fingerprint
    assert ok(DOCTOR.post(f"/referrals/{rid}/packages/1/verify-own-copy"))["result"] == "match"
    actions = {a["action"] for a in ok(STAFF.get(f"/referrals/{rid}/audit"))}
    assert {"retention.purge_working_set", "package.verify_own_copy"} <= actions

    # Retrieving again (e.g. for an amendment) fetches fresh copies; removed content is never reused.
    ok(STAFF.post(f"/referrals/{rid}/retrieve"))
    again = ok(DOCTOR.get(f"/referrals/{rid}/evidence"))
    assert again and all(e["display"] != "[removed: working set ended]" for e in again)
    assert not _ref(rid)["working_set_purged_at"]


SEED = {"P1": ("Rubina", "akuh", "dentistry"), "P2": ("Tariq", "ziauddin", "cardiology"),
        "P3": ("Gondal", "akuh", "orthopaedics"), "P4": ("Shazia", "ziauddin", "gastro_hepatology"),
        "P5": ("Imtiaz", "akuh", "general_surgery")}
SEED_SOURCE = {"clinic-ali": "drali", "aku": "akuh"}


@pytest.mark.parametrize("code", sorted(SEED))
def test_default_selection_matches_seed_expected_view(code):
    """The rule-based default (no model) selects exactly the visits from the last 6 months listed in
    the seed's expected_retrieval_view; older visits are retrieved but start unselected."""
    from pathlib import Path

    from conftest import ROOT

    seed = json.loads(next(Path(ROOT, "seed-data", "patients").glob(f"{code}_*.json")).read_text(encoding="utf-8"))
    name, dest, dept = SEED[code]
    r = new_referral(name, dest, dept, None)
    used = {x["source_institution"] for x in ok(STAFF.post(f"/referrals/{r['id']}/retrieve"))["results"]
            if x["status"] in ("successful", "partial")}
    # a source beyond MAX_RETRIEVAL_SOURCES (or unavailable) is not read, so its visits are not expected
    expected = {v["date"] for v in seed["expected_retrieval_view"].get("visits_last_6_months", [])
                if SEED_SOURCE.get(v["source"], v["source"]) in used}
    visits = [e for e in ok(STAFF.get(f"/referrals/{r['id']}/evidence", params={"category": "visit"})) if e["origin"] == "source"]
    selected = {(e["clinical_time"] or "")[:10] for e in visits if e["selected"]}
    assert selected == expected, (selected, expected)
    assert all(e["in_default"] == e["selected"] for e in visits if e["selection_source"] == "default")
