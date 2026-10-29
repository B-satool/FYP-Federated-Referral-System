/**
 * The doctor's medicines step (spec v4 steps 1 and 4, section 9).
 *
 * The doctor asks the patient for their current medicines and enters them here; the list is encrypted on this
 * device and becomes an item of the package. Medicines on record come from the decrypted records. Layer 1 flags are
 * computed here from the hash-checked data bundle; nothing about the medicines leaves the device for that. Layer 2,
 * the AI, is asked only when the doctor clicks, with generic names and the procedure only, after a preview.
 * Staff never see this step (spec v4 D14).
 */
import { useEffect, useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Alert, Box, Button, Checkbox, Dialog, DialogActions, DialogContent, DialogTitle, FormControlLabel, IconButton, MenuItem,
  Stack, Table, TableBody, TableCell, TableHead, TableRow, TextField, Typography } from "@mui/material";
import Delete from "@mui/icons-material/Delete";
import { api } from "../../api/client";
import type { ReferralDetail } from "../../api/types";
import { Empty, ErrorAlert, Loading, Section } from "../../components/common";
import { useDeviceKeys } from "../../crypto/session";
import { useRefData } from "../../hooks";
import { DeviceKeyPanel } from "../keys/DeviceKey";
import { useMedBundle } from "../e2e/bundle";
import { ageYears, Scrubber } from "../e2e/deidentify";
import { evaluate, Evaluation, Med } from "../e2e/flags";
import { AiFlag, Decision, Layer1Flags, Layer2Flags, NotAssessed } from "../e2e/FlagViews";
import { latestById, OpenedItem } from "../e2e/records";
import { uploadOwnItems } from "../e2e/upload";
import { useOpenedRecords } from "./Records";
import type { Role } from "./steps";
import { useInvalidateReferral } from "./ReferralWorkspace";

export type ListedMedicine = { name: string; strength: string; dose: string; frequency: string; over_the_counter: boolean; choice?: string | null };
type SavedList = { medicines: ListedMedicine[]; checked_note?: string; decisions?: Record<string, Decision> };

const EMPTY: ListedMedicine = { name: "", strength: "", dose: "", frequency: "", over_the_counter: false };

/** The newest medicine list the doctor saved, and the medicines on record, from the decrypted items. */
export function medicinesFrom(items: OpenedItem[]): { list: SavedList | null; listItem: OpenedItem | null; recorded: Med[] } {
  const ok = latestById(items).filter((i) => i.state === "ok" && i.content);
  const lists = ok.filter((i) => i.content!.category === "medication_list");
  const listItem = lists[lists.length - 1] ?? null;
  const recorded = ok.filter((i) => i.content!.category === "medication").map((i) => {
    const rec = i.content!.record as Record<string, string | null>;
    return { id: `rec:${i.title.item_id}`, name: [rec.name, rec.brand ? `(${rec.brand})` : null].filter(Boolean).join(" ") || i.title.label,
      strength: rec.strength, dose: rec.dose, frequency: rec.frequency, source: i.content!.source_name ?? i.title.source_name ?? "record" };
  });
  return { list: listItem ? (listItem.content!.record as unknown as SavedList) : null, listItem, recorded };
}

export function medsForEvaluation(list: ListedMedicine[], recorded: Med[]): Med[] {
  return [...recorded, ...list.filter((m) => m.name.trim()).map((m, n) => ({ id: `list:${n}`, name: m.name.trim(),
    strength: m.strength, dose: m.dose, frequency: m.frequency, source: "asked from the patient", choice: m.choice ?? null }))];
}

