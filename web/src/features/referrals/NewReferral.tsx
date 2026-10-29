import { useEffect, useState } from "react";
import { Link as RouterLink, useNavigate, useSearchParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Alert, Box, Button, ButtonBase, Dialog, DialogContent, DialogTitle, Divider, InputAdornment, List, ListItemButton, ListItemText, Paper, Stack, TextField, Typography } from "@mui/material";
import Add from "@mui/icons-material/Add";
import Biotech from "@mui/icons-material/Biotech";
import PersonSearch from "@mui/icons-material/PersonSearch";
import Search from "@mui/icons-material/Search";
import { api } from "../../api/client";
import type { PatientIndexEntry, Referral, RequestKind } from "../../api/types";
import { ErrorAlert, KeyValue, Loading, PageHeader } from "../../components/common";
import { fmtCnic } from "../../components/ReferralLetter";
import { isDoctor, useMe, useRefData } from "../../hooks";
import { tokens } from "../../theme";
import { DiagnosticDraft, DiagnosticFields, diagnosticComplete, emptyDiagnostic, FormValues, procedurePayload, ReferralFields } from "./ReferralForm";

export const formatCnic = fmtCnic;

const CHOICES: { kind: RequestKind; title: string; body: string; icon: typeof PersonSearch }[] = [
  {
    kind: "referral",
    title: "Refer to a doctor or department",
    body: "The patient is seen by a specialist at another clinic or hospital. Staff gather the records and medicines; you review the medication flags; staff send it.",
    icon: PersonSearch,
  },
  {
    kind: "test",
    title: "Request a test or scan",
    body: "Laboratory tests, scans or ECG at a laboratory, radiology or cardiac department elsewhere. Staff send the orders and the results come back to you.",
    icon: Biotech,
  },
];

function ChoiceCards({ onPick }: { onPick: (k: RequestKind) => void }) {
  return (
    <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
      {CHOICES.map((c) => (
        <ButtonBase key={c.kind} onClick={() => onPick(c.kind)} focusRipple
          sx={{ flex: 1, textAlign: "left", display: "block", border: `1px solid ${tokens.line}`, borderRadius: 1, p: 2.5, "&:hover": { borderColor: tokens.brand, backgroundColor: tokens.sunken } }}>
          <Stack direction="row" spacing={1.5} alignItems="flex-start">
            <c.icon aria-hidden sx={{ color: tokens.brand, mt: 0.25 }} />
            <Box>
              <Typography variant="h6" component="span" display="block">
                {c.title}
              </Typography>
              <Typography variant="body2" color="text.secondary" component="span" display="block">
                {c.body}
              </Typography>
            </Box>
          </Stack>
        </ButtonBase>
      ))}
    </Stack>
  );
}

/** "New request": the doctor first chooses a referral or a test/scan request. */
export function NewRequestButton({ size = "medium" }: { size?: "small" | "medium" | "large" }) {
  const [open, setOpen] = useState(false);
  const nav = useNavigate();
  return (
    <>
      <Button variant="contained" startIcon={<Add />} size={size} onClick={() => setOpen(true)}>
        New request
      </Button>
      <Dialog open={open} onClose={() => setOpen(false)} fullWidth maxWidth="md" aria-labelledby="new-request-title">
        <DialogTitle id="new-request-title">What do you need?</DialogTitle>
        <DialogContent>
          <ChoiceCards onPick={(k) => { setOpen(false); nav(`/referrals/new?kind=${k}`); }} />
        </DialogContent>
      </Dialog>
    </>
  );
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
                secondary={`Born ${p.birth_date} · ${p.sex === "F" ? "Female" : p.sex === "M" ? "Male" : p.sex} · CNIC ${fmtCnic(p.cnic)}`} />
            </ListItemButton>
          ))}
          {search.data?.length === 0 && <Typography color="text.secondary" sx={{ px: 2 }}>No matching patient at your institution.</Typography>}
        </List>
      )}
    </Stack>
  );
}

function PatientBlock({ patient, setPatient, institution }: { patient: PatientIndexEntry | null; setPatient: (p: PatientIndexEntry | null) => void; institution: string | null }) {
  return (
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
            ["CNIC", fmtCnic(patient.cnic)],
            [`${institution} ID`, patient.local_patient_id],
          ]} />
          <Button onClick={() => setPatient(null)} sx={{ alignSelf: "start" }}>Change patient</Button>
        </Stack>
      ) : (
        <PatientPicker onPick={setPatient} />
      )}
    </Paper>
  );
}

