import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Alert,
  Autocomplete,
  Button,
  Checkbox,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import Add from "@mui/icons-material/Add";
import { api } from "../../api/client";
import type { MedicationEntry, MedicationView, MedicineNamesView, ReferralDetail } from "../../api/types";
import { FlagCard } from "../../components/FlagCard";
import { Empty, ErrorAlert, fmtDate, Loading, ReasonDialog, Section, Tag } from "../../components/common";
import { useInvalidateReferral } from "./ReferralWorkspace";
import type { Role } from "./steps";

const LOCKED = ["response_returned", "followup_pending", "closed", "declined", "cancelled"];

function AddMedicineDialog({ referralId, onClose, onDone }: { referralId: number; onClose: () => void; onDone: () => void }) {
  const names = useQuery({ queryKey: ["medicine-names"], queryFn: () => api.get<MedicineNamesView>("/medicine-names") });
  const [v, setV] = useState({ name: "", strength: "", dose: "", frequency: "", route: "", over_the_counter: true, note: "" });
  const save = useMutation({
    mutationFn: () => api.post(`/referrals/${referralId}/medications/manual`, {
      ...v, strength: v.strength || null, dose: v.dose || v.strength || null, frequency: v.frequency || null, route: v.route || null,
    }),
    meta: { success: "Medicine added." },
    onSuccess: onDone,
  });
  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>Add a medicine the patient takes</DialogTitle>
      <DialogContent>
        <Stack spacing={1.5} sx={{ mt: 1 }}>
          <Typography variant="body2" color="text.secondary">
            Ask the patient about every medicine, including ones bought without a prescription (for example painkillers or supplements).
          </Typography>
          <Autocomplete freeSolo options={(names.data?.names ?? []).map((n) => n.display)} value={v.name}
            onInputChange={(_, name) => setV({ ...v, name })}
            renderInput={(p) => <TextField {...p} label="Medicine (as the patient says it)" required autoFocus />} />
          <Stack direction="row" spacing={1.5}>
            <TextField label="Strength" placeholder="e.g. 400 mg" value={v.strength} onChange={(e) => setV({ ...v, strength: e.target.value })} />
            <TextField label="How often" placeholder="e.g. twice daily, as needed" value={v.frequency} onChange={(e) => setV({ ...v, frequency: e.target.value })} sx={{ flex: 1 }} />
          </Stack>
          <FormControlLabel control={<Checkbox checked={v.over_the_counter} onChange={(e) => setV({ ...v, over_the_counter: e.target.checked })} />}
            label="Bought over the counter (no prescription)" />
          <TextField label="Note (optional)" value={v.note} onChange={(e) => setV({ ...v, note: e.target.value })} />
          <ErrorAlert error={save.error} />
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="contained" disabled={v.name.trim().length < 2 || save.isPending} onClick={() => save.mutate()}>
          Add medicine
        </Button>
      </DialogActions>
    </Dialog>
  );
}

