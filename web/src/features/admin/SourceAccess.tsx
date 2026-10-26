import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Checkbox, FormControlLabel, FormGroup, MenuItem, Paper, Stack, Table, TableBody, TableCell, TableHead, TableRow, TextField, Typography } from "@mui/material";
import { api } from "../../api/client";
import { ErrorAlert, fmtDate, Loading, PageHeader, ReasonDialog, Tag } from "../../components/common";
import type { AccessGrant } from "../../api/types";
import { ownService, useMe, useRefData } from "../../hooks";

type Grant = AccessGrant;
const STATE_LABEL: Record<Grant["state"], string> = { active: "active", expired: "expired", revoked: "revoked", legacy_no_expiry: "active, no end date" };
const SOON_MS = 3 * 24 * 3600 * 1000;
const soon = (g: Grant) => g.state === "active" && !!g.expires_at && new Date(g.expires_at).getTime() - Date.now() < SOON_MS;

const CATEGORIES = ["demographics", "conditions", "surgeries", "visits", "medications", "labs", "imaging", "documents"];

export function SourceAccess() {
  const { data: me } = useMe();
  const ref = useRefData();
  const qc = useQueryClient();
  const service = ownService(me);
  const hasSystem = !!me?.institution_id && service !== "central";
  const q = useQuery({ queryKey: ["grants", service], queryFn: () => api.get<Grant[]>("/admin/grants", service), enabled: hasSystem });
  const [form, setForm] = useState({ grantee_institution: "", local_patient_id: "", categories: [] as string[], basis: "", duration_days: 14 });
  const [filter, setFilter] = useState<"all" | "live" | "soon">("live");
  const [extending, setExtending] = useState<Grant | null>(null);
  const [days, setDays] = useState(7);
  const extend = useMutation({
    mutationFn: (reason: string) => api.post(`/admin/grants/${extending!.id}/extend`, { days, reason }, service),
    meta: { success: "Access extended." },
    onSuccess: () => {
      setExtending(null);
      qc.invalidateQueries({ queryKey: ["grants", service] });
    },
  });
  const create = useMutation({
    mutationFn: () => api.post("/admin/grants", form, service),
    meta: { success: "Access granted." },
    onSuccess: () => {
      setForm({ ...form, local_patient_id: "", basis: "", categories: [] });
      qc.invalidateQueries({ queryKey: ["grants", service] });
    },
  });
  const revoke = useMutation({
    mutationFn: (id: number) => api.post(`/admin/grants/${id}/revoke`, undefined, service),
    meta: { success: "Access revoked." },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["grants", service] }),
  });
  if (me && !hasSystem) return <Alert severity="info">Your institution does not run its own patient system in this demonstration.</Alert>;
  const others = Object.entries(ref.data?.institutions ?? {}).filter(([k]) => k !== me?.institution_id);
  return (
    <>
      <PageHeader title="Record sharing" subtitle={`${me?.institution_name ?? ""} decides which other institutions may read which of its patients' records. Its own system enforces this.`} />
      <Alert severity="info" sx={{ mb: 2 }}>
        Sharing is normally set up automatically: when your staff approve a patient-link request from another institution, that institution may read
        the patient's referral-relevant records here, for a limited time (at most 30 days). Sharing for a referral ends when the referral is
        finished. Use this page to review, extend or revoke sharing, or to add it by hand.
      </Alert>
      <ErrorAlert error={q.error || create.error || revoke.error || extend.error} />
      <Paper sx={{ p: 2, mb: 2 }}>
        <Typography variant="h6" gutterBottom>
          Share records by hand
        </Typography>
        <Stack spacing={1.5}>
          <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
            <TextField select size="small" label="Share with" value={form.grantee_institution} onChange={(e) => setForm({ ...form, grantee_institution: e.target.value })} sx={{ minWidth: 260 }}>
              {others.map(([k, v]) => (
                <MenuItem key={k} value={k}>
                  {v.name}
                </MenuItem>
              ))}
            </TextField>
            <TextField size="small" label="Our patient ID" value={form.local_patient_id} onChange={(e) => setForm({ ...form, local_patient_id: e.target.value })} />
          </Stack>
          <FormGroup row>
            {CATEGORIES.map((c) => (
              <FormControlLabel
                key={c}
                control={<Checkbox checked={form.categories.includes(c)} onChange={(e) => setForm({ ...form, categories: e.target.checked ? [...form.categories, c] : form.categories.filter((x) => x !== c) })} />}
                label={c}
              />
            ))}
          </FormGroup>
          <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
            <TextField size="small" label="Basis (consent or agreement)" value={form.basis} onChange={(e) => setForm({ ...form, basis: e.target.value })} sx={{ flex: 1 }} />
            <TextField size="small" type="number" label="For how many days (1 to 30)" value={form.duration_days} inputProps={{ min: 1, max: 30 }}
              onChange={(e) => setForm({ ...form, duration_days: Number(e.target.value) })} sx={{ width: 220 }} />
          </Stack>
          <Button
            variant="contained"
            sx={{ alignSelf: "start" }}
            disabled={!form.grantee_institution || !form.local_patient_id || !form.categories.length || create.isPending}
            onClick={() => create.mutate()}
          >
            Share
          </Button>
        </Stack>
      </Paper>
      {q.isLoading && <Loading />}
      {q.data && (
        <TextField select size="small" label="Show" value={filter} onChange={(e) => setFilter(e.target.value as typeof filter)} sx={{ mb: 1.5, minWidth: 220 }}>
          <MenuItem value="live">Active</MenuItem>
          <MenuItem value="soon">Ending within 3 days</MenuItem>
          <MenuItem value="all">All, including ended</MenuItem>
        </TextField>
      )}
      {q.data && (
        <Paper>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Shared with</TableCell>
                <TableCell>Our patient ID</TableCell>
                <TableCell>Records</TableCell>
                <TableCell>Basis</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Ends</TableCell>
                <TableCell>
                  <span className="sr-only">Actions</span>
                </TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {q.data.filter((g) => filter === "all" || (filter === "soon" ? soon(g) : ["active", "legacy_no_expiry"].includes(g.state))).map((g) => (
                <TableRow key={g.id}>
                  <TableCell>{ref.data?.institutions[g.grantee_institution]?.name ?? g.grantee_institution}</TableCell>
                  <TableCell>{g.local_patient_id}</TableCell>
                  <TableCell>{g.categories.join(", ")}</TableCell>
                  <TableCell>
                    {g.basis}
                    <Typography variant="caption" display="block" color="text.secondary">
                      {g.granted_by}, {fmtDate(g.created_at)}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Tag tone={g.state === "active" ? (soon(g) ? "warn" : "ok") : g.state === "legacy_no_expiry" ? "warn" : "off"} label={STATE_LABEL[g.state]} />
                    {g.revoked_by && <Typography variant="caption" display="block">by {g.revoked_by}</Typography>}
                    {g.referral_ref && <Typography variant="caption" display="block" color="text.secondary">for {g.referral_ref}</Typography>}
                  </TableCell>
                  <TableCell>{g.expires_at ? fmtDate(g.expires_at) : "No end date"}</TableCell>
                  <TableCell>
                    {g.status === "active" && (
                      <Stack direction="row" spacing={0.5}>
                        <Button size="small" onClick={() => setExtending(g)}>Extend</Button>
                        <Button size="small" color="error" onClick={() => revoke.mutate(g.id)}>
                          Revoke
                        </Button>
                      </Stack>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Paper>
      )}
      {extending && (
        <ReasonDialog open title={`Extend sharing with ${ref.data?.institutions[extending.grantee_institution]?.name ?? extending.grantee_institution}`}
          label="Reason" confirm={`Extend by ${days} day(s) from today`} onClose={() => setExtending(null)} onConfirm={(r) => extend.mutate(r)} busy={extend.isPending}>
          <TextField size="small" type="number" label="Days from today (1 to 30)" value={days} inputProps={{ min: 1, max: 30 }} onChange={(e) => setDays(Number(e.target.value))} sx={{ mt: 1 }} />
        </ReasonDialog>
      )}
    </>
  );
}
