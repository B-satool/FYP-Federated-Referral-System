/**
 * End-to-end encryption suite `refx-p256-v1` (docs/crypto.md), browser side.
 *
 * The same suite as libs/common/refcommon/e2e.py, byte for byte: tests/test_e2e_interop.py runs this file under
 * Node against the Python implementation. Every primitive is a WebCrypto call (AES-256-GCM, ECDH and ECDSA on
 * P-256, HKDF-SHA-256, PBKDF2-HMAC-SHA-256); nothing here implements a cipher, a curve or a MAC.
 *
 * This file has no imports, so Node can run it directly (type stripping) for the interop test.
 */

export const SUITE = "refx-p256-v1";
export const WRAP_ALG = "ECIES-P256-HKDF-SHA256-A256GCM";
export const PBKDF2_ITERATIONS = 600_000;
export const CHUNK_SIZE = 1024 * 1024;

const subtle = globalThis.crypto.subtle;
const enc = new TextEncoder();
const dec = new TextDecoder();

export class CryptoError extends Error {}

export type Sealed = { nonce: string; ciphertext: string };
export type Wrapped = { alg: string; epk: string; nonce: string; ct: string };
export type PassphraseBlob = { kdf: string; iter: number; salt: string; nonce: string; ct: string };
export type SignedObject = Record<string, unknown> & { signature?: string };

// --------------------------------------------------------------------------- encoding
export function b64e(bytes: Uint8Array | ArrayBuffer): string {
  const u = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
  let s = "";
  for (let i = 0; i < u.length; i += 0x8000) s += String.fromCharCode(...u.subarray(i, i + 0x8000));
  return btoa(s);
}

export function b64d(text: string): Uint8Array {
  try {
    const s = atob(text);
    const out = new Uint8Array(s.length);
    for (let i = 0; i < s.length; i++) out[i] = s.charCodeAt(i);
    return out;
  } catch {
    throw new CryptoError("value is not valid base64");
  }
}

export const utf8 = (s: string): Uint8Array => enc.encode(s);
export const fromUtf8 = (b: Uint8Array | ArrayBuffer): string => dec.decode(b);

/** Canonical JSON: keys sorted, no whitespace. Same bytes as refcommon.e2e.canonical (no floats allowed). */
export function canonicalJson(value: unknown): string {
  if (value === null || typeof value === "boolean" || typeof value === "string") return JSON.stringify(value);
  if (typeof value === "number") {
    if (!Number.isInteger(value)) throw new CryptoError("signed objects must not contain fractional numbers");
    return String(value);
  }
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (typeof value === "object") {
    const obj = value as Record<string, unknown>;
    const keys = Object.keys(obj).filter((k) => obj[k] !== undefined).sort();
    return `{${keys.map((k) => `${JSON.stringify(k)}:${canonicalJson(obj[k])}`).join(",")}}`;
  }
  throw new CryptoError("value cannot be signed");
}

export function unsigned<T extends SignedObject>(obj: T): Omit<T, "signature"> {
  const { signature: _ignored, ...rest } = obj;
  return rest;
}

export async function sha256Hex(data: Uint8Array | string): Promise<string> {
  const bytes = typeof data === "string" ? utf8(data) : data;
  const digest = new Uint8Array(await subtle.digest("SHA-256", bytes as BufferSource));
  return Array.from(digest, (b) => b.toString(16).padStart(2, "0")).join("");
}

export const randomBytes = (n: number): Uint8Array => globalThis.crypto.getRandomValues(new Uint8Array(n));

// --------------------------------------------------------------------------- keys
export async function keyId(spkiB64: string): Promise<string> {
  return (await sha256Hex(b64d(spkiB64))).slice(0, 16);
}

export async function fingerprint(spkiB64: string): Promise<string> {
  const kid = await keyId(spkiB64);
  return kid.match(/.{1,4}/g)!.join(" ");
}

const EC = { name: "ECDH", namedCurve: "P-256" } as const;
const SIG = { name: "ECDSA", namedCurve: "P-256" } as const;

/** Generated extractable so the private key can be sealed with the passphrase; the session then re-imports it
 * as a non-extractable key. */
