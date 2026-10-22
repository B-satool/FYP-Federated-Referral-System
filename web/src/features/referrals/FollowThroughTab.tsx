import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Grid,
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
import { api } from "../../api/client";
import type { ConsultationResponse, FollowupTask, ReferralDetail, ReferralEvent } from "../../api/types";
import { Empty, ErrorAlert, fmtDate, KeyValue, ReasonDialog, Tag } from "../../components/common";
import { hasRole, useMe } from "../../hooks";
import { useInvalidateReferral } from "./ReferralWorkspace";

type OutboxRow = { id: number; kind: string; message_key: string; status: string; attempts: number; last_error: string | null; created_at: string; sent_at: string | null };

export function FollowThroughTab({ r }: { r: ReferralDetail }) {
  const { data: me } = useMe();
  const refresh = useInvalidateReferral(r.id);
  const outbox = useQuery({ queryKey: ["referral", r.id, "delivery", r.row_version, r.status], queryFn: () => api.get<OutboxRow[]>(`/referrals/${r.id}/delivery`), refetchInterval: r.delivery_status === "pending" || r.delivery_status === "retrying" ? 3000 : false });
  const events = useQuery({ queryKey: ["referral", r.id, "events", r.row_version, r.status], queryFn: () => api.get<ReferralEvent[]>(`/referrals/${r.id}/events`) });
  const responses = useQuery({ queryKey: ["referral", r.id, "responses", r.row_version, r.status], queryFn: () => api.get<ConsultationResponse[]>(`/referrals/${r.id}/responses`) });
  const tasks = useQuery({ queryKey: ["referral", r.id, "tasks", r.row_version, r.status], queryFn: () => api.get<FollowupTask[]>(`/referrals/${r.id}/tasks`) });
  const [task, setTask] = useState({ description: "", assignee_name: "", due_date: "", specified_by: "" });
  const [outcomeFor, setOutcomeFor] = useState<{ task: FollowupTask; status: string } | null>(null);
  const [reviewFor, setReviewFor] = useState<ConsultationResponse | null>(null);
  const act = useMutation({
    mutationFn: ({ path, body }: { path: string; body?: unknown }) => api.post(path, body),
    onSuccess: () => {
      setOutcomeFor(null);
      setReviewFor(null);
      refresh();
    },
  });
  const addTask = useMutation({
    mutationFn: () => api.post(`/referrals/${r.id}/tasks`, { ...task, due_date: task.due_date || null, specified_by: task.specified_by || null }),
    onSuccess: () => {
      setTask({ description: "", assignee_name: "", due_date: "", specified_by: "" });
      refresh();
    },
  });
  const isClinician = hasRole(me, "clinician");
  const specialistEvents = (events.data ?? []).filter((e) => e.institution_id === "spec-c" || e.event_type.startsWith("deliver") || e.event_type.startsWith("send") || e.event_type.startsWith("amendment"));
  const canTasks = ["response_returned", "followup_pending"].includes(r.status);

  return (
    <Grid container spacing={2}>
      <Grid item xs={12} lg={6}>
        <Paper sx={{ p: 2 }}>
          <Typography variant="h6" gutterBottom>
            Delivery
          </Typography>
          <KeyValue
            items={[
              ["Delivery status", r.delivery_status],
              ["Received by specialist system", r.submitted_package_version ? `version ${r.submitted_package_version}` : "not yet"],
              ["Human acknowledgment", r.acknowledged_at ? fmtDate(r.acknowledged_at) : "not yet"],
              ["Acceptance", r.accepted_at ? fmtDate(r.accepted_at) : r.status === "declined" ? `declined: ${r.decline_reason}` : "not yet"],
            ]}
          />
          <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>
            Delivery, acknowledgment and acceptance are recorded separately.
          </Typography>
          {(outbox.data ?? []).map((o) => (
            <Alert key={o.id} severity={o.status === "sent" ? "success" : o.status === "failed" ? "error" : "info"} sx={{ mt: 1 }}>
              {o.kind.replace("_", " ")} · {o.status} · {o.attempts} attempt(s) · key {o.message_key}
              {o.last_error && <Typography variant="caption" display="block">{o.last_error}</Typography>}
            </Alert>
          ))}
          {r.delivery_status === "failed" && (
            <Button sx={{ mt: 1 }} variant="outlined" onClick={() => act.mutate({ path: `/referrals/${r.id}/retry-delivery` })}>
              Retry delivery
            </Button>
          )}
        </Paper>
        <Paper sx={{ p: 2, mt: 2 }}>
          <Typography variant="h6" gutterBottom>
            Specialist activity
          </Typography>
          {specialistEvents.length === 0 && <Empty>No activity yet.</Empty>}
          {specialistEvents.map((e) => (
            <Typography key={e.id} variant="body2" sx={{ mb: 0.5 }}>
              {fmtDate(e.created_at)}: {e.event_type === "status_change" ? `status → ${e.to_status}` : e.event_type.replace(/_/g, " ")} ({e.actor})
              {e.detail?.package_version ? ` · package v${String(e.detail.package_version)}` : ""}
            </Typography>
          ))}
        </Paper>
      </Grid>
      <Grid item xs={12} lg={6}>
        <Paper sx={{ p: 2 }}>
          <Typography variant="h6" gutterBottom>
            Consultation response
          </Typography>
          <ErrorAlert error={act.error || addTask.error} />
          {(responses.data ?? []).length === 0 && <Empty>No response returned yet.</Empty>}
          {(responses.data ?? []).map((resp) => (
            <Stack key={resp.id} spacing={1}>
              <Typography variant="body2" color="text.secondary">
                Approved by {resp.specialist_name}, {fmtDate(resp.approved_at)} · for package v{resp.package_version} · received {fmtDate(resp.received_at)}
              </Typography>
              <KeyValue items={Object.entries(resp.content).map(([k, v]) => [k.replace(/_/g, " "), v])} />
              <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                {resp.receipt_recorded_at ? (
                  <Tag tone="ok" label={`receipt recorded by ${resp.receipt_recorded_by}`} />
                ) : (
                  <Button size="small" variant="outlined" onClick={() => act.mutate({ path: `/responses/${resp.id}/record-receipt` })}>
                    Record receipt
                  </Button>
                )}
                {resp.reviewed_at ? (
                  <Tag tone="ok" label={`reviewed by ${resp.reviewed_by}`} />
                ) : (
                  <Button size="small" variant="contained" disabled={!isClinician} onClick={() => setReviewFor(resp)}>
                    {isClinician ? "Record clinician review" : "Clinician review pending"}
                  </Button>
                )}
              </Stack>
            </Stack>
          ))}
        </Paper>
        <Paper sx={{ p: 2, mt: 2 }}>
          <Typography variant="h6" gutterBottom>
            Follow-up tasks
          </Typography>
          {(tasks.data ?? []).length > 0 && (
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Task</TableCell>
                  <TableCell>Owner</TableCell>
                  <TableCell>Due</TableCell>
                  <TableCell>Status</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {tasks.data!.map((t) => (
                  <TableRow key={t.id}>
                    <TableCell>
                      {t.description}
                      <Typography variant="caption" display="block" color="text.secondary">
                        specified by {t.specified_by}
                      </Typography>
                    </TableCell>
                    <TableCell>{t.assignee_name ?? "Unassigned"}</TableCell>
                    <TableCell>{t.due_date ?? "No due date"}</TableCell>
                    <TableCell>
                      {t.status === "open" ? (
                        <Stack direction="row" spacing={0.5}>
                          <Button size="small" onClick={() => setOutcomeFor({ task: t, status: "completed" })}>
                            Completed
                          </Button>
                          <Button size="small" onClick={() => setOutcomeFor({ task: t, status: "not_completed" })}>
                            Not completed
                          </Button>
                        </Stack>
                      ) : (
                        <>
                          <Tag tone={t.status === "completed" ? "ok" : "warn"} label={t.status.replace("_", " ")} />
                          <Typography variant="caption" display="block">
                            {t.outcome} ({t.completed_by})
                          </Typography>
                        </>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
          {canTasks ? (
            <Stack spacing={1} sx={{ mt: 2 }}>
              <TextField size="small" label="Task (as specified by the clinician)" value={task.description} onChange={(e) => setTask({ ...task, description: e.target.value })} />
              <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
                <TextField size="small" label="Owner" value={task.assignee_name} onChange={(e) => setTask({ ...task, assignee_name: e.target.value })} />
                <TextField size="small" type="date" label="Due (optional)" InputLabelProps={{ shrink: true }} value={task.due_date} onChange={(e) => setTask({ ...task, due_date: e.target.value })} />
                {!isClinician && <TextField size="small" label="Specified by (clinician)" value={task.specified_by} onChange={(e) => setTask({ ...task, specified_by: e.target.value })} />}
              </Stack>
              <Button variant="outlined" sx={{ alignSelf: "start" }} disabled={task.description.length < 3 || addTask.isPending} onClick={() => addTask.mutate()}>
                Add task
              </Button>
            </Stack>
          ) : (
            <Typography variant="body2" color="text.secondary">
              Tasks are recorded after the specialist response is received.
            </Typography>
          )}
        </Paper>
        <Paper sx={{ p: 2, mt: 2 }}>
          <Typography variant="h6" gutterBottom>
            Closure
          </Typography>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            Closing records completion of the referral workflow after response review and disposition of all tasks. It is not a statement that the
            patient's condition has resolved.
          </Typography>
          {r.status === "closed" ? (
            <Tag tone="ok" label={`closed by ${r.closed_by}, ${fmtDate(r.closed_at)}`} />
          ) : (
            <Button variant="contained" disabled={!["response_returned", "followup_pending"].includes(r.status) || act.isPending} onClick={() => act.mutate({ path: `/referrals/${r.id}/close`, body: { expected_version: r.row_version } })}>
              Close referral
            </Button>
          )}
        </Paper>
      </Grid>
      {outcomeFor && (
        <ReasonDialog
          open
          title={outcomeFor.status === "completed" ? "Record task completion" : "Record why the task was not completed"}
          label="Outcome"
          confirm="Save"
          minLength={2}
          onClose={() => setOutcomeFor(null)}
          onConfirm={(outcome) => act.mutate({ path: `/tasks/${outcomeFor.task.id}/outcome`, body: { status: outcomeFor.status, outcome } })}
        />
      )}
      {reviewFor && (
        <ReasonDialog open title="Clinician review of the specialist response" label="Review note" confirm="Record review" minLength={2} onClose={() => setReviewFor(null)} onConfirm={(note) => act.mutate({ path: `/responses/${reviewFor.id}/review`, body: { note } })} />
      )}
    </Grid>
  );
}
