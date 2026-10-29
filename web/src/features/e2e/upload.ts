/**
 * The doctor's own items for a referral (consultation notes, the medicine list asked from the patient, scanned
 * papers), encrypted on this device before upload (spec v4 5.6). One data key per upload ("batch"), wrapped to the
 * doctor's own key; the approval later re-wraps it to the receiving department and the patient.
 */
import { api } from "../../api/client";
import type { UnlockedKeys } from "../../crypto/session";
import { b64e, CHUNK_SIZE, encrypt, encryptChunks, itemAad, newDek, randomBytes, utf8, wrap, wrapContext } from "../../crypto/suite";

export type OwnItem =
  | { category: string; kind: "note" | "prescription" | "other"; label: string; record: Record<string, unknown> }
  | { category: "scan"; kind: "scan"; label: string; bytes: Uint8Array; mime: string };

const today = () => new Date().toISOString().slice(0, 10);

export function newBatchId(prefix: "doc" | "pat" = "doc"): string {
  return `${prefix}-${b64e(randomBytes(9)).replace(/[^A-Za-z0-9]/g, "").slice(0, 12).toLowerCase()}`;
}

/** Encrypt and upload; returns the new item ids. The platform receives titles and ciphertext only. */
export async function uploadOwnItems(referralId: number, reference: string, keys: UnlockedKeys, items: OwnItem[]): Promise<string[]> {
  const batch = newBatchId();
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
  const wraps = [{ recipient_key_id: keys.encKeyId, wrapped: await wrap(keys.encPublic, dek, wrapContext(reference, batch, keys.encKeyId)) }];
  await api.post(`/referrals/${referralId}/encrypted-batches`, { batch_id: batch, items: out, wraps });
  return out.map((x) => x.title.item_id);
}
