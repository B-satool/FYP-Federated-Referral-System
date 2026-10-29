/**
 * Approving the package on the doctor's device (spec v4 5.8).
 *
 * 1. The receiving department's group key and the patient's key are verified against their issuers' pinned keys.
 * 2. The manifest lists each chosen item with the SHA-256 of its plaintext and of its stored ciphertext, and is
 *    signed with the doctor's signing key.
 * 3. Each included batch's data key is re-wrapped to the department and the patient. The platform stores the
 *    signed manifest and the wraps; it never sees a data key.
 */
import { api } from "../../api/client";
import type { ReferralDetail } from "../../api/types";
import { verifiedEntry } from "../../crypto/directory";
import type { UnlockedKeys } from "../../crypto/session";
import { DirectoryEntry, fingerprint, Manifest, ManifestItem, packageManifest, signObject, wrap, wrapContext } from "../../crypto/suite";
import type { OpenedItem } from "./records";

export type Recipients = { department: DirectoryEntry; patient: DirectoryEntry | null; departmentFingerprint: string };

/** The verified recipients, or an error saying which key was refused (reported for the audit trail). */
export async function recipients(r: ReferralDetail): Promise<Recipients> {
  const rk = r.recipient_keys;
  if (!rk?.department) throw new Error("The receiving department has not published its key yet");
  const department = await verifiedEntry(rk.department, r.id);
  const patient = rk.patient ? await verifiedEntry(rk.patient, r.id) : null;
  return { department, patient, departmentFingerprint: await fingerprint(department.enc_public_key) };
}

export async function approve(r: ReferralDetail, keys: UnlockedKeys, chosen: OpenedItem[], to: Recipients): Promise<Manifest> {
  if (!keys.entry) throw new Error("Your key is waiting for your hospital to sign it");
  const usable = chosen.filter((i) => i.state === "ok" && i.dek && i.plainHash);
  if (!usable.length) throw new Error("Choose at least one record or add your notes");
  const items: ManifestItem[] = usable.map((i) => ({
    batch_id: i.title.batch_id, item_id: i.title.item_id, kind: i.title.kind, title: i.content?.label ?? i.title.label,
    content_hash: i.plainHash!, ciphertext_hash: i.ciphertext_sha256,
  }));
  const manifest = await packageManifest({
    referral: r.reference, version: (r.packages[0]?.version ?? 0) + 1, signerSubject: keys.entry.subject_id,
    signerSigPublic: keys.sigPublic, signerHospital: keys.entry.hospital_id, recipient: to.department, patient: to.patient, items,
  });
  const signed = await signObject(keys.sigPrivate, manifest);
  const deks = new Map(usable.map((i) => [i.title.batch_id, i.dek!]));
  const wraps = [];
  for (const [batch, dek] of deks) {
    for (const target of [to.department, to.patient].filter(Boolean) as DirectoryEntry[]) {
      wraps.push({ batch_id: batch, recipient_key_id: target.enc_key_id,
        wrapped: await wrap(target.enc_public_key, dek, wrapContext(r.reference, batch, target.enc_key_id)) });
    }
  }
  await api.post(`/referrals/${r.id}/packages`, { manifest: signed, wraps });
  return signed as Manifest;
}
