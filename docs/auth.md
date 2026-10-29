# Authentication and authorization (architecture spec v4, WP2)

There are three separate questions, each answered by a different mechanism:

| Question | Mechanism | Where |
|---|---|---|
| Who is this person? | **Keycloak** (OIDC, authorization code with PKCE) | Browser sign-in. Each service verifies the token and introspects it. |
| May this institution's system ask that institution's system? | **Signed request assertions**: ES256 JWTs signed with the caller's pinned key | Between the platform and every adapter, in both directions |
| May this record be released, to whom, and for what? | **Consent** (signed by the patient) plus **the institution's own policy** | Each adapter decides, every time |

Sign-in no longer decides record access between institutions. The per-patient sharing grants are gone (approval A3).

## Machine-to-machine requests: SMART Backend Services key model (decision O8)

**Choice:** we follow the key model of **SMART Backend Services** (`private_key_jwt`). We did not choose UDAP B2B.

**What we kept from SMART Backend Services:**
- an asymmetric key per client;
- the public key published as a JWKS (`/.well-known/jwks.json` for the platform);
- an ES256-signed JWT with `iss = sub` = the caller, `aud` = the callee, `exp` within 5 minutes, and a unique `jti`.

**One simplification:** there is no separate token endpoint. The signed assertion itself authorizes **one request**, rather than being exchanged for an access token first. Each request carries a fresh assertion with its own `jti`, which the receiver remembers until it expires (a replay is refused). That gives one round trip per request and no bearer token that could be reused.

**Why not UDAP B2B:** the claim set UDAP's `hl7-b2b` extension carries (organisation, user, purpose, consent) is carried here in a `refx` claim instead. UDAP would add certificate chains and dynamic client registration, which a four-institution demonstration does not need. Moving to UDAP later would change the envelope, not the checks.

### Claims of a records request (platform to adapter)

```json
{
  "iss": "hub", "sub": "hub", "aud": "chughtai", "iat": 1761750000, "exp": 1761750300, "jti": "…uuid…",
  "refx": {
    "org": "drali",                 // which organisation asks
    "practitioner": "<subject id>", // which doctor asks (their hospital-signed key travels in the body)
    "purpose": "TREAT",             // HL7 v3 PurposeOfUse; must be allowed by the participation agreement
    "consent": "CNS-2026-00012",    // link to the patient's Consent (fetched and verified by the adapter)
    "referral": "REF-2026-00034"
  }
}
```

### What the adapter checks, in order

`services/provider/app/m2m.py`, `release.py` and `policy.py`. Every refusal is audited.

1. **Signature** against the platform key pinned at onboarding (never a key from the request). Then audience = this institution, issuer = `hub`, `exp`, a lifetime of at most 5 minutes, and a `jti` not seen before. Any failure returns **401**.
2. **Requesting organisation** is a participant in good standing. **Purpose** is one the agreement allows. The consent, referral and doctor are named. Any failure returns **403**, with the structured refusal `request_incomplete_or_invalid`.
3. **The requesting doctor's key** is signed by the doctor's own hospital (pinned key), belongs to the doctor the assertion names, and is in its validity period. Failure means a refusal plus a `directory.signature_failure` audit entry.
4. **The consent**, fetched through the link with the adapter's own signed request:
   - The patient's key entry must be signed by the pinned platform key.
   - The CNIC must be this patient's.
   - The patient's signature must be valid.
   - The consent must name this institution as custodian and the requester as recipient, cover the purpose and the referral, and be inside its period and not revoked.
   - Failure gives `consent_expired_or_out_of_range` or `request_incomplete_or_invalid`.
5. **The institution's own policy** (`services/provider/policies/<institution>.json`) gives an answer, a structured refusal, or `pending_manual_review`.

### The other direction (adapter to platform)

The adapters publish key-directory entries, fetch consents and push answers after staff review. They sign their assertions with their **hospital signing key**. The platform verifies them against the pinned registry, checks audience `hub`, expiry, lifetime and `jti`, and refuses a suspended participant.

### Pinned keys and onboarding

`scripts/onboard_participants.py` writes `infra/participants/participants.json`. This file pins:
- each institution's hospital signing key;
- the platform's signing key;
- the participation agreement (version, date, allowed purposes);
- each participant's status (`active` or `suspended`).

The file is mounted read-only into every service and served to the browser as `/participants.json`. The platform's API never serves or changes it. Re-run the script after a key changes; it warns when a pinned key differs.

## Keycloak (people)

Unchanged:
- authorization code with PKCE for the web client;
- each service verifies the signature, issuer and its own audience, then introspects the token so that a disabled account stops at once.

**Roles:** `clinician`, `clinic_staff`, `diagnostics_staff`, `institution_admin`, `rule_reviewer`, `patient`.

**Patients:** a patient account carries a `cnic` claim set by an administrator. The patient cannot edit it. Patients belong to no institution.

## Tests

| Test | Coverage | File |
|---|---|---|
| T-TOKEN-1 | Every case in the list above | `tests/test_e2e_consent.py::test_adapter_rejects_bad_request_assertions` |
| T-DIR-1, platform side | | `tests/test_e2e_keys.py` |
| Replay and wrong audience, adapter-to-platform direction | | `tests/test_e2e_keys.py` |
