"""End-to-end encryption suite `refx-p256-v1` (docs/crypto.md), shared by the institution adapters, the platform
and the tests. The browser implements the same suite with WebCrypto (web/src/crypto/suite.ts); both must stay
byte-compatible, and tests/test_e2e_interop.py checks that.

Every primitive is a call into the `cryptography` library: AES-256-GCM, ECDH and ECDSA on P-256, HKDF-SHA-256,
PBKDF2-HMAC-SHA-256. Nothing here implements a cipher, a curve or a MAC.

Encodings: binary values (keys, nonces, ciphertext, signatures) are standard base64 with padding. Public keys
are SPKI DER. Signatures are raw r||s (64 bytes, IEEE P1363), as WebCrypto produces. Signed JSON objects are
signed over their canonical form (keys sorted, no spaces, UTF-8) without the `signature` field, and must not
contain floating-point numbers (Python and JavaScript print them differently).
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from cryptography.exceptions import InvalidSignature, InvalidTag
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature, encode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

SUITE = "refx-p256-v1"
WRAP_ALG = "ECIES-P256-HKDF-SHA256-A256GCM"
PBKDF2_ITERATIONS = 600_000
CHUNK_SIZE = 1024 * 1024  # scans and images are encrypted in 1 MB chunks
ASSERTION_TTL_SECONDS = 300


class CryptoError(Exception):
    """Decryption, unwrapping or verification failed. The message never contains key material or plaintext."""


# --------------------------------------------------------------------------- encoding
def b64e(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def b64d(text: str) -> bytes:
    try:
        return base64.b64decode(text, validate=True)
    except (ValueError, TypeError) as exc:
        raise CryptoError("value is not valid base64") from exc


def canonical(obj: Any) -> bytes:
    """Canonical JSON: sorted keys, no whitespace, UTF-8. Same bytes as canonicalJson() in suite.ts."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def unsigned(obj: dict) -> dict:
    return {k: v for k, v in obj.items() if k != "signature"}


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def iso_in(days: int) -> str:
    return (datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=days)).isoformat().replace("+00:00", "Z")


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


# --------------------------------------------------------------------------- keys
def generate_key() -> ec.EllipticCurvePrivateKey:
    """A P-256 key pair. The same curve serves ECDH (encryption keys) and ECDSA (signing keys); the suite never
    uses one key pair for both purposes."""
    return ec.generate_private_key(ec.SECP256R1())


def public_spki(key: ec.EllipticCurvePrivateKey | ec.EllipticCurvePublicKey) -> str:
    pub = key.public_key() if isinstance(key, ec.EllipticCurvePrivateKey) else key
    return b64e(pub.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo))


def load_public(spki_b64: str) -> ec.EllipticCurvePublicKey:
    try:
        key = serialization.load_der_public_key(b64d(spki_b64))
    except ValueError as exc:
        raise CryptoError("public key is not a valid SPKI key") from exc
    if not isinstance(key, ec.EllipticCurvePublicKey) or key.curve.name != "secp256r1":
        raise CryptoError("public key is not a P-256 key")
    return key


def private_pkcs8(key: ec.EllipticCurvePrivateKey) -> bytes:
    return key.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())


def load_private(pkcs8: bytes) -> ec.EllipticCurvePrivateKey:
    try:
        key = serialization.load_der_private_key(pkcs8, password=None)
    except ValueError as exc:
        raise CryptoError("private key is not a valid PKCS#8 key") from exc
    if not isinstance(key, ec.EllipticCurvePrivateKey) or key.curve.name != "secp256r1":
        raise CryptoError("private key is not a P-256 key")
    return key


def key_id(spki_b64: str) -> str:
    """Short, stable identifier of a public key: the first 16 hex characters of SHA-256 over its SPKI bytes."""
    return sha256_hex(b64d(spki_b64))[:16]


def fingerprint(spki_b64: str) -> str:
    """What a person compares: the key id in groups of four ("ab12 cd34 ef56 7890")."""
    kid = key_id(spki_b64)
    return " ".join(kid[i:i + 4] for i in range(0, len(kid), 4))


# --------------------------------------------------------------------------- signatures
def sign_bytes(key: ec.EllipticCurvePrivateKey, data: bytes) -> str:
    r, s = decode_dss_signature(key.sign(data, ec.ECDSA(hashes.SHA256())))
    return b64e(r.to_bytes(32, "big") + s.to_bytes(32, "big"))


