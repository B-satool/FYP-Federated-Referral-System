import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Dialog, DialogActions, DialogContent, DialogTitle, Grid, List, ListItemButton, ListItemText, Paper, Stack, Table, TableBody, TableCell, TableHead, TableRow, TextField, Typography } from "@mui/material";
import { api } from "../../api/client";
import { ErrorAlert, fmtDate, Loading, PageHeader, Tag } from "../../components/common";

type LabPatient = { local_patient_id: string; given: string; family: string; birth_date: string; sex: string };
type LabResult = {
  id: string;
  test_name: string;
  loinc: string | null;
  value_num: number | null;
  value_text: string | null;
  unit: string | null;
  reference_range: string | null;
  specimen: string | null;
  collected_at: string;
  resulted_at: string;
  status: string;
  version: number;
  revisions: { version: number; reason: string; changed_by: string; changed_at: string; snapshot: Record<string, unknown> }[];
};

export function LabWorkspace() {
  const [params] = useSearchParams();
  const qc = useQueryClient();
  const [patient, setPatient] = useState<string | null>(params.get("patient") || null);
  const [editing, setEditing] = useState<LabResult | null>(null);
  const [value, setValue] = useState("");
  const [reason, setReason] = useState("");
  const patients = useQuery({ queryKey: ["lab-patients"], queryFn: () => api.get<LabPatient[]>("/lab/patients", "lab") });
  const results = useQuery({ queryKey: ["lab-results", patient], queryFn: () => api.get<LabResult[]>(`/lab/patients/${patient}/results`, "lab"), enabled: !!patient });
  const correct = useMutation({
    mutationFn: () => api.post(`/lab/results/${editing!.id}/correct`, { value_num: value === "" ? null : Number(value), reason, expected_version: editing!.version }, "lab"),
    onSuccess: () => {
      setEditing(null);
      qc.invalidateQueries({ queryKey: ["lab-results", patient] });
    },
  });
  return (
    <>
      <PageHeader title="Laboratory records" subtitle="Lab B - Saddar Diagnostic Laboratory, Karachi. Corrections publish a new record version; earlier versions are retained." />
      <Grid container spacing={2}>
        <Grid item xs={12} md={3}>
          <Paper>
            {patients.isLoading && <Loading />}
            <ErrorAlert error={patients.error} />
            <List dense>
              {patients.data?.map((p) => (
                <ListItemButton key={p.local_patient_id} selected={patient === p.local_patient_id} onClick={() => setPatient(p.local_patient_id)}>
                  <ListItemText primary={`${p.given} ${p.family}`} secondary={`${p.local_patient_id} · born ${p.birth_date}`} />
                </ListItemButton>
              ))}
            </List>
          </Paper>
        </Grid>
        <Grid item xs={12} md={9}>
          <Paper sx={{ p: 2 }}>
            {!patient && <Typography color="text.secondary">Choose a patient.</Typography>}
            {results.isLoading && <Loading />}
            <ErrorAlert error={results.error || correct.error} />
            {results.data && (
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Test</TableCell>
                    <TableCell>Value</TableCell>
                    <TableCell>Collected</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell />
                  </TableRow>
                </TableHead>
                <TableBody>
                  {results.data.map((r) => (
                    <TableRow key={r.id}>
                      <TableCell>
                        {r.test_name}
                        <Typography variant="caption" display="block" color="text.secondary">
                          {r.id} · LOINC {r.loinc} · {r.specimen}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        {r.value_num ?? r.value_text ?? <Tag tone="warn" label="not recorded" />} {r.unit}
                        <Typography variant="caption" display="block" color="text.secondary">
                          ref {r.reference_range}
                        </Typography>
                      </TableCell>
                      <TableCell>{fmtDate(r.collected_at)}</TableCell>
                      <TableCell>
                        <Tag tone={r.status === "final" ? "ok" : r.status === "corrected" ? "info" : "warn"} label={`${r.status} v${r.version}`} />
                        {r.revisions.map((rv) => (
                          <Typography key={rv.version} variant="caption" display="block">
                            v{rv.version}: {String(rv.snapshot.value_num ?? rv.snapshot.value_text ?? "no value")} → corrected by {rv.changed_by}: {rv.reason}
                          </Typography>
                        ))}
                      </TableCell>
                      <TableCell>
                        <Button size="small" onClick={() => { setEditing(r); setValue(r.value_num?.toString() ?? ""); setReason(""); }}>
                          Correct
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </Paper>
        </Grid>
      </Grid>
      {editing && (
        <Dialog open onClose={() => setEditing(null)} fullWidth maxWidth="xs">
          <DialogTitle>Correct {editing.test_name}</DialogTitle>
          <DialogContent>
            <Stack spacing={2} sx={{ mt: 1 }}>
              <TextField label={`Value (${editing.unit ?? ""})`} value={value} onChange={(e) => setValue(e.target.value)} />
              <TextField label="Reason for correction" value={reason} onChange={(e) => setReason(e.target.value)} />
            </Stack>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setEditing(null)}>Cancel</Button>
            <Button variant="contained" disabled={reason.trim().length < 3 || correct.isPending} onClick={() => correct.mutate()}>
              Publish corrected version
            </Button>
          </DialogActions>
        </Dialog>
      )}
    </>
  );
}
