// T-PERF-1 (spec v4 17): time and size to open a typical referral on a device: 30 items, 5 of them scans (1.5 MB
// each, in 1 MB chunks), in 4 batches, using the browser suite (src/crypto/suite.ts, WebCrypto) under Node.
// Run: node web/scripts/perf-decrypt.ts   (prints JSON; the numbers are for the machine it runs on)
import * as s from "../src/crypto/suite.ts";

const REF = "REF-2026-PERF";
const kp = await s.generateEncryptionKeyPair();
const pub = await s.exportSpki(kp.publicKey);
const kid = await s.keyId(pub);
const priv = await s.importEncPrivate(await s.exportPkcs8(kp.privateKey));

type Item = { id: string; batch: string; sealed: s.Sealed | { chunks: s.Sealed[] } };
const items: Item[] = [];
const wraps: { batch: string; wrapped: s.Wrapped }[] = [];
const record = JSON.stringify({ type: "refx.item/v1", category: "lab", label: "Complete blood count",
  record: { test: "Haemoglobin", value: "12.1", unit: "g/dL", note: "x".repeat(600) } });
let bytes = 0;
const scan = new Uint8Array(1_500_000).map((_, i) => (i * 2654435761) >>> 24); // stand-in image bytes
const plan = [9, 8, 8, 5]; // three institutions' answers (25 records), then the doctor's batch of 5 scans
for (const [b, count] of plan.entries()) {
  const batch = `batch-${b}`;
  const dek = s.newDek();
  wraps.push({ batch, wrapped: await s.wrap(pub, dek, s.wrapContext(REF, batch, kid)) });
  for (let i = 0; i < count; i++) {
    const id = `${batch}:${i}`;
    if (b === 3) {
      const chunks = await s.encryptChunks(dek, scan, REF, id, batch);
      bytes += chunks.reduce((n, c) => n + c.ciphertext.length, 0);
      items.push({ id, batch, sealed: { chunks } });
    } else {
      const sealed = await s.encrypt(dek, s.utf8(record), s.itemAad(REF, id, batch));
      bytes += sealed.ciphertext.length;
      items.push({ id, batch, sealed });
    }
  }
}

const runs: number[] = [];
for (let r = 0; r < 5; r++) {
  const t0 = performance.now();
  const deks = new Map<string, Uint8Array>();
  for (const w of wraps) deks.set(w.batch, await s.unwrap(priv, w.wrapped, s.wrapContext(REF, w.batch, kid)));
  for (const it of items) {
    const dek = deks.get(it.batch)!;
    const pt = "chunks" in it.sealed ? await s.decryptChunks(dek, it.sealed.chunks, REF, it.id, it.batch)
      : await s.decrypt(dek, it.sealed, s.itemAad(REF, it.id, it.batch));
    await s.sha256Hex(pt); // the plaintext hash checked against the signed manifest
  }
  runs.push(performance.now() - t0);
}
runs.sort((a, b) => a - b);
console.log(JSON.stringify({ items: items.length, scans: items.filter((i) => "chunks" in i.sealed).length, batches: wraps.length,
  download_bytes_base64: bytes, median_ms: Math.round(runs[2]), min_ms: Math.round(runs[0]), max_ms: Math.round(runs[4]),
  node: process.version }));
