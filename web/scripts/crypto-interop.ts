// Interop check between the browser suite (src/crypto/suite.ts, WebCrypto) and refcommon/e2e.py.
// Run by tests/test_e2e_interop.py:  node web/scripts/crypto-interop.ts <python-vectors.json> <node-output.json>
// Reads what Python produced, checks it here, and writes what this side produced for Python to check.
import { readFileSync, writeFileSync } from "node:fs";
import * as s from "../src/crypto/suite.ts";

const [, , inPath, outPath] = process.argv;
const v = JSON.parse(readFileSync(inPath, "utf8"));
const checks: Record<string, boolean> = {};

const encPriv = await s.importEncPrivate(s.b64d(v.enc_private_pkcs8));
const dek = await s.unwrap(encPriv, v.wrapped, v.wrap_context);
checks.unwrap = s.b64e(dek) === v.dek_for_test;
checks.decrypt = s.fromUtf8(await s.decrypt(dek, v.sealed, v.aad)) === v.plaintext;
checks.decrypt_wrong_aad_fails = await s.decrypt(dek, v.sealed, v.aad + "x").then(() => false, () => true);
checks.chunks = s.fromUtf8(await s.decryptChunks(dek, v.chunks, v.ref, v.item_id, v.key_version)) === v.chunk_plaintext;
checks.verify_object = await s.verifyObject(v.sig_public, v.signed);
checks.verify_tampered_fails = !(await s.verifyObject(v.sig_public, { ...v.signed, note: "changed" }));
checks.canonical = s.canonicalJson(v.canonical_input) === v.canonical_output;
checks.passphrase = s.fromUtf8(await s.openWithPassphrase(v.passphrase, v.passphrase_blob)) === v.passphrase_secret;
checks.entry_valid = (await s.checkEntry(v.entry, v.hospital_public)) === null;
checks.entry_tampered_rejected = (await s.checkEntry({ ...v.entry, department: "psychiatry" }, v.hospital_public)) !== null;
checks.entry_wrong_issuer_rejected = (await s.checkEntry(v.entry, v.sig_public)) !== null;
checks.key_id = (await s.keyId(v.enc_public)) === v.enc_key_id;
checks.public_from_pkcs8 = (await s.publicFromPkcs8(s.b64d(v.enc_private_pkcs8))) === v.enc_public;

// What this side produces for Python to check
const dek2 = s.newDek();
const sig = await s.generateSigningKeyPair();
const out = {
  checks,
  dek_for_test: s.b64e(dek2),
  wrapped: await s.wrap(v.enc_public, dek2, v.wrap_context),
  sealed: await s.encrypt(dek2, s.utf8(v.plaintext), v.aad),
  chunks: await s.encryptChunks(dek2, s.utf8(v.chunk_plaintext), v.ref, v.item_id, v.key_version, 7),
  sig_public: await s.exportSpki(sig.publicKey),
  signed: await s.signObject(sig.privateKey, { type: "test", n: 3, text: v.plaintext, nested: { b: 1, a: [true, null] } }),
  passphrase_blob: await s.sealWithPassphrase(v.passphrase, s.utf8(v.passphrase_secret), 1000),
};
writeFileSync(outPath, JSON.stringify(out));
const failed = Object.entries(checks).filter(([, ok]) => !ok).map(([k]) => k);
if (failed.length) {
  console.error("FAILED: " + failed.join(", "));
  process.exit(1);
}
console.log(`node checks passed: ${Object.keys(checks).length}`);
