"""The browser suite (web/src/crypto/suite.ts, WebCrypto under Node) and refcommon.e2e interoperate both ways."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from refcommon import e2e

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "web" / "scripts" / "crypto-interop.ts"
CANARY = "CANARY-9F3A-NOT-A-REAL-PATIENT: Ahmed Khan, 42101-1234567-1, ünïcode ✓"


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is not installed")
def test_python_and_browser_suites_interoperate(tmp_path):
    enc, sig, hospital = e2e.generate_key(), e2e.generate_key(), e2e.generate_key()
    dek = e2e.new_dek()
    ref, item, kv = "REF-2026-00001", "it-7", "batch-3"
    ctx = e2e.wrap_context(ref, kv, e2e.key_id(e2e.public_spki(enc)))
    entry = e2e.sign_object(hospital, e2e.directory_entry(
        subject_id="doc-1", subject_type="doctor", role="doctor", hospital_id="ziauddin", department="cardiology",
        display_name="Dr Test", enc_public_key=e2e.public_spki(enc), sig_public_key=e2e.public_spki(sig),
        key_version=1, valid_days=30, issued_by="ziauddin", signer_key_id=e2e.key_id(e2e.public_spki(hospital))))
    canonical_input = {"z": [1, {"y": None, "x": True}], "a": "é ✓ \n\t\"q\"", "m": -5}
    vectors = {
        "enc_private_pkcs8": e2e.b64e(e2e.private_pkcs8(enc)), "enc_public": e2e.public_spki(enc),
        "enc_key_id": e2e.key_id(e2e.public_spki(enc)), "dek_for_test": e2e.b64e(dek),
        "wrap_context": ctx, "wrapped": e2e.wrap(e2e.public_spki(enc), dek, ctx),
        "plaintext": CANARY, "aad": e2e.item_aad(ref, item, kv), "ref": ref, "item_id": item, "key_version": kv,
        "sealed": e2e.encrypt(dek, CANARY.encode(), e2e.item_aad(ref, item, kv)),
        "chunk_plaintext": CANARY * 3,
        "chunks": e2e.encrypt_chunks(dek, (CANARY * 3).encode(), ref, item, kv, size=10),
        "sig_public": e2e.public_spki(sig), "signed": e2e.sign_object(sig, {"type": "test", "note": CANARY, "n": 1}),
        "canonical_input": canonical_input, "canonical_output": e2e.canonical(canonical_input).decode(),
        "passphrase": "pass phrase ✓", "passphrase_secret": "the private key",
        "passphrase_blob": e2e.seal_with_passphrase("pass phrase ✓", b"the private key", iterations=1000),
        "entry": entry, "hospital_public": e2e.public_spki(hospital),
    }
    src, out = tmp_path / "py.json", tmp_path / "node.json"
    src.write_text(json.dumps(vectors), encoding="utf-8")
    run = subprocess.run(["node", str(SCRIPT), str(src), str(out)], capture_output=True, text=True, timeout=120,
                         encoding="utf-8")
    assert run.returncode == 0, run.stderr + run.stdout
    node = json.loads(out.read_text(encoding="utf-8"))
    assert all(node["checks"].values()) and len(node["checks"]) >= 13
    # what the browser produced opens here
    dek2 = e2e.unwrap(enc, node["wrapped"], ctx)
    assert e2e.b64e(dek2) == node["dek_for_test"]
    assert e2e.decrypt(dek2, node["sealed"], e2e.item_aad(ref, item, kv)).decode() == CANARY
    assert e2e.decrypt_chunks(dek2, node["chunks"], ref, item, kv).decode() == CANARY * 3
    assert e2e.verify_object(node["sig_public"], node["signed"])
    assert not e2e.verify_object(node["sig_public"], {**node["signed"], "n": 4})
    assert e2e.open_with_passphrase("pass phrase ✓", node["passphrase_blob"]) == b"the private key"
