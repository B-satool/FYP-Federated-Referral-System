import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  MenuItem,
  Paper,
  Stack,
  Switch,
  TextField,
  Typography,
} from "@mui/material";
import { api } from "../../api/client";
import type { Clarification, ReferralDetail, ReviewItem } from "../../api/types";
import { Empty, ErrorAlert, fmtDate, Loading, ReasonDialog, Tag } from "../../components/common";
import { EvidenceRef } from "../../components/EvidenceRef";
import { hasRole, useMe, useRefData } from "../../hooks";
import { useInvalidateReferral } from "../referrals/ReferralWorkspace";

const KIND_TONE = { missing: "bad", unresolved: "warn", discrepancy: "bad", link_invalidated: "bad" } as const;
const ACTIONS: [string, string][] = [
  ["resolved", "Mark resolved"],
  ["uncertainty_recorded", "Record remaining uncertainty"],
  ["not_applicable", "Not applicable"],
  ["overridden", "Clinician override"],
];

function NewClarification({ r, item, onClose, onDone }: { r: ReferralDetail; item: ReviewItem | null; onClose: () => void; onDone: () => void }) {
  const ref = useRefData();
  const options = [r.source_institution, ...r.verified_links.map((l) => l.institution_id)];
  const [assignee, setAssignee] = useState(options[0]);
  const [question, setQuestion] = useState(item ? `Please provide: ${item.title}` : "");
  const [due, setDue] = useState("");
  const create = useMutation({
    mutationFn: () => api.post(`/referrals/${r.id}/clarifications`, { question, assignee_institution: assignee, review_item_id: item?.id ?? null, due_date: due || null }),
    onSuccess: onDone,
  });
  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>Request missing or corrected information</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          <TextField select label="Assign to" value={assignee} onChange={(e) => setAssignee(e.target.value)} helperText="Your clinic, or a participating institution with a verified link for this patient">
            {options.map((o) => (
              <MenuItem key={o} value={o}>
                {ref.data?.institutions[o]?.name ?? o}
              </MenuItem>
            ))}
          </TextField>
          <TextField label="Question" multiline minRows={3} value={question} onChange={(e) => setQuestion(e.target.value)} />
          <TextField type="date" label="Due date (optional)" InputLabelProps={{ shrink: true }} value={due} onChange={(e) => setDue(e.target.value)} />
          <ErrorAlert error={create.error} />
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="contained" onClick={() => create.mutate()} disabled={question.trim().length < 5 || create.isPending}>
          Send request
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export function ReviewTab({ r }: { r: ReferralDetail }) {
  const { data: me } = useMe();
  const refresh = useInvalidateReferral(r.id);
  const [showAll, setShowAll] = useState(false);
  const [resolving, setResolving] = useState<{ item: ReviewItem; action: string } | null>(null);
  const [clarifyFor, setClarifyFor] = useState<ReviewItem | null | undefined>(undefined);
  const [answering, setAnswering] = useState<Clarification | null>(null);
  const items = useQuery({ queryKey: ["referral", r.id, "review-items"], queryFn: () => api.get<ReviewItem[]>(`/referrals/${r.id}/review-items`) });
  const clars = useQuery({ queryKey: ["referral", r.id, "clarifications"], queryFn: () => api.get<Clarification[]>(`/referrals/${r.id}/clarifications`) });
  const resolve = useMutation({
    mutationFn: ({ id, action, rationale }: { id: number; action: string; rationale: string }) => api.post(`/review-items/${id}/resolve`, { action, rationale }),
    onSuccess: () => {
      setResolving(null);
      refresh();
    },
  });
  const clarAct = useMutation({
    mutationFn: ({ path, body }: { path: string; body: unknown }) => api.post(path, body),
    onSuccess: () => {
      setAnswering(null);
      refresh();
    },
  });
  const isClinician = hasRole(me, "clinician");
  const visible = (items.data ?? []).filter((i) => showAll || i.status === "open");

  return (
    <Stack spacing={2}>
      <ErrorAlert error={resolve.error || clarAct.error} />
      <Paper sx={{ p: 2 }}>
        <Stack direction="row" justifyContent="space-between" alignItems="center">
          <Typography variant="h6">Missing, unresolved and conflicting information</Typography>
          <FormControlLabel control={<Switch checked={showAll} onChange={(e) => setShowAll(e.target.checked)} />} label="Show resolved" />
        </Stack>
        <Typography variant="body2" color="text.secondary" gutterBottom>
          The checklist assesses completeness against agreed requirements; it does not recommend investigations. Values that changed over time are not
          treated as conflicts.
        </Typography>
        {items.isLoading && <Loading />}
        {visible.length === 0 && <Empty>No open items.</Empty>}
        <Stack spacing={1.5}>
          {visible.map((i) => (
            <Paper key={i.id} sx={{ p: 1.5 }}>
              <Stack direction="row" justifyContent="space-between" spacing={1}>
                <Typography variant="subtitle2">{i.title}</Typography>
                <Stack direction="row" spacing={0.5}>
                  <Tag tone={KIND_TONE[i.kind]} label={i.kind.replace("_", " ")} />
                  {i.blocking && i.status === "open" && <Tag tone="warn" label="blocks submission" />}
                  {i.status !== "open" && <Tag tone="ok" label={i.status.replace(/_/g, " ")} />}
                </Stack>
              </Stack>
              <Typography variant="body2" sx={{ my: 0.5 }}>
                {i.detail}
              </Typography>
              {i.evidence_ids.length > 0 && <div>{i.evidence_ids.map((e) => <EvidenceRef key={e} id={e} />)}</div>}
              {i.resolution && (
                <Typography variant="caption" display="block">
                  {i.status.replace(/_/g, " ")} by {i.resolved_by} ({fmtDate(i.resolved_at)}): {i.resolution}
                </Typography>
              )}
              <Stack direction="row" spacing={1} sx={{ mt: 1 }} flexWrap="wrap" useFlexGap>
                {i.status === "open" &&
                  ACTIONS.filter(([a]) => (a === "resolved" ? i.kind !== "missing" : i.override_allowed)).map(([a, label]) => (
                    <Button key={a} size="small" disabled={i.clinical && !isClinician} onClick={() => setResolving({ item: i, action: a })}>
                      {label}
                    </Button>
                  ))}
                {i.status === "open" && (
                  <Button size="small" onClick={() => setClarifyFor(i)}>
                    Request information
                  </Button>
                )}
                {i.status !== "open" && i.resolved_by !== "system" && (
                  <Button size="small" onClick={() => resolve.mutate({ id: i.id, action: "reopen", rationale: "" })}>
                    Reopen
                  </Button>
                )}
                {i.clinical && !isClinician && i.status === "open" && <Typography variant="caption">Clinical item: a clinician resolves this.</Typography>}
              </Stack>
            </Paper>
          ))}
        </Stack>
      </Paper>

      <Paper sx={{ p: 2 }}>
        <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
          <Typography variant="h6">Clarification requests</Typography>
          <Button variant="outlined" onClick={() => setClarifyFor(null)}>
            New request
          </Button>
        </Stack>
        {(clars.data ?? []).length === 0 && <Empty>No clarification requests.</Empty>}
        <Stack spacing={1.5}>
          {(clars.data ?? []).map((c) => (
            <Paper key={c.id} sx={{ p: 1.5 }}>
              <Stack direction="row" justifyContent="space-between">
                <Typography variant="subtitle2">
                  #{c.id} {c.origin === "specialist" ? "From specialist" : "Clinic request"} → {c.assignee_institution_name}
                  {c.flag_id ? ` (about medication flag #${c.flag_id})` : ""}
                </Typography>
                <Tag tone={c.status === "open" ? "warn" : c.status === "answered" ? "info" : "ok"} label={c.status} />
              </Stack>
              <Typography variant="body2" sx={{ my: 0.5 }}>
                {c.question}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {c.created_by}, {fmtDate(c.created_at)}
                {c.due_date ? ` · due ${c.due_date}` : ""}
              </Typography>
              {c.response_text && (
                <Typography variant="body2" sx={{ mt: 0.5 }}>
                  <strong>Answer ({c.answered_by}, {fmtDate(c.answered_at)}):</strong> {c.response_text}
                </Typography>
              )}
              <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
                {c.status === "open" && c.assignee_institution === me?.institution_id && (
                  <Button size="small" variant="contained" onClick={() => setAnswering(c)}>
                    Answer
                  </Button>
                )}
                {c.origin === "clinic" && ["open", "answered"].includes(c.status) && (
                  <>
                    <Button size="small" onClick={() => clarAct.mutate({ path: `/clarifications/${c.id}/resolve`, body: { note: "Resolved" } })}>
                      Mark resolved
                    </Button>
                    <Button size="small" color="error" onClick={() => clarAct.mutate({ path: `/clarifications/${c.id}/cancel`, body: { note: "No longer needed" } })}>
                      Cancel
                    </Button>
                  </>
                )}
              </Stack>
            </Paper>
          ))}
        </Stack>
      </Paper>
      {resolving && (
        <ReasonDialog
          open
          title={ACTIONS.find(([a]) => a === resolving.action)?.[1] ?? "Resolve"}
          label="Rationale (recorded with your name)"
          confirm="Save"
          onClose={() => setResolving(null)}
          onConfirm={(rationale) => resolve.mutate({ id: resolving.item.id, action: resolving.action, rationale })}
          busy={resolve.isPending}
        >
          <Typography variant="body2">{resolving.item.title}</Typography>
        </ReasonDialog>
      )}
      {clarifyFor !== undefined && <NewClarification r={r} item={clarifyFor} onClose={() => setClarifyFor(undefined)} onDone={() => { setClarifyFor(undefined); refresh(); }} />}
      {answering && (
        <ReasonDialog
          open
          title={`Answer request #${answering.id}`}
          label="Answer"
          confirm="Send answer"
          onClose={() => setAnswering(null)}
          onConfirm={(text) => clarAct.mutate({ path: `/clarifications/${answering.id}/answer`, body: { response_text: text } })}
          busy={clarAct.isPending}
        >
          <Typography variant="body2">{answering.question}</Typography>
        </ReasonDialog>
      )}
    </Stack>
  );
}
