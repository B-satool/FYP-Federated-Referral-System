import { Alert, Autocomplete, Box, Button, FormControlLabel, IconButton, MenuItem, Paper, Radio, RadioGroup, Stack, TextField, Typography } from "@mui/material";
import DeleteOutline from "@mui/icons-material/DeleteOutline";
import Add from "@mui/icons-material/Add";
import type { ReferenceData } from "../../api/types";

export type DiagnosticDraft = {
  category: string;
  test: string;
  body_area: string;
  clinical_question: string;
  urgency: string;
  destination_institution: string;
  destination_department: string;
};

export type FormValues = {
  source_department: string;
  destination_institution: string;
  destination_department: string;
  destination_doctor: string;
  reason: string;
  urgency: string;
  procedure_status: "known" | "none" | "unknown" | "other";
  planned_procedure: string;
  procedure_other: string;
};

export const emptyDiagnostic = (): DiagnosticDraft => ({
  category: "laboratory", test: "", body_area: "", clinical_question: "", urgency: "routine",
  destination_institution: "", destination_department: "",
});

const KIND_FOR_CATEGORY: Record<string, string> = { laboratory: "laboratory", imaging: "imaging", cardiac: "cardiac" };

/** The clinical part of the referral form (shared by "New referral" and editing a request). */
export function ReferralFields({ rd, me, values, onChange, disabled }: {
  rd: ReferenceData;
  me: { institution_id: string | null; department: string | null };
  values: FormValues;
  onChange: (v: FormValues) => void;
  disabled?: boolean;
}) {
  const set = (patch: Partial<FormValues>) => onChange({ ...values, ...patch });
  const own = me.institution_id ?? "";
  const ownDepts = (rd.institutions[own]?.departments ?? []).filter((d) => rd.departments[d]?.kind === "clinical");
  const hospitals = Object.entries(rd.institutions).filter(([id, i]) => i.kind === "hospital" && id !== own);
  const destDepts = (rd.institutions[values.destination_institution]?.departments ?? []).filter((d) => rd.departments[d]?.kind === "clinical");
  const doctors = rd.practitioners.filter((p) => p.institution === values.destination_institution && p.department === values.destination_department);
  const procedures = Object.entries(rd.procedures).filter(([, p]) => !values.destination_department || p.departments.includes(values.destination_department));

  return (
    <Stack spacing={2.5}>
      <Box>
        <Typography variant="subtitle1" component="h2" gutterBottom>
          Referring from
        </Typography>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
          <TextField select label="Your department" value={values.source_department} onChange={(e) => set({ source_department: e.target.value })} disabled={disabled} sx={{ minWidth: 260 }}>
            {ownDepts.map((d) => (
              <MenuItem key={d} value={d}>
                {rd.departments[d].name}
              </MenuItem>
            ))}
          </TextField>
        </Stack>
      </Box>

      <Box>
        <Typography variant="subtitle1" component="h2" gutterBottom>
          Referring to
        </Typography>
        <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
          <TextField select required label="Hospital" value={values.destination_institution} disabled={disabled}
            onChange={(e) => set({ destination_institution: e.target.value, destination_department: "", destination_doctor: "", planned_procedure: "" })} sx={{ minWidth: 260 }}>
            {hospitals.map(([id, i]) => (
              <MenuItem key={id} value={id}>
                {i.name}
              </MenuItem>
            ))}
          </TextField>
          <TextField select required label="Department" value={values.destination_department} disabled={disabled || !values.destination_institution}
            onChange={(e) => set({ destination_department: e.target.value, destination_doctor: "", planned_procedure: "" })} sx={{ minWidth: 300 }}>
            {destDepts.map((d) => (
              <MenuItem key={d} value={d}>
                {rd.departments[d].name}
              </MenuItem>
            ))}
          </TextField>
          <TextField select label="Doctor (optional)" value={values.destination_doctor} disabled={disabled || !values.destination_department}
            onChange={(e) => set({ destination_doctor: e.target.value })} sx={{ minWidth: 240 }}
            helperText={doctors.length ? " " : "Any doctor in the department"}>
            <MenuItem value="">Any doctor in the department</MenuItem>
            {doctors.map((p) => (
              <MenuItem key={p.name} value={p.name}>
                {p.name}
              </MenuItem>
            ))}
          </TextField>
        </Stack>
      </Box>

      <Box>
        <Typography variant="subtitle1" component="h2" gutterBottom>
          Clinical
        </Typography>
        <Stack spacing={2}>
          <TextField required label="Reason for referral" multiline minRows={4} value={values.reason} disabled={disabled}
            onChange={(e) => set({ reason: e.target.value })}
            helperText="What you want the specialist to address, and the key history." />
          <Box>
            <Typography id="urgency-label" variant="body2" color="text.secondary" gutterBottom>
              Urgency
            </Typography>
            <RadioGroup aria-labelledby="urgency-label" value={values.urgency} onChange={(e) => set({ urgency: e.target.value })}>
              {Object.entries(rd.urgencies).map(([k, u]) => (
                <FormControlLabel key={k} value={k} disabled={disabled} control={<Radio />}
                  label={<><strong>{u.label}</strong> - {u.detail}</>} />
              ))}
            </RadioGroup>
            <Typography variant="caption" color="text.secondary">
              {rd.urgency_note}
            </Typography>
          </Box>
          <Box>
            <Typography id="procedure-label" variant="body2" color="text.secondary" gutterBottom>
              Planned procedure
            </Typography>
            <RadioGroup row aria-labelledby="procedure-label" value={values.procedure_status}
              onChange={(e) => set({ procedure_status: e.target.value as FormValues["procedure_status"] })}>
              <FormControlLabel value="known" control={<Radio />} label="From the list" disabled={disabled} />
              <FormControlLabel value="none" control={<Radio />} label="None (consultation only)" disabled={disabled} />
              <FormControlLabel value="unknown" control={<Radio />} label="Not known yet" disabled={disabled} />
              <FormControlLabel value="other" control={<Radio />} label="Other" disabled={disabled} />
            </RadioGroup>
            {values.procedure_status === "known" && (
              <TextField select fullWidth label="Procedure" value={values.planned_procedure} disabled={disabled}
                onChange={(e) => set({ planned_procedure: e.target.value })}
                helperText={values.destination_department ? "Procedures for the chosen department" : "Choose the department first to narrow the list"}>
                {procedures.map(([code, p]) => (
                  <MenuItem key={code} value={code}>
                    {p.label}
                  </MenuItem>
                ))}
              </TextField>
            )}
            {values.procedure_status === "other" && (
              <TextField fullWidth label="Describe the procedure" value={values.procedure_other} disabled={disabled}
                onChange={(e) => set({ procedure_other: e.target.value })} />
            )}
            {["unknown", "other"].includes(values.procedure_status) && (
              <Alert severity="info" sx={{ mt: 1 }}>
                Medicines can only be checked against a procedure from the list. Until then the check is shown as not done; nothing is guessed.
              </Alert>
            )}
          </Box>
        </Stack>
      </Box>
    </Stack>
  );
}

