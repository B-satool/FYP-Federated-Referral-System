"""The end-to-end suite (refcommon.e2e): round trips, tamper detection, entry and assertion checks."""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from refcommon import e2e

CANARY = "CANARY-9F3A-NOT-A-REAL-PATIENT"


def test_item_round_trip_and_associated_data_binding():
    dek = e2e.new_dek()
    sealed = e2e.encrypt(dek, CANARY.encode(), e2e.item_aad("REF-1", "it-1", "b1"))
    assert CANARY not in sealed["ciphertext"]
    assert e2e.decrypt(dek, sealed, e2e.item_aad("REF-1", "it-1", "b1")).decode() == CANARY
    for aad in (e2e.item_aad("REF-2", "it-1", "b1"), e2e.item_aad("REF-1", "it-2", "b1"),
                e2e.item_aad("REF-1", "it-1", "b2")):
        with pytest.raises(e2e.CryptoError):
            e2e.decrypt(dek, sealed, aad)  # moved to another referral, item or key version
    with pytest.raises(e2e.CryptoError):
        e2e.decrypt(e2e.new_dek(), sealed, e2e.item_aad("REF-1", "it-1", "b1"))


def test_fresh_nonce_every_time():
    dek = e2e.new_dek()
    a = e2e.encrypt(dek, b"same", "aad")
    b = e2e.encrypt(dek, b"same", "aad")
    assert a["nonce"] != b["nonce"] and a["ciphertext"] != b["ciphertext"]


def test_chunks_cannot_be_reordered_or_truncated():
    dek = e2e.new_dek()
    data = bytes(range(256)) * 50
    chunks = e2e.encrypt_chunks(dek, data, "REF-1", "scan-1", "b1", size=1000)
    assert len(chunks) > 3
    assert e2e.decrypt_chunks(dek, chunks, "REF-1", "scan-1", "b1") == data
    with pytest.raises(e2e.CryptoError):
        e2e.decrypt_chunks(dek, [chunks[1], chunks[0], *chunks[2:]], "REF-1", "scan-1", "b1")
    with pytest.raises(e2e.CryptoError):
        e2e.decrypt_chunks(dek, chunks[:-1], "REF-1", "scan-1", "b1")  # the new last chunk is not marked last


def test_wrap_only_opens_for_its_recipient_and_context():
    alice, bob = e2e.generate_key(), e2e.generate_key()
    dek = e2e.new_dek()
    ctx = e2e.wrap_context("REF-1", "b1", e2e.key_id(e2e.public_spki(alice)))
    w = e2e.wrap(e2e.public_spki(alice), dek, ctx)
    assert e2e.unwrap(alice, w, ctx) == dek
    with pytest.raises(e2e.CryptoError):
        e2e.unwrap(bob, w, ctx)
    with pytest.raises(e2e.CryptoError):
        e2e.unwrap(alice, w, e2e.wrap_context("REF-2", "b1", "x"))


def test_signatures_are_raw_64_bytes_and_detect_changes():
    key = e2e.generate_key()
    obj = e2e.sign_object(key, {"b": 2, "a": "één", "list": [1, None, True]})
    assert len(e2e.b64d(obj["signature"])) == 64
    assert e2e.verify_object(e2e.public_spki(key), obj)
    assert not e2e.verify_object(e2e.public_spki(key), {**obj, "b": 3})
    assert not e2e.verify_object(e2e.public_spki(e2e.generate_key()), obj)
    assert e2e.canonical({"b": 1, "a": [2, {"d": 1, "c": 0}]}) == b'{"a":[2,{"c":0,"d":1}],"b":1}'


def test_passphrase_blob():
    blob = e2e.seal_with_passphrase("correct horse", b"private", iterations=1000)
    assert e2e.open_with_passphrase("correct horse", blob) == b"private"
    with pytest.raises(e2e.CryptoError):
        e2e.open_with_passphrase("wrong", blob)
    assert e2e.PBKDF2_ITERATIONS >= 600_000


def _entry(hospital):
    doctor_enc, doctor_sig = e2e.generate_key(), e2e.generate_key()
    entry = e2e.directory_entry(
        subject_id="doc-1", subject_type="doctor", role="doctor", hospital_id="ziauddin", department="cardiology",
        display_name="Dr Test", enc_public_key=e2e.public_spki(doctor_enc), sig_public_key=e2e.public_spki(doctor_sig),
        key_version=1, valid_days=30, issued_by="ziauddin", signer_key_id=e2e.key_id(e2e.public_spki(hospital)))
    return e2e.sign_object(hospital, entry)


def test_directory_entry_checks():
    hospital = e2e.generate_key()
    pinned = e2e.public_spki(hospital)
    entry = _entry(hospital)
    assert e2e.check_entry(entry, pinned) is None
    assert "signature" in e2e.check_entry({**entry, "department": "psychiatry"}, pinned)
    assert e2e.check_entry({k: v for k, v in entry.items() if k != "signature"}, pinned)
    impostor = e2e.generate_key()
    forged = e2e.sign_object(impostor, {**entry, "signer_key_id": e2e.key_id(pinned)})
    assert e2e.check_entry(forged, pinned) == "issuer signature is missing or invalid"
    assert e2e.check_entry(entry, e2e.public_spki(impostor)) == "signed by a key that is not the issuer's pinned key"
    later = datetime.now(timezone.utc) + timedelta(days=40)
    assert e2e.check_entry(entry, pinned, at=later) == "outside its validity period"


def test_revocation_signature():
    hospital = e2e.generate_key()
    pinned = e2e.public_spki(hospital)
    rev = e2e.sign_object(hospital, e2e.revocation(subject_id="doc-1", enc_key_id="ab", key_version=1, reason="left",
                                                   issued_by="ziauddin", signer_key_id=e2e.key_id(pinned)))
    assert e2e.check_revocation(rev, pinned)
    assert not e2e.check_revocation({**rev, "subject_id": "doc-2"}, pinned)


def test_assertions():
    key = e2e.generate_key()
    pub = e2e.public_spki(key)
    token = e2e.make_assertion(key, issuer="hub", audience="ziauddin", claims={"refx": {"purpose": "TREAT"}})
    claims = e2e.verify_assertion(token, pub, audience="ziauddin", issuer="hub")
    assert claims["refx"]["purpose"] == "TREAT" and claims["jti"]
    with pytest.raises(e2e.CryptoError, match="audience"):
        e2e.verify_assertion(token, pub, audience="akuh", issuer="hub")
    with pytest.raises(e2e.CryptoError, match="signature"):
        e2e.verify_assertion(token, e2e.public_spki(e2e.generate_key()), audience="ziauddin", issuer="hub")
    old = e2e.make_assertion(key, issuer="hub", audience="ziauddin", ttl=-100)
    with pytest.raises(e2e.CryptoError, match="expired"):
        e2e.verify_assertion(old, pub, audience="ziauddin", issuer="hub")
    now = int(time.time())
    long_lived = jwt.encode({"iss": "hub", "sub": "hub", "aud": "ziauddin", "iat": now, "exp": now + 86400, "jti": "x"},
                            key, algorithm="ES256")
    with pytest.raises(e2e.CryptoError, match="lifetime"):
        e2e.verify_assertion(long_lived, pub, audience="ziauddin", issuer="hub")
    assert e2e.assertion_issuer(token)[0] == "hub"


def test_store_key_needs_a_real_secret():
    with pytest.raises(e2e.CryptoError):
        e2e.store_key("short")
    assert len(e2e.store_key("a-long-enough-secret")) == 32
