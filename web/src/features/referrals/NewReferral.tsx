import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Alert, Box, Button, Divider, InputAdornment, List, ListItemButton, ListItemText, Paper, Stack, TextField, Typography } from "@mui/material";
import Search from "@mui/icons-material/Search";
import { api } from "../../api/client";
import type { PatientIndexEntry, Referral } from "../../api/types";
import { ErrorAlert, KeyValue, Loading, PageHeader } from "../../components/common";
import { isDoctor, useMe, useRefData } from "../../hooks";
import { DiagnosticDraft, DiagnosticFields, diagnosticComplete, FormValues, ReferralFields } from "./ReferralForm";

export function formatCnic(c: string | null | undefined) {
  if (!c) return "Not recorded";
  const d = c.replace(/\D/g, "");
  return d.length === 13 ? `${d.slice(0, 5)}-${d.slice(5, 12)}-${d.slice(12)}` : c;
}

function PatientPicker({ onPick }: { onPick: (p: PatientIndexEntry) => void }) {
  const [q, setQ] = useState("");
  const search = useQuery({
    queryKey: ["patients", q],
    queryFn: () => api.get<PatientIndexEntry[]>(`/patients/search?q=${encodeURIComponent(q)}`),
  });
  return (
    <Stack spacing={1}>
      <TextField label="Find the patient" placeholder="Name, CNIC or clinic ID" value={q} onChange={(e) => setQ(e.target.value)}
        InputProps={{ startAdornment: <InputAdornment position="start"><Search /></InputAdornment> }} />
      <ErrorAlert error={search.error} />
      {search.isLoading ? <Loading /> : (
        <List dense aria-label="Patients">
          {(search.data ?? []).map((p) => (
            <ListItemButton key={p.local_patient_id} onClick={() => onPick(p)}>
              <ListItemText primary={`${p.name} (${p.local_patient_id})`}
                secondary={`Born ${p.birth_date} · ${p.sex === "F" ? "Female" : p.sex === "M" ? "Male" : p.sex} · CNIC ${formatCnic(p.cnic)}`} />
            </ListItemButton>
          ))}
          {search.data?.length === 0 && <Typography color="text.secondary" sx={{ px: 2 }}>No matching patient at your institution.</Typography>}
        </List>
      )}
    </Stack>
  );
}

export function NewReferral() {
  const nav = useNavigate();
  const { data: me } = useMe();
  const rd = useRefData();
  const [patient, setPatient] = useState<PatientIndexEntry | null>(null);
  const [values, setValues] = useState<FormValues>({
    source_department: me?.department ?? "", destination_institution: "", destination_department: "", destination_doctor: "",
    reason: "", urgency: "routine", procedure_status: "unknown", planned_procedure: "", procedure_other: "",
  });
  const [tests, setTests] = useState<DiagnosticDraft[]>([]);
  // The signed-in doctor's own department, once their profile has loaded.
  useEffect(() => {
    if (me?.department) setValues((v) => (v.source_department ? v : { ...v, source_department: me.department! }));
  }, [me?.department]);
  const save = useMutation({
    mutationFn: (submit: boolean) =>
      api.post<Referral>("/referrals", {
        patient_local_id: patient!.local_patient_id, ...values,
        source_department: values.source_department || me?.department, destination_doctor: values.destination_doctor || null,
        planned_procedure: values.procedure_status === "known" ? values.planned_procedure : null,
        procedure_other: values.procedure_status === "other" ? values.procedure_other : null,
        diagnostic_requests: tests.map((d) => ({ ...d, body_area: d.body_area || null })), submit,
      }),
    meta: { success: "Referral saved." },
    onSuccess: (r) => nav(`/referrals/${r.id}`),
  });

  if (!me || !rd.data) return <Loading />;
  if (!isDoctor(me)) return <Alert severity="info">Only a doctor can request a referral. Staff prepare and send referrals once a doctor has requested them.</Alert>;
  const ready = patient && values.destination_institution && values.destination_department && values.reason.trim().length >= 10
    && (values.procedure_status !== "known" || values.planned_procedure) && (values.procedure_status !== "other" || values.procedure_other.trim())
    && tests.every(diagnosticComplete);

  return (
    <>
      <PageHeader title="New referral" subtitle="Fill in the request. Staff then link the patient, gather the records and send it to the hospital." back={{ to: "/referrals", label: "Referrals" }} />
      <Stack spacing={2}>
        <Paper sx={{ p: { xs: 2, md: 2.5 } }}>
          <Typography variant="h6" component="h2" gutterBottom>
            Patient
          </Typography>
          {patient ? (
            <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" spacing={2}>
              <KeyValue items={[
                ["Name", patient.name],
                ["Date of birth", patient.birth_date],
                ["Sex", patient.sex === "F" ? "Female" : patient.sex === "M" ? "Male" : patient.sex],
                ["CNIC", formatCnic(patient.cnic)],
                [`${me.institution_name} ID`, patient.local_patient_id],
              ]} />
              <Button onClick={() => setPatient(null)} sx={{ alignSelf: "start" }}>Change patient</Button>
            </Stack>
          ) : (
            <PatientPicker onPick={setPatient} />
          )}
        </Paper>
        <Paper sx={{ p: { xs: 2, md: 2.5 } }}>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Requested by <strong>{me.name}</strong>, {me.institution_name}
          </Typography>
          <ReferralFields rd={rd.data} me={me} values={values} onChange={setValues} />
        </Paper>
        <Paper sx={{ p: { xs: 2, md: 2.5 } }}>
          <Typography variant="h6" component="h2">
            Tests, scans or equipment (optional)
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Ask for anything your clinic does not have. Each request is a separate order with its own status; the result comes back into this referral.
          </Typography>
          <DiagnosticFields rd={rd.data} items={tests} onChange={setTests} ownInstitution={me.institution_id ?? ""} />
        </Paper>
        <Divider />
        <ErrorAlert error={save.error} />
        <Box>
          <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5}>
            <Button variant="contained" size="large" disabled={!ready || save.isPending} onClick={() => save.mutate(true)}>
              Submit request
            </Button>
            <Button variant="outlined" disabled={!patient || !values.destination_institution || !values.destination_department || save.isPending}
              onClick={() => save.mutate(false)}>
              Save as draft
            </Button>
          </Stack>
          {!ready && (
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
              To submit: choose the patient, the hospital and department, write the reason (at least 10 characters), and complete any test requests.
            </Typography>
          )}
        </Box>
      </Stack>
    </>
  );
}
