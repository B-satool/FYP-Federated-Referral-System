import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Alert, Box, Button, Paper, Stack, Typography } from "@mui/material";
import { api } from "../../api/client";
import type { Diagnostic, ReferralDetail } from "../../api/types";
import { ResultReport } from "../../components/ResultReport";
import { Empty, ErrorAlert, fmtDate, KeyValue, Loading, OrderStatus, ReasonDialog, Section, Tag, UrgencyTag } from "../../components/common";
import { useMe, useRefData } from "../../hooks";
import { DiagnosticDraft, DiagnosticFields, diagnosticComplete } from "./ReferralForm";
import { useInvalidateReferral } from "./ReferralWorkspace";
import type { Role } from "./steps";

/** A returned result, laid out as a report with its images. */
export function ResultView({ d }: { d: Diagnostic }) {
  const rep = d.report;
  if (!rep) return null;
  return (
    <Box sx={{ mt: 1.5 }}>
      <ResultReport title={d.test + (d.body_area ? ` (${d.body_area})` : "")} subtitle={`${d.destination_name}, ${d.destination_department_name}`}
        values={rep.values} findings={rep.findings} impression={rep.impression} reportedBy={rep.reported_by} reportedAt={rep.reported_at}
        files={d.attachments.map((a) => ({ key: a.n, filename: a.filename, content_type: a.content_type, path: `/diagnostics/${d.id}/attachments/${a.n}` }))} />
    </Box>
  );
}