function MatchDialog({ referralId, entry, onClose, onDone }: { referralId: number; entry: MedicationEntry; onClose: () => void; onDone: () => void }) {
  const names = useQuery({ queryKey: ["medicine-names"], queryFn: () => api.get<MedicineNamesView>("/medicine-names") });
  const [ingredient, setIngredient] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: () => api.post(`/referrals/${referralId}/medications/${entry.id}/mapping`, { ingredient }),
    meta: { success: "Medicine matched." },
    onSuccess: onDone,
  });
  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>Which medicine is "{entry.original_name}"?</DialogTitle>
      <DialogContent>
        <Typography variant="body2" sx={{ mb: 2 }}>
          Choose it only if you are sure (for example from the box or the prescription). If it is not in the list, leave it: it stays shown as not recognised and a
          clinical reviewer can add the name.
        </Typography>
        <Autocomplete options={names.data?.ingredients ?? []} value={ingredient} onChange={(_, v) => setIngredient(v)}
          renderInput={(p) => <TextField {...p} label="Medicine (ingredient)" />} />
        <ErrorAlert error={save.error} />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="contained" disabled={!ingredient || save.isPending} onClick={() => save.mutate()}>
          Match
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export function MedicinesTab({ r, role }: { r: ReferralDetail; role: Role }) {
  const refresh = useInvalidateReferral(r.id);
  const q = useQuery({ queryKey: ["referral", r.id, "medications"], queryFn: () => api.get<MedicationView>(`/referrals/${r.id}/medications`) });
  const [adding, setAdding] = useState(false);
  const [excluding, setExcluding] = useState<MedicationEntry | null>(null);
  const [matching, setMatching] = useState<MedicationEntry | null>(null);
  const done = () => {
    setAdding(false);
    setExcluding(null);
    setMatching(null);
    q.refetch();
    refresh();
  };
  const act = useMutation({
    mutationFn: ({ path, body }: { path: string; body?: unknown }) => api.post(path, body ?? {}),
    onSuccess: done,
  });
  const ack = useMutation({
    mutationFn: ({ id, version }: { id: number; version: number }) => api.post(`/referrals/${r.id}/flags/${id}/acknowledge`, { flag_version: version }),
    meta: { success: "Flag acknowledged." },
    onSuccess: done,
  });
  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorAlert error={q.error} />;
  const v = q.data!;
  const locked = LOCKED.includes(r.status);
  const reps = v.entries.filter((e) => !e.duplicate_of);
  const dups = (id: number) => v.entries.filter((e) => e.duplicate_of === id);
  const confirmedFlags = v.flags.filter((f) => f.kind === "confirmed");
  const otherFlags = v.flags.filter((f) => f.kind !== "confirmed");

  return (
    <Stack spacing={2}>
      <Section
        title={`Current medicines (${reps.length})`}
        description="Only medicines the patient takes now. The same medicine from different places is shown once, with every place that records it."
        actions={!locked && (
          <Button variant="outlined" startIcon={<Add />} onClick={() => setAdding(true)}>
            Add a medicine
          </Button>
        )}
      >
        <ErrorAlert error={act.error} />
        {reps.length === 0 ? (
          <Empty>No current medicines yet. Retrieve the records, check the patient's papers, and ask the patient.</Empty>
        ) : (
          <Table size="small" aria-label="Current medicines">
            <TableHead>
              <TableRow>
                <TableCell>Medicine</TableCell>
                <TableCell>Dose</TableCell>
                <TableCell>Recorded by</TableCell>
                <TableCell />
              </TableRow>
            </TableHead>
            <TableBody>
              {reps.map((m) => (
                <TableRow key={m.id}>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>
                      {m.original_name}
                      {m.brand && !m.original_name.toLowerCase().includes(m.brand.toLowerCase()) ? ` (${m.brand})` : ""}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {m.ingredient ? `${m.ingredient}${m.drug_class_label ? `, ${m.drug_class_label.toLowerCase()}` : ""}` : "Not recognised"}
                    </Typography>
                    <Stack direction="row" spacing={0.5} sx={{ mt: 0.5 }} flexWrap="wrap" useFlexGap>
                      {m.over_the_counter && <Tag tone="info" label="over the counter" />}
                      {m.dose_differs && <Tag tone="warn" label="dose differs between records" />}
                      {["unmapped", "ambiguous"].includes(m.mapping_status) && <Tag tone="warn" label="not recognised" />}
                    </Stack>
                  </TableCell>
                  <TableCell>{m.dose ?? "Not recorded"}</TableCell>
                  <TableCell>
                    <Typography variant="body2">{m.source_label}</Typography>
                    {dups(m.id).map((d) => (
                      <Typography key={d.id} variant="caption" display="block" color="text.secondary">
                        Also: {d.source_label}
                      </Typography>
                    ))}
                  </TableCell>
                  <TableCell align="right" sx={{ whiteSpace: "nowrap" }}>
                    {!locked && ["unmapped", "ambiguous"].includes(m.mapping_status) && (
                      <Button size="small" onClick={() => setMatching(m)}>Match</Button>
                    )}
                    {!locked && (
                      <Button size="small" onClick={() => setExcluding(m)}>Not current</Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
        {reps.some((m) => m.dose_differs) && (
          <Alert severity="warning" sx={{ mt: 1.5 }}>
            Different doses are recorded for the same medicine. Check with the patient or their papers, then mark the one that is not current.
          </Alert>
        )}
        {!!v.excluded.length && (
          <details style={{ marginTop: 12 }}>
            <summary>
              <Typography component="span" variant="body2">Marked not current ({v.excluded.length})</Typography>
            </summary>
            {v.excluded.map((m) => (
              <Stack key={m.id} direction="row" justifyContent="space-between" alignItems="center" sx={{ py: 0.5 }}>
                <Typography variant="body2">
                  {m.original_name} ({m.source_label}): {m.excluded_reason}, by {m.excluded_by}
                </Typography>
                {!locked && <Button size="small" onClick={() => act.mutate({ path: `/referrals/${r.id}/medications/${m.id}/restore` })}>Restore</Button>}
              </Stack>
            ))}
          </details>
        )}
        <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} alignItems={{ sm: "center" }} sx={{ mt: 2 }}>
          {v.meds_checked.at ? (
            <Tag tone="ok" label={`Patient asked about all medicines: ${v.meds_checked.by}, ${fmtDate(v.meds_checked.at)}`} />
          ) : role === "staff" && !locked ? (
            <Button variant="contained" onClick={() => act.mutate({ path: `/referrals/${r.id}/medications/checked`, body: { note: "" } })}>
              I asked the patient about all their medicines
            </Button>
          ) : (
            <Tag tone="wait" label="Staff have not yet confirmed the list with the patient" />
          )}
        </Stack>
      </Section>

      <Section
        title="Medication flags"
        description="Checked automatically: each current medicine against the planned procedure, using reviewer-approved rules."
      >
        <ErrorAlert error={ack.error} />
        {v.evaluation && (
          <Alert severity={v.evaluation.status === "failed" ? "error" : v.evaluation.outcome === "flags" ? "warning" : "info"} sx={{ mb: 2 }}>
            {v.evaluation.summary_message}
          </Alert>
        )}
        <Stack spacing={1.5}>
          {[...confirmedFlags, ...otherFlags].map((f) => {
            const a = f.acknowledgements.find((x) => x.side === "referring");
            return (
              <FlagCard key={f.id} flag={f} acknowledged={a ? { by: a.by, at: a.created_at } : null}
                actions={role === "doctor" && !a && !locked ? (
                  <Button variant="contained" size="small" disabled={ack.isPending} onClick={() => ack.mutate({ id: f.id, version: f.version })}>
                    Acknowledge for this patient
                  </Button>
                ) : undefined}
                footer={role === "staff" && !a ? <Tag tone="wait" label={`Waiting for ${r.requesting_doctor_name} to acknowledge`} /> : undefined} />
            );
          })}
          {v.flags.length === 0 && <Empty>No flags for the planned procedure.</Empty>}
        </Stack>
      </Section>

      {adding && <AddMedicineDialog referralId={r.id} onClose={() => setAdding(false)} onDone={done} />}
      {matching && <MatchDialog referralId={r.id} entry={matching} onClose={() => setMatching(null)} onDone={done} />}
      {excluding && (
        <ReasonDialog open title={`Mark "${excluding.original_name}" as not current`} label="Why (for example: stopped, old prescription, wrong dose recorded)"
          confirm="Mark not current" onClose={() => setExcluding(null)} busy={act.isPending}
          onConfirm={(reason) => act.mutate({ path: `/referrals/${r.id}/medications/${excluding.id}/exclude`, body: { reason } })}>
          <Typography variant="body2" sx={{ mb: 1 }}>
            The record stays in the history with your name and reason; it is no longer listed or checked against the procedure.
          </Typography>
        </ReasonDialog>
      )}
    </Stack>
  );
}