def verify_bytes(public: ec.EllipticCurvePublicKey | str, data: bytes, signature_b64: str) -> bool:
    pub = load_public(public) if isinstance(public, str) else public
    try:
        raw = b64d(signature_b64)
    except CryptoError:
        return False
    if len(raw) != 64:
        return False
    der = encode_dss_signature(int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big"))
    try:
        pub.verify(der, data, ec.ECDSA(hashes.SHA256()))
    except InvalidSignature:
        return False
    return True


def sign_object(key: ec.EllipticCurvePrivateKey, obj: dict) -> dict:
    """The object with its `signature` over the canonical form of everything else."""
    body = unsigned(obj)
    return {**body, "signature": sign_bytes(key, canonical(body))}


def verify_object(public: ec.EllipticCurvePublicKey | str, obj: dict) -> bool:
    sig = obj.get("signature")
    if not isinstance(sig, str):
        return False
    return verify_bytes(public, canonical(unsigned(obj)), sig)


# --------------------------------------------------------------------------- content encryption
def new_dek() -> bytes:
    return AESGCM.generate_key(bit_length=256)


def item_aad(referral_ref: str, item_id: str, key_version: str) -> str:
    return f"refx/v1|item|{referral_ref}|{item_id}|{key_version}"


def chunk_aad(referral_ref: str, item_id: str, key_version: str, index: int, last: bool) -> str:
    return f"refx/v1|chunk|{referral_ref}|{item_id}|{key_version}|{index}|{1 if last else 0}"


def encrypt(dek: bytes, plaintext: bytes, aad: str) -> dict:
    nonce = os.urandom(12)
    return {"nonce": b64e(nonce), "ciphertext": b64e(AESGCM(dek).encrypt(nonce, plaintext, aad.encode("utf-8")))}


def decrypt(dek: bytes, sealed: dict, aad: str) -> bytes:
    try:
        return AESGCM(dek).decrypt(b64d(sealed["nonce"]), b64d(sealed["ciphertext"]), aad.encode("utf-8"))
    except (InvalidTag, KeyError, ValueError) as exc:
        raise CryptoError("ciphertext could not be decrypted (wrong key, or altered data)") from exc


def encrypt_chunks(dek: bytes, data: bytes, referral_ref: str, item_id: str, key_version: str,
                   size: int = CHUNK_SIZE) -> list[dict]:
    """Large files: one AES-GCM message per chunk; the index and a last-chunk marker are bound in the associated
    data, so chunks cannot be reordered, dropped from the end or swapped between items."""
    parts = [data[i:i + size] for i in range(0, len(data), size)] or [b""]
    return [encrypt(dek, part, chunk_aad(referral_ref, item_id, key_version, i, i == len(parts) - 1))
            for i, part in enumerate(parts)]


def decrypt_chunks(dek: bytes, chunks: list[dict], referral_ref: str, item_id: str, key_version: str) -> bytes:
    return b"".join(decrypt(dek, c, chunk_aad(referral_ref, item_id, key_version, i, i == len(chunks) - 1))
                    for i, c in enumerate(chunks))


# --------------------------------------------------------------------------- key wrapping (ECIES on P-256)
def _wrap_key_material(shared: bytes, epk_spki: bytes, context: str) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=epk_spki,
                info=f"refx/v1|wrap|{context}".encode("utf-8")).derive(shared)


def wrap_context(referral_ref: str, key_version: str, recipient_key_id: str) -> str:
    return f"{referral_ref}|{key_version}|{recipient_key_id}"


def group_context(hospital_id: str, department: str, group_version: int, member_key_id: str) -> str:
    return f"group|{hospital_id}|{department}|{group_version}|{member_key_id}"


def wrap(recipient_public: ec.EllipticCurvePublicKey | str, secret: bytes, context: str) -> dict:
    """Encrypt a data key (or a group private key) to one recipient's encryption public key."""
    pub = load_public(recipient_public) if isinstance(recipient_public, str) else recipient_public
    eph = generate_key()
    epk = eph.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    kek = _wrap_key_material(eph.exchange(ec.ECDH(), pub), epk, context)
    nonce = os.urandom(12)
    return {"alg": WRAP_ALG, "epk": b64e(epk), "nonce": b64e(nonce),
            "ct": b64e(AESGCM(kek).encrypt(nonce, secret, context.encode("utf-8")))}


def unwrap(recipient_private: ec.EllipticCurvePrivateKey, wrapped: dict, context: str) -> bytes:
    try:
        if wrapped.get("alg") != WRAP_ALG:
            raise CryptoError("unknown key-wrapping algorithm")
        epk_bytes = b64d(wrapped["epk"])
        epk = serialization.load_der_public_key(epk_bytes)
        kek = _wrap_key_material(recipient_private.exchange(ec.ECDH(), epk), epk_bytes, context)
        return AESGCM(kek).decrypt(b64d(wrapped["nonce"]), b64d(wrapped["ct"]), context.encode("utf-8"))
    except (InvalidTag, KeyError, ValueError, TypeError) as exc:
        raise CryptoError("wrapped key could not be opened (not addressed to this key, or altered)") from exc