/** Tests, scans or equipment the clinic does not have, sent as separate orders with the referral. */
export function DiagnosticFields({ rd, items, onChange, ownInstitution }: {
  rd: ReferenceData;
  items: DiagnosticDraft[];
  onChange: (items: DiagnosticDraft[]) => void;
  ownInstitution: string;
}) {
  const update = (i: number, patch: Partial<DiagnosticDraft>) => onChange(items.map((d, j) => (j === i ? { ...d, ...patch } : d)));
  return (
    <Stack spacing={2}>
      {items.map((d, i) => {
        const kind = KIND_FOR_CATEGORY[d.category];
        const places = Object.entries(rd.institutions).filter(([, inst]) => inst.departments.some((dep) => rd.departments[dep]?.kind === kind));
        const depts = (rd.institutions[d.destination_institution]?.departments ?? []).filter((dep) => rd.departments[dep]?.kind === kind);
        const suggestions = rd.test_suggestions.filter((t) => t.category === d.category).map((t) => t.test);
        return (
          <Paper key={i} variant="outlined" sx={{ p: 2 }}>
            <Stack spacing={1.5}>
              <Stack direction="row" justifyContent="space-between" alignItems="center">
                <Typography variant="subtitle2">Request {i + 1}</Typography>
                <IconButton aria-label={`Remove request ${i + 1}`} onClick={() => onChange(items.filter((_, j) => j !== i))}>
                  <DeleteOutline />
                </IconButton>
              </Stack>
              <Stack direction={{ xs: "column", md: "row" }} spacing={1.5}>
                <TextField select size="small" label="Type" value={d.category} sx={{ minWidth: 180 }}
                  onChange={(e) => update(i, { category: e.target.value, destination_institution: "", destination_department: "" })}>
                  {Object.entries(rd.diagnostic_categories).map(([k, label]) => (
                    <MenuItem key={k} value={k}>
                      {label}
                    </MenuItem>
                  ))}
                </TextField>
                <Autocomplete freeSolo options={suggestions} value={d.test} sx={{ flex: 1, minWidth: 220 }}
                  onInputChange={(_, v) => update(i, { test: v, body_area: rd.test_suggestions.find((t) => t.test === v)?.body_area ?? d.body_area })}
                  renderInput={(p) => <TextField {...p} size="small" label="Test or scan" required />} />
                <TextField size="small" label="Body area" value={d.body_area} onChange={(e) => update(i, { body_area: e.target.value })} />
              </Stack>
              <TextField size="small" label="Clinical question" required value={d.clinical_question}
                onChange={(e) => update(i, { clinical_question: e.target.value })}
                helperText="What the result should answer" />
              <Stack direction={{ xs: "column", md: "row" }} spacing={1.5}>
                <TextField select size="small" label="Where" value={d.destination_institution} sx={{ minWidth: 260 }}
                  onChange={(e) => {
                    const inst = e.target.value;
                    const only = (rd.institutions[inst]?.departments ?? []).filter((dep) => rd.departments[dep]?.kind === kind);
                    update(i, { destination_institution: inst, destination_department: only.length === 1 ? only[0] : "" });
                  }}>
                  {places.map(([id, inst]) => (
                    <MenuItem key={id} value={id}>
                      {inst.name}
                      {id === ownInstitution ? " (here)" : ""}
                    </MenuItem>
                  ))}
                </TextField>
                <TextField select size="small" label="Department" value={d.destination_department} disabled={!d.destination_institution}
                  onChange={(e) => update(i, { destination_department: e.target.value })} sx={{ minWidth: 240 }}>
                  {depts.map((dep) => (
                    <MenuItem key={dep} value={dep}>
                      {rd.departments[dep].name}
                    </MenuItem>
                  ))}
                </TextField>
                <TextField select size="small" label="Urgency" value={d.urgency} onChange={(e) => update(i, { urgency: e.target.value })} sx={{ minWidth: 160 }}>
                  {Object.entries(rd.urgencies).map(([k, u]) => (
                    <MenuItem key={k} value={k}>
                      {u.label}
                    </MenuItem>
                  ))}
                </TextField>
              </Stack>
            </Stack>
          </Paper>
        );
      })}
      <Button startIcon={<Add />} variant="outlined" onClick={() => onChange([...items, emptyDiagnostic()])} sx={{ alignSelf: "start" }}>
        Add a test or scan
      </Button>
    </Stack>
  );
}

export function diagnosticComplete(d: DiagnosticDraft) {
  return d.test.trim().length > 1 && d.clinical_question.trim().length > 2 && d.destination_institution && d.destination_department;
}
