/**
 * The receiving department's doctor opens a sent referral on their own device (spec v4 5.5, 5.8).
 *
 * The package comes from the platform as ciphertext with each batch's data key wrapped to the department group key.
 * The group key (wrapped to this doctor's key) was unlocked with the device key. After decrypting, the signer's key
 * is verified against the referring hospital's pinned key, the manifest signature is checked, and every item's
 * plaintext hash is compared with what the referring doctor signed.
 */
import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Alert, Box, Collapse, IconButton, Stack, Table, TableBody, TableCell, TableRow, Typography } from "@mui/material";
import ExpandMore from "@mui/icons-material/ExpandMore";
import { api } from "../../api/client";
import type { Case } from "../../api/types";
import { Empty, ErrorAlert, fmtDate, Loading, Section } from "../../components/common";
import { DirectoryRow, verifiedEntry } from "../../crypto/directory";
import { useDeviceKeys } from "../../crypto/session";
import { checkCopy, Manifest } from "../../crypto/suite";
import { DeviceKeyPanel } from "../keys/DeviceKey";
import { medicinesFrom, medsForEvaluation } from "../referrals/MedicinesTab";
import { Detail } from "../referrals/Records";
import { useMedBundle } from "./bundle";
import { evaluate } from "./flags";
import { Decision, Layer1Flags, NotAssessed } from "./FlagViews";
import { CATEGORY_GROUPS, EncryptedResponse, latestById, openAll, OpenedItem, reportOpened, summary } from "./records";

type ReceivedResponse = EncryptedResponse & { version: number; manifest: Manifest; manifest_sha256: string; signer: DirectoryRow | null };
export type Opened = { items: OpenedItem[]; problems: string[]; signer: string | null; version: number; sha: string };

/** Decrypt and verify the sent package with this device's department group key. */
export function useReceivedPackage(c: Pick<Case, "central_referral_id" | "department">, hospital: string, enabled = true) {
  const dk = useDeviceKeys();
  const reported = useRef(false);
  const q = useQuery({
    queryKey: ["received", c.central_referral_id, dk.keys?.encKeyId, dk.keys?.groups.size],
    enabled: enabled && dk.status === "unlocked",
    gcTime: 0,
    staleTime: Infinity,
    retry: false,
    queryFn: async (): Promise<Opened> => {
      const resp = await api.get<ReceivedResponse>(`/e2e/received/${encodeURIComponent(c.central_referral_id)}/package`);
      const items = await openAll(resp, dk.keys!, (w) => {
        const key = w.key_version != null ? dk.groupKey(hospital, c.department, w.key_version) : null;
        return key ? { key, keyId: w.recipient_key_id } : null;
      });
      let problems: string[];
      let signer: string | null = null;
      try {
        if (!resp.signer) throw new Error("the signer's key is not in the directory");
        const entry = await verifiedEntry(resp.signer);
        signer = `${entry.display_name}, ${entry.hospital_id}`;
        const hashes = new Map(items.filter((i) => i.plainHash).map((i) => [i.title.item_id, i.plainHash!]));
        problems = await checkCopy(resp.manifest, entry.sig_public_key!, hashes);
      } catch (e) {
        problems = [e instanceof Error ? e.message : String(e)];
      }
      return { items: latestById(items), problems, signer, version: resp.version, sha: resp.manifest_sha256 };
    },
  });
  useEffect(() => {
    if (q.data && !reported.current) {
      reported.current = true;
      reportOpened(c.central_referral_id, q.data.items);
    }
  }, [q.data, c.central_referral_id]);
  return q;
}

function Row({ item }: { item: OpenedItem }) {
  const [open, setOpen] = useState(item.title.category === "note");
  const ok = item.state === "ok";
  return (
    <>
      <TableRow>
        <TableCell>
          <Typography variant="body2">{ok && item.content ? summary(item.content) : item.title.label}</Typography>
          <Typography variant="caption" color="text.secondary">
            {item.content?.source_name ?? item.title.source_name ?? item.title.source_institution}
            {item.title.date ? ` · ${fmtDate(item.title.date, false)}` : ""}
          </Typography>
          {item.state === "no_key" && <Typography variant="caption" display="block" color="warning.main">Encrypted to a department key version this device does not hold.</Typography>}
          {item.state === "failed" && <Typography variant="caption" display="block" color="error">Could not be decrypted (altered or damaged).</Typography>}
        </TableCell>
        <TableCell align="right" sx={{ width: 48 }}>
          {ok && <IconButton size="small" aria-label="Show the full record" onClick={() => setOpen(!open)}><ExpandMore /></IconButton>}
        </TableCell>
      </TableRow>
      {ok && (
        <TableRow>
          <TableCell colSpan={2} sx={{ py: 0, borderBottom: open ? undefined : "none" }}>
            <Collapse in={open} unmountOnExit><Box sx={{ py: 1.5 }}><Detail item={item} /></Box></Collapse>
          </TableCell>
        </TableRow>
      )}
    </>
  );
}

