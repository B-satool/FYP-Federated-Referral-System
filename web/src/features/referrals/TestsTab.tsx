import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Alert, Box, Button, Paper, Stack, Table, TableBody, TableCell, TableHead, TableRow, Typography } from "@mui/material";
import { api } from "../../api/client";
import type { Diagnostic, ReferralDetail } from "../../api/types";
import { Empty, ErrorAlert, fmtDate, KeyValue, Loading, OrderStatus, ReasonDialog, Section, UrgencyTag } from "../../components/common";
import { useMe, useRefData } from "../../hooks";
import { DiagnosticDraft, DiagnosticFields, diagnosticComplete } from "./ReferralForm";
import { useInvalidateReferral } from "./ReferralWorkspace";
import type { Role } from "./steps";

export function ResultView({ d }: { d: Diagnostic }) {
  const rep = d.report;
  if (!rep) return null;
  return (
    <Box sx={{ mt: 1.5 }}>
      <Typography variant="subtitle2">Result</Typography>
      {rep.findings && <Typography variant="body2"><strong>Findings:</strong> {rep.findings}</Typography>}
      {rep.impression && <Typography variant="body2"><strong>Impression:</strong> {rep.impression}</Typography>}
      {!!rep.values?.length && (
        <Table size="small" sx={{ mt: 1 }} aria-label={`${d.test} results`}>
          <TableHead>
            <TableRow>
              <TableCell>Test</TableCell>
              <TableCell>Value</TableCell>
              <TableCell>Reference</TableCell>
              <TableCell>Flag</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {rep.values.map((v, i) => (
              <TableRow key={i}>
                <TableCell>{v.test}</TableCell>
                <TableCell>{v.value} {v.unit ?? ""}</TableCell>
                <TableCell>{v.reference ?? ""}</TableCell>
                <TableCell>{v.flag ?? ""}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
      <Typography variant="caption" color="text.secondary">
        Reported by {rep.reported_by}, {fmtDate(rep.reported_at)}
      </Typography>
    </Box>
  );
}

export function TestsTab({ r, role }: { r: ReferralDetail; role: Role }) {
  const { data: me } = useMe();
  const rd = useRefData();
  const refresh = useInvalidateReferral(r.id);
  const [draft, setDraft] = useState<DiagnosticDraft[]>([]);
  const [cancelling, setCancelling] = useState<Diagnostic | null>(null);
  const act = useMutation({
    mutationFn: ({ path, body }: { path: string; body?: unknown }) => api.post(path, body ?? {}),
    onSuccess: () => {
      setCancelling(null);
      refresh();
    },
  });
  const add = useMutation({
    mutationFn: async () => {
      for (const d of draft) await api.post(`/referrals/${r.id}/diagnostics`, { ...d, body_area: d.body_area || null });
    },
    meta: { success: "Request added." },
    onSuccess: () => {
      setDraft([]);
      refresh();
    },
  });
  if (!rd.data || !me) return <Loading />;
  const closed = ["closed", "declined", "cancelled"].includes(r.status);
  const items = r.diagnostics;

  return (
    <Stack spacing={2}>
      <Alert severity="info">
        Each test or scan is a separate order with its own status. It can be done before the specialist has looked at the referral, and the result comes
        back here. The laboratory or imaging department also confirms the patient before accepting.
      </Alert>
      <ErrorAlert error={act.error} />
      {items.length === 0 && <Empty>No tests or scans requested.</Empty>}
      {items.map((d) => (
        <Paper key={d.id} sx={{ p: 2 }}>
          <Stack direction={{ xs: "column", md: "row" }} justifyContent="space-between" spacing={1}>
            <Box>
              <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                {d.test}
                {d.body_area ? ` (${d.body_area})` : ""}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {d.category_label} · {d.destination_name}, {d.destination_department_name} · {d.reference}
              </Typography>
            </Box>
            <Stack direction="row" spacing={1} alignItems="center">
              <UrgencyTag urgency={d.urgency} label={d.urgency_label} />
              <OrderStatus status={d.status} />
            </Stack>
          </Stack>
          <KeyValue items={[
            ["Clinical question", d.clinical_question],
            ["Requested by", d.requested_by],
            ...(d.sent_at ? [["Sent", `${d.sent_by}, ${fmtDate(d.sent_at)}`] as [string, string]] : []),
            ...(d.scheduled_for ? [["Appointment", fmtDate(d.scheduled_for)] as [string, string]] : []),
            ...(d.reject_reason ? [["Not accepted because", d.reject_reason] as [string, string]] : []),
          ]} />
          <ResultView d={d} />
          {d.seen_at && <Typography variant="caption" display="block">Seen by {d.seen_by}, {fmtDate(d.seen_at)}</Typography>}
          <Stack direction="row" spacing={1} sx={{ mt: 1.5 }} flexWrap="wrap" useFlexGap>
            {role === "staff" && d.status === "draft" && !closed && (
              <Button variant="contained" size="small" disabled={act.isPending} onClick={() => act.mutate({ path: `/diagnostics/${d.id}/send` })}>
                Send to {d.destination_name}
              </Button>
            )}
            {role === "doctor" && d.status === "reported" && !d.seen_at && (
              <Button variant="contained" size="small" disabled={act.isPending} onClick={() => act.mutate({ path: `/diagnostics/${d.id}/seen` })}>
                I have seen the result
              </Button>
            )}
            {["draft", "rejected"].includes(d.status) && !closed && (
              <Button size="small" onClick={() => setCancelling(d)}>Cancel request</Button>
            )}
          </Stack>
          {d.history.length > 1 && (
            <details style={{ marginTop: 8 }}>
              <summary><Typography component="span" variant="caption">History</Typography></summary>
              {d.history.map((h, i) => (
                <Typography key={i} variant="caption" display="block">
                  {fmtDate(h.at)}: {h.status} by {h.by}{h.reason ? ` (${h.reason})` : ""}
                </Typography>
              ))}
            </details>
          )}
        </Paper>
      ))}
      {!closed && (
        <Section title="Request another test or scan">
          <DiagnosticFields rd={rd.data} items={draft} onChange={setDraft} ownInstitution={me.institution_id ?? ""} />
          <ErrorAlert error={add.error} />
          {draft.length > 0 && (
            <Button variant="contained" sx={{ mt: 2 }} disabled={add.isPending || !draft.every(diagnosticComplete)} onClick={() => add.mutate()}>
              Add {draft.length === 1 ? "request" : `${draft.length} requests`}
            </Button>
          )}
        </Section>
      )}
      {cancelling && (
        <ReasonDialog open title={`Cancel ${cancelling.test}`} label="Reason" confirm="Cancel request" busy={act.isPending}
          onClose={() => setCancelling(null)} onConfirm={(reason) => act.mutate({ path: `/diagnostics/${cancelling.id}/cancel`, body: { reason } })} />
      )}
    </Stack>
  );
}