export async function generateEncryptionKeyPair(): Promise<CryptoKeyPair> {
  return subtle.generateKey(EC, true, ["deriveBits"]) as Promise<CryptoKeyPair>;
}

export async function generateSigningKeyPair(): Promise<CryptoKeyPair> {
  return subtle.generateKey(SIG, true, ["sign", "verify"]) as Promise<CryptoKeyPair>;
}

/** Device keys: the private halves are non-extractable from the start (the public halves are always exportable). */
export async function generateDeviceKeyPairs(): Promise<{ enc: CryptoKeyPair; sig: CryptoKeyPair }> {
  const enc = (await subtle.generateKey(EC, false, ["deriveBits"])) as CryptoKeyPair;
  const sig = (await subtle.generateKey(SIG, false, ["sign", "verify"])) as CryptoKeyPair;
  return { enc, sig };
}

export async function exportSpki(key: CryptoKey): Promise<string> {
  return b64e(await subtle.exportKey("spki", key));
}

export async function exportPkcs8(key: CryptoKey): Promise<Uint8Array> {
  return new Uint8Array(await subtle.exportKey("pkcs8", key));
}

export async function importEncPublic(spkiB64: string): Promise<CryptoKey> {
  try {
    return await subtle.importKey("spki", b64d(spkiB64) as BufferSource, EC, true, []);
  } catch {
    throw new CryptoError("public key is not a valid P-256 key");
  }
}

export async function importSigPublic(spkiB64: string): Promise<CryptoKey> {
  try {
    return await subtle.importKey("spki", b64d(spkiB64) as BufferSource, SIG, true, ["verify"]);
  } catch {
    throw new CryptoError("public key is not a valid P-256 key");
  }
}

export async function importEncPrivate(pkcs8: Uint8Array, extractable = false): Promise<CryptoKey> {
  return subtle.importKey("pkcs8", pkcs8 as BufferSource, EC, extractable, ["deriveBits"]);
}

export async function importSigPrivate(pkcs8: Uint8Array, extractable = false): Promise<CryptoKey> {
  return subtle.importKey("pkcs8", pkcs8 as BufferSource, SIG, extractable, ["sign"]);
}

/** The public key (SPKI, base64) that belongs to a P-256 private key given as PKCS#8. */
export async function publicFromPkcs8(pkcs8: Uint8Array): Promise<string> {
  const priv = await subtle.importKey("pkcs8", pkcs8 as BufferSource, EC, true, ["deriveBits"]);
  const jwk = await subtle.exportKey("jwk", priv);
  const pub = await subtle.importKey("jwk", { kty: "EC", crv: "P-256", x: jwk.x, y: jwk.y, ext: true }, EC, true, []);
  return exportSpki(pub);
}

// --------------------------------------------------------------------------- signatures
export async function signBytes(key: CryptoKey, data: Uint8Array): Promise<string> {
  return b64e(await subtle.sign({ name: "ECDSA", hash: "SHA-256" }, key, data as BufferSource));
}

export async function verifyBytes(spkiB64: string, data: Uint8Array, signatureB64: string): Promise<boolean> {
  let sig: Uint8Array;
  try {
    sig = b64d(signatureB64);
  } catch {
    return false;
  }
  if (sig.length !== 64) return false;
  const key = await importSigPublic(spkiB64);
  return subtle.verify({ name: "ECDSA", hash: "SHA-256" }, key, sig as BufferSource, data as BufferSource);
}

export async function signObject<T extends SignedObject>(key: CryptoKey, obj: T): Promise<T & { signature: string }> {
  const body = unsigned(obj);
  return { ...(body as T), signature: await signBytes(key, utf8(canonicalJson(body))) };
}

export async function verifyObject(spkiB64: string, obj: SignedObject): Promise<boolean> {
  if (typeof obj.signature !== "string") return false;
  try {
    return await verifyBytes(spkiB64, utf8(canonicalJson(unsigned(obj))), obj.signature);
  } catch {
    return false;
  }
}

// --------------------------------------------------------------------------- content encryption
export const newDek = (): Uint8Array => randomBytes(32);

