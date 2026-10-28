import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Alert, Button, MenuItem, Stack, Step, StepLabel, Stepper, TextField, Typography } from "@mui/material";
import { api } from "../../api/client";
import type { ConsultationResponse, FollowupTask, ReferralDetail } from "../../api/types";
import { Empty, ErrorAlert, fmtDate, KeyValue, ReasonDialog, Section, Tag } from "../../components/common";
import { useInvalidateReferral } from "./ReferralWorkspace";
import type { Role } from "./steps";
import { HoldNotice } from "./HoldNotice";

// The receiving doctor accepts or declines; no response is written (2026-10-28).
const PROGRESS = [
  ["submitted", "Delivered"],
  ["acknowledged", "Acknowledged"],
  ["accepted", "Accepted"],
  ["closed", "Closed"],
] as const;
const ORDER = ["requested", "submitted", "acknowledged", "accepted", "response_returned", "followup_pending", "closed"];

function Answer({ id, onDone }: { id: number; onDone: () => void }) {
  const [text, setText] = useState("");
  const send = useMutation({ mutationFn: () => api.post(`/clarifications/${id}/answer`, { answer: text }), meta: { success: "Answer sent." }, onSuccess: onDone });
  return (
    <Stack spacing={1}>
      <TextField multiline minRows={2} label="Your answer" value={text} onChange={(e) => setText(e.target.value)} />
      <ErrorAlert error={send.error} />
      <Button variant="contained" size="small" sx={{ alignSelf: "start" }} disabled={text.trim().length < 2 || send.isPending} onClick={() => send.mutate()}>
        Send answer
      </Button>
    </Stack>
  );
}

