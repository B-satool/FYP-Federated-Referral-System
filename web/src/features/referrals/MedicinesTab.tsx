import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Alert,
  Autocomplete,
  Box,
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
import type { AiSuggestion, Flag, FlagDecision, MedicationEntry, MedicationView, MedicineNamesView, ReferralDetail } from "../../api/types";
import { FlagCard } from "../../components/FlagCard";
import { Empty, ErrorAlert, fmtDate, Loading, ReasonDialog, Section, Tag } from "../../components/common";
import { useRefData } from "../../hooks";
import { tokens } from "../../theme";
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

/** A DRAP brand registered for different products: the doctor picks the one on the pack, by company. */
function ChooseProduct({ referralId, entry, onDone }: { referralId: number; entry: MedicationEntry; onDone: () => void }) {
  const choose = useMutation({
    mutationFn: (c: NonNullable<MedicationEntry["mapping_choices"]>[number]) =>
      api.post(`/referrals/${referralId}/medications/${entry.id}/mapping`, { ingredient: c.ingredient, company: c.company, drap_reg_no: c.drap_reg_no }),
    meta: { success: "Medicine chosen. The flags are checked again." },
    onSuccess: onDone,
  });
  return (
    <Box sx={{ mt: 1, p: 1.25, border: `1px solid ${tokens.warn.text}`, borderRadius: 1, maxWidth: 560 }}>
      <Typography variant="body2" sx={{ fontWeight: 600 }}>Which {entry.original_name} is it? Check the company on the pack.</Typography>
      <Stack spacing={0.75} sx={{ mt: 1 }}>
        {(entry.mapping_choices ?? []).map((c) => (
          <Stack key={`${c.ingredient}-${c.company}-${c.drap_reg_no}`} direction="row" spacing={1} alignItems="center">
            <Button size="small" variant="outlined" disabled={choose.isPending || c.known === false} onClick={() => choose.mutate(c)}>
              {c.ingredient}
            </Button>
            <Typography variant="caption" color="text.secondary">
              {[c.company || "company not recorded", [c.strength, c.dosage_form].filter(Boolean).join(" "), c.drap_reg_no && `DRAP ${c.drap_reg_no}`]
                .filter(Boolean).join(" · ")}
              {c.known === false ? " · not in the medicine list yet" : ""}
            </Typography>
          </Stack>
        ))}
      </Stack>
      <ErrorAlert error={choose.error} />
    </Box>
  );
}

const SEVERITY_ORDER: Record<string, number> = { Major: 0, high: 0, Moderate: 1, moderate: 1, Minor: 2, low: 2, Unknown: 3 };

/** Flags grouped so the ones that need a decision come first and low-severity ones are collapsed. */
function flagGroups(flags: Flag[]) {
  const decided = (f: Flag) => f.acknowledgements.some((a) => a.side === "referring");
  const bySeverity = (a: Flag, b: Flag) => (SEVERITY_ORDER[a.severity ?? ""] ?? 9) - (SEVERITY_ORDER[b.severity ?? ""] ?? 9);
  const required = flags.filter((f) => f.requires_decision);
  const optional = flags.filter((f) => !f.requires_decision);
  const ddi = optional.filter((f) => f.kind === "interaction").sort(bySeverity);
  const label = optional.filter((f) => f.kind === "label_warning").sort(bySeverity);
  const rest = optional.filter((f) => !["interaction", "label_warning"].includes(f.kind));
  return [
    { key: "required", title: "Needs your decision", note: "Approved rules, Major interactions, boxed warnings and contraindications, and anything that could not be checked.",
      flags: required.sort((a, b) => Number(decided(a)) - Number(decided(b))), collapsed: false },
    { key: "ddi", title: "Other drug interactions (DDInter)", note: "Moderate, minor and ungraded interactions, for reading.", flags: ddi, collapsed: false },
    { key: "label", title: "Other drug-label mentions", note: "Label warnings and precautions that mention the procedure or a recorded condition.", flags: label, collapsed: true },
    { key: "rest", title: "Other notes", note: "", flags: rest, collapsed: false },
  ].filter((g) => g.flags.length > 0);
}

function FlagGroup({ title, note, flags, collapsed, render }: { title: string; note: string; flags: Flag[]; collapsed: boolean; render: (f: Flag) => JSX.Element }) {
  const [open, setOpen] = useState(!collapsed);
  const minor = flags.filter((f) => ["Minor", "Unknown", "low"].includes(f.severity ?? ""));
  const [showMinor, setShowMinor] = useState(false);
  const shown = showMinor || flags.length === minor.length ? flags : flags.filter((f) => !minor.includes(f));
  return (
    <Box component="section" aria-label={title}>
      <Stack direction="row" justifyContent="space-between" alignItems="baseline" spacing={1}>
        <Typography variant="subtitle1" component="h3" sx={{ fontWeight: 700 }}>
          {title} ({flags.length})
        </Typography>
        <Button size="small" onClick={() => setOpen(!open)}>{open ? "Hide" : "Show"}</Button>
      </Stack>
      {note && <Typography variant="caption" color="text.secondary" component="div" sx={{ mb: 1 }}>{note}</Typography>}
      {open && (
        <Stack spacing={1.5}>
          {shown.map(render)}
          {minor.length > 0 && shown.length < flags.length && (
            <Button size="small" sx={{ alignSelf: "start" }} onClick={() => setShowMinor(true)}>
              Show {minor.length} minor or ungraded
            </Button>
          )}
        </Stack>
      )}
    </Box>
  );
}

