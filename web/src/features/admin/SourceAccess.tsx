import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Checkbox, FormControlLabel, FormGroup, MenuItem, Paper, Stack, Table, TableBody, TableCell, TableHead, TableRow, TextField, Typography } from "@mui/material";
import { api, Service } from "../../api/client";
import { ErrorAlert, fmtDate, Loading, PageHeader, Tag } from "../../components/common";
import { useMe, useRefData } from "../../hooks";

type Grant = { id: number; grantee_institution: string; local_patient_id: string; categories: string[]; status: string; basis: string; granted_by: string; created_at: string; revoked_by: string | null; revoked_at: string | null };

export const SOURCE_SERVICE: Record<string, Service> = { "clinic-a": "clinic", "lab-b": "lab", "spec-c": "specialist" };
const CATEGORIES = ["demographics", "encounters", "conditions", "medications", "labs", "documents", "consultations"];

export function SourceAccess() {
  const { data: me } = useMe();
  const ref = useRefData();
  const qc = useQueryClient();
  const service = SOURCE_SERVICE[me?.institution_id ?? ""];
  const q = useQuery({ queryKey: ["grants", service], queryFn: () => api.get<Grant[]>("/admin/grants", service), enabled: !!service });
  const [form, setForm] = useState({ grantee_institution: "clinic-a", local_patient_id: "", categories: [] as string[], basis: "" });
  const create = useMutation({
    mutationFn: () => api.post("/admin/grants", form, service),
    onSuccess: () => {
      setForm({ ...form, local_patient_id: "", basis: "", categories: [] });
      qc.invalidateQueries({ queryKey: ["grants", service] });
    },
  });
  const revoke = useMutation({ mutationFn: (id: number) => api.post(`/admin/grants/${id}/revoke`, undefined, service), onSuccess: () => qc.invalidateQueries({ queryKey: ["grants", service] }) });
  if (!service) return <Alert severity="info">Your institution does not operate a source system in this demonstration.</Alert>;
  return (
    <>
      <PageHeader title="Source access grants" subtitle={`${me?.institution_name} decides which other institutions may read which patient records. Enforced by this source service itself.`} />
      <ErrorAlert error={q.error || create.error || revoke.error} />
      <Paper sx={{ p: 2, mb: 2 }}>
        <Typography variant="h6" gutterBottom>
          Grant access
        </Typography>
        <Stack spacing={1.5}>
          <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
            <TextField select size="small" label="Grantee institution" value={form.grantee_institution} onChange={(e) => setForm({ ...form, grantee_institution: e.target.value })} sx={{ minWidth: 260 }}>
              {Object.entries(ref.data?.institutions ?? {})
                .filter(([k]) => k !== me?.institution_id && k !== "central-platform")
                .map(([k, v]) => (
                  <MenuItem key={k} value={k}>
                    {v.name}
                  </MenuItem>
                ))}
            </TextField>
            <TextField size="small" label="Our local patient ID" value={form.local_patient_id} onChange={(e) => setForm({ ...form, local_patient_id: e.target.value })} />
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
          <TextField size="small" label="Basis (consent / agreement)" value={form.basis} onChange={(e) => setForm({ ...form, basis: e.target.value })} />
          <Button variant="contained" sx={{ alignSelf: "start" }} disabled={!form.local_patient_id || !form.categories.length || create.isPending} onClick={() => create.mutate()}>
            Grant
          </Button>
        </Stack>
      </Paper>
      {q.isLoading && <Loading />}
      {q.data && (
        <Paper>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Grantee</TableCell>
                <TableCell>Patient</TableCell>
                <TableCell>Categories</TableCell>
                <TableCell>Basis</TableCell>
                <TableCell>Status</TableCell>
                <TableCell />
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
