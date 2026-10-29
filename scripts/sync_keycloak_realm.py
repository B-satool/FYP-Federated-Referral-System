"""Add to a running local Keycloak realm what the repository's realm file has and the realm lacks.

Keycloak imports infra/keycloak/import/referral-realm.json only on its first start. When the file gains roles,
user-profile attributes, token mappers, demo accounts or service-account permissions, an existing local realm
does not see them. This script adds only what is missing. It never deletes or changes anything that exists (use
scripts/refresh-keycloak-realm.ps1 -Force to start the realm over instead). Local development only; synthetic
demo accounts only.

Usage (stack running):  python scripts/sync_keycloak_realm.py
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
REALM_FILE = ROOT / "infra" / "keycloak" / "import" / "referral-realm.json"
BASE = os.environ.get("KEYCLOAK_URL", "http://localhost:8080")


def env() -> dict:
    out = dict(os.environ)
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            out.setdefault(k.strip(), v.strip())
    out.setdefault("WEB_ORIGIN", "http://localhost:3000")
    return out


def main() -> int:
    e = env()
    raw = REALM_FILE.read_text(encoding="utf-8")
    realm = json.loads(re.sub(r"\$\{(\w+)\}", lambda m: json.dumps(e.get(m.group(1), ""))[1:-1], raw))
    name = realm["realm"]
    tok = httpx.post(f"{BASE}/realms/master/protocol/openid-connect/token", timeout=15,
                     data={"grant_type": "password", "client_id": "admin-cli", "username": "admin",
                           "password": e["KEYCLOAK_ADMIN_PASSWORD"]}).json()["access_token"]
    kc = httpx.Client(base_url=f"{BASE}/admin/realms/{name}", headers={"Authorization": f"Bearer {tok}"}, timeout=30)
    added: list[str] = []

    have_roles = {r["name"] for r in kc.get("/roles").json()}
    for role in realm["roles"]["realm"]:
        if role["name"] not in have_roles:
            kc.post("/roles", json=role).raise_for_status()
            added.append(f"realm role {role['name']}")

    # user-profile attributes (e.g. cnic): add missing attribute definitions, keep everything else
    profile = kc.get("/users/profile").json()
    have_attrs = {a["name"] for a in profile.get("attributes", [])}
    wanted = []
    for comp in realm.get("components", {}).get("org.keycloak.userprofile.UserProfileProvider", []):
        for cfg in comp.get("config", {}).get("kc.user.profile.config", []):
            wanted += json.loads(cfg).get("attributes", [])
    missing = [a for a in wanted if a["name"] not in have_attrs]
    if missing:
        profile["attributes"] = profile.get("attributes", []) + missing
        kc.put("/users/profile", json=profile).raise_for_status()
        added += [f"user attribute {a['name']}" for a in missing]

    clients = {c["clientId"]: c for c in kc.get("/clients").json()}
    for c in realm["clients"]:
        live = clients.get(c["clientId"])
        if live is None:
            continue  # a missing client is not created here; refresh the realm instead
        have = {m["name"] for m in kc.get(f"/clients/{live['id']}/protocol-mappers/models").json()}
        for m in c.get("protocolMappers", []):
            if m["name"] not in have:
                kc.post(f"/clients/{live['id']}/protocol-mappers/models", json=m).raise_for_status()
                added.append(f"token mapper {c['clientId']}/{m['name']}")

    groups = {}

    def walk(gs, prefix=""):
        for g in gs:
            groups[f"{prefix}/{g['name']}"] = g["id"]
            walk(g.get("subGroups") or kc.get(f"/groups/{g['id']}/children").json() if g.get("subGroupCount") else
                 g.get("subGroups", []), f"{prefix}/{g['name']}")

    walk(kc.get("/groups", params={"briefRepresentation": "false"}).json())
    roles = {r["name"]: r for r in kc.get("/roles").json()}
    rm = next((c for c in clients.values() if c["clientId"] == "realm-management"), None)
    for u in realm["users"]:
        if u.get("serviceAccountClientId"):
            live = clients.get(u["serviceAccountClientId"])
            if live is None or rm is None:
                continue
            sa = kc.get(f"/clients/{live['id']}/service-account-user").json()
            have = {r["name"] for r in kc.get(f"/users/{sa['id']}/role-mappings/clients/{rm['id']}").json()}
            want = [r for r in kc.get(f"/clients/{rm['id']}/roles").json()
                    if r["name"] in set(u.get("clientRoles", {}).get("realm-management", [])) - have]
            if want:
                kc.post(f"/users/{sa['id']}/role-mappings/clients/{rm['id']}", json=want).raise_for_status()
                added += [f"{u['username']}: realm-management/{r['name']}" for r in want]
            continue
        if kc.get("/users", params={"username": u["username"], "exact": "true"}).json():
            continue
        body = {k: u[k] for k in ("username", "enabled", "emailVerified", "firstName", "lastName", "email",
                                  "attributes", "credentials") if k in u}
        kc.post("/users", json=body).raise_for_status()
        uid = kc.get("/users", params={"username": u["username"], "exact": "true"}).json()[0]["id"]
        rr = [roles[r] for r in u.get("realmRoles", []) if r in roles]
        if rr:
            kc.post(f"/users/{uid}/role-mappings/realm", json=rr).raise_for_status()
        for g in u.get("groups", []):
            if g in groups:
                kc.put(f"/users/{uid}/groups/{groups[g]}").raise_for_status()
        added.append(f"user {u['username']}")
    print("\n".join(added) if added else "Nothing missing: the running realm already has everything in the file.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