/** The medicines in the package and the Layer 1 flags, recomputed on this device from the hash-checked bundle. */
function ReceivedMedicines({ items, reference }: { items: OpenedItem[]; reference: string }) {
  const bundle = useMedBundle();
  const [decisions, setDecisions] = useState<Record<string, Decision>>({});
  const { list, recorded } = medicinesFrom(items);
  const meds = medsForEvaluation(list?.medicines ?? [], recorded);
  if (!meds.length) return null;
  const ev = bundle.data ? evaluate(meds, bundle.data) : null;
  return (
    <Section title="Medicines and flags" description="The referring doctor's medicine list and the medicines on record; flags checked again on this device.">
      {list?.checked_note && <Typography variant="body2" sx={{ mb: 1 }}>Referring doctor's note: {list.checked_note}</Typography>}
      <Box component="ul" sx={{ m: 0, mb: 1.5, pl: 2.5 }}>
        {meds.map((m) => <li key={m.id}><Typography variant="body2">{m.name}{m.dose ? `, ${m.dose}` : ""}{m.frequency ? `, ${m.frequency}` : ""} · {m.source}</Typography></li>)}
      </Box>
      <ErrorAlert error={bundle.error} />
      {ev && <Stack spacing={1.5}><Layer1Flags ev={ev} referral={reference} decisions={decisions} onDecide={(k, d) => setDecisions({ ...decisions, [k]: d })} /><NotAssessed ev={ev} /></Stack>}
    </Section>
  );
}

export function ReceivedPackage({ c, hospital }: { c: Case; hospital: string }) {
  const dk = useDeviceKeys();
  const q = useReceivedPackage(c, hospital);
  if (dk.status !== "unlocked") return <Section title="The referral"><DeviceKeyPanel compact /></Section>;
  if (q.isLoading) return <Loading label="Decrypting on this device…" />;
  if (q.error) return <Section title="The referral"><ErrorAlert error={q.error} /></Section>;
  const { items, problems, signer, version, sha } = q.data!;
  const groups = CATEGORY_GROUPS.map(([cat, label]) => [label, items.filter((i) => (i.content?.category ?? i.title.category) === cat)] as const)
    .filter(([, list]) => list.length);
  const other = items.filter((i) => !CATEGORY_GROUPS.some(([cat]) => (i.content?.category ?? i.title.category) === cat));
  return (
    <>
    <Section title={`The referral (version ${version})`} description="Decrypted on this device with your department's key. Nothing decrypted is stored here or sent anywhere.">
      {problems.length ? (
        <Alert severity="error" sx={{ mb: 1.5 }} data-testid="package-verification">
          This copy does not match what the referring doctor signed: {problems.join("; ")}
        </Alert>
      ) : (
        <Alert severity="success" sx={{ mb: 1.5 }} data-testid="package-verification">
          Signed by {signer}; every item matches the signature. Fingerprint {sha.slice(0, 16)}…
        </Alert>
      )}
      {!items.length ? <Empty>Nothing in this package opened on this device.</Empty> : (
        <Stack spacing={2}>
          {[...groups, ...(other.length ? [["Other", other] as const] : [])].map(([label, list]) => (
            <Box key={label}>
              <Typography variant="subtitle2" sx={{ mb: 0.5 }}>{label} ({list.length})</Typography>
              <Table size="small"><TableBody>{list.map((i) => <Row key={i.title.item_id} item={i} />)}</TableBody></Table>
            </Box>
          ))}
        </Stack>
      )}
    </Section>
    <ReceivedMedicines items={items} reference={c.central_referral_id} />
    </>
  );
}
