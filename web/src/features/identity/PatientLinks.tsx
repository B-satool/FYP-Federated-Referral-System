import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Grid, List, ListItemButton, ListItemText, MenuItem, Paper, Stack, TextField, Typography } from "@mui/material";
import { api } from "../../api/client";
import type { PatientLink, PatientSummary } from "../../api/types";
import { Empty, ErrorAlert, fmtDate, PageHeader, ReasonDialog, Tag } from "../../components/common";
import { hasRole, useMe, useRefData } from "../../hooks";

const TONE: Record<string, "ok" | "warn" | "off" | "neutral"> = { verified: "ok", pending: "warn", invalidated: "off", rejected: "off" };

export function PatientLinks() {
  const { data: me } = useMe();
  const ref = useRefData();
  const qc = useQueryClient();
  const [params] = useSearchParams();
  const [search, setSearch] = useState(params.get("patient") ?? "");
  const [patient, setPatient] = useState<string | null>(params.get("patient"));
  const [form, setForm] = useState({ b_institution: "lab-b", b_local_id: "", basis: "", family: "", given: "", birth_date: "" });
  const [dialog, setDialog] = useState<{ link: PatientLink; action: "verify" | "reject" | "invalidate" } | null>(null);
  const canSearch = hasRole(me, "clinic_staff", "clinician");
  const patients = useQuery({
    queryKey: ["patient-search", search],
    queryFn: () => api.get<PatientSummary[]>(`/patients/search?q=${encodeURIComponent(search)}`),
    enabled: canSearch,
  });
  const links = useQuery({
    queryKey: ["links", patient],
    queryFn: () => api.get<PatientLink[]>(`/patient-links?institution=${me!.institution_id}&local_id=${encodeURIComponent(patient!)}`),
    enabled: !!patient && !!me,
  });
  const selected = patients.data?.find((p) => p.local_patient_id === patient);
  const refresh = () => qc.invalidateQueries({ queryKey: ["links", patient] });
  const propose = useMutation({
    mutationFn: () =>
      api.post("/patient-links", {
        a_local_id: patient,
        b_institution: form.b_institution,
        b_local_id: form.b_local_id,
        basis: form.basis,
        check_demographics: form.family && form.given && form.birth_date ? { family: form.family, given: form.given, birth_date: form.birth_date } : null,
      }),
    onSuccess: () => {
      setForm({ ...form, b_local_id: "", basis: "" });
      refresh();
    },
  });
  const act = useMutation({
    mutationFn: ({ link, action, note }: { link: PatientLink; action: string; note: string }) => api.post(`/patient-links/${link.id}/${action}`, { note }),
    onSuccess: () => {
      setDialog(null);
      refresh();
    },
  });
  const canVerify = hasRole(me, "clinician", "institution_admin");

  return (
    <>
      <PageHeader
        title="Patient links"
        subtitle="Records at different institutions are separate until an authorized user verifies they belong to the same person. Matching IDs or similar names never link records automatically."
      />
      <Grid container spacing={2}>
        <Grid item xs={12} md={4}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              Patient ({me?.institution_name})
            </Typography>
            {canSearch ? (
              <>
                <TextField fullWidth size="small" label="Search" value={search} onChange={(e) => setSearch(e.target.value)} />
                <List dense>
                  {patients.data?.map((p) => (
                    <ListItemButton
                      key={p.local_patient_id}
                      selected={p.local_patient_id === patient}
                      onClick={() => {
                        setPatient(p.local_patient_id);
                        setForm((f) => ({ ...f, family: p.family, given: p.given, birth_date: p.birth_date }));
                      }}
                    >
                      <ListItemText primary={`${p.given} ${p.family}`} secondary={`${p.local_patient_id} · born ${p.birth_date}`} />
                    </ListItemButton>
                  ))}
                </List>
              </>
            ) : (
              <TextField fullWidth size="small" label="Local patient ID" value={patient ?? ""} onChange={(e) => setPatient(e.target.value || null)} helperText="Administrators enter the local ID for link corrections" />
            )}
          </Paper>
        </Grid>
        <Grid item xs={12} md={8}>
          {!patient && <Alert severity="info">Choose a patient.</Alert>}
          {patient && (
            <Stack spacing={2}>
              <Paper sx={{ p: 2 }}>
                <Typography variant="h6" gutterBottom>
                  Links for {selected ? `${selected.given} ${selected.family}` : patient} ({me?.institution_id} / {patient})
                </Typography>
                <ErrorAlert error={links.error || act.error} />
                {links.data?.length === 0 && <Empty>No links.</Empty>}
                <Stack spacing={1.5}>
                  {links.data?.map((l) => {
                    const other = l.a_institution === me?.institution_id && l.a_local_id === patient ? [l.b_institution, l.b_local_id] : [l.a_institution, l.a_local_id];
                    const mc = l.match_check as Record<string, boolean | string> | null;
                    return (
                      <Paper key={l.id} sx={{ p: 1.5 }}>
                        <Stack direction="row" justifyContent="space-between">
                          <Typography variant="subtitle2">
                            ↔ {ref.data?.institutions[other[0]]?.name ?? other[0]} / {other[1]}
                          </Typography>
                          <Tag tone={TONE[l.status] ?? "neutral"} label={l.status} />
                        </Stack>
                        <Typography variant="body2" sx={{ whiteSpace: "pre-line" }}>
                          Basis: {l.basis}
                        </Typography>
                        {mc && (
                          <Typography variant="caption" display="block">
                            Identity check at source: {mc.error ? String(mc.error) : `record ${mc.record_exists ? "exists" : "NOT FOUND"} · family ${mc.family_match ? "matches" : "differs"} · given ${mc.given_match ? "matches" : "differs"} · date of birth ${mc.birth_date_match ? "matches" : "differs"}`}
                          </Typography>
                        )}
                        <Typography variant="caption" color="text.secondary" display="block">
                          Proposed by {l.proposed_by} ({fmtDate(l.proposed_at)}){l.verified_by ? ` · verified by ${l.verified_by} (${fmtDate(l.verified_at)})` : ""}
                          {l.invalidated_by ? ` · ${l.status} by ${l.invalidated_by} (${fmtDate(l.invalidated_at)}): ${l.invalidation_reason}` : ""}
                        </Typography>
                        <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
                          {l.status === "pending" && canVerify && (
                            <Button size="small" variant="contained" onClick={() => setDialog({ link: l, action: "verify" })}>
                              Verify
                            </Button>
                          )}
                          {l.status === "pending" && (
                            <Button size="small" onClick={() => setDialog({ link: l, action: "reject" })}>
                              Reject
                            </Button>
                          )}
                          {l.status === "verified" && canVerify && (
                            <Button size="small" color="error" onClick={() => setDialog({ link: l, action: "invalidate" })}>
                              Invalidate
                            </Button>
                          )}
                        </Stack>
                        {!!l.events?.length && (
                          <details>
                            <summary>
                              <Typography variant="caption" component="span">History ({l.events.length})</Typography>
                            </summary>
                            {l.events.map((e, i) => (
                              <Typography key={i} variant="caption" display="block">
                                {fmtDate(e.created_at)} {e.action} by {e.actor}: {e.note}
                              </Typography>
                            ))}
                          </details>
                        )}
                      </Paper>
                    );
                  })}
                </Stack>
              </Paper>
              {canSearch && (
                <Paper sx={{ p: 2 }}>
                  <Typography variant="h6" gutterBottom>
                    Propose a link
                  </Typography>
                  <Stack spacing={1.5}>
                    <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
                      <TextField select size="small" label="Institution" value={form.b_institution} onChange={(e) => setForm({ ...form, b_institution: e.target.value })} sx={{ minWidth: 260 }}>
                        <MenuItem value="lab-b">Lab B - Saddar Diagnostic Laboratory, Karachi</MenuItem>
                        <MenuItem value="spec-c">Specialist C - Clifton Dental & Orthodontic Centre, Karachi</MenuItem>
                      </TextField>
                      <TextField size="small" label="Their local patient ID" value={form.b_local_id} onChange={(e) => setForm({ ...form, b_local_id: e.target.value })} />
                    </Stack>
                    <TextField size="small" label="Verification basis (what evidence was checked)" value={form.basis} onChange={(e) => setForm({ ...form, basis: e.target.value })} />
                    <Typography variant="body2" color="text.secondary">
                      Optional identity check: the other institution confirms field matches without revealing its record.
                    </Typography>
                    <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
                      <TextField size="small" label="Family name" value={form.family} onChange={(e) => setForm({ ...form, family: e.target.value })} />
                      <TextField size="small" label="Given name" value={form.given} onChange={(e) => setForm({ ...form, given: e.target.value })} />
                      <TextField size="small" label="Date of birth (YYYY-MM-DD)" value={form.birth_date} onChange={(e) => setForm({ ...form, birth_date: e.target.value })} />
                    </Stack>
                    <ErrorAlert error={propose.error} />
                    <Button variant="contained" sx={{ alignSelf: "start" }} disabled={!form.b_local_id || form.basis.length < 5 || propose.isPending} onClick={() => propose.mutate()}>
                      Propose link (pending verification)
                    </Button>
                  </Stack>
                </Paper>
              )}
            </Stack>
          )}
        </Grid>
      </Grid>
      {dialog && (
        <ReasonDialog
          open
          title={{ verify: "Verify patient link", reject: "Reject proposed link", invalidate: "Invalidate patient link" }[dialog.action]}
          label={dialog.action === "verify" ? "Verification evidence checked" : "Reason"}
          confirm={{ verify: "Verify", reject: "Reject", invalidate: "Invalidate" }[dialog.action]}
          minLength={5}
          onClose={() => setDialog(null)}
          onConfirm={(note) => act.mutate({ link: dialog.link, action: dialog.action, note })}
          busy={act.isPending}
        >
          {dialog.action === "invalidate" && (
            <Alert severity="warning" sx={{ mb: 1 }}>
              Evidence imported through this link will stop being usable. Affected drafts and approved packages are flagged for review; history is kept.
            </Alert>
          )}
        </ReasonDialog>
      )}
    </>
  );
}
