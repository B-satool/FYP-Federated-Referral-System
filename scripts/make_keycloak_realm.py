"""Generates infra/keycloak/import/referral-realm.json for the v2 demo (synthetic accounts).

Run: python scripts/make_keycloak_realm.py infra/keycloak/import/referral-realm.json
Secrets and the demo password stay as ${...} placeholders, filled from .env at import.
"""
import json
import sys
from pathlib import Path

SEED_PATIENTS = Path(__file__).resolve().parents[1] / "seed-data" / "patients"

INSTITUTIONS = {
    "drali": ["general_practice", "clinic_tests"],
    "ziauddin": ["cardiology", "gastro_hepatology", "radiology", "cardiac_diagnostics", "laboratory"],
    "akuh": ["dentistry", "orthopaedics", "general_surgery", "radiology", "laboratory"],
    "chughtai": ["laboratory", "radiology"],
}
PROVIDERS = ["drali", "chughtai", "ziauddin", "akuh"]

USERS = [
    # username, first, last, roles, group path
    ("dr.ali", "Dr Ali", "Raza", ["clinician"], "/drali/general_practice"),
    ("staff.ali", "Hina", "Raza", ["clinic_staff"], "/drali/general_practice"),
    ("tech.ali", "Bilal", "Ahmed", ["diagnostics_staff"], "/drali/clinic_tests"),
    ("admin.ali", "Adeel", "Shah", ["institution_admin"], "/drali"),
    ("dr.asma", "Dr Asma", "Rauf", ["clinician"], "/ziauddin/cardiology"),
    ("dr.irfan", "Dr Irfan", "Siddiqui", ["clinician"], "/ziauddin/gastro_hepatology"),
    ("staff.zia", "Kiran", "Shah", ["clinic_staff"], "/ziauddin"),
    ("rad.zia", "Dr Hira", "Anwar", ["diagnostics_staff"], "/ziauddin/radiology"),
    ("tech.zia", "Usman", "Ali", ["diagnostics_staff"], "/ziauddin/cardiac_diagnostics"),
    ("lab.zia", "Rabia", "Qureshi", ["diagnostics_staff"], "/ziauddin/laboratory"),
    ("dr.faisal", "Dr Faisal", "Haider", ["clinician"], "/akuh/dentistry"),
    ("dr.salman", "Dr Salman", "Akhtar", ["clinician"], "/akuh/orthopaedics"),
    ("dr.naveed", "Dr Naveed", "Baig", ["clinician"], "/akuh/general_surgery"),
    ("staff.aku", "Mariam", "Noor", ["clinic_staff"], "/akuh"),
    ("rad.aku", "Dr Sana", "Javed", ["diagnostics_staff"], "/akuh/radiology"),
    ("lab.aku", "Kamran", "Butt", ["diagnostics_staff"], "/akuh/laboratory"),
    ("admin.aku", "Rabia", "Javed", ["institution_admin"], "/akuh"),
    ("dr.reviewer", "Dr Nadia", "Hassan", ["rule_reviewer"], "/akuh"),
    ("lab.chughtai", "Imran", "Butt", ["diagnostics_staff"], "/chughtai/laboratory"),
    ("rad.chughtai", "Dr Zainab", "Ali", ["diagnostics_staff"], "/chughtai/radiology"),
    ("staff.chughtai", "Ayesha", "Malik", ["clinic_staff"], "/chughtai"),
]


def patient_accounts() -> list[tuple[str, str, str, str]]:
    """One patient account per seed patient: (username, first, last, CNIC). The username is the
    seed file's name slug, e.g. P1_rubina-akhtar.json -> rubina.akhtar."""
    out = []
    for path in sorted(SEED_PATIENTS.glob("P*.json")):
        demo = json.loads(path.read_text(encoding="utf-8"))["demographics"]
        first, _, last = demo["name"].partition(" ")
        out.append((path.stem.split("_", 1)[1].replace("-", "."), first, last, demo["cnic"]))
    return out