export function ResponseTab({ r, role }: { r: ReferralDetail; role: Role }) {
  const refresh = useInvalidateReferral(r.id);
  const responses = useQuery({ queryKey: ["referral", r.id, "responses", r.row_version], queryFn: () => api.get<ConsultationResponse[]>(`/referrals/${r.id}/responses`) });
  const tasks = useQuery({ queryKey: ["referral", r.id, "tasks", r.row_version], queryFn: () => api.get<FollowupTask[]>(`/referrals/${r.id}/tasks`) });
  const [informing, setInforming] = useState(false);
  const [task, setTask] = useState({ description: "", assignee_name: "", due_date: "" });
  const [outcome, setOutcome] = useState<FollowupTask | null>(null);
  const [reviewNote, setReviewNote] = useState("");
  const done = () => {
    setInforming(false);
    setOutcome(null);
    responses.refetch();
    tasks.refetch();
    refresh();
  };
  const act = useMutation({ mutationFn: ({ path, body }: { path: string; body?: unknown }) => api.post(path, body ?? {}), onSuccess: done });
  const addTask = useMutation({
    mutationFn: () => api.post(`/referrals/${r.id}/tasks`, { description: task.description, assignee_name: task.assignee_name || null, due_date: task.due_date || null }),
    meta: { success: "Task added." },
    onSuccess: () => {
      setTask({ description: "", assignee_name: "", due_date: "" });
      done();
    },
  });
  const idx = ORDER.indexOf(r.status);
  const response = responses.data?.[responses.data.length - 1];
  const openTasks = (tasks.data ?? []).filter((t) => t.status === "open");
  const canFollowUp = ["accepted", "response_returned", "followup_pending"].includes(r.status);
  const canInform = canFollowUp || r.status === "declined";

  return (
    <Stack spacing={2}>
      {r.submitted_package_version && !["declined", "cancelled"].includes(r.status) && (
        <Section title={`Progress at ${r.destination_name}`}>
          <Stepper activeStep={PROGRESS.findIndex(([s]) => ORDER.indexOf(s) > idx) === -1 ? PROGRESS.length : PROGRESS.findIndex(([s]) => ORDER.indexOf(s) > idx)} alternativeLabel>
            {PROGRESS.map(([s, label]) => (
              <Step key={s} completed={ORDER.indexOf(s) <= idx}>
                <StepLabel>{label}</StepLabel>
              </Step>
            ))}
          </Stepper>
        </Section>
      )}
      {r.status === "declined" && <Alert severity="warning">{r.destination_name} declined this referral. Reason: {r.decline_reason}</Alert>}
      {r.submitted_package_version && <HoldNotice r={r} />}

      {r.clarifications.length > 0 && (
        <Section title="Questions from the receiving hospital">
          <Stack spacing={2}>
            {r.clarifications.map((c) => (
              <Stack key={c.id} spacing={1}>
                <Typography variant="body2"><strong>{c.asked_by}</strong>, {fmtDate(c.asked_at)}: {c.question}</Typography>
                {c.status === "answered" ? (
                  <Typography variant="body2" color="text.secondary">Answered by {c.answered_by}, {fmtDate(c.answered_at)}: {c.answer}</Typography>
                ) : (
                  <Answer id={c.id} onDone={done} />
                )}
              </Stack>
            ))}
          </Stack>
        </Section>
      )}

      <Section title="Outcome">
        <ErrorAlert error={responses.error || act.error} />
        {r.status === "declined" ? (
          <Typography variant="body2">Declined by {r.destination_name}. Reason: {r.decline_reason}</Typography>
        ) : r.accepted_at ? (
          <Typography variant="body2">
            Accepted by {r.destination_name} on {fmtDate(r.accepted_at)}.
            {r.receiver_completed_at ? ` Marked complete by ${r.receiver_completed_by} on ${fmtDate(r.receiver_completed_at)}.` : ""}
          </Typography>
        ) : (
          <Empty>{r.submitted_package_version ? `Waiting for ${r.destination_name} to accept or decline.` : "The outcome appears here after the referral is sent."}</Empty>
        )}
        {response && ( /* a specialist response sent before 2026-10-28 */
          <Stack spacing={1.5}>
            <KeyValue items={[
              ["From", `${response.specialist_name}, ${r.destination_name}`],
              ["Received", fmtDate(response.received_at)],
              ["Assessment", response.content.assessment || "Not given"],
              ["Plan", response.content.plan || "Not given"],
              ["Instructions for the clinic", response.content.instructions_for_clinic || "None"],
              ["Appointment", response.content.appointment || "Not given"],
            ]} />
            {response.reviewed_at ? (
              <Tag tone="ok" label={`Seen by ${response.reviewed_by}, ${fmtDate(response.reviewed_at)}`} />
            ) : role === "doctor" ? (
              <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
                <TextField size="small" label="Note (optional)" value={reviewNote} onChange={(e) => setReviewNote(e.target.value)} sx={{ flex: 1 }} />
                <Button variant="contained" onClick={() => act.mutate({ path: `/responses/${response.id}/review`, body: { note: reviewNote } })}>
                  I have reviewed the outcome
                </Button>
              </Stack>
            ) : (
              <Tag tone="wait" label={`Waiting for ${r.requesting_doctor_name} to review`} />
            )}
          </Stack>
        )}
      </Section>

      {(canInform || r.status === "closed") && (
        <Section title="Follow-up">
          <Stack spacing={2}>
            <Stack direction={{ xs: "column", sm: "row" }} spacing={1} alignItems={{ sm: "center" }}>
              {r.patient_informed_at ? (
                <Tag tone="ok" label={`Patient informed by ${r.patient_informed_by}, ${fmtDate(r.patient_informed_at)}`} />
              ) : (
                <Button variant="contained" onClick={() => setInforming(true)} disabled={!canInform}>
                  Record that the patient was told
                </Button>
              )}
              {r.patient_informed_note && <Typography variant="body2" color="text.secondary">{r.patient_informed_note}</Typography>}
            </Stack>
            <Typography variant="subtitle2">Tasks</Typography>
            {(tasks.data ?? []).length === 0 && <Empty>No tasks.</Empty>}
            {(tasks.data ?? []).map((t) => (
              <Stack key={t.id} direction="row" justifyContent="space-between" alignItems="center">
                <Typography variant="body2">
                  {t.description}
                  {t.assignee_name ? ` · ${t.assignee_name}` : ""}
                  {t.due_date ? ` · due ${t.due_date}` : ""}
                  {t.status !== "open" ? ` · ${t.status.replace("_", " ")}: ${t.outcome}` : ""}
                </Typography>
                {t.status === "open" && canFollowUp && <Button size="small" onClick={() => setOutcome(t)}>Record outcome</Button>}
              </Stack>
            ))}
            {canFollowUp && (
              <Stack direction={{ xs: "column", md: "row" }} spacing={1}>
                <TextField size="small" label="New task (e.g. repeat HbA1c, confirm attendance)" value={task.description} onChange={(e) => setTask({ ...task, description: e.target.value })} sx={{ flex: 2 }} />
                <TextField size="small" label="Who" value={task.assignee_name} onChange={(e) => setTask({ ...task, assignee_name: e.target.value })} />
                <TextField size="small" type="date" label="Due" InputLabelProps={{ shrink: true }} value={task.due_date} onChange={(e) => setTask({ ...task, due_date: e.target.value })} />
                <Button variant="outlined" disabled={task.description.trim().length < 3 || addTask.isPending} onClick={() => addTask.mutate()}>Add task</Button>
              </Stack>
            )}
            {canFollowUp && (
              <>
                <Button variant="contained" color="success" sx={{ alignSelf: "start" }}
                  disabled={!r.patient_informed_at || openTasks.length > 0 || act.isPending}
                  onClick={() => act.mutate({ path: `/referrals/${r.id}/close`, body: { expected_version: r.row_version } })}>
                  Close referral
                </Button>
                <Typography variant="caption" color="text.secondary">
                  The doctor or staff can close the referral once the patient has been told and every task has an outcome. Closing does not describe the patient's condition.
                </Typography>
              </>
            )}
            {r.status === "closed" && <Alert severity="success">Closed by {r.closed_by}, {fmtDate(r.closed_at)}.</Alert>}
          </Stack>
        </Section>
      )}

      <ReasonDialog open={informing} title="Patient informed" label="How and what (e.g. phoned, clinic date given)" confirm="Record" busy={act.isPending}
        onClose={() => setInforming(false)} onConfirm={(note) => act.mutate({ path: `/referrals/${r.id}/patient-informed`, body: { note } })} />
      {outcome && (
        <ReasonDialog open title={`Outcome: ${outcome.description}`} label="Outcome" confirm="Mark completed" busy={act.isPending}
          onClose={() => setOutcome(null)} onConfirm={(text) => act.mutate({ path: `/tasks/${outcome.id}/outcome`, body: { status: "completed", outcome: text } })}>
          <TextField select size="small" label="Status" value="completed" sx={{ mb: 1 }} disabled>
            <MenuItem value="completed">Completed</MenuItem>
          </TextField>
        </ReasonDialog>
      )}
    </Stack>
  );
}
