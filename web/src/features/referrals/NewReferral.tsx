import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useForm, Controller } from "react-hook-form";
import {
  Alert,
  Button,
  FormControlLabel,
  List,
  ListItemButton,
  ListItemText,
  MenuItem,
  Paper,
  Radio,
  RadioGroup,
  Stack,
  TextField,
  Typography,
  FormLabel,
  FormControl,
} from "@mui/material";
import { api } from "../../api/client";
import type { PatientSummary, Referral } from "../../api/types";
import { ErrorAlert, Loading, PageHeader } from "../../components/common";
import { hasRole, useMe, useRefData } from "../../hooks";

type FormValues = { reason: string; priority: string; procedure_status: "known" | "unknown" | "not_stated"; planned_procedure: string };

export function NewReferral() {
  const nav = useNavigate();
  const { data: me } = useMe();
  const ref = useRefData();
  const [search, setSearch] = useState("");
  const [patient, setPatient] = useState<PatientSummary | null>(null);
  const patients = useQuery({
    queryKey: ["patient-search", search],
    queryFn: () => api.get<PatientSummary[]>(`/patients/search?q=${encodeURIComponent(search)}`),
  });
  const { control, register, handleSubmit, watch, formState } = useForm<FormValues>({
    defaultValues: { reason: "", priority: "", procedure_status: "not_stated", planned_procedure: "" },
  });
  const create = useMutation({
    mutationFn: (v: FormValues) =>
      api.post<Referral>("/referrals", {
        patient_local_id: patient!.local_patient_id,
        reason: v.reason,
        priority: v.priority || null,
        procedure_status: v.procedure_status,
        planned_procedure: v.procedure_status === "known" ? v.planned_procedure : null,
        destination_institution: "spec-c",
        specialty: "orthodontics",
      }),
    onSuccess: (r) => nav(`/referrals/${r.id}`),
  });
  const isClinician = hasRole(me, "clinician");
  const procStatus = watch("procedure_status");

  return (
    <>
      <PageHeader title="New referral" subtitle="Select the patient's local record, then describe the referral" />
      <Stack direction={{ xs: "column", md: "row" }} spacing={2} alignItems="flex-start">
        <Paper sx={{ p: 2, flex: 1, width: "100%" }}>
          <Typography variant="h6" gutterBottom>
            1. Patient ({me?.institution_name})
          </Typography>
          <TextField fullWidth size="small" label="Search by name or local ID" value={search} onChange={(e) => setSearch(e.target.value)} />
          {patients.isLoading && <Loading />}
          <ErrorAlert error={patients.error} />
          <List dense aria-label="Matching patients">
            {patients.data?.map((p) => (
              <ListItemButton key={p.local_patient_id} selected={patient?.local_patient_id === p.local_patient_id} onClick={() => setPatient(p)}>
                <ListItemText
                  primary={`${p.given} ${p.family}`}
                  secondary={`${p.institution_id} / ${p.local_patient_id} · born ${p.birth_date} · ${p.sex}${p.synthetic ? " · synthetic" : ""}`}
                />
              </ListItemButton>
            ))}
          </List>
        </Paper>
        <Paper sx={{ p: 2, flex: 1.4, width: "100%" }} component="form" onSubmit={handleSubmit((v) => create.mutate(v))}>
          <Typography variant="h6" gutterBottom>
            2. Referral details
          </Typography>
          <Stack spacing={2}>
            {patient ? (
              <Alert severity="info">
                Patient: <strong>{patient.given} {patient.family}</strong> ({patient.institution_id} / {patient.local_patient_id})
              </Alert>
            ) : (
              <Alert severity="warning">Select a patient first.</Alert>
            )}
            <TextField label="Destination" value="Specialist C - Smile Orthodontic Centre (Orthodontics)" disabled />
            <TextField label="Reason for referral" multiline minRows={3} {...register("reason")} helperText="What do you want the specialist to address?" />
            <Controller
              name="priority"
              control={control}
              render={({ field }) => (
                <TextField select label="Priority (clinician-selected)" {...field} disabled={!isClinician} helperText={isClinician ? "The system never assigns urgency" : "A clinician will set the priority"}>
                  <MenuItem value="">Not set</MenuItem>
                  {ref.data?.priorities.map((p) => (
                    <MenuItem key={p} value={p}>
                      {p}
                    </MenuItem>
                  ))}
                </TextField>
              )}
            />
            <FormControl>
              <FormLabel id="proc-label">Planned procedure</FormLabel>
              <Controller
                name="procedure_status"
                control={control}
                render={({ field }) => (
                  <RadioGroup row aria-labelledby="proc-label" {...field}>
                    <FormControlLabel value="known" control={<Radio />} label="Known" />
                    <FormControlLabel value="unknown" control={<Radio />} label="Explicitly unknown" />
                    <FormControlLabel value="not_stated" control={<Radio />} label="Decide later" />
                  </RadioGroup>
                )}
              />
            </FormControl>
            {procStatus === "known" && (
              <Controller
                name="planned_procedure"
                control={control}
                rules={{ required: true }}
                render={({ field }) => (
                  <TextField select label="Procedure" {...field}>
                    {Object.entries(ref.data?.procedures ?? {}).map(([k, v]) => (
                      <MenuItem key={k} value={k}>
                        {v}
                      </MenuItem>
                    ))}
                  </TextField>
                )}
              />
            )}
            <ErrorAlert error={create.error} />
            <Stack direction="row" spacing={1}>
              <Button type="submit" variant="contained" disabled={!patient || create.isPending || (procStatus === "known" && !watch("planned_procedure"))}>
                Create draft
              </Button>
              <Button onClick={() => nav("/referrals")}>Cancel</Button>
            </Stack>
            {formState.isSubmitted && !patient && <Typography color="error">Choose a patient.</Typography>}
          </Stack>
        </Paper>
      </Stack>
    </>
  );
}
