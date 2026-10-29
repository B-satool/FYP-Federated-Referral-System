/**
 * Items encrypted on this device before upload (spec v4 5.6): the doctor's own items (consultation notes, the medicine
 * list asked from the patient, scanned papers) and papers the patient adds in the app. One data key per upload
 * ("batch"), wrapped to each recipient's verified public key; the platform gets titles and ciphertext only.
 */
import { api } from "../../api/client";
import type { UnlockedKeys } from "../../crypto/session";
import { b64e, CHUNK_SIZE, encrypt, encryptChunks, itemAad, newDek, randomBytes, utf8, wrap, wrapContext } from "../../crypto/suite";

export type OwnItem =
  | { category: string; kind: "note" | "prescription" | "other"; label: string; record: Record<string, unknown> }
  | { category: "scan"; kind: "scan"; label: string; bytes: Uint8Array; mime: string };
export type Recipient = { keyId: string; publicKey: string };

const today = () => new Date().toISOString().slice(0, 10);

export function newBatchId(prefix: "doc" | "pat" = "doc"): string {
  return `${prefix}-${b64e(randomBytes(9)).replace(/[^A-Za-z0-9]/g, "").slice(0, 12).toLowerCase()}`;
}

/** Encrypt items under one new data key and wrap it to each recipient. */
export async function encryptBatch(prefix: "doc" | "pat", reference: string, items: OwnItem[], recipients: Recipient[]) {
  const batch = newBatchId(prefix);
  const dek = newDek();
  const out = [];
  for (const [n, it] of items.entries()) {
    const itemId = `${batch}:${it.category}${items.length > 1 ? `-${n + 1}` : ""}`;
    const title = { item_id: itemId, kind: it.kind, category: it.category, label: it.label, date: today() };
    if ("bytes" in it) {
      const chunks = await encryptChunks(dek, it.bytes, reference, itemId, batch, CHUNK_SIZE);
      out.push({ title, sealed: { chunks, mime: it.mime } });
    } else {
      const content = { type: "refx.item/v1", item_id: itemId, category: it.category, label: it.label, date: today(), record: it.record };
      out.push({ title, sealed: await encrypt(dek, utf8(JSON.stringify(content)), itemAad(reference, itemId, batch)) });
    }
  }
  const wraps = [];
  for (const r of recipients) {
    wraps.push({ recipient_key_id: r.keyId, wrapped: await wrap(r.publicKey, dek, wrapContext(reference, batch, r.keyId)) });
  }
  return { batch_id: batch, items: out, wraps };
}

/** The doctor's own items, wrapped to the doctor's own key; returns the new item ids. */
export async function uploadOwnItems(referralId: number, reference: string, keys: UnlockedKeys, items: OwnItem[]): Promise<string[]> {
  const body = await encryptBatch("doc", reference, items, [{ keyId: keys.encKeyId, publicKey: keys.encPublic }]);
  await api.post(`/referrals/${referralId}/encrypted-batches`, body);
  return body.items.map((x) => x.title.item_id);
}