# --------------------------------------------------------------------------- passphrase / secret protected blobs
def seal_with_passphrase(passphrase: str, secret: bytes, iterations: int = PBKDF2_ITERATIONS) -> dict:
    salt, nonce = os.urandom(16), os.urandom(12)
    key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=iterations).derive(passphrase.encode("utf-8"))
    return {"kdf": "PBKDF2-SHA256", "iter": iterations, "salt": b64e(salt), "nonce": b64e(nonce),
            "ct": b64e(AESGCM(key).encrypt(nonce, secret, b"refx/v1|keyblob"))}


def open_with_passphrase(passphrase: str, blob: dict) -> bytes:
    try:
        key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=b64d(blob["salt"]),
                         iterations=int(blob["iter"])).derive(passphrase.encode("utf-8"))
        return AESGCM(key).decrypt(b64d(blob["nonce"]), b64d(blob["ct"]), b"refx/v1|keyblob")
    except (InvalidTag, KeyError, ValueError) as exc:
        raise CryptoError("wrong passphrase, or the key file is damaged") from exc


def store_key(secret: str) -> bytes:
    """AES key for a service's own key store, derived from its configured secret (HKDF, fixed label)."""
    if len(secret) < 16:
        raise CryptoError("key-store secret is too short (at least 16 characters)")
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=b"refx/v1|keystore",
                info=b"refx/v1|keystore|aes").derive(secret.encode("utf-8"))


# --------------------------------------------------------------------------- directory entries
ENTRY_TYPE = "refx.directory.entry/v1"
REVOCATION_TYPE = "refx.directory.revocation/v1"


def directory_entry(*, subject_id: str, subject_type: str, role: str, hospital_id: str | None, department: str | None,
                    display_name: str, enc_public_key: str, sig_public_key: str | None, key_version: int,
                    valid_days: int, issued_by: str, signer_key_id: str, patient_cnic: str | None = None) -> dict:
    entry = {"type": ENTRY_TYPE, "suite": SUITE, "subject_id": subject_id, "subject_type": subject_type, "role": role,
             "hospital_id": hospital_id, "department": department, "display_name": display_name,
             "enc_public_key": enc_public_key, "enc_key_id": key_id(enc_public_key),
             "sig_public_key": sig_public_key, "key_version": key_version, "valid_from": now_iso(),
             "valid_to": iso_in(valid_days), "issued_by": issued_by, "signer_key_id": signer_key_id}
    if patient_cnic is not None:
        entry["patient_cnic"] = patient_cnic
    return entry


def revocation(*, subject_id: str, enc_key_id: str, key_version: int, reason: str, issued_by: str,
               signer_key_id: str) -> dict:
    return {"type": REVOCATION_TYPE, "subject_id": subject_id, "enc_key_id": enc_key_id, "key_version": key_version,
            "revoked_at": now_iso(), "reason": reason, "issued_by": issued_by, "signer_key_id": signer_key_id}


def check_entry(entry: dict, issuer_public: str, *, at: datetime | None = None) -> str | None:
    """Why this directory entry must not be used, or None if it is valid: signed by its issuer's pinned key,
    inside its validity period, and internally consistent."""
    if entry.get("type") != ENTRY_TYPE or entry.get("suite") != SUITE:
        return "not a directory entry of this suite"
    if entry.get("signer_key_id") != key_id(issuer_public):
        return "signed by a key that is not the issuer's pinned key"
    if not verify_object(issuer_public, entry):
        return "issuer signature is missing or invalid"
    try:
        if entry.get("enc_key_id") != key_id(entry["enc_public_key"]):
            return "key id does not match the key"
        load_public(entry["enc_public_key"])
        if entry.get("sig_public_key"):
            load_public(entry["sig_public_key"])
        now = at or datetime.now(timezone.utc)
        if not parse_iso(entry["valid_from"]) <= now + timedelta(minutes=5) or now > parse_iso(entry["valid_to"]):
            return "outside its validity period"
    except (KeyError, ValueError, CryptoError):
        return "malformed entry"
    return None


def check_revocation(rev: dict, issuer_public: str) -> bool:
    return rev.get("type") == REVOCATION_TYPE and rev.get("signer_key_id") == key_id(issuer_public) \
        and verify_object(issuer_public, rev)


# --------------------------------------------------------------------------- signed package manifests (spec v4 5.8)
MANIFEST_TYPE = "refx.package.manifest/v1"
MANIFEST_ITEM_KEYS = ("batch_id", "item_id", "kind", "title", "content_hash", "ciphertext_hash")