function AiCheck({ r, ev, onResult }: { r: ReferralDetail; ev: Evaluation; onResult: (x: AiFlag[]) => void }) {
  const ref = useRefData();
  const [includeRaw, setIncludeRaw] = useState(false);
  const [preview, setPreview] = useState<string | null>(null);
  const build = () => {
    const places = Object.values(ref.data?.institutions ?? {}).map((i) => ({ name: i.name, kind: i.kind }));
    const on = new Date(r.requested_at ?? r.created_at);
    const s = new Scrubber(r.patient.name, [r.patient.cnic, r.patient.local_patient_id, r.reference], places, on);
    const generic = [...new Set(ev.results.filter((x) => x.mapping.ingredient).flatMap((x) => x.ingredients))];
    const raw = includeRaw ? ev.notAssessed.filter((x) => x.med.mapping.status === "unmapped").map((x) => s.text(x.med.name)) : [];
    const age = ageYears(r.patient.birth_date, on);
    return {
      medicines: [...generic, ...raw],
      procedure: r.procedure_status === "planned" && r.planned_procedure ? s.text(r.planned_procedure) : null,
      age_band: age == null ? null : `${Math.floor(age / 10) * 10}-${Math.floor(age / 10) * 10 + 9}`,
      already_flagged: ev.flags.map((f) => f.ingredients),
      not_in_dataset: [...new Set(ev.notAssessed.filter((x) => x.med.mapping.ingredient).flatMap((x) => x.med.ingredients)), ...raw],
    };
  };
  const send = useMutation({
    mutationFn: () => api.post<{ suggestions: AiFlag[] }>("/ai/relay/flags", { referral_id: r.id, payload: JSON.parse(preview!) }),
    meta: { silent: true },
    onSuccess: (x) => { onResult(x.suggestions); setPreview(null); },
  });
  let parseError: string | null = null;
  if (preview) { try { JSON.parse(preview); } catch (e) { parseError = (e as Error).message; } }
  return (
    <Box>
      <FormControlLabel control={<Checkbox checked={includeRaw} onChange={(e) => setIncludeRaw(e.target.checked)} />}
        label="Also send names no dataset recognised, as written (they are health information, but not the patient's identity)" />
      <Box><Button variant="outlined" onClick={() => setPreview(JSON.stringify(build(), null, 2))} disabled={!ev.results.length}>Ask the AI about gaps and the procedure</Button></Box>
      <ErrorAlert error={send.error} />
      <Dialog open={!!preview} onClose={() => setPreview(null)} maxWidth="sm" fullWidth>
        <DialogTitle>What is sent to the AI</DialogTitle>
        <DialogContent>
          <Alert severity="info" sx={{ mb: 1.5 }}>Generic medicine names, the procedure and an age band only. It passes through our server to the model and is not stored.</Alert>
          <TextField value={preview ?? ""} onChange={(e) => setPreview(e.target.value)} multiline fullWidth minRows={8}
            inputProps={{ "aria-label": "Text sent to the AI", style: { fontFamily: "monospace", fontSize: 12 } }} error={!!parseError} helperText={parseError ?? " "} />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPreview(null)}>Cancel</Button>
          <Button variant="contained" disabled={!!parseError || send.isPending} onClick={() => send.mutate()}>Send to the AI</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

export function MedicinesTab({ r, role }: { r: ReferralDetail; role: Role }) {
  const dk = useDeviceKeys();
  const refresh = useInvalidateReferral(r.id);
  const opened = useOpenedRecords(r);
  const bundle = useMedBundle();
  const { list: saved, recorded } = useMemo(() => medicinesFrom(opened.data ?? []), [opened.data]);
  const [rows, setRows] = useState<ListedMedicine[] | null>(null);
  const [note, setNote] = useState("");
  const [decisions, setDecisions] = useState<Record<string, Decision>>({});
  const [ai, setAi] = useState<AiFlag[] | null>(null);
  useEffect(() => {
    if (rows === null && opened.data) {
      setRows(saved?.medicines?.length ? saved.medicines : [{ ...EMPTY }]);
      setNote(saved?.checked_note ?? "");
      setDecisions(saved?.decisions ?? {});
    }
  }, [opened.data, saved, rows]);
  const list = rows ?? [];
  const ev = useMemo(() => (bundle.data ? evaluate(medsForEvaluation(list, recorded), bundle.data) : null), [bundle.data, list, recorded]);
  const locked = !["draft", "requested"].includes(r.status) && !r.amendment_open;
  const save = useMutation({
    mutationFn: () => uploadOwnItems(r.id, r.reference, dk.keys!, [{ category: "medication_list", kind: "prescription",
      label: "Medicine list (asked from the patient)", record: { medicines: list.filter((m) => m.name.trim()), checked_note: note, decisions } }]),
    meta: { success: "Saved, encrypted on this device. Include it when you approve the package." },
    onSuccess: async () => { await opened.refetch(); refresh(); },
  });
  const decide = (key: string, d: Decision) => setDecisions((x) => ({ ...x, [key]: d }));
  const set = (n: number, patch: Partial<ListedMedicine>) => setRows(list.map((m, i) => (i === n ? { ...m, ...patch } : m)));

  if (role !== "doctor") return <Alert severity="info">Medicines are entered and checked by the doctor.</Alert>;
  if (r.working_set_purged_at) return <Alert severity="info">This referral's encrypted content was purged.</Alert>;
  if (dk.status !== "unlocked") return <DeviceKeyPanel compact />;
  if (opened.isLoading || bundle.isLoading || rows === null) return <Loading label="Decrypting on this device…" />;
  return (
    <Stack spacing={2}>
      <ErrorAlert error={bundle.error} />
      <Section title="Medicines the patient takes" description="Ask the patient about every medicine, including over-the-counter ones. Encrypted on this device when you save.">
        <Table size="small">
          <TableHead><TableRow><TableCell>Medicine (as on the pack)</TableCell><TableCell>Strength</TableCell><TableCell>Dose</TableCell><TableCell>How often</TableCell><TableCell>Over the counter</TableCell><TableCell /></TableRow></TableHead>
          <TableBody>
            {list.map((m, n) => {
              const res = ev?.results.find((x) => x.id === `list:${n}`);
              return (
                <TableRow key={n}>
                  <TableCell>
                    <TextField size="small" value={m.name} disabled={locked} onChange={(e) => set(n, { name: e.target.value, choice: null })}
                      inputProps={{ "aria-label": `Medicine ${n + 1}` }} />
                    {res && res.mapping.status !== "unmapped" && (
                      <Typography variant="caption" display="block" color={res.mapping.status === "mapped" ? "text.secondary" : "warning.main"}>
                        {res.mapping.ingredient ? `${res.mapping.ingredient}` : ""}{res.mapping.note ? ` · ${res.mapping.note}` : ""}
                      </Typography>
                    )}
                    {res?.mapping.status === "ambiguous" && res.mapping.options.length > 0 && (
                      <TextField select size="small" label="Which product is it?" value={m.choice ?? ""} sx={{ mt: 1, minWidth: 260 }}
                        onChange={(e) => set(n, { choice: e.target.value })}>
                        {res.mapping.options.map((o) => <MenuItem key={`${o.ingredient}${o.drap_reg_no}`} value={o.ingredient}>
                          {o.ingredient} ({o.company ?? "company not recorded"}{o.strength ? `, ${o.strength}` : ""})</MenuItem>)}
                      </TextField>
                    )}
                  </TableCell>
                  <TableCell><TextField size="small" value={m.strength} disabled={locked} onChange={(e) => set(n, { strength: e.target.value })} sx={{ width: 100 }} /></TableCell>
                  <TableCell><TextField size="small" value={m.dose} disabled={locked} onChange={(e) => set(n, { dose: e.target.value })} sx={{ width: 100 }} /></TableCell>
                  <TableCell><TextField size="small" value={m.frequency} disabled={locked} onChange={(e) => set(n, { frequency: e.target.value })} sx={{ width: 120 }} /></TableCell>
                  <TableCell><Checkbox checked={m.over_the_counter} disabled={locked} onChange={(e) => set(n, { over_the_counter: e.target.checked })} /></TableCell>
                  <TableCell><IconButton aria-label="Remove" disabled={locked} onClick={() => setRows(list.filter((_, i) => i !== n))}><Delete /></IconButton></TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
        {!locked && (
          <Stack spacing={1.5} sx={{ mt: 1.5 }}>
            <Box><Button onClick={() => setRows([...list, { ...EMPTY }])}>Add a medicine</Button></Box>
            <TextField label="Note (for example: asked the patient about all medicines, including herbal ones)" value={note} onChange={(e) => setNote(e.target.value)} />
            <ErrorAlert error={save.error} />
            <Box><Button variant="contained" onClick={() => save.mutate()} disabled={save.isPending}>Save the list</Button></Box>
          </Stack>
        )}
      </Section>
      <Section title="Medicines on record" description="From the records the institutions released, decrypted on this device.">
        {recorded.length ? (
          <Box component="ul" sx={{ m: 0, pl: 2.5 }}>
            {recorded.map((m) => <li key={m.id}><Typography variant="body2">{m.name}{m.dose ? `, ${m.dose}` : ""}{m.frequency ? `, ${m.frequency}` : ""} · {m.source}</Typography></li>)}
          </Box>
        ) : <Empty>No medicines on record were received (this is not "none": records may not have been requested or released).</Empty>}
      </Section>
      {ev && (
        <Section title="Flags from the interaction data" description={`Checked on this device against ${ev.datasetVersion ? `DDInter (${ev.datasetVersion})` : "the interaction data"} and the Pakistani brand names. A decision means "seen"; it never advises a change.`}>
          <Stack spacing={1.5}>
            <Layer1Flags ev={ev} referral={r.id} decisions={decisions} onDecide={decide} />
            <NotAssessed ev={ev} />
          </Stack>
        </Section>
      )}
      {ev && !locked && (
        <Section title="AI check" description="Optional: for medicines the data does not cover and for risks with the planned procedure. Suggestions are labelled and never replace the flags above.">
          <AiCheck r={r} ev={ev} onResult={setAi} />
          {ai && <Box sx={{ mt: 1.5 }}><Layer2Flags items={ai} referral={r.id} decisions={decisions} onDecide={decide} /></Box>}
        </Section>
      )}
    </Stack>
  );
}