# Keycloak 26 keeps only declared user attributes. "cnic" is declared and only administrators can see or
# change it, so a patient can never edit the identity their records are matched on.
USER_PROFILE = {
    "attributes": [
        {"name": "username",
         "validations": {"length": {"min": 3, "max": 255}, "username-prohibited-characters": {},
                         "up-username-not-idn-homograph": {}},
         "permissions": {"view": ["admin", "user"], "edit": ["admin", "user"]}, "multivalued": False},
        {"name": "email", "validations": {"email": {}, "length": {"max": 255}},
         "required": {"roles": ["user"]}, "permissions": {"view": ["admin", "user"], "edit": ["admin", "user"]},
         "multivalued": False},
        {"name": "firstName",
         "validations": {"length": {"max": 255}, "person-name-prohibited-characters": {}},
         "required": {"roles": ["user"]}, "permissions": {"view": ["admin", "user"], "edit": ["admin", "user"]},
         "multivalued": False},
        {"name": "lastName",
         "validations": {"length": {"max": 255}, "person-name-prohibited-characters": {}},
         "required": {"roles": ["user"]}, "permissions": {"view": ["admin", "user"], "edit": ["admin", "user"]},
         "multivalued": False},
        {"name": "cnic", "displayName": "CNIC", "validations": {"length": {"min": 13, "max": 15}},
         "permissions": {"view": ["admin"], "edit": ["admin"]}, "multivalued": False},
    ],
    "groups": [{"name": "user-metadata", "displayHeader": "User metadata",
                "displayDescription": "Attributes, which refer to user metadata"}],
}

CNIC_MAPPER = {"name": "cnic", "protocol": "openid-connect", "protocolMapper": "oidc-usermodel-attribute-mapper",
               "consentRequired": False,
               "config": {"user.attribute": "cnic", "claim.name": "cnic", "jsonType.label": "String",
                          "access.token.claim": "true", "id.token.claim": "false", "userinfo.token.claim": "false",
                          "introspection.token.claim": "true"}}


def aud(client):
    return {"name": f"aud-{client}", "protocol": "openid-connect", "protocolMapper": "oidc-audience-mapper",
            "consentRequired": False, "config": {"included.client.audience": client, "id.token.claim": "false",
                                                 "access.token.claim": "true", "introspection.token.claim": "true"}}


def hardcoded_institution(inst):
    return {"name": "institution", "protocol": "openid-connect", "protocolMapper": "oidc-hardcoded-claim-mapper",
            "consentRequired": False, "config": {"claim.name": "institution_id", "claim.value": inst,
                                                 "jsonType.label": "String", "access.token.claim": "true",
                                                 "id.token.claim": "false", "introspection.token.claim": "true"}}


GROUPS_MAPPER = {"name": "groups", "protocol": "openid-connect", "protocolMapper": "oidc-group-membership-mapper",
                 "consentRequired": False,
                 "config": {"full.path": "true", "claim.name": "groups", "id.token.claim": "true",
                            "access.token.claim": "true", "userinfo.token.claim": "true",
                            "introspection.token.claim": "true"}}
USER_AUDIENCES = ["central-api"] + [f"{p}-api" for p in PROVIDERS]

