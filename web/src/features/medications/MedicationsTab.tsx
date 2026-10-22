import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Alert,
  AlertTitle,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
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
import { api } from "../../api/client";
import type { MedicationEntry, MedicationsResponse, ReferralDetail } from "../../api/types";
import { ErrorAlert, fmtDate, Loading, ReasonDialog, Tag } from "../../components/common";
import { EvidenceRef } from "../../components/EvidenceRef";
import { FlagCard } from "../../components/FlagCard";
import { hasRole, useMe } from "../../hooks";
import { useInvalidateReferral } from "../referrals/ReferralWorkspace";

const USE_OPTIONS = [
  ["unverified", "Not yet verified"],
  ["confirmed_current", "Confirmed current"],
  ["historical_stopped", "Historical / stopped"],
  ["uncertain", "Uncertain"],
  ["conflicting", "Conflicting"],
] as const;

const MAPPING_TONE: Record<string, "ok" | "warn" | "bad" | "info"> = { mapped: "ok", clinician_mapped: "info", ambiguous: "warn", unmapped: "warn" };

function MappingDialog({ entry, referralId, onClose, onDone }: { entry: MedicationEntry; referralId: number; onClose: () => void; onDone: () => void }) {
  const dict = useQuery({ queryKey: ["dictionary"], queryFn: () => api.get<{ reviewed_entries: { ingredient: string; class: string; names: string[] }[] }>("/medication-dictionary") });
  const [ingredient, setIngredient] = useState("");
  const [note, setNote] = useState("");
  const save = useMutation({ mutationFn: () => api.post(`/referrals/${referralId}/medications/${entry.id}/mapping`, { ingredient, note }), onSuccess: onDone });
  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>Resolve mapping for "{entry.original_name}"</DialogTitle>
      <DialogContent>
        <Alert severity="info" sx={{ mb: 2 }}>
          The original name is kept. Choose only from reviewed dictionary entries; leave unresolved if unsure. {entry.mapping_note}
        </Alert>
        <TextField select fullWidth label="Verified ingredient" value={ingredient} onChange={(e) => setIngredient(e.target.value)} sx={{ mb: 2 }}>
          {dict.data?.reviewed_entries.map((d) => (
            <MenuItem key={d.ingredient} value={d.ingredient}>
              {d.ingredient}: {d.class.replace(/_/g, " ")} ({d.names.join(", ")})
            </MenuItem>
          ))}
        </TextField>
        <TextField fullWidth label="Basis (e.g. confirmed with patient / pharmacy)" value={note} onChange={(e) => setNote(e.target.value)} />
        <ErrorAlert error={save.error} />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="contained" disabled={!ingredient || note.trim().length < 3 || save.isPending} onClick={() => save.mutate()}>
          Save mapping
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export function MedicationsTab({ r }: { r: ReferralDetail }) {
  const { data: me } = useMe();
  const refresh = useInvalidateReferral(r.id);
  const q = useQuery({ queryKey: ["referral", r.id, "medications"], queryFn: () => api.get<MedicationsResponse>(`/referrals/${r.id}/medications`) });
  const [mapping, setMapping] = useState<MedicationEntry | null>(null);
  const [clarifyFlag, setClarifyFlag] = useState<{ id: number; version: number } | null>(null);
  const [showHistory, setShowHistory] = useState(false);
  const setUse = useMutation({ mutationFn: ({ id, use_status }: { id: number; use_status: string }) => api.post(`/referrals/${r.id}/medications/${id}/use`, { use_status }), onSuccess: refresh });
  const review = useMutation({
    mutationFn: (b: { id: number; version: number; action: string; question?: string }) =>
      api.post(`/referrals/${r.id}/flags/${b.id}/review`, { action: b.action, flag_version: b.version, question: b.question }),
    onSuccess: () => {
      setClarifyFlag(null);
      refresh();
    },
  });
  const rerun = useMutation({ mutationFn: () => api.post(`/referrals/${r.id}/medications/evaluate`), onSuccess: refresh });
  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorAlert error={q.error} />;
  const data = q.data!;
  const isClinician = hasRole(me, "clinician");
  const locked = ["response_returned", "followup_pending", "closed", "declined", "cancelled"].includes(r.status);
  const ev = data.evaluation;

  return (
    <Stack spacing={2}>
      <ErrorAlert error={setUse.error || review.error || rerun.error} />
      <Paper sx={{ p: 2 }}>
        <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
          <Typography variant="h6">Referral-specific medication flags</Typography>
          <Button size="small" onClick={() => rerun.mutate()} disabled={locked || rerun.isPending}>
            Re-run evaluation
          </Button>
        </Stack>
        {ev && (
          <Alert severity={ev.status === "failed" ? "error" : ev.outcome === "unsupported_coverage" ? "warning" : "info"} sx={{ mb: 2 }}>
            <AlertTitle>
              {ev.status === "failed" ? "Evaluation failed" : ev.outcome === "flags" ? "Flags from approved rules" : ev.outcome === "no_match" ? "No matching flag" : "Rules not active"}
            </AlertTitle>
            {ev.summary_message}
            <Typography variant="caption" display="block" sx={{ mt: 0.5 }}>
              Deterministic evaluation · rules {Object.entries(ev.rule_versions).map(([k, v]) => `${k} v${v}`).join(", ") || "none active"} · mapping {ev.mapping_version} · context{" "}
              {String(ev.context.procedure_status)}
              {ev.context.planned_procedure ? ` (${String(ev.context.planned_procedure)})` : ""} · {fmtDate(ev.created_at)} ({ev.trigger.replace(/_/g, " ")})
            </Typography>
          </Alert>
        )}
        <Stack spacing={1.5}>
          {data.flags.length === 0 && <Typography color="text.secondary">No active flags or prompts.</Typography>}
          {data.flags.map((f) => {
            const clinicReview = f.reviews.find((x) => x.side === "referring" && x.action === "reviewed" && x.flag_version === f.version);
            return (
              <FlagCard
                key={f.id}
                flag={f}
                reviews={f.reviews}
                evidence={f.evidence_ids.map((id) => <EvidenceRef key={id} id={id} />)}
                actions={
                  isClinician && !locked ? (
                    <>
                      <Button size="small" variant={clinicReview ? "outlined" : "contained"} disabled={!!clinicReview || review.isPending} onClick={() => review.mutate({ id: f.id, version: f.version, action: "reviewed" })}>
                        {clinicReview ? "Reviewed" : "Mark reviewed"}
                      </Button>
                      <Button size="small" onClick={() => setClarifyFlag({ id: f.id, version: f.version })}>
                        Request clarification
                      </Button>
                    </>
                  ) : undefined
                }
              />
            );
          })}
        </Stack>
        {data.flag_history.length > 0 && (
          <Button size="small" sx={{ mt: 1 }} onClick={() => setShowHistory(!showHistory)}>
            {showHistory ? "Hide" : "Show"} superseded / withdrawn flag versions ({data.flag_history.length})
          </Button>
        )}
        {showHistory &&
          data.flag_history.map((f) => (
            <Typography key={f.id} variant="body2" color="text.secondary">
              v{f.version} {f.status}: {f.title} {f.medication ? `, ${f.medication}` : ""} ({fmtDate(f.superseded_at)})
            </Typography>
          ))}
      </Paper>

      <Paper sx={{ p: 2 }}>
        <Typography variant="h6" gutterBottom>
          Medication list
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          A past prescription alone does not establish current use. {isClinician ? "Confirm the current-use status of each entry." : "A clinician must confirm current use."}
        </Typography>
        <Table size="small" aria-label="Medication list">
          <TableHead>
            <TableRow>
              <TableCell>Ref</TableCell>
              <TableCell>Documented name / dose</TableCell>
              <TableCell>Source</TableCell>
              <TableCell>Mapping</TableCell>
              <TableCell sx={{ minWidth: 220 }}>Current use</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {data.entries.map((m) => (
              <TableRow key={m.id}>
                <TableCell>
                  <EvidenceRef id={m.evidence_id} />
                </TableCell>
                <TableCell>
                  <strong>{m.original_name}</strong>
                  <Typography variant="caption" display="block">
                    {[m.dose, m.route, m.frequency].filter(Boolean).join(" · ") || "dose not recorded"}
                    {m.start_date ? ` · from ${m.start_date.slice(0, 10)}` : ""}
                    {m.end_date ? ` to ${m.end_date.slice(0, 10)}` : ""}
                    {m.source_status ? ` · source status: ${m.source_status}` : ""}
                  </Typography>
                </TableCell>
                <TableCell>
                  <Typography variant="body2">{m.source_label}</Typography>
                </TableCell>
                <TableCell>
                  <Tag tone={MAPPING_TONE[m.mapping_status] ?? "info"} label={m.mapping_status.replace("_", " ")} />
                  <Typography variant="caption" display="block">
                    {m.ingredient ? `${m.ingredient} (RxCUI ${m.ingredient_code}) · ${m.drug_class?.replace(/_/g, " ")} ${m.class_code ?? ""}` : m.mapping_note}
                  </Typography>
                  {isClinician && !locked && ["ambiguous", "unmapped"].includes(m.mapping_status) && (
                    <Button size="small" onClick={() => setMapping(m)}>
                      Resolve mapping
                    </Button>
                  )}
                </TableCell>
                <TableCell>
                  <TextField
                    select
                    size="small"
                    fullWidth
                    value={m.use_status}
                    disabled={!isClinician || locked || setUse.isPending}
                    onChange={(e) => setUse.mutate({ id: m.id, use_status: e.target.value })}
                    inputProps={{ "aria-label": `Current use of ${m.original_name}` }}
                  >
                    {USE_OPTIONS.map(([v, l]) => (
                      <MenuItem key={v} value={v}>
                        {l}
                      </MenuItem>
                    ))}
                  </TextField>
                  {m.use_verified_by && (
                    <Typography variant="caption" color="text.secondary">
                      {m.use_verified_by}, {fmtDate(m.use_verified_at)}
                    </Typography>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        {data.entries.length === 0 && <Typography color="text.secondary">No medication records retrieved or extracted yet.</Typography>}
      </Paper>
      {mapping && <MappingDialog entry={mapping} referralId={r.id} onClose={() => setMapping(null)} onDone={() => { setMapping(null); refresh(); }} />}
      <ReasonDialog
        open={!!clarifyFlag}
        title="Request clarification about this flag"
        label="Question"
        confirm="Create request"
        minLength={5}
        onClose={() => setClarifyFlag(null)}
        onConfirm={(question) => clarifyFlag && review.mutate({ ...clarifyFlag, action: "request_clarification", question })}
        busy={review.isPending}
      />
    </Stack>
  );
}