export const itemAad = (referralRef: string, itemId: string, keyVersion: string) =>
  `refx/v1|item|${referralRef}|${itemId}|${keyVersion}`;

export const chunkAad = (referralRef: string, itemId: string, keyVersion: string, index: number, last: boolean) =>
  `refx/v1|chunk|${referralRef}|${itemId}|${keyVersion}|${index}|${last ? 1 : 0}`;

async function aesKey(raw: Uint8Array, usage: KeyUsage[]): Promise<CryptoKey> {
  return subtle.importKey("raw", raw as BufferSource, { name: "AES-GCM" }, false, usage);
}

export async function encrypt(dek: Uint8Array, plaintext: Uint8Array, aad: string): Promise<Sealed> {
  const nonce = randomBytes(12);
  const ct = await subtle.encrypt({ name: "AES-GCM", iv: nonce as BufferSource, additionalData: utf8(aad) as BufferSource },
    await aesKey(dek, ["encrypt"]), plaintext as BufferSource);
  return { nonce: b64e(nonce), ciphertext: b64e(ct) };
}

export async function decrypt(dek: Uint8Array, sealed: Sealed, aad: string): Promise<Uint8Array> {
  try {
    const pt = await subtle.decrypt({ name: "AES-GCM", iv: b64d(sealed.nonce) as BufferSource, additionalData: utf8(aad) as BufferSource },
      await aesKey(dek, ["decrypt"]), b64d(sealed.ciphertext) as BufferSource);
    return new Uint8Array(pt);
  } catch {
    throw new CryptoError("ciphertext could not be decrypted (wrong key, or altered data)");
  }
}

export async function encryptChunks(dek: Uint8Array, data: Uint8Array, referralRef: string, itemId: string,
  keyVersion: string, size = CHUNK_SIZE): Promise<Sealed[]> {
  const parts: Uint8Array[] = [];
  for (let i = 0; i < data.length; i += size) parts.push(data.subarray(i, i + size));
  if (!parts.length) parts.push(new Uint8Array(0));
  const out: Sealed[] = [];
  for (let i = 0; i < parts.length; i++) {
    out.push(await encrypt(dek, parts[i], chunkAad(referralRef, itemId, keyVersion, i, i === parts.length - 1)));
  }
  return out;
}

export async function decryptChunks(dek: Uint8Array, chunks: Sealed[], referralRef: string, itemId: string,
  keyVersion: string): Promise<Uint8Array> {
  const parts: Uint8Array[] = [];
  for (let i = 0; i < chunks.length; i++) {
    parts.push(await decrypt(dek, chunks[i], chunkAad(referralRef, itemId, keyVersion, i, i === chunks.length - 1)));
  }
  const out = new Uint8Array(parts.reduce((n, p) => n + p.length, 0));
  let at = 0;
  for (const p of parts) {
    out.set(p, at);
    at += p.length;
  }
  return out;
}

// --------------------------------------------------------------------------- key wrapping (ECIES on P-256)
export const wrapContext = (referralRef: string, keyVersion: string, recipientKeyId: string) =>
  `${referralRef}|${keyVersion}|${recipientKeyId}`;

export const groupContext = (hospitalId: string, department: string, groupVersion: number, memberKeyId: string) =>
  `group|${hospitalId}|${department}|${groupVersion}|${memberKeyId}`;

async function kekFrom(shared: ArrayBuffer, epkSpki: Uint8Array, context: string): Promise<CryptoKey> {
  const base = await subtle.importKey("raw", shared, "HKDF", false, ["deriveBits"]);
  const bits = await subtle.deriveBits({ name: "HKDF", hash: "SHA-256", salt: epkSpki as BufferSource,
    info: utf8(`refx/v1|wrap|${context}`) as BufferSource }, base, 256);
  return aesKey(new Uint8Array(bits), ["encrypt", "decrypt"]);
}

