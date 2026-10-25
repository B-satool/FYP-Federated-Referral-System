import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Checkbox, FormControlLabel, FormGroup, MenuItem, Paper, Stack, Table, TableBody, TableCell, TableHead, TableRow, TextField, Typography } from "@mui/material";
import { api } from "../../api/client";
import { ErrorAlert, fmtDate, Loading, PageHeader, Tag } from "../../components/common";
import { ownService, useMe, useRefData } from "../../hooks";

type Grant = { id: number; grantee_institution: string; local_patient_id: string; categories: string[]; status: string; basis: string; granted_by: string; created_at: string; revoked_by: string | null; revoked_at: string | null };

const CATEGORIES = ["demographics", "conditions", "surgeries", "visits", "medications", "labs", "imaging", "documents"];

export function SourceAccess() {
  const { data: me } = useMe();
  const ref = useRefData();
  const qc = useQueryClient();
  const service = ownService(me);
  const hasSystem = !!me?.institution_id && service !== "central";
  const q = useQuery({ queryKey: ["grants", service], queryFn: () => api.get<Grant[]>("/admin/grants", service), enabled: hasSystem });
  const [form, setForm] = useState({ grantee_institution: "", local_patient_id: "", categories: [] as string[], basis: "" });
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
        the patient's referral-relevant records here. Use this page to review or revoke sharing, or to add it by hand.
      </Alert>
      <ErrorAlert error={q.error || create.error || revoke.error} />
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
          <TextField size="small" label="Basis (consent or agreement)" value={form.basis} onChange={(e) => setForm({ ...form, basis: e.target.value })} />
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
        <Paper>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Shared with</TableCell>
                <TableCell>Our patient ID</TableCell>
                <TableCell>Records</TableCell>
                <TableCell>Basis</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>
                  <span className="sr-only">Actions</span>
                </TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {q.data.map((g) => (
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
                    <Tag tone={g.status === "active" ? "ok" : "off"} label={g.status} />
                    {g.revoked_by && <Typography variant="caption" display="block">by {g.revoked_by}</Typography>}
                  </TableCell>
                  <TableCell>
                    {g.status === "active" && (
                      <Button size="small" color="error" onClick={() => revoke.mutate(g.id)}>
                        Revoke
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Paper>
      )}
    </>
  );
}
