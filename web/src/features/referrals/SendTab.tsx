import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Alert, Box, Button, Link, List, ListItem, ListItemIcon, ListItemText, Stack, Table, TableBody, TableCell, TableHead,
  TableRow, TextField, Typography } from "@mui/material";
import CheckCircle from "@mui/icons-material/CheckCircle";
import InfoOutlined from "@mui/icons-material/InfoOutlined";
import RadioButtonUnchecked from "@mui/icons-material/RadioButtonUnchecked";
import { api } from "../../api/client";
import type { ReferralDetail } from "../../api/types";
import { Empty, ErrorAlert, fmtDate, Loading, Section, Tag } from "../../components/common";
import { useDeviceKeys } from "../../crypto/session";
import { DeviceKeyPanel } from "../keys/DeviceKey";
import { approve, recipients, Recipients } from "../e2e/approve";
import { latestById, summary } from "../e2e/records";
import { isSelected, loadChoices } from "../e2e/selection";
import { uploadOwnItems } from "../e2e/upload";
import { useOpenedRecords } from "./Records";
import { useInvalidateReferral } from "./ReferralWorkspace";

type Delivery = { id: number; kind: string; target_institution: string; status: string; attempts: number; last_error: string | null; created_at: string; sent_at: string | null };

const KIND_LABEL: Record<string, string> = {
  deliver_package: "Referral notice",
  deliver_order: "Test or scan order",
  clarification_answer: "Answer to a question",
  expire_shared: "Removal notice",
};

export function Readiness({ r }: { r: ReferralDetail }) {
  const [, setParams] = useSearchParams();
  const items = r.readiness ?? [];
  return (
    <List dense aria-label="Before sending">
      {items.map((i) => (
        <ListItem key={i.key} disableGutters alignItems="flex-start">
          <ListItemIcon sx={{ minWidth: 36, mt: 0.5 }}>
            {!i.blocking ? <InfoOutlined color="info" titleAccess="For information" />
              : i.ok ? <CheckCircle color="success" titleAccess="Done" /> : <RadioButtonUnchecked titleAccess="Not done" />}
          </ListItemIcon>
          <ListItemText
            primary={<><span>{i.label}</span>{i.blocking && !i.ok && i.who !== "system" && <Tag tone={i.who === "doctor" ? "info" : "warn"} label={i.who === "doctor" ? "doctor" : "staff"} />}</>}
            secondary={
              <>
                {i.detail}
                {i.blocking && !i.ok && i.tab && i.tab !== "send" && (
                  <>
                    {" "}
                    <Link component="button" type="button" variant="body2" onClick={() => setParams({ tab: i.tab! })}>Go there</Link>
                  </>
                )}
              </>
            }
          />
        </ListItem>
      ))}
    </List>
  );
}

