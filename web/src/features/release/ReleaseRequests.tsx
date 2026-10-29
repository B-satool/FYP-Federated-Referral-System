import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, MenuItem, Paper, Stack, Table, TableBody, TableCell, TableHead, TableRow, TextField, Typography } from "@mui/material";
import { api } from "../../api/client";
import { ErrorAlert, fmtDate, Loading, PageHeader, Tag, Tone } from "../../components/common";
import { ownService, useMe, useRefData } from "../../hooks";

type ReleaseRequest = {
  id: number; referral_ref: string; requesting_org: string; practitioner_name: string | null; purpose: string;
  consent_ref: string; local_patient_id: string | null; categories: string[]; sensitive: string[]; since: string | null;
  reason: string | null; status: string; refusals: { reason: string; message: string; categories: string[] }[];
  item_count: number; policy_version: string; decided_by: string | null; decided_at: string | null; delivered: boolean;
  delivery_error: string | null; created_at: string;
};

const TONE: Record<string, Tone> = { pending_manual_review: "warn", answered: "ok", partial: "warn", refused: "bad", no_records: "neutral" };
const PURPOSE: Record<string, string> = { TREAT: "Treatment and referral", ETREAT: "Emergency treatment", PATRQT: "Patient's own request" };
const DECLINE: [string, string][] = [
  ["request_incomplete_or_invalid", "The request is incomplete or invalid"],
  ["consent_expired_or_out_of_range", "The consent does not cover it"],
  ["sensitive_category_no_specific_consent", "Too sensitive without the patient's specific consent"],
  ["prohibited_by_law", "The law does not allow it"],
];

/** Requests from other institutions that this institution's policy holds for its staff (spec v4 6.2). Staff see the
 * request (who asks, why, under which consent), never the records; approving releases them encrypted. */
export function ReleaseRequests() {
  const { data: me } = useMe();
  const ref = useRefData();
  const service = ownService(me);
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["release-requests", service], queryFn: () => api.get<ReleaseRequest[]>("/e2e/record-requests", service),
    enabled: service !== "central" });
  const [declining, setDeclining] = useState<ReleaseRequest | null>(null);
  const [reason, setReason] = useState(DECLINE[0][0]);
  const [note, setNote] = useState("");
  const done = () => qc.invalidateQueries({ queryKey: ["release-requests", service] });
  const approve = useMutation({ mutationFn: (id: number) => api.post(`/e2e/record-requests/${id}/approve`, undefined, service),
    meta: { success: "Released, encrypted for the requesting doctor." }, onSuccess: done });
  const decline = useMutation({ mutationFn: () => api.post(`/e2e/record-requests/${declining!.id}/decline`, { reason, note }, service),
    meta: { success: "Declined; the requester sees the reason." }, onSuccess: () => { setDeclining(null); done(); } });
  const redeliver = useMutation({ mutationFn: (id: number) => api.post(`/e2e/record-requests/${id}/redeliver`, undefined, service),
    meta: { success: "Sent again." }, onSuccess: done });
  if (service === "central") return <Alert severity="info">Requests are reviewed in each institution's own system.</Alert>;
  if (q.isLoading) return <Loading />;
  const rows = q.data ?? [];
  const pending = rows.filter((x) => x.status === "pending_manual_review");
  const inst = (id: string) => ref.data?.institutions[id]?.name ?? id;
  return (
    <>
      <PageHeader title="Records requests from other institutions"
        subtitle={`${me?.institution_name ?? ""} answers these under the patient's consent and its own release policy. Most are answered automatically; these wait for you.`} />
      <ErrorAlert error={q.error || approve.error || decline.error || redeliver.error} />
      <Paper sx={{ mb: 2, overflowX: "auto" }}>
        <Typography variant="h6" sx={{ p: 2, pb: 0 }}>Waiting for review ({pending.length})</Typography>
        <Table size="small">
          <TableHead><TableRow><TableCell>Referral</TableCell><TableCell>Who asks</TableCell><TableCell>Why</TableCell><TableCell>Consent</TableCell><TableCell>Held because</TableCell><TableCell /></TableRow></TableHead>
          <TableBody>
            {pending.map((x) => (
              <TableRow key={x.id}>
                <TableCell>{x.referral_ref}<Typography variant="caption" display="block">patient {x.local_patient_id}</Typography></TableCell>
                <TableCell>{x.practitioner_name ?? "A doctor"}, {inst(x.requesting_org)}</TableCell>
                <TableCell>{PURPOSE[x.purpose] ?? x.purpose}{x.reason ? `: ${x.reason}` : ""}</TableCell>
                <TableCell>{x.consent_ref}{x.sensitive.length ? ` · names ${x.sensitive.join(", ")}` : ""}</TableCell>
                <TableCell>{x.refusals.filter((f) => f.reason === "pending_manual_review").map((f) => f.message).join(" ")} <Typography variant="caption" display="block">policy {x.policy_version}</Typography></TableCell>
                <TableCell align="right">
                  <Stack direction="row" spacing={1} justifyContent="flex-end">
                    <Button size="small" variant="contained" onClick={() => approve.mutate(x.id)} disabled={approve.isPending}>Release</Button>
                    <Button size="small" color="warning" onClick={() => setDeclining(x)}>Decline</Button>
                  </Stack>
                </TableCell>
              </TableRow>
            ))}
            {!pending.length && <TableRow><TableCell colSpan={6}>Nothing is waiting.</TableCell></TableRow>}
          </TableBody>
        </Table>
      </Paper>
      <Paper sx={{ overflowX: "auto" }}>
        <Typography variant="h6" sx={{ p: 2, pb: 0 }}>All requests</Typography>
        <Table size="small">
          <TableHead><TableRow><TableCell>When</TableCell><TableCell>Referral</TableCell><TableCell>From</TableCell><TableCell>Outcome</TableCell><TableCell>Records</TableCell><TableCell /></TableRow></TableHead>
          <TableBody>
            {rows.map((x) => (
              <TableRow key={x.id}>
                <TableCell>{fmtDate(x.created_at)}</TableCell>
                <TableCell>{x.referral_ref}</TableCell>
                <TableCell>{inst(x.requesting_org)}</TableCell>
                <TableCell><Tag tone={TONE[x.status] ?? "info"} label={x.status.replace(/_/g, " ")} />
                  {x.refusals.filter((f) => f.reason !== "pending_manual_review").map((f, i) => <Typography key={i} variant="caption" display="block">{f.reason}: {f.message}</Typography>)}
                  {x.decided_by && <Typography variant="caption" display="block">by {x.decided_by}</Typography>}</TableCell>
                <TableCell>{x.item_count}</TableCell>
                <TableCell>{!x.delivered && x.delivery_error && <Button size="small" onClick={() => redeliver.mutate(x.id)}>Send again</Button>}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Paper>
      {declining && (
        <Paper sx={{ p: 2, mt: 2 }}>
          <Typography variant="h6">Decline {declining.referral_ref}</Typography>
          <TextField select fullWidth label="Reason (sent to the requester)" value={reason} onChange={(e) => setReason(e.target.value)} sx={{ my: 1 }}>
            {DECLINE.map(([k, v]) => <MenuItem key={k} value={k}>{v}</MenuItem>)}
          </TextField>
          <TextField fullWidth label="Note (optional)" value={note} onChange={(e) => setNote(e.target.value)} />
          <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
            <Button variant="contained" color="warning" onClick={() => decline.mutate()}>Decline</Button>
            <Button onClick={() => setDeclining(null)}>Cancel</Button>
          </Stack>
        </Paper>
      )}
    </>
  );
}
