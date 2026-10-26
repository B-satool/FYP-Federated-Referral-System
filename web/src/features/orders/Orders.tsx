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
import { fmtCnic } from "../../components/ReferralLetter";
import { ReportFile, ResultReport } from "../../components/ResultReport";
import { ownService, useMe, useRefData } from "../../hooks";
import { ConfirmPatient, sexLabel } from "../identity/ConfirmPatient";

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
type PickedFile = { filename: string; content_type: string; size: number; data: string };

const FILE_TYPES = ["image/png", "image/jpeg", "application/pdf"];
const MAX_FILE_BYTES = 5 * 1024 * 1024;
const MAX_FILES = 6;

/** Reads a file as base64 without the "data:...;base64," prefix. */
function readBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const s = String(reader.result ?? "");
      resolve(s.slice(s.indexOf(",") + 1));
    };
    reader.onerror = () => reject(reader.error ?? new Error("Could not read the file"));
    reader.readAsDataURL(file);
  });
}

function fmtSize(bytes: number) {
  return bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

function ReportForm({ o, onSubmit, busy, error }: { o: Order; onSubmit: (body: unknown) => void; busy: boolean; error: unknown }) {
  const lab = o.category === "laboratory";
  const [rows, setRows] = useState<ValueRow[]>([{ ...EMPTY_ROW }]);
  const [findings, setFindings] = useState("");
  const [impression, setImpression] = useState("");
  const [files, setFiles] = useState<PickedFile[]>([]);
  const [fileProblem, setFileProblem] = useState<string | null>(null);
  const setRow = (i: number, patch: Partial<ValueRow>) => setRows(rows.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  const filled = rows.filter((r) => r.test.trim() && r.value.trim());

  const problems: string[] = [];
  if (lab) {
    if (filled.length === 0) problems.push("Enter at least one result (test name and result).");
  } else {
    if (findings.trim().length < 10) problems.push("Write the findings (at least 10 characters).");
    if (impression.trim().length < 5) problems.push("Write the impression (at least 5 characters).");
    if (files.length === 0) problems.push("Attach at least one image or file.");
  }
  const canSend = problems.length === 0;

  const pick = async (list: FileList | null) => {
    setFileProblem(null);
    if (!list) return;
    const next = [...files];
    const issues: string[] = [];
    for (const f of Array.from(list)) {
      if (!FILE_TYPES.includes(f.type)) {
        issues.push(`${f.name}: only PNG, JPEG or PDF files can be attached.`);
        continue;
      }
      if (f.size > MAX_FILE_BYTES) {
        issues.push(`${f.name}: each file must be under 5 MB.`);
        continue;
      }
      if (next.length >= MAX_FILES) {
        issues.push(`Up to ${MAX_FILES} files can be attached.`);
        break;
      }
      try {
        next.push({ filename: f.name, content_type: f.type, size: f.size, data: await readBase64(f) });
      } catch {
        issues.push(`${f.name}: could not be read.`);
      }
    }
    setFiles(next);
    if (issues.length) setFileProblem(issues.join(" "));
  };

  const submit = () =>
    onSubmit({
      findings: findings.trim(),
      impression: impression.trim(),
      values: lab
        ? filled.map((r) => ({ test: r.test.trim(), value: r.value.trim(), unit: r.unit.trim() || null, reference: r.reference.trim() || null, flag: r.flag || null }))
        : [],
      attachments: files.map((f) => ({ filename: f.filename, content_type: f.content_type, data: f.data })),
    });
  const inputId = `report-files-${o.id}`;
  return (
    <Stack spacing={1.5}>
      {lab && (
        <>
          <Typography variant="subtitle2">Results</Typography>
          <Table size="small" aria-label="Result values">
            <TableBody>
              {rows.map((r, i) => (
                <TableRow key={i} sx={{ "& td": { borderBottom: 0, px: 0.5, pt: 1.25 } }}>
                  <TableCell>
                    <TextField size="small" label="Test" value={r.test} onChange={(e) => setRow(i, { test: e.target.value })} />
                  </TableCell>
                  <TableCell>
                    <TextField size="small" label="Result" value={r.value} onChange={(e) => setRow(i, { value: e.target.value })} sx={{ width: 110 }} />
                  </TableCell>
                  <TableCell>
                    <TextField size="small" label="Unit" value={r.unit} onChange={(e) => setRow(i, { unit: e.target.value })} sx={{ width: 100 }} />
                  </TableCell>
                  <TableCell>
                    <TextField size="small" label="Reference range" value={r.reference} onChange={(e) => setRow(i, { reference: e.target.value })} sx={{ width: 150 }} />
                  </TableCell>
                  <TableCell>
                    <TextField select size="small" label="Flag" value={r.flag} onChange={(e) => setRow(i, { flag: e.target.value })} sx={{ width: 100 }}>
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
              Add a result row
            </Button>
          </Box>
        </>
      )}
      <TextField
        label="Findings"
        helperText={lab ? "Optional for a laboratory report" : "Required, at least 10 characters"}
        multiline
        minRows={3}
        value={findings}
        onChange={(e) => setFindings(e.target.value)}
      />
      <TextField
        label="Impression"
        helperText={lab ? "Optional for a laboratory report" : "Required, at least 5 characters"}
        multiline
        minRows={2}
        value={impression}
        onChange={(e) => setImpression(e.target.value)}
      />
      <Box>
        <Typography variant="subtitle2">Images and files{lab ? " (optional)" : " (at least one)"}</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          PNG, JPEG or PDF, each under 5 MB, up to {MAX_FILES}.
        </Typography>
        <Button component="label" htmlFor={inputId} variant="outlined" size="small" disabled={files.length >= MAX_FILES}>
          Choose files
        </Button>
        <input
          id={inputId}
          className="sr-only"
          type="file"
          aria-label="Add images or files"
          accept="image/png,image/jpeg,application/pdf"
          multiple
          onChange={(e) => {
            const list = e.target.files;
            void pick(list).finally(() => {
              e.target.value = "";
            });
          }}
        />
        {fileProblem && (
          <Alert severity="warning" sx={{ mt: 1 }}>
            {fileProblem}
          </Alert>
        )}
        {files.length > 0 && (
          <Stack component="ul" spacing={0.5} sx={{ m: 0, mt: 1, pl: 0, listStyle: "none" }}>
            {files.map((f, i) => (
              <Stack component="li" key={`${f.filename}-${i}`} direction="row" spacing={1} alignItems="center">
                <Typography variant="body2">
                  {f.filename} <Typography component="span" variant="caption" color="text.secondary">({fmtSize(f.size)})</Typography>
                </Typography>
                <IconButton size="small" aria-label={`Remove ${f.filename}`} onClick={() => setFiles(files.filter((_, j) => j !== i))}>
                  <DeleteOutline fontSize="small" />
                </IconButton>
              </Stack>
            ))}
          </Stack>
        )}
      </Box>
      {!canSend && (
        <Box component="ul" sx={{ m: 0, pl: 2.5, color: "text.secondary" }}>
          {problems.map((p) => (
            <li key={p}>
              <Typography variant="body2">{p}</Typography>
            </li>
          ))}
        </Box>
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
  const needsPatient = !o.local_patient_id;
  const files: ReportFile[] = (o.attachments ?? []).map((a) => ({ key: a.id, filename: a.filename, content_type: a.content_type, path: `/orders/${o.id}/attachments/${a.id}` }));

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
              ["Patient", `${o.patient_name}${o.patient_birth_date ? `, born ${o.patient_birth_date}` : ""}${o.patient_sex ? `, ${sexLabel(o.patient_sex).toLowerCase()}` : ""}`],
              ["CNIC", fmtCnic(o.patient_cnic)],
              ["Our patient record", o.local_patient_id ?? "Not confirmed yet"],
              ["Requested by", `${o.requested_by}, ${o.sender_name || ref.data?.institutions[o.sender_institution]?.name || o.sender_institution}`],
              ["Referral", o.central_referral_id],
              ["Received", fmtDate(o.received_at)],
              ...(o.scheduled_for ? ([["Scheduled for", fmtDate(o.scheduled_for)]] as [string, string][]) : []),
              ...(o.reject_reason ? ([["Not accepted because", o.reject_reason]] as [string, string][]) : []),
            ]}
          />
        </Section>

        {(o.status === "requested" || needsPatient) && !["reported", "rejected", "cancelled"].includes(o.status) && (
          <Section
            title="Confirm the patient"
            description={needsPatient ? "Before accepting, check who this patient is in your records: match an existing record or register the patient as new." : undefined}
          >
            <ConfirmPatient
              linkId={o.link_request_id}
              localPatientId={o.local_patient_id}
              patient={{ name: o.patient_name, birth_date: o.patient_birth_date, sex: o.patient_sex, cnic: o.patient_cnic }}
              requester={o.sender_name || ref.data?.institutions[o.sender_institution]?.name || o.sender_institution}
              onDone={refresh}
            />
          </Section>
        )}

        {!["reported", "rejected", "cancelled"].includes(o.status) && (
          <Section title="Next step" description="Each step is sent back to the referring clinic.">
            <ErrorAlert error={act.error} />
            <Stack direction={{ xs: "column", sm: "row" }} spacing={1} alignItems={{ sm: "center" }} flexWrap="wrap" useFlexGap>
              {o.status === "requested" && (
                <Button
                  variant="contained"
                  onClick={() => act.mutate({ path: "accept" })}
                  disabled={act.isPending || needsPatient}
                  title={needsPatient ? "Confirm the patient first" : undefined}
                >
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
                  Reject order
                </Button>
              )}
            </Stack>
            {o.status === "requested" && needsPatient && (
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                Confirm the patient above before accepting the order.
              </Typography>
            )}
          </Section>
        )}

        {["accepted", "scheduled", "done"].includes(o.status) && (
          <Section title="Report" description="Write the result. It is filed in your own records and sent back to the referring clinic.">
            <ReportForm o={o} onSubmit={(body) => report.mutate(body)} busy={report.isPending} error={report.error} />
          </Section>
        )}
        {o.status === "reported" && (
          <Section title="Report" description="Filed in your records and returned to the referring clinic.">
            <ResultReport
              title={o.test}
              subtitle={`${CATEGORY[o.category] ?? o.category} · ${o.order_ref} · ${o.patient_name}`}
              values={o.values}
              findings={o.findings ?? (o.values.length ? null : o.report_text)}
              impression={o.impression}
              reportedBy={o.reported_by}
              reportedAt={o.reported_at}
              files={files}
              service={service}
            />
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
        title="Reject this order"
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