/** Encrypt a data key (or a group private key) to one recipient's encryption public key. */
export async function wrap(recipientSpki: string, secret: Uint8Array, context: string): Promise<Wrapped> {
  const recipient = await importEncPublic(recipientSpki);
  const eph = await subtle.generateKey(EC, true, ["deriveBits"]) as CryptoKeyPair;
  const epk = new Uint8Array(await subtle.exportKey("spki", eph.publicKey));
  const shared = await subtle.deriveBits({ name: "ECDH", public: recipient }, eph.privateKey, 256);
  const kek = await kekFrom(shared, epk, context);
  const nonce = randomBytes(12);
  const ct = await subtle.encrypt({ name: "AES-GCM", iv: nonce as BufferSource, additionalData: utf8(context) as BufferSource },
    kek, secret as BufferSource);
  return { alg: WRAP_ALG, epk: b64e(epk), nonce: b64e(nonce), ct: b64e(ct) };
}

export async function unwrap(recipientPrivate: CryptoKey, wrapped: Wrapped, context: string): Promise<Uint8Array> {
  try {
    if (wrapped.alg !== WRAP_ALG) throw new CryptoError("unknown key-wrapping algorithm");
    const epkBytes = b64d(wrapped.epk);
    const epk = await subtle.importKey("spki", epkBytes as BufferSource, EC, false, []);
    const shared = await subtle.deriveBits({ name: "ECDH", public: epk }, recipientPrivate, 256);
    const kek = await kekFrom(shared, epkBytes, context);
    return new Uint8Array(await subtle.decrypt({ name: "AES-GCM", iv: b64d(wrapped.nonce) as BufferSource,
      additionalData: utf8(context) as BufferSource }, kek, b64d(wrapped.ct) as BufferSource));
  } catch {
    throw new CryptoError("wrapped key could not be opened (not addressed to this key, or altered)");
  }
}

// --------------------------------------------------------------------------- passphrase-protected key blobs
export async function sealWithPassphrase(passphrase: string, secret: Uint8Array,
  iterations = PBKDF2_ITERATIONS): Promise<PassphraseBlob> {
  const salt = randomBytes(16);
  const nonce = randomBytes(12);
  const key = await passphraseKey(passphrase, salt, iterations);
  const ct = await subtle.encrypt({ name: "AES-GCM", iv: nonce as BufferSource, additionalData: utf8("refx/v1|keyblob") as BufferSource },
    key, secret as BufferSource);
  return { kdf: "PBKDF2-SHA256", iter: iterations, salt: b64e(salt), nonce: b64e(nonce), ct: b64e(ct) };
}

export async function openWithPassphrase(passphrase: string, blob: PassphraseBlob): Promise<Uint8Array> {
  try {
    const key = await passphraseKey(passphrase, b64d(blob.salt), blob.iter);
    return new Uint8Array(await subtle.decrypt({ name: "AES-GCM", iv: b64d(blob.nonce) as BufferSource,
      additionalData: utf8("refx/v1|keyblob") as BufferSource }, key, b64d(blob.ct) as BufferSource));
  } catch {
    throw new CryptoError("wrong passphrase, or the key file is damaged");
  }
}

async function passphraseKey(passphrase: string, salt: Uint8Array, iterations: number): Promise<CryptoKey> {
  const base = await subtle.importKey("raw", utf8(passphrase) as BufferSource, "PBKDF2", false, ["deriveBits"]);
  const bits = await subtle.deriveBits({ name: "PBKDF2", hash: "SHA-256", salt: salt as BufferSource, iterations }, base, 256);
  return aesKey(new Uint8Array(bits), ["encrypt", "decrypt"]);
}

// --------------------------------------------------------------------------- directory entries
export type DirectoryEntry = {
  type: string; suite: string; subject_id: string; subject_type: "doctor" | "department" | "patient"; role: string;
  hospital_id: string | null; department: string | null; display_name: string; enc_public_key: string;
  enc_key_id: string; sig_public_key: string | null; key_version: number; valid_from: string; valid_to: string;
  issued_by: string; signer_key_id: string; patient_cnic?: string; signature: string;
};

export type Revocation = {
  type: string; subject_id: string; enc_key_id: string; key_version: number; revoked_at: string; reason: string;
  issued_by: string; signer_key_id: string; signature: string;
};

