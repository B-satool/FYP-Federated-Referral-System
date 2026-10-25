import { useState } from "react";
import { Link as RouterLink, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Box,
  Button,
  IconButton,
  Link,
  MenuItem,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import DeleteOutline from "@mui/icons-material/DeleteOutline";
import { api } from "../../api/client";
import type { Order } from "../../api/types";
import { Empty, ErrorAlert, fmtDate, KeyValue, Loading, OrderStatus, PageHeader, ReasonDialog, Section, UrgencyTag } from "../../components/common";
import { ownService, useMe, useRefData } from "../../hooks";

const TODO = ["requested", "accepted", "scheduled", "done"];
const CATEGORY: Record<string, string> = { laboratory: "Laboratory test", imaging: "Imaging or scan", cardiac: "Cardiac test" };

function OrdersTable({ orders, label }: { orders: Order[]; label: string }) {
  const ref = useRefData();
  return (
    <Table size="small" aria-label={label}>
      <TableHead>
        <TableRow>
          <TableCell>Test or scan</TableCell>
          <TableCell>Patient</TableCell>
          <TableCell>From</TableCell>
          <TableCell>Urgency</TableCell>
          <TableCell>Status</TableCell>
          <TableCell>Received</TableCell>
        </TableRow>
      </TableHead>
      <TableBody>
        {orders.map((o) => (
          <TableRow key={o.id} hover>
            <TableCell>
              <Link component={RouterLink} to={`/orders/${o.id}`}>
                {o.test}
              </Link>
              <Typography variant="caption" display="block" color="text.secondary">
                {CATEGORY[o.category] ?? o.category} · {o.order_ref}
              </Typography>
            </TableCell>
            <TableCell>{o.patient_name}</TableCell>
            <TableCell>{o.sender_name || ref.data?.institutions[o.sender_institution]?.name || o.sender_institution}</TableCell>
            <TableCell>
              <UrgencyTag urgency={o.urgency} label={ref.data?.urgencies[o.urgency]?.label} />
            </TableCell>
            <TableCell>
              <OrderStatus status={o.status} />
            </TableCell>
            <TableCell>{fmtDate(o.received_at)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

export function OrderList() {
  const { data: me } = useMe();
  const service = ownService(me);
  const q = useQuery({ queryKey: ["orders", service], queryFn: () => api.get<Order[]>("/orders", service), enabled: !!me, refetchInterval: 15000 });
  const todo = (q.data ?? []).filter((o) => TODO.includes(o.status));
  const done = (q.data ?? []).filter((o) => !TODO.includes(o.status));
  return (
    <>
      <PageHeader
        title="Test and scan orders"
        subtitle={`Orders for ${me?.department_name ?? me?.department ?? "your department"} at ${me?.institution_name ?? "your institution"}.`}
      />
      {q.isLoading && <Loading />}
      <ErrorAlert error={q.error} />
      {q.data && (
        <Stack spacing={2}>
          <Section title={`To do (${todo.length})`} description="New, accepted and scheduled orders, and done orders waiting for a report.">
            {todo.length ? <OrdersTable orders={todo} label="Orders to do" /> : <Empty>Nothing to do.</Empty>}
          </Section>
          <Section title={`Finished (${done.length})`} description="Reported or not accepted.">
            {done.length ? <OrdersTable orders={done} label="Finished orders" /> : <Empty>No finished orders yet.</Empty>}
          </Section>
        </Stack>
      )}
    </>
  );
}

type ValueRow = { test: string; value: string; unit: string; reference: string; flag: string };
const EMPTY_ROW: ValueRow = { test: "", value: "", unit: "", reference: "", flag: "" };

function ReportView({ o }: { o: Order }) {
  return (
    <Stack spacing={1.5}>
      {o.report_text && <Typography sx={{ whiteSpace: "pre-wrap" }}>{o.report_text}</Typography>}
      {o.values.length > 0 && (
        <Table size="small" aria-label="Reported values">
          <TableHead>
            <TableRow>
              <TableCell>Test</TableCell>
              <TableCell>Value</TableCell>
              <TableCell>Reference</TableCell>
              <TableCell>Flag</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {o.values.map((v, i) => (
              <TableRow key={i}>
                <TableCell>{v.test}</TableCell>
                <TableCell>
                  {v.value} {v.unit ?? ""}
                </TableCell>
                <TableCell>{v.reference ?? ""}</TableCell>
                <TableCell>{v.flag ?? ""}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
      <Typography variant="caption" color="text.secondary">
        Reported by {o.reported_by}, {fmtDate(o.reported_at)}. Returned to the referring clinic.
      </Typography>
    </Stack>
  );
}

function ReportForm({ o, onSubmit, busy, error }: { o: Order; onSubmit: (body: unknown) => void; busy: boolean; error: unknown }) {
  const lab = o.category === "laboratory";
  const [rows, setRows] = useState<ValueRow[]>([{ ...EMPTY_ROW }]);
  const [findings, setFindings] = useState("");
  const [impression, setImpression] = useState("");
  const setRow = (i: number, patch: Partial<ValueRow>) => setRows(rows.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  const filled = rows.filter((r) => r.test.trim() && r.value.trim());
  const canSend = lab ? filled.length > 0 : !!(findings.trim() || impression.trim());
  const submit = () =>
    onSubmit({
      findings: findings.trim(),
      impression: impression.trim(),
      values: lab
        ? filled.map((r) => ({ test: r.test.trim(), value: r.value.trim(), unit: r.unit.trim() || null, reference: r.reference.trim() || null, flag: r.flag || null }))
        : [],
    });
  return (
    <Stack spacing={1.5}>
      {lab ? (
        <>
          <Table size="small" aria-label="Result values">
            <TableHead>
              <TableRow>
                <TableCell>Test</TableCell>
                <TableCell>Value</TableCell>
                <TableCell>Unit</TableCell>
                <TableCell>Reference range</TableCell>
                <TableCell>Flag</TableCell>
                <TableCell>
                  <span className="sr-only">Remove</span>
                </TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {rows.map((r, i) => (
                <TableRow key={i}>
                  <TableCell>
                    <TextField size="small" inputProps={{ "aria-label": `Test ${i + 1}` }} value={r.test} onChange={(e) => setRow(i, { test: e.target.value })} />
                  </TableCell>
                  <TableCell>
                    <TextField size="small" inputProps={{ "aria-label": `Value ${i + 1}` }} value={r.value} onChange={(e) => setRow(i, { value: e.target.value })} sx={{ width: 110 }} />
                  </TableCell>
                  <TableCell>
                    <TextField size="small" inputProps={{ "aria-label": `Unit ${i + 1}` }} value={r.unit} onChange={(e) => setRow(i, { unit: e.target.value })} sx={{ width: 100 }} />
                  </TableCell>
                  <TableCell>
                    <TextField size="small" inputProps={{ "aria-label": `Reference range ${i + 1}` }} value={r.reference} onChange={(e) => setRow(i, { reference: e.target.value })} sx={{ width: 130 }} />
                  </TableCell>
                  <TableCell>
                    <TextField select size="small" inputProps={{ "aria-label": `Flag ${i + 1}` }} value={r.flag} onChange={(e) => setRow(i, { flag: e.target.value })} sx={{ width: 100 }}>
                      <MenuItem value="">None</MenuItem>
                      <MenuItem value="high">High</MenuItem>
                      <MenuItem value="low">Low</MenuItem>
                    </TextField>
                  </TableCell>
                  <TableCell>
                    <IconButton aria-label={`Remove row ${i + 1}`} disabled={rows.length === 1} onClick={() => setRows(rows.filter((_, j) => j !== i))}>
                      <DeleteOutline />
                    </IconButton>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <Box>
            <Button size="small" onClick={() => setRows([...rows, { ...EMPTY_ROW }])}>
              Add a result
            </Button>
          </Box>
          <TextField label="Note (optional)" multiline minRows={2} value={findings} onChange={(e) => setFindings(e.target.value)} />
        </>
      ) : (
        <>
          <TextField label="Findings" multiline minRows={3} value={findings} onChange={(e) => setFindings(e.target.value)} />
          <TextField label="Impression" multiline minRows={2} value={impression} onChange={(e) => setImpression(e.target.value)} />
        </>
      )}
      <ErrorAlert error={error} />
      <Box>
        <Button variant="contained" onClick={submit} disabled={busy || !canSend}>
          Send report
        </Button>
      </Box>
    </Stack>
  );
}

export function OrderView() {
  const id = Number(useParams().id);
  const { data: me } = useMe();
  const ref = useRefData();
  const qc = useQueryClient();
  const service = ownService(me);
  const q = useQuery({ queryKey: ["order", service, id], queryFn: () => api.get<Order>(`/orders/${id}`, service), enabled: !!me });
  const [rejectOpen, setRejectOpen] = useState(false);
  const [when, setWhen] = useState("");
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["order", service, id] });
    qc.invalidateQueries({ queryKey: ["orders", service] });
  };
  const act = useMutation({
    mutationFn: ({ path, body }: { path: string; body?: unknown }) => api.post(`/orders/${id}/${path}`, body ?? {}, service),
    meta: { success: "Order updated. The referring clinic is told." },
    onSuccess: () => {
      setRejectOpen(false);
      refresh();
    },
  });
  const report = useMutation({
    mutationFn: (body: unknown) => api.post(`/orders/${id}/report`, body, service),
    meta: { success: "Report sent to the referring clinic." },
    onSuccess: refresh,
  });

  if (q.isLoading || !me) return <Loading />;
  if (q.error) return <ErrorAlert error={q.error} />;
  const o = q.data!;
  const canReject = ["requested", "accepted", "scheduled"].includes(o.status);

  return (
    <>
      <PageHeader
        title={`${o.test} · ${o.patient_name}`}
        back={{ to: "/orders", label: "Test and scan orders" }}
        subtitle={
          <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
            <OrderStatus status={o.status} />
            <UrgencyTag urgency={o.urgency} label={ref.data?.urgencies[o.urgency]?.label} />
            <span>{o.order_ref}</span>
          </Stack>
        }
      />
      <Stack spacing={2}>
        <Section title="Order">
          <KeyValue
            items={[
              ["Test or scan", `${o.test} (${CATEGORY[o.category] ?? o.category})`],
              ["Body area", o.body_area ?? "Not recorded"],
              ["Clinical question", o.clinical_question],
              ["Patient", `${o.patient_name}${o.patient_birth_date ? `, born ${o.patient_birth_date}` : ""}`],
              ["Our patient record", o.local_patient_id ?? "Not linked"],
              ["Requested by", `${o.requested_by}, ${o.sender_name || ref.data?.institutions[o.sender_institution]?.name || o.sender_institution}`],
              ["Referral", o.central_referral_id],
              ["Received", fmtDate(o.received_at)],
              ...(o.scheduled_for ? ([["Scheduled for", fmtDate(o.scheduled_for)]] as [string, string][]) : []),
              ...(o.reject_reason ? ([["Not accepted because", o.reject_reason]] as [string, string][]) : []),
            ]}
          />
        </Section>

        {!["reported", "rejected"].includes(o.status) && (
          <Section title="Next step" description="Each step is sent back to the referring clinic.">
            <ErrorAlert error={act.error} />
            <Stack direction={{ xs: "column", sm: "row" }} spacing={1} alignItems={{ sm: "center" }} flexWrap="wrap" useFlexGap>
              {o.status === "requested" && (
                <Button variant="contained" onClick={() => act.mutate({ path: "accept" })} disabled={act.isPending}>
                  Accept order
                </Button>
              )}
              {["accepted", "scheduled"].includes(o.status) && (
                <>
                  <TextField
                    type="datetime-local"
                    size="small"
                    label={o.status === "scheduled" ? "Change appointment" : "Appointment"}
                    InputLabelProps={{ shrink: true }}
                    value={when}
                    onChange={(e) => setWhen(e.target.value)}
                  />
                  <Button variant="outlined" disabled={!when || act.isPending} onClick={() => act.mutate({ path: "schedule", body: { scheduled_for: new Date(when).toISOString() } })}>
                    Schedule
                  </Button>
                  <Button variant="outlined" onClick={() => act.mutate({ path: "done" })} disabled={act.isPending}>
                    Mark as done
                  </Button>
                </>
              )}
              {canReject && (
                <Button color="error" variant="outlined" onClick={() => setRejectOpen(true)}>
                  Do not accept
                </Button>
              )}
            </Stack>
          </Section>
        )}

        {["accepted", "scheduled", "done"].includes(o.status) && (
          <Section title="Report" description="Write the result. It is filed in your own records and sent back to the referring clinic.">
            <ReportForm o={o} onSubmit={(body) => report.mutate(body)} busy={report.isPending} error={report.error} />
          </Section>
        )}
        {o.status === "reported" && (
          <Section title="Report">
            <ReportView o={o} />
          </Section>
        )}
        {o.status === "rejected" && <Alert severity="warning">Not accepted: {o.reject_reason}. The referring clinic has been told.</Alert>}

        <Section title="History">
          {o.history.length === 0 && <Empty>No history.</Empty>}
          <Paper variant="outlined" component="ol" sx={{ m: 0, p: 1.5, pl: 4 }}>
            {o.history.map((h, i) => (
              <li key={i}>
                <Typography variant="body2">
                  <strong>{h.status}</strong> · {h.by} · {fmtDate(h.at)}
                  {h.reason ? `. Reason: ${h.reason}` : ""}
                  {h.scheduled_for ? `. For ${fmtDate(h.scheduled_for)}` : ""}
                </Typography>
              </li>
            ))}
          </Paper>
        </Section>
      </Stack>

      <ReasonDialog
        open={rejectOpen}
        title="Do not accept this order"
        label="Reason"
        confirm="Send back to the clinic"
        onClose={() => setRejectOpen(false)}
        onConfirm={(reason) => act.mutate({ path: "reject", body: { reason } })}
        busy={act.isPending}
      >
        <Typography variant="body2" sx={{ mb: 1 }}>
          The reason goes back to the referring clinic so they can act on it, for example: wrong test, the patient needs preparation, or no capacity.
        </Typography>
      </ReasonDialog>
    </>
  );
}