/** Staff record that the patient was told, then close the request once the doctor has seen every result. */
function FollowUp({ r }: { r: ReferralDetail }) {
  const refresh = useInvalidateReferral(r.id);
  const [informing, setInforming] = useState(false);
  const act = useMutation({
    mutationFn: ({ path, body }: { path: string; body?: unknown }) => api.post(path, body ?? {}),
    onSuccess: () => {
      setInforming(false);
      refresh();
    },
  });
  const unseen = r.diagnostics.filter((d) => d.status === "reported" && !d.seen_at);
  if (!["response_returned", "closed"].includes(r.status)) return null;
  return (
    <Section title="Follow-up">
      <ErrorAlert error={act.error} />
      <Stack spacing={1.5}>
        {unseen.length > 0 && <Tag tone="wait" label={`Waiting for ${r.requesting_doctor_name} to see ${unseen.length} result(s)`} />}
        {r.patient_informed_at ? (
          <Typography variant="body2">Patient told by {r.patient_informed_by}, {fmtDate(r.patient_informed_at)}: {r.patient_informed_note}</Typography>
        ) : (
          r.status !== "closed" && (
            <Button variant="contained" sx={{ alignSelf: "start" }} onClick={() => setInforming(true)}>
              Record that the patient was told
            </Button>
          )
        )}
        {r.status === "closed" ? (
          <Alert severity="success">Closed by {r.closed_by}, {fmtDate(r.closed_at)}.</Alert>
        ) : (
          <Button variant="contained" color="success" sx={{ alignSelf: "start" }} disabled={unseen.length > 0 || !r.patient_informed_at || act.isPending}
            onClick={() => act.mutate({ path: `/referrals/${r.id}/close`, body: { expected_version: r.row_version } })}>
            Close request
          </Button>
        )}
      </Stack>
      <ReasonDialog open={informing} title="Patient informed" label="How and what (e.g. phoned, clinic date given)" confirm="Record" busy={act.isPending}
        onClose={() => setInforming(false)} onConfirm={(note) => act.mutate({ path: `/referrals/${r.id}/patient-informed`, body: { note } })} />
    </Section>
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
    meta: { success: "Test added." },
    onSuccess: () => {
      setDraft([]);
      refresh();
    },
  });
  if (!rd.data || !me) return <Loading />;
  const closed = ["closed", "declined", "cancelled"].includes(r.status);
  const items = r.diagnostics;
  const canAdd = role === "doctor" && ["draft", "requested"].includes(r.status);

  return (
    <Stack spacing={2}>
      <Alert severity="info">
        {role === "staff"
          ? "Check each test and send it. The order carries the patient's name, date of birth, sex and CNIC; the department confirms the patient when it arrives."
          : "Each test is a separate order with its own status. Results come back here with the report and any images."}
      </Alert>
      <ErrorAlert error={act.error} />
      {items.length === 0 && <Empty>No tests or scans requested.</Empty>}
      {items.map((d) => (
        <Paper key={d.id} sx={{ p: 2 }}>
          <Stack direction={{ xs: "column", md: "row" }} justifyContent="space-between" spacing={1}>
            <Box>
              <Typography variant="subtitle1" component="h2" sx={{ fontWeight: 600 }}>
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
            ["Clinical question", d.clinical_question ?? "Visible to doctors only"],
            ["Requested by", d.requested_by],
            ...(d.sent_at ? [["Sent", `${d.sent_by}, ${fmtDate(d.sent_at)}`] as [string, string]] : []),
            ...(d.status === "requested" && !d.local_patient_id ? [["Patient", `${d.destination_name} confirms the patient when the order arrives`] as [string, string]] : []),
            ...(d.local_patient_id ? [["Their record", d.local_patient_id] as [string, string]] : []),
            ...(d.scheduled_for ? [["Appointment", fmtDate(d.scheduled_for)] as [string, string]] : []),
            ...(d.reject_reason ? [["Not accepted because", d.reject_reason] as [string, string]] : []),
          ]} />
          <ResultView d={d} />
          {d.seen_at && <Typography variant="caption" display="block" sx={{ mt: 1 }}>Seen by {d.seen_by}, {fmtDate(d.seen_at)}</Typography>}
          <Stack direction="row" spacing={1} sx={{ mt: 1.5 }} flexWrap="wrap" useFlexGap>
            {role === "staff" && d.status === "draft" && !closed && r.status !== "draft" && (
              <Button variant="contained" size="small" disabled={act.isPending} onClick={() => act.mutate({ path: `/diagnostics/${d.id}/send` })}>
                Send to {d.destination_name}
              </Button>
            )}
            {role === "doctor" && d.status === "reported" && !d.seen_at && (
              <Button variant="contained" size="small" disabled={act.isPending} onClick={() => act.mutate({ path: `/diagnostics/${d.id}/seen` })}>
                I have seen the result
              </Button>
            )}
            {role === "doctor" && ["draft", "rejected"].includes(d.status) && !closed && (
              <Button size="small" onClick={() => setCancelling(d)}>Withdraw this test</Button>
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
      {role === "staff" && <FollowUp r={r} />}
      {canAdd && (
        <Section title="Add another test or scan">
          {draft.length === 0 ? (
            <Button variant="outlined" onClick={() => setDraft([{ category: "laboratory", test: "", body_area: "", clinical_question: "", urgency: "routine", destination_institution: "", destination_department: "" }])}>
              Add a test or scan
            </Button>
          ) : (
            <DiagnosticFields rd={rd.data} items={draft} onChange={setDraft} ownInstitution={me.institution_id ?? ""} />
          )}
          <ErrorAlert error={add.error} />
          {draft.length > 0 && (
            <Button variant="contained" sx={{ mt: 2 }} disabled={add.isPending || !draft.every(diagnosticComplete)} onClick={() => add.mutate()}>
              Add {draft.length === 1 ? "test" : `${draft.length} tests`}
            </Button>
          )}
        </Section>
      )}
      {cancelling && (
        <ReasonDialog open title={`Withdraw ${cancelling.test}`} label="Reason" confirm="Withdraw test" busy={act.isPending}
          onClose={() => setCancelling(null)} onConfirm={(reason) => act.mutate({ path: `/diagnostics/${cancelling.id}/cancel`, body: { reason } })} />
      )}
    </Stack>
  );
}
