/**
 * Encrypted referral content, opened on this device (spec v4 5.6).
 *
 * The platform sends titles, ciphertext and the data keys wrapped to this user's keys. Each batch's data key is
 * unwrapped here (with the device key, or a department group key on the receiving side) and the items decrypted
 * in memory. Nothing decrypted is sent back; the platform is told only which item ids were opened (audit).
 */
import { api } from "../../api/client";
import type { UnlockedKeys } from "../../crypto/session";
import { decrypt, decryptChunks, fromUtf8, itemAad, Sealed, unwrap, wrapContext, Wrapped } from "../../crypto/suite";

export type Title = {
  item_id: string; batch_id: string; kind: string; category: string | null; label: string; date: string | null;
  source_institution: string | null; source_name: string | null; sensitive: boolean;
};
export type SealedItem = Title & { sealed: Sealed | { chunks: Sealed[] }; ciphertext_sha256: string };
export type WrapDto = { batch_id: string; recipient_type: string; recipient_key_id: string; key_version: number | null; wrapped: Wrapped };
export type BatchDto = { batch_id: string; origin: string; source_institution: string | null; source_name: string | null; created_at: string };
export type EncryptedResponse = { reference: string; items: SealedItem[]; wraps: WrapDto[]; batches: BatchDto[] };

/** What an item decrypts to. Records from an institution carry `record` (the fields) and `fhir` (the resource). */
export type ItemContent = {
  type: string; item_id: string; category: string; label: string; date: string | null;
  source_institution?: string; source_name?: string; sensitive_category?: string | null;
  record: Record<string, unknown>; fhir?: Record<string, unknown>;
};

export type OpenedItem = {
  title: Title;
  origin: string;
  state: "ok" | "no_key" | "failed";
  content?: ItemContent; // JSON items
  bytes?: Uint8Array; // files (scans), decrypted from chunks
  sealed: SealedItem["sealed"];
  ciphertext_sha256: string;
  dek?: Uint8Array; // kept in memory so the doctor can re-wrap it on approval (spec v4 5.8)
};

/** How to unwrap a wrap addressed to a department group key on the receiving side. */
export type GroupResolver = (w: WrapDto) => { key: CryptoKey; keyId: string } | null;

export async function openAll(resp: EncryptedResponse, keys: UnlockedKeys, group?: GroupResolver): Promise<OpenedItem[]> {
  const deks = new Map<string, Uint8Array>();
  for (const w of resp.wraps) {
    if (deks.has(w.batch_id)) continue;
    try {
      if (w.recipient_key_id === keys.encKeyId) {
        deks.set(w.batch_id, await unwrap(keys.encPrivate, w.wrapped, wrapContext(resp.reference, w.batch_id, keys.encKeyId)));
      } else if (group) {
        const g = group(w);
        if (g) deks.set(w.batch_id, await unwrap(g.key, w.wrapped, wrapContext(resp.reference, w.batch_id, g.keyId)));
      }
    } catch {
      /* a wrap that does not open is treated as no key for that batch */
    }
  }
  const origin = new Map(resp.batches.map((b) => [b.batch_id, b.origin]));
  const out: OpenedItem[] = [];
  for (const it of resp.items) {
    const dek = deks.get(it.batch_id);
    const base = { title: it, origin: origin.get(it.batch_id) ?? "custodian", sealed: it.sealed, ciphertext_sha256: it.ciphertext_sha256 };
    if (!dek) {
      out.push({ ...base, state: "no_key" });
      continue;
    }
    try {
      if ("chunks" in it.sealed) {
        out.push({ ...base, state: "ok", bytes: await decryptChunks(dek, it.sealed.chunks, resp.reference, it.item_id, it.batch_id), dek });
      } else {
        const pt = await decrypt(dek, it.sealed, itemAad(resp.reference, it.item_id, it.batch_id));
        out.push({ ...base, state: "ok", content: JSON.parse(fromUtf8(pt)) as ItemContent, dek });
      }
    } catch {
      out.push({ ...base, state: "failed" });
    }
  }
  return out;
}

/** Report which items were opened (ids only; best effort: a modified client could skip it). */
export function reportOpened(referralId: number, items: OpenedItem[]) {
  const ids = items.filter((i) => i.state === "ok").map((i) => i.title.item_id);
  if (!ids.length) return;
  void api.post("/e2e/client-events", { action: "decrypt.opened", target_type: "referral", target_id: String(referralId),
    referral_id: referralId, detail: { item_ids: ids.slice(0, 300), count: ids.length } }).catch(() => undefined);
  const failed = items.filter((i) => i.state === "failed").map((i) => i.title.item_id);
  if (failed.length) {
    void api.post("/e2e/client-events", { action: "decrypt.failed", target_type: "referral", target_id: String(referralId),
      referral_id: referralId, detail: { item_ids: failed.slice(0, 300), reason: "ciphertext did not decrypt" } }).catch(() => undefined);
  }
}

/** Newest version of each item (a later batch replaces an earlier one with the same item id). */
export function latestById(items: OpenedItem[]): OpenedItem[] {
  const m = new Map<string, OpenedItem>();
  for (const i of items) {
    const prev = m.get(i.title.item_id);
    if (!prev || (prev.state !== "ok" && i.state === "ok") || i.state === "ok") m.set(i.title.item_id, i);
  }
  return [...m.values()];
}

export const CATEGORY_GROUPS: [string, string][] = [
  ["condition", "Diagnoses"], ["surgery", "Previous operations"], ["medication", "Medicines on record"],
  ["visit", "Visits"], ["lab", "Test results"], ["imaging", "Imaging reports"], ["scan", "Scanned papers"],
  ["note", "Notes"], ["medication_list", "Medicine list"], ["restricted", "Restricted records"],
];

/** A one-line view of a decrypted record for lists (the full record is shown when opened). */
export function summary(c: ItemContent): string {
  const r = c.record ?? {};
  const s = (k: string) => (r[k] == null || r[k] === "" ? null : String(r[k]));
  switch (c.category) {
    case "condition": return [s("display"), s("status"), s("onset") && `since ${s("onset")}`].filter(Boolean).join(" · ");
    case "surgery": return [s("procedure"), s("performed"), s("location")].filter(Boolean).join(" · ");
    case "visit": return [s("setting"), s("reason"), s("summary")].filter(Boolean).join(" · ");
    case "medication": return [s("name"), s("brand") && `(${s("brand")})`, s("dose"), s("frequency")].filter(Boolean).join(" ");
    case "lab": return `${s("test")}: ${s("value") ?? "–"}${s("unit") ? ` ${s("unit")}` : ""}${s("flag") ? ` (${s("flag")})` : ""}${s("reference_range") ? ` · normal ${s("reference_range")}` : ""}`;
    case "imaging": return [s("study"), s("impression") || s("findings")].filter(Boolean).join(" · ");
    default: return c.label;
  }
}
