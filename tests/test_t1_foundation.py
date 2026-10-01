"""T1 - running foundation and access control (FR-01 to FR-05)."""
from __future__ import annotations

import time

import httpx
from conftest import new_referral
from helpers import CENTRAL, CLINIC, LAB, SPECIALIST, central, ok, token


def test_all_services_ready():
    for base in (CENTRAL, CLINIC, LAB, SPECIALIST):
        assert httpx.get(base + "/ready", timeout=10).status_code == 200, base


def test_unauthenticated_requests_rejected():
    for base, path in ((CENTRAL, "/referrals"), (CLINIC, "/patients"), (LAB, "/fhir/patients/LB-5531/results")):
        assert httpx.get(base + path, timeout=10).status_code == 401
    forged = "Bearer eyJhbGciOiJub25lIn0.eyJzdWIiOiJ4In0."
    assert httpx.get(CENTRAL + "/me", headers={"Authorization": forged}, timeout=10).status_code == 401


def test_me_reports_institution_and_role():
    me = ok(central("dr.malik").get("/me"))
    assert me["institution_id"] == "clinic-a" and "clinician" in me["roles"]


def test_cross_institution_denied_at_central():
    ref = new_referral("MR-418", procedure=None)
    other = central("staff.x").get(f"/referrals/{ref['id']}")
    assert other.status_code == 403
    listed = ok(central("staff.x").get("/referrals"))
    assert all(r["source_institution"] == "clinic-x" for r in listed)


def test_admin_has_no_implicit_clinical_access():
    ref = new_referral("MR-418", procedure=None)
    assert central("admin.a").get(f"/referrals/{ref['id']}").status_code == 403


def test_source_level_authorization():
    hdr = lambda u: {"Authorization": f"Bearer {token(u)}"}  # noqa: E731
    # own clinician allowed
    assert httpx.get(f"{CLINIC}/fhir/patients/MR-102/records", headers=hdr("dr.malik"), timeout=10).status_code == 200
    # another clinic denied by Clinic A's own decision
    assert httpx.get(f"{CLINIC}/fhir/patients/MR-102/records", headers=hdr("staff.x"), timeout=10).status_code == 403
    # Lab B grants Clinic A access to LB-5531 but not to its MR-102 (a different person)
    assert httpx.get(f"{LAB}/fhir/patients/LB-5531/results", headers=hdr("dr.malik"), timeout=10).status_code == 200
    assert httpx.get(f"{LAB}/fhir/patients/MR-102/results", headers=hdr("dr.malik"), timeout=10).status_code == 403
    # clinic staff are not given clinical notes categories they lack (partial, not silent)
    bundle = httpx.get(f"{CLINIC}/fhir/patients/MR-102/records", headers=hdr("staff.a"), timeout=10).json()
    outcomes = [e for e in bundle["entry"] if e["resource"]["resourceType"] == "OperationOutcome"]
    assert outcomes and "conditions" in outcomes[0]["resource"]["issue"][0]["diagnostics"]


def test_disabled_account_loses_access_immediately_and_at_sources():
    admin = central("admin.a")
    users = ok(admin.get("/admin/users"))
    locum = next(u for u in users if u["username"] == "dr.locum")
    t = token("dr.locum", fresh=True)
    h = {"Authorization": f"Bearer {t}"}
    assert httpx.get(CENTRAL + "/me", headers=h, timeout=10).status_code == 200
    try:
        ok(admin.post(f"/admin/users/{locum['id']}/disable", {"reason": "Locum contract ended (test)"}))
        # central: immediate (central account status)
        assert httpx.get(CENTRAL + "/me", headers=h, timeout=10).status_code == 401
        # source: session revoked -> introspection inactive once the short cache expires
        time.sleep(11)
        assert httpx.get(f"{CLINIC}/fhir/patients/MR-102/records", headers=h, timeout=10).status_code == 401
        # cannot obtain a new token either
        r = httpx.post("http://localhost:8080/realms/referral/protocol/openid-connect/token",
                       data={"grant_type": "password", "client_id": "dev-cli", "username": "dr.locum", "password": "demo1234"})
        assert r.status_code in (400, 401)
    finally:
        ok(admin.post(f"/admin/users/{locum['id']}/enable", {"reason": "Restore after test"}))


def test_admin_cannot_manage_other_institution_accounts():
    users = ok(central("admin.a").get("/admin/users"))
    assert all(u["username"] != "lab.b" for u in users)
    lab_users = ok(central("admin.b").get("/admin/users"))
    lab_user = next(u for u in lab_users if u["username"] == "lab.b")
    assert central("admin.a").post(f"/admin/users/{lab_user['id']}/disable", {"reason": "x" * 5}).status_code == 403