realm = {
    "realm": "referral",
    "displayName": "Referral Platform (synthetic demo)",
    "enabled": True, "sslRequired": "external", "registrationAllowed": False, "loginWithEmailAllowed": False,
    "accessTokenLifespan": 300, "ssoSessionIdleTimeout": 1800, "ssoSessionMaxLifespan": 36000,
    "bruteForceProtected": True,
    "roles": {"realm": [
        {"name": "clinician", "description": "Doctor: requests referrals, acknowledges medication flags, receives referrals for their department"},
        {"name": "clinic_staff", "description": "Staff: patient links, records, papers and medicines; sends referrals; follow-up"},
        {"name": "diagnostics_staff", "description": "Laboratory, imaging or ECG staff: test and scan orders"},
        {"name": "institution_admin", "description": "Institution administrator (accounts, source access, audit; no clinical access)"},
        {"name": "rule_reviewer", "description": "Clinical reviewer who approves medication rules and medicine names"},
        {"name": "patient", "description": "Patient: sees their own referrals and reads their own records from each institution"},
        {"name": "svc_central", "description": "Central platform service identity"},
        {"name": "svc_provider", "description": "Institution service identity"},
    ]},
    "groups": [{"name": inst, "subGroups": [{"name": d} for d in depts]} for inst, depts in INSTITUTIONS.items()],
    "components": {"org.keycloak.userprofile.UserProfileProvider": [
        {"providerId": "declarative-user-profile", "subComponents": {},
         "config": {"kc.user.profile.config": [json.dumps(USER_PROFILE)]}}]},
    "clients": [
        {"clientId": "referral-web", "name": "Referral web application", "enabled": True, "publicClient": True,
         "standardFlowEnabled": True, "directAccessGrantsEnabled": False, "implicitFlowEnabled": False,
         "redirectUris": ["${WEB_ORIGIN}/*"], "webOrigins": ["${WEB_ORIGIN}"],
         "attributes": {"pkce.code.challenge.method": "S256", "post.logout.redirect.uris": "${WEB_ORIGIN}/*"},
         "protocolMappers": [GROUPS_MAPPER, CNIC_MAPPER] + [aud(a) for a in USER_AUDIENCES]},
        {"clientId": "dev-cli", "name": "Development/test client (password grant; local synthetic demo only)",
         "enabled": True, "publicClient": True, "standardFlowEnabled": False, "directAccessGrantsEnabled": True,
         "protocolMappers": [GROUPS_MAPPER, CNIC_MAPPER] + [aud(a) for a in USER_AUDIENCES]},
        {"clientId": "central-api", "name": "Central referral platform", "enabled": True, "publicClient": False,
         "clientAuthenticatorType": "client-secret", "secret": "${CENTRAL_CLIENT_SECRET}",
         "standardFlowEnabled": False, "directAccessGrantsEnabled": False, "serviceAccountsEnabled": True,
         "protocolMappers": [hardcoded_institution("central-platform")] + [aud(f"{p}-api") for p in PROVIDERS]},
    ] + [
        {"clientId": f"{p}-api", "name": f"{p} institution service", "enabled": True, "publicClient": False,
         "clientAuthenticatorType": "client-secret", "secret": "${" + p.upper() + "_CLIENT_SECRET}",
         "standardFlowEnabled": False, "directAccessGrantsEnabled": False, "serviceAccountsEnabled": True,
         "protocolMappers": [hardcoded_institution(p), aud("central-api")]}
        for p in PROVIDERS
    ],
    "users": [
        {"username": u, "enabled": True, "emailVerified": True, "firstName": f, "lastName": l,
         "email": f"{u}@{g.strip('/').split('/')[0]}.example", "realmRoles": roles, "groups": [g],
         "credentials": [{"type": "password", "value": "${DEMO_USER_PASSWORD}", "temporary": False}]}
        for u, f, l, roles, g in USERS
    ] + [
        # patients belong to no institution; their CNIC is what each institution matches its own record on
        {"username": u, "enabled": True, "emailVerified": True, "firstName": f, "lastName": l,
         "email": f"{u}@patients.example", "realmRoles": ["patient"], "attributes": {"cnic": [cnic]},
         "credentials": [{"type": "password", "value": "${DEMO_USER_PASSWORD}", "temporary": False}]}
        for u, f, l, cnic in patient_accounts()
    ] + [
        {"username": "service-account-central-api", "enabled": True, "serviceAccountClientId": "central-api",
         "realmRoles": ["svc_central"], "clientRoles": {"realm-management": ["view-users", "query-users", "manage-users", "view-realm"]}},
    ] + [
        {"username": f"service-account-{p}-api", "enabled": True, "serviceAccountClientId": f"{p}-api",
         "realmRoles": ["svc_provider"]}
        for p in PROVIDERS
    ],
}

with open(sys.argv[1], "w", encoding="utf-8") as fh:
    json.dump(realm, fh, indent=2)
    fh.write("\n")
print("users:", len(realm["users"]), "clients:", len(realm["clients"]))