function ReferralRequest() {
  const nav = useNavigate();
  const { data: me } = useMe();
  const rd = useRefData();
  const [patient, setPatient] = useState<PatientIndexEntry | null>(null);
  const [values, setValues] = useState<FormValues>({
    source_department: me?.department ?? "", destination_institution: "", destination_department: "", destination_doctor: "",
    reason: "", consultation_notes: "", urgency: "routine", procedure_status: "unknown", planned_procedure: "", procedure_tags: [],
  });
  // The signed-in doctor's own department, once their profile has loaded.
  useEffect(() => {
    if (me?.department) setValues((v) => (v.source_department ? v : { ...v, source_department: me.department! }));
  }, [me?.department]);
  const save = useMutation({
    mutationFn: (submit: boolean) =>
      api.post<Referral>("/referrals", {
        kind: "referral", patient_local_id: patient!.local_patient_id, source_department: values.source_department || me?.department,
        destination_institution: values.destination_institution, destination_department: values.destination_department,
        destination_doctor: values.destination_doctor || null, reason: values.reason, consultation_notes: values.consultation_notes, urgency: values.urgency,
        ...procedurePayload(values), submit,
      }),
    meta: { success: "Request saved." },
    onSuccess: (r) => nav(`/referrals/${r.id}`),
  });
  if (!me || !rd.data) return <Loading />;
  const ready = patient && values.destination_institution && values.destination_department && values.reason.trim().length >= 10
    && (values.procedure_status !== "planned" || values.planned_procedure.trim().length >= 3);
  return (
    <Stack spacing={2}>
      <PatientBlock patient={patient} setPatient={setPatient} institution={me.institution_name} />
      <Paper sx={{ p: { xs: 2, md: 2.5 } }}>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Requested by <strong>{me.name}</strong>, {me.institution_name}
        </Typography>
        <ReferralFields rd={rd.data} me={me} values={values} onChange={setValues} />
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
            To submit: choose the patient, where you are referring to, write the reason (at least 10 characters), and name the procedure if one is planned.
          </Typography>
        )}
      </Box>
    </Stack>
  );
}

function TestRequest() {
  const nav = useNavigate();
  const { data: me } = useMe();
  const rd = useRefData();
  const [patient, setPatient] = useState<PatientIndexEntry | null>(null);
  const [details, setDetails] = useState("");
  const [tests, setTests] = useState<DiagnosticDraft[]>([emptyDiagnostic()]);
  const save = useMutation({
    mutationFn: () =>
      api.post<Referral>("/referrals", {
        kind: "test", patient_local_id: patient!.local_patient_id, source_department: me?.department, reason: details,
        urgency: tests.some((t) => t.urgency === "urgent") ? "urgent" : tests.some((t) => t.urgency === "soon") ? "soon" : "routine",
        diagnostic_requests: tests.map((d) => ({ ...d, body_area: d.body_area || null })), submit: true,
      }),
    meta: { success: "Test request sent to staff." },
    onSuccess: (r) => nav(`/referrals/${r.id}`),
  });
  if (!me || !rd.data) return <Loading />;
  const ready = patient && tests.length > 0 && tests.every(diagnosticComplete);
  return (
    <Stack spacing={2}>
      <PatientBlock patient={patient} setPatient={setPatient} institution={me.institution_name} />
      <Paper sx={{ p: { xs: 2, md: 2.5 } }}>
        <Typography variant="h6" component="h2">
          Tests and scans
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Each test is a separate order to the laboratory, radiology or cardiac department you choose. The results come back to you.
        </Typography>
        <DiagnosticFields rd={rd.data} items={tests} onChange={setTests} ownInstitution={me.institution_id ?? ""} />
        <TextField fullWidth multiline minRows={2} sx={{ mt: 2 }} label="Clinical details (optional)" value={details} onChange={(e) => setDetails(e.target.value)}
          helperText="Anything the department should know, for example allergies or kidney function before contrast." />
      </Paper>
      <ErrorAlert error={save.error} />
      <Box>
        <Button variant="contained" size="large" disabled={!ready || save.isPending} onClick={() => save.mutate()}>
          Submit request
        </Button>
        {!ready && (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
            To submit: choose the patient and complete each test (name, clinical question, where).
          </Typography>
        )}
      </Box>
    </Stack>
  );
}

export function NewReferral() {
  const { data: me } = useMe();
  const [params, setParams] = useSearchParams();
  const kind = params.get("kind") as RequestKind | null;
  if (!me) return <Loading />;
  if (!isDoctor(me)) return <Alert severity="info">Only a doctor makes a request. Staff prepare and send it once a doctor has submitted it.</Alert>;
  const title = kind === "test" ? "Request a test or scan" : kind === "referral" ? "Refer to a doctor or department" : "New request";
  const subtitle = kind === "test"
    ? "Staff check and send each order. Results come back to you."
    : kind === "referral"
      ? "Staff gather the records and medicines; you then review the medication flags; staff send it."
      : "Choose what you need.";
  return (
    <>
      <PageHeader title={title} subtitle={subtitle} back={{ to: "/referrals", label: "Requests" }}
        actions={kind ? <Button component={RouterLink} to="/referrals/new">Change type</Button> : undefined} />
      {!kind && <ChoiceCards onPick={(k) => setParams({ kind: k })} />}
      {kind === "referral" && <ReferralRequest />}
      {kind === "test" && <TestRequest />}
    </>
  );
}