/** Reviewed, Ignore (not relevant for this patient) or Research (needs follow-up), with an optional note. */
function DecisionButtons({ busy, onDecide }: { busy: boolean; onDecide: (d: FlagDecision, note: string) => void }) {
  const [pending, setPending] = useState<FlagDecision | null>(null);
  const [note, setNote] = useState("");
  const close = () => {
    setPending(null);
    setNote("");
  };
  return (
    <>
      <Button variant="contained" size="small" disabled={busy} onClick={() => onDecide("reviewed", "")}>Mark as reviewed</Button>
      <Button variant="outlined" size="small" disabled={busy} onClick={() => setPending("ignore")}>Ignore</Button>
      <Button variant="outlined" size="small" disabled={busy} onClick={() => setPending("research")}>Research</Button>
      <Dialog open={!!pending} onClose={close} fullWidth maxWidth="sm">
        <DialogTitle>{pending === "ignore" ? "Ignore this flag for this patient" : "Mark for research (needs follow-up)"}</DialogTitle>
        <DialogContent>
          <Typography variant="body2" sx={{ mb: 1 }}>
            {pending === "ignore"
              ? "The flag stays in the record with your name and note. Ignoring is not treatment clearance."
              : "The flag is marked as needing follow-up; open the source to look into it."}
          </Typography>
          <TextField fullWidth multiline minRows={2} label="Note (optional)" value={note} onChange={(e) => setNote(e.target.value)} />
        </DialogContent>
        <DialogActions>
          <Button onClick={close}>Cancel</Button>
          <Button variant="contained" onClick={() => { onDecide(pending!, note.trim()); close(); }}>
            {pending === "ignore" ? "Ignore" : "Mark for research"}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}

/** Model suggestions for pairs DDInter does not cover: separate from flags, never verified, never blocking. */
function AiSuggestions({ r, role, items, label, locked, onDone }: { r: ReferralDetail; role: Role; items: AiSuggestion[]; label: string; locked: boolean; onDone: () => void }) {
  const review = useMutation({
    mutationFn: ({ pair_key, decision }: { pair_key: string; decision: "ignore" | "research" }) =>
      api.post(`/referrals/${r.id}/ai-suggestions/review`, { pair_key, decision, note: "" }),
    meta: { success: "Recorded." },
    onSuccess: onDone,
  });
  return (
    <Section title={`AI suggestions (${items.length})`}
      description={`Possible clashes between current medicines that have no entry in DDInter, scored by a small model trained on DDInter's known interactions. These are not flags: they are unverified and never block sending. They go with the referral labelled "${label}", with your decision.`}>
      <ErrorAlert error={review.error} />
      <Stack spacing={1.5}>
        {items.map((s) => (
          <Alert key={s.pair_key} severity="info" variant="outlined" sx={{ "& .MuiAlert-message": { width: "100%" } }}>
            <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
              <Typography variant="body2" sx={{ fontWeight: 700 }}>{s.ingredients.join(" and ")}</Typography>
              <Tag tone="info" label={label} />
              <Tag tone="neutral" label={`score ${s.score.toFixed(2)}`} />
            </Stack>
            <Typography variant="body2" sx={{ mt: 0.5 }}>{s.reason}</Typography>
            <Typography variant="caption" color="text.secondary" component="div">
              Model {s.model_version}{s.data_version ? ` · trained on ${s.data_version}` : ""}
            </Typography>
            {s.review ? (
              <Typography variant="body2" sx={{ mt: 0.5 }}>
                <strong>{s.review.decision === "research" ? "Research (needs follow-up)" : "Ignored (not relevant for this patient)"}</strong> by {s.review.by}, {fmtDate(s.review.at)}
              </Typography>
            ) : role === "doctor" && !locked ? (
              <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
                <Button size="small" variant="outlined" disabled={review.isPending} onClick={() => review.mutate({ pair_key: s.pair_key, decision: "ignore" })}>Ignore</Button>
                <Button size="small" variant="outlined" disabled={review.isPending} onClick={() => review.mutate({ pair_key: s.pair_key, decision: "research" })}>Research</Button>
              </Stack>
            ) : null}
          </Alert>
        ))}
      </Stack>
    </Section>
  );
}

export function MedicinesTab({ r, role }: { r: ReferralDetail; role: Role }) {
  const rd = useRefData();
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
    mutationFn: ({ id, version, decision, note }: { id: number; version: number; decision: FlagDecision; note: string }) =>
      api.post(`/referrals/${r.id}/flags/${id}/acknowledge`, { flag_version: version, decision, note }),
    meta: { success: "Decision recorded." },
    onSuccess: done,
  });
  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorAlert error={q.error} />;
  const v = q.data!;
  const locked = LOCKED.includes(r.status);
  // only the doctor sees and changes the medicine list and flags (decision 2026-10-29)
  const editor = role === "doctor";
  if (v.redacted) {
    return (
      <Section title="Medicines and flags" description="The doctor confirms the medicine list with the patient and reviews the medication flags. You see the progress only.">
        <Stack spacing={1}>
          <Typography variant="body2">{v.medicine_count ?? 0} current medicine(s) on the list.</Typography>
          <Typography variant="body2">
            {v.flag_count ?? 0} medication flag(s){v.flags_awaiting_doctor ? `, ${v.flags_awaiting_doctor} waiting for the doctor's decision` : ""}.
          </Typography>
          {v.meds_checked.at
            ? <Tag tone="ok" label={`Medicine list confirmed by ${v.meds_checked.by}, ${fmtDate(v.meds_checked.at)}`} />
            : <Tag tone="wait" label="The doctor has not confirmed the medicine list yet" />}
        </Stack>
      </Section>
    );
  }
  const gathering = !r.prepared_at && r.status === "requested";
  if (editor && gathering) {
    return (
      <Alert severity="info">
        Staff are still retrieving the records and uploading the patient's papers. You will be notified when the referral is ready for you to check
        the medicines and review the flags.
      </Alert>
    );
  }
  const reps = v.entries.filter((e) => !e.duplicate_of);
  const dups = (id: number) => v.entries.filter((e) => e.duplicate_of === id);

  return (
    <Stack spacing={2}>
      <Section
        title={`Current medicines (${reps.length})`}
        description="Only medicines the patient takes now. The same medicine from different places is shown once, with every place that records it."
        actions={!locked && editor && (
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
                    {m.mapping_note && m.mapping_status !== "mapped" && (
                      <Typography variant="caption" display="block" color="text.secondary" sx={{ mt: 0.5, maxWidth: 560 }}>{m.mapping_note}</Typography>
                    )}
                    {!locked && m.mapping_status === "ambiguous" && !!m.mapping_choices?.length && (
                      <ChooseProduct referralId={r.id} entry={m} onDone={done} />
                    )}
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
                    {!locked && editor && ["unmapped", "ambiguous"].includes(m.mapping_status) && (
                      <Button size="small" onClick={() => setMatching(m)}>Match</Button>
                    )}
                    {!locked && editor && (
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
                {!locked && editor && <Button size="small" onClick={() => act.mutate({ path: `/referrals/${r.id}/medications/${m.id}/restore` })}>Restore</Button>}
              </Stack>
            ))}
          </details>
        )}
        <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} alignItems={{ sm: "center" }} sx={{ mt: 2 }}>
          {v.meds_checked.at ? (
            <Tag tone="ok" label={`Patient asked about all medicines: ${v.meds_checked.by}, ${fmtDate(v.meds_checked.at)}`} />
          ) : editor && !locked ? (
            <Button variant="contained" onClick={() => act.mutate({ path: `/referrals/${r.id}/medications/checked`, body: { note: "" } })}>
              I asked the patient about all their medicines
            </Button>
          ) : (
            <Tag tone="wait" label="The medicine list has not been confirmed with the patient yet" />
          )}
        </Stack>
      </Section>

      <Section
        title="Medication flags"
        description="Checked automatically against approved rules, drug interactions (DDInter) and US drug labels. Flags under 'Needs your decision' must each be marked before you can mark the packet reviewed; the others are for reading."
      >
        <ErrorAlert error={ack.error} />
        {v.evaluation && (
          <Alert severity={v.evaluation.status === "failed" ? "error" : v.evaluation.outcome === "flags" ? "warning" : "info"} sx={{ mb: 1.5 }}>
            {v.evaluation.summary_message}
          </Alert>
        )}
        {rd.data?.flag_disclaimer && (
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            {rd.data.flag_disclaimer}
          </Typography>
        )}
        {v.flags.length === 0 && <Empty>No matching rule on file for these medicines. This is not treatment clearance.</Empty>}
        <Stack spacing={2.5}>
          {flagGroups(v.flags).map((g) => (
            <FlagGroup key={g.key} title={g.title} note={g.note} flags={g.flags} collapsed={g.collapsed}
              render={(f) => {
                const a = f.acknowledgements.find((x) => x.side === "referring");
                return (
                  <FlagCard key={f.id} flag={f} acknowledged={a ? { by: a.by, at: a.created_at, decision: a.decision, note: a.note } : null}
                    actions={role === "doctor" && !a && !locked ? (
                      <DecisionButtons busy={ack.isPending} onDecide={(decision, note) => ack.mutate({ id: f.id, version: f.version, decision, note })} />
                    ) : undefined}
                    footer={undefined} />
                );
              }} />
          ))}
        </Stack>
      </Section>

      {v.ai_suggestions.length > 0 && <AiSuggestions r={r} role={role} items={v.ai_suggestions} label={v.ai_label} locked={locked} onDone={done} />}

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
