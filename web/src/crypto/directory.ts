/**
 * Pinned keys and verified directory entries.
 *
 * The pinned participant registry (/participants.json) is written at onboarding and served with this application,
 * not by the platform's API. Every directory entry is checked against its issuer's pinned key before it is used to
 * encrypt to anyone; a failure is refused here and reported for the audit trail (spec v4 5.4, T-DIR-1).
 */
import { api } from "../api/client";
import { checkEntry, checkRevocation, DirectoryEntry, Revocation } from "./suite";

export type Pinned = {
  agreement: { version: string; date: string; purposes: string[] };
  platform: { id: string; signing_key: string; key_id: string };
  institutions: Record<string, { name: string; signing_key: string; key_id: string; status: string }>;
};

export type DirectoryRow = { entry: DirectoryEntry; revocation: Revocation | null; revoked: boolean; fingerprint: string };

let pinned: Promise<Pinned> | null = null;

export function pinnedRegistry(): Promise<Pinned> {
  if (!pinned) {
    pinned = fetch("/participants.json", { cache: "no-cache" }).then(async (r) => {
      if (!r.ok) throw new Error("This installation has not been onboarded yet (no pinned participant keys)");
      return (await r.json()) as Pinned;
    });
    pinned.catch(() => (pinned = null));
  }
  return pinned;
}

export async function issuerKey(issuer: string): Promise<string | null> {
  const reg = await pinnedRegistry();
  if (issuer === reg.platform.id) return reg.platform.signing_key;
  const inst = reg.institutions[issuer];
  return inst && inst.status === "active" ? inst.signing_key : null;
}

export class UntrustedKeyError extends Error {}

/** The entry, if its issuer's pinned key signed it and it is not revoked; otherwise an error (reported). */
export async function verifiedEntry(row: DirectoryRow, referralId?: number): Promise<DirectoryEntry> {
  const key = await issuerKey(row.entry.issued_by);
  let problem = key ? await checkEntry(row.entry, key) : "issuer is not a pinned participant in good standing";
  if (!problem && row.revocation && key && (await checkRevocation(row.revocation, key))) problem = "key was revoked";
  if (problem) {
    void api.post("/e2e/client-events", {
      action: "directory.signature_failure", target_type: "directory_entry", target_id: row.entry.subject_id ?? "?",
      referral_id: referralId ?? null, detail: { reason: problem, key_id: row.entry.enc_key_id },
    }).catch(() => undefined);
    throw new UntrustedKeyError(`The key for ${row.entry.display_name ?? "this recipient"} was refused: ${problem}`);
  }
  return row.entry;
}

/** The receiving department's current group key, verified. */
export async function departmentEntry(hospitalId: string, department: string, referralId?: number): Promise<DirectoryEntry> {
  const rows = await api.get<DirectoryRow[]>(`/e2e/directory/departments/${hospitalId}/${department}`);
  const current = rows.filter((r) => !r.revoked).sort((a, b) => b.entry.key_version - a.entry.key_version)[0];
  if (!current) throw new UntrustedKeyError("The receiving department has no usable key yet");
  return verifiedEntry(current, referralId);
}

/** A subject's current verified entry (doctor or patient). */
export async function subjectEntry(subjectId: string, referralId?: number): Promise<DirectoryEntry | null> {
  const rows = await api.get<DirectoryRow[]>(`/e2e/directory?subject_id=${encodeURIComponent(subjectId)}`);
  const current = rows.filter((r) => !r.revoked).sort((a, b) => b.entry.key_version - a.entry.key_version)[0];
  return current ? verifiedEntry(current, referralId) : null;
}