/** Signed versions: who signed, when, the manifest fingerprint, and whether staff have sent it. No content. */
function Versions({ r }: { r: ReferralDetail }) {
  if (!r.packages.length) return <Empty>No signed version yet.</Empty>;
  return (
    <Table size="small">
      <TableHead><TableRow><TableCell>Version</TableCell><TableCell>Signed by</TableCell><TableCell>Records</TableCell><TableCell>Fingerprint</TableCell><TableCell>Sent</TableCell></TableRow></TableHead>
      <TableBody>
        {r.packages.map((p) => (
          <TableRow key={p.version} data-testid={`version-${p.version}`}>
            <TableCell>v{p.version}{p.superseded ? " (replaced)" : ""}</TableCell>
            <TableCell>{p.signed_by}, {fmtDate(p.signed_at)}</TableCell>
            <TableCell>{p.item_count}</TableCell>
            <TableCell sx={{ fontFamily: "monospace", fontSize: 12 }}>{p.manifest_sha256.slice(0, 16)}…</TableCell>
            <TableCell>{p.sent ? <Tag tone="ok" label="sent" /> : <Tag tone="wait" label="not yet" />}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function Deliveries({ r }: { r: ReferralDetail }) {
  const refresh = useInvalidateReferral(r.id);
  const delivery = useQuery({ queryKey: ["referral", r.id, "delivery", r.row_version], queryFn: () => api.get<Delivery[]>(`/referrals/${r.id}/delivery`) });
  const retry = useMutation({ mutationFn: () => api.post(`/referrals/${r.id}/retry-delivery`), meta: { success: "Retrying." }, onSuccess: refresh });
  if (!delivery.data?.length) return null;
  return (
    <Box sx={{ mt: 2 }}>
      <Typography variant="subtitle2">Deliveries</Typography>
      {delivery.data.map((d) => (
        <Typography key={d.id} variant="body2">
          {KIND_LABEL[d.kind] ?? d.kind}: <Tag tone={d.status === "sent" ? "ok" : d.status === "failed" ? "bad" : "wait"} label={d.status} />{" "}
          {d.sent_at ? fmtDate(d.sent_at) : `${d.attempts} attempt(s)`}{d.last_error ? ` · ${d.last_error}` : ""}
        </Typography>
      ))}
      {r.delivery_status === "failed" && (
        <Button variant="contained" sx={{ mt: 1.5 }} onClick={() => retry.mutate()} disabled={retry.isPending}>Retry delivery</Button>
      )}
    </Box>
  );
}

/** Staff: send the version the doctor signed. The receiving hospital gets a notice with record titles; its doctors
 * open the encrypted package on their own devices. Staff never see content (spec v4 D14). */
export function SendTab({ r }: { r: ReferralDetail }) {
  const refresh = useInvalidateReferral(r.id);
  const send = useMutation({
    mutationFn: () => api.post(`/referrals/${r.id}/send`, { expected_version: r.row_version }),
    meta: { success: "Referral is being sent." },
    onSuccess: refresh,
  });
  const canSend = r.status === "requested" || r.amendment_open;
  const ready = (r.readiness ?? []).every((i) => !i.blocking || i.ok);
  return (
    <Stack spacing={2}>
      {canSend && (
        <Section title={r.amendment_open ? "Send the new version" : "Before sending"}
          description="Ask the patient for consent and request the records. The doctor reads them on their device, chooses what goes in, and signs the package; then you send it.">
          <Readiness r={r} />
          <ErrorAlert error={send.error} />
          <Button variant="contained" size="large" sx={{ mt: 1 }} disabled={!ready || send.isPending} onClick={() => send.mutate()}>
            {r.amendment_open ? "Send the new version" : `Send to ${r.destination_name}`}
          </Button>
        </Section>
      )}
      <Section title="Signed versions and delivery" description="Each version is signed by the doctor; its fingerprint identifies exactly what was approved. Content is encrypted for the receiving department.">
        <Versions r={r} />
        <Deliveries r={r} />
      </Section>
    </Stack>
  );
}

/** The doctor: what goes in the package (from the Records step), notes for the specialist, and approve and sign. */
export function SummaryTab({ r }: { r: ReferralDetail }) {
  const dk = useDeviceKeys();
  const refresh = useInvalidateReferral(r.id);
  const opened = useOpenedRecords(r);
  const [notes, setNotes] = useState("");
  const [to, setTo] = useState<Recipients | null>(null);
  const [toError, setToError] = useState<unknown>(null);
  useEffect(() => {
    let live = true;
    recipients(r).then((x) => live && setTo(x), (e) => live && setToError(e));
    return () => { live = false; };
  }, [r]);
  const preparing = r.status === "requested" || r.amendment_open;
  const items = latestById(opened.data ?? []);
  const choices = loadChoices(r.id);
  const chosen = items.filter((i) => i.state === "ok" && isSelected(i, choices));
  const sign = useMutation({
    mutationFn: async () => {
      let all = chosen;
      if (notes.trim()) {
        const added = await uploadOwnItems(r.id, r.reference, dk.keys!, [{ category: "note", kind: "note",
          label: "Notes for the specialist", record: { text: notes.trim() } }]);
        const ids = new Set([...chosen.map((i) => i.title.item_id), ...added]);
        all = latestById((await opened.refetch()).data ?? []).filter((i) => ids.has(i.title.item_id));
      }
      return approve(r, dk.keys!, all, to!);
    },
    meta: { success: "Signed. Staff have been told it is ready to send." },
    onSuccess: () => { setNotes(""); refresh(); },
  });
  if (r.working_set_purged_at) return <Alert severity="info">This referral's encrypted content was purged. The signed manifest's fingerprint remains.</Alert>;
  return (
    <Stack spacing={2}>
      {dk.status !== "unlocked" && <DeviceKeyPanel compact />}
      {preparing && r.readiness && <Section title="Progress before sending"><Readiness r={r} /></Section>}
      {preparing && (
        <Section title="Approve and sign the package"
          description="The package is what you chose on the Records step, the medicine list and any papers you added, and your notes. Signing records a fingerprint of each item; any later change needs a new signed version.">
          {dk.status !== "unlocked" ? <Empty>Unlock your device key to approve.</Empty>
            : opened.isLoading ? <Loading label="Decrypting on this device…" />
            : (
              <Stack spacing={1.5}>
                <Typography variant="subtitle2">{chosen.length} item(s) chosen</Typography>
                <Box component="ul" sx={{ m: 0, pl: 3 }}>
                  {chosen.map((i) => <li key={i.title.item_id}><Typography variant="body2">{i.content ? summary(i.content) : i.title.label}</Typography></li>)}
                </Box>
                <TextField label="Notes for the specialist (optional)" multiline minRows={3} value={notes} onChange={(e) => setNotes(e.target.value)}
                  helperText="Encrypted on this device and included in the package." />
                {to ? (
                  <Alert severity="info" data-testid="recipient-key">
                    Sending to {r.destination_department_name}, {r.destination_name}: department key {to.departmentFingerprint}
                    {to.patient ? " · a copy for the patient's app" : " · the patient has no app key yet, so no patient copy"}
                  </Alert>
                ) : <ErrorAlert error={toError} />}
                <ErrorAlert error={sign.error} />
                <Box>
                  <Button variant="contained" size="large" disabled={!to || sign.isPending || (!chosen.length && !notes.trim())}
                    onClick={() => sign.mutate()}>
                    {r.packages.length ? `Approve and sign version ${r.packages[0].version + 1}` : "Approve and sign"}
                  </Button>
                </Box>
              </Stack>
            )}
        </Section>
      )}
      <Section title="Signed versions"><Versions r={r} /></Section>
    </Stack>
  );
}
