/**
 * The patient's own copy of a referral (spec v4 11.3, step 12) and papers they add (step 2).
 *
 * "Save a copy on this phone" stores the signed package as received: ciphertext, the data keys wrapped to the
 * patient's key, the signed manifest and the signer's directory entry, in this browser's storage (IndexedDB). Opening
 * it decrypts with the patient's device key and checks it against the referring doctor's signature, so it still opens
 * and verifies after the referral is purged from the platform (T-LIFE-2). The download is the same encrypted copy.
 * If the phone is lost, so is the copy: the hospitals still hold the originals.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Box, Button, Typography } from "@mui/material";
import { api } from "../../api/client";
import { ErrorAlert, fmtDate, Loading } from "../../components/common";
import { subjectEntry, verifiedEntry, DirectoryRow } from "../../crypto/directory";
import { listCopies, LocalCopy, saveCopy } from "../../crypto/keystore";
import { useDeviceKeys } from "../../crypto/session";
import { checkCopy, Manifest } from "../../crypto/suite";
import { DeviceKeyPanel } from "../keys/DeviceKey";
import { EncryptedResponse, latestById, openAll, OpenedItem, summary } from "../e2e/records";
import { encryptBatch } from "../e2e/upload";

type CopyBundle = EncryptedResponse & { version: number; manifest: Manifest; manifest_sha256: string; signer: DirectoryRow | null };
type Opened = { items: OpenedItem[]; problems: string[]; signer: string | null };

async function openCopy(b: CopyBundle, keys: NonNullable<ReturnType<typeof useDeviceKeys>["keys"]>): Promise<Opened> {
  const items = await openAll(b, keys);
  const problems: string[] = [];
  let signer: string | null = null;
  try {
    if (!b.signer) throw new Error("the doctor's key is not in the copy");
    const entry = await verifiedEntry(b.signer);
    signer = entry.display_name;
    // 1. the signature over the manifest (every item's plaintext hash is in it)
    const listed = new Map(b.manifest.items.map((x) => [x.item_id, x.content_hash]));
    problems.push(...(await checkCopy(b.manifest, entry.sig_public_key!, listed)));
    // 2. every item that opens with the patient's key matches what was signed; items the doctor did not share with the
    //    patient have no wrap for them and are simply not in this copy
    for (const i of items) {
      const signed = listed.get(i.title.item_id);
      if (i.plainHash && signed && i.plainHash !== signed) problems.push(`${i.title.label}: content differs from what was signed`);
    }
    if (!items.some((i) => i.plainHash)) problems.push("nothing in this copy opens with your key");
  } catch (e) {
    problems.push(e instanceof Error ? e.message : String(e));
  }
  return { items: latestById(items).filter((i) => i.state === "ok"), problems, signer };
}

export function MyCopy({ reference, available, purgedAt }: { reference: string; available: boolean; purgedAt: string | null }) {
  const dk = useDeviceKeys();
  const qc = useQueryClient();
  const subject = dk.subjectId ?? "";
  const copies = useQuery({ queryKey: ["copies", subject], enabled: !!subject, queryFn: () => listCopies(subject) });
  const mine = (copies.data ?? []).filter((c) => c.reference === reference).sort((a, b) => b.saved_at.localeCompare(a.saved_at))[0];
  const [opened, setOpened] = useState<Opened | null>(null);
  const save = useMutation({
    mutationFn: async () => {
      const b = await api.get<CopyBundle>(`/patient-access/referrals/${encodeURIComponent(reference)}/copy`);
      const c: LocalCopy = { id: `${subject}:${reference}:v${b.version}`, subject, reference, saved_at: new Date().toISOString(), bundle: b };
      await saveCopy(c);
      return c;
    },
    meta: { success: "Saved on this phone, still encrypted with your key." },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["copies", subject] }),
  });
  const open = useMutation({ mutationFn: () => openCopy(mine!.bundle as CopyBundle, dk.keys!), meta: { silent: true }, onSuccess: setOpened });
  const download = () => {
    const url = URL.createObjectURL(new Blob([JSON.stringify(mine!.bundle)], { type: "application/json" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `${reference}-encrypted-copy.json`;
    a.click();
    URL.revokeObjectURL(url);
  };
  if (dk.status !== "unlocked") return <DeviceKeyPanel compact />;
  if (copies.isLoading) return <Loading />;
  return (
    <Box>
      {purgedAt && <Alert severity="info" sx={{ mb: 1 }}>Purged from the platform on {fmtDate(purgedAt)}. {mine ? "The copy on this phone is the only one." : "No copy was saved on this phone."}</Alert>}
      {mine ? (
        <Typography variant="body2" sx={{ mb: 1 }}>Copy saved on this phone {fmtDate(mine.saved_at)} (version {(mine.bundle as CopyBundle).version}).</Typography>
      ) : !purgedAt && !available ? <Typography variant="body2" color="text.secondary">A copy can be saved once your doctor has signed the referral.</Typography> : null}
      <ErrorAlert error={save.error || open.error} />
      <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
        {available && !purgedAt && <Button variant="contained" size="small" onClick={() => save.mutate()} disabled={save.isPending}>{mine ? "Save the latest copy" : "Save a copy on this phone"}</Button>}
        {mine && <Button variant="outlined" size="small" onClick={() => open.mutate()} disabled={open.isPending}>Open my copy</Button>}
        {mine && <Button size="small" onClick={download}>Download (encrypted)</Button>}
      </Box>
      {opened && (
        <Box sx={{ mt: 1.5 }} data-testid="my-copy">
          {opened.problems.length
            ? <Alert severity="error">This copy does not match what your doctor signed: {opened.problems.join("; ")}</Alert>
            : <Alert severity="success">Signed by {opened.signer}; every item matches the signature.</Alert>}
          <Box component="ul" sx={{ pl: 2.5 }}>
            {opened.items.map((i) => <li key={i.title.item_id}><Typography variant="body2">{i.content ? summary(i.content) : i.title.label}</Typography></li>)}
          </Box>
        </Box>
      )}
      <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>
        If you lose this phone, the copy is lost; the hospitals still hold the originals and you can ask them.
      </Typography>
    </Box>
  );
}

/** A paper the patient adds to an open referral: encrypted on the phone to the referring doctor's key and their own. */
export function AddPaper({ reference, doctorId }: { reference: string; doctorId: string | null }) {
  const dk = useDeviceKeys();
  const [done, setDone] = useState(false);
  const send = useMutation({
    mutationFn: async (file: File) => {
      if (file.size > 10 * 1024 * 1024) throw new Error("At most 10 MB");
      const doctor = doctorId ? await subjectEntry(doctorId) : null;
      if (!doctor) throw new Error("Your doctor has not set up their key yet; try again later");
      const me = dk.keys!;
      const body = await encryptBatch("pat", reference, [{ category: "scan", kind: "scan", label: "Patient-provided document",
        bytes: new Uint8Array(await file.arrayBuffer()), mime: file.type || "application/octet-stream" }],
      [{ keyId: doctor.enc_key_id, publicKey: doctor.enc_public_key }, { keyId: me.encKeyId, publicKey: me.encPublic }]);
      await api.post(`/patient-access/referrals/${encodeURIComponent(reference)}/papers`, body);
    },
    meta: { success: "Sent to your doctor, encrypted on this phone." },
    onSuccess: () => setDone(true),
  });
  if (dk.status !== "unlocked") return <DeviceKeyPanel compact />;
  return (
    <Box>
      <Button variant="outlined" size="small" component="label" disabled={send.isPending}>
        Add a photo of a paper
        <input hidden type="file" accept="image/jpeg,image/png,image/webp,application/pdf" onChange={(e) => e.target.files?.[0] && send.mutate(e.target.files[0])} />
      </Button>
      <Typography variant="caption" color="text.secondary" display="block">Only your doctor and you can read it. Staff see only that a paper was added.</Typography>
      {done && <Typography variant="body2">Added.</Typography>}
      <ErrorAlert error={send.error} />
    </Box>
  );
}