def package_manifest(*, referral: str, version: int, signer_subject: str, signer_sig_public: str,
                     signer_hospital: str | None, recipient_hospital: str, recipient_department: str,
                     group_enc_public: str, group_key_version: int, items: list[dict],
                     patient_enc_public: str | None = None) -> dict:
    """The unsigned manifest a doctor's device signs on approval: the ordered items (each with the SHA-256 of its
    plaintext and of its stored ciphertext), the receiving department's group key, and the referral. The signature
    covers the plaintext hashes, so anyone holding a decrypted copy can check it is what was approved."""
    return {"type": MANIFEST_TYPE, "suite": SUITE, "referral": referral, "version": version, "created_at": now_iso(),
            "signer": {"subject_id": signer_subject, "sig_key_id": key_id(signer_sig_public),
                       "hospital_id": signer_hospital},
            "recipient": {"hospital_id": recipient_hospital, "department": recipient_department,
                          "group_key_id": key_id(group_enc_public), "key_version": group_key_version},
            "patient_key_id": key_id(patient_enc_public) if patient_enc_public else None,
            "items": [{k: it.get(k) for k in MANIFEST_ITEM_KEYS} for it in items]}


def check_copy(manifest: dict, signer_sig_public: str, plaintexts: dict[str, bytes]) -> list[str]:
    """What is wrong with a decrypted copy against its signed manifest (empty if it verifies): the signature, then
    each listed item's plaintext hash. `plaintexts` maps item ids to their decrypted bytes."""
    if manifest.get("type") != MANIFEST_TYPE or not verify_object(signer_sig_public, manifest):
        return ["the manifest signature does not verify"]
    problems = []
    for it in manifest.get("items", []):
        data = plaintexts.get(it["item_id"])
        if data is None:
            problems.append(f"{it['item_id']}: missing from the copy")
        elif sha256_hex(data) != it["content_hash"]:
            problems.append(f"{it['item_id']}: content differs from what was approved")
    return problems


# --------------------------------------------------------------------------- machine-to-machine assertions (ES256)
def make_assertion(key: ec.EllipticCurvePrivateKey, *, issuer: str, audience: str, claims: dict | None = None,
                   ttl: int = ASSERTION_TTL_SECONDS) -> str:
    """A short-lived signed request assertion (SMART Backend Services key model: ES256, iss = sub = the caller,
    aud = the callee, exp within minutes, a unique jti)."""
    now = int(time.time())
    payload = {"iss": issuer, "sub": issuer, "aud": audience, "iat": now, "exp": now + ttl, "jti": str(uuid.uuid4()),
               **(claims or {})}
    return jwt.encode(payload, key, algorithm="ES256", headers={"kid": key_id(public_spki(key))})


def assertion_issuer(token: str) -> tuple[str | None, str | None]:
    """(iss, kid) read without verification, only to choose which pinned key to verify with."""
    try:
        return jwt.decode(token, options={"verify_signature": False}).get("iss"), jwt.get_unverified_header(token).get("kid")
    except jwt.PyJWTError:
        return None, None


def verify_assertion(token: str, public_spki_b64: str, *, audience: str, issuer: str,
                     max_ttl: int = ASSERTION_TTL_SECONDS) -> dict:
    """Signature, audience, issuer, expiry and a bounded lifetime. Replay (jti) is checked by the caller, which
    keeps the store of seen ids. Raises CryptoError with the reason."""
    try:
        claims = jwt.decode(token, load_public(public_spki_b64), algorithms=["ES256"], audience=audience, issuer=issuer,
                            options={"require": ["iss", "sub", "aud", "exp", "iat", "jti"]}, leeway=30)
    except jwt.ExpiredSignatureError as exc:
        raise CryptoError("assertion expired") from exc
    except jwt.InvalidAudienceError as exc:
        raise CryptoError("assertion is for another audience") from exc
    except jwt.InvalidIssuerError as exc:
        raise CryptoError("assertion issuer does not match") from exc
    except jwt.InvalidSignatureError as exc:
        raise CryptoError("assertion signature is invalid") from exc
    except jwt.PyJWTError as exc:
        raise CryptoError(f"assertion rejected: {exc}") from exc
    if claims["sub"] != claims["iss"]:
        raise CryptoError("assertion subject must equal its issuer")
    if claims["exp"] - claims["iat"] > max_ttl + 5:
        raise CryptoError("assertion lifetime is longer than allowed")
    return claims


def jwk(public_spki_b64: str) -> dict:
    """The public key as a JWK (for /.well-known/jwks.json)."""
    nums = load_public(public_spki_b64).public_numbers()

    def b64u(n: int) -> str:
        return base64.urlsafe_b64encode(n.to_bytes(32, "big")).decode("ascii").rstrip("=")

    return {"kty": "EC", "crv": "P-256", "x": b64u(nums.x), "y": b64u(nums.y), "use": "sig", "alg": "ES256",
            "kid": key_id(public_spki_b64)}