/** Why a directory entry must not be used, or null when it is valid: signed by its issuer's pinned key, inside
 * its validity period, and internally consistent (same checks as refcommon.e2e.check_entry). */
export async function checkEntry(entry: DirectoryEntry, issuerSpki: string, at = new Date()): Promise<string | null> {
  if (entry.type !== "refx.directory.entry/v1" || entry.suite !== SUITE) return "not a directory entry of this suite";
  if (entry.signer_key_id !== await keyId(issuerSpki)) return "signed by a key that is not the issuer's pinned key";
  if (!await verifyObject(issuerSpki, entry)) return "issuer signature is missing or invalid";
  try {
    if (entry.enc_key_id !== await keyId(entry.enc_public_key)) return "key id does not match the key";
    await importEncPublic(entry.enc_public_key);
    if (entry.sig_public_key) await importSigPublic(entry.sig_public_key);
    const from = Date.parse(entry.valid_from);
    const to = Date.parse(entry.valid_to);
    if (Number.isNaN(from) || Number.isNaN(to)) return "malformed entry";
    if (from > at.getTime() + 5 * 60_000 || at.getTime() > to) return "outside its validity period";
  } catch {
    return "malformed entry";
  }
  return null;
}

export async function checkRevocation(rev: Revocation, issuerSpki: string): Promise<boolean> {
  return rev.type === "refx.directory.revocation/v1" && rev.signer_key_id === await keyId(issuerSpki)
    && verifyObject(issuerSpki, rev);
}

// --------------------------------------------------------------------------- signed package manifests (spec v4 5.8)
export const MANIFEST_TYPE = "refx.package.manifest/v1";

export type ManifestItem = { batch_id: string; item_id: string; kind: string; title: string; content_hash: string; ciphertext_hash: string };
export type Manifest = {
  type: string; suite: string; referral: string; version: number; created_at: string;
  signer: { subject_id: string; sig_key_id: string; hospital_id: string | null };
  recipient: { hospital_id: string; department: string; group_key_id: string; key_version: number };
  patient_key_id: string | null;
  items: ManifestItem[];
  signature?: string;
};

/** The unsigned manifest (same fields as refcommon.e2e.package_manifest). The signature covers each item's
 * plaintext hash, so anyone holding a decrypted copy can check it is exactly what was approved. */
export async function packageManifest(a: {
  referral: string; version: number; signerSubject: string; signerSigPublic: string; signerHospital: string | null;
  recipient: DirectoryEntry; patient: DirectoryEntry | null; items: ManifestItem[];
}): Promise<Manifest> {
  return {
    type: MANIFEST_TYPE, suite: SUITE, referral: a.referral, version: a.version,
    created_at: new Date().toISOString().replace(/\.\d{3}Z$/, "+00:00"),
    signer: { subject_id: a.signerSubject, sig_key_id: await keyId(a.signerSigPublic), hospital_id: a.signerHospital },
    recipient: { hospital_id: a.recipient.hospital_id!, department: a.recipient.department!, group_key_id: a.recipient.enc_key_id,
      key_version: a.recipient.key_version },
    patient_key_id: a.patient ? a.patient.enc_key_id : null,
    items: a.items.map(({ batch_id, item_id, kind, title, content_hash, ciphertext_hash }) =>
      ({ batch_id, item_id, kind, title, content_hash, ciphertext_hash })),
  };
}

/** What is wrong with a decrypted copy against its signed manifest (empty when it verifies). */
export async function checkCopy(manifest: Manifest, signerSigPublic: string, plaintextHashes: Map<string, string>): Promise<string[]> {
  if (manifest.type !== MANIFEST_TYPE || !(await verifyObject(signerSigPublic, manifest as unknown as SignedObject))) {
    return ["the manifest signature does not verify"];
  }
  const problems: string[] = [];
  for (const it of manifest.items) {
    const h = plaintextHashes.get(it.item_id);
    if (h === undefined) problems.push(`${it.title}: missing from this copy`);
    else if (h !== it.content_hash) problems.push(`${it.title}: content differs from what was approved`);
  }
  return problems;
}
