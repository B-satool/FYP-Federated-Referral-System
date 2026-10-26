import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Alert, Box, Button, Paper, Stack, TextField, Typography } from "@mui/material";
import { api } from "../../api/client";
import type { LookupCandidate, PatientLink } from "../../api/types";
import { Empty, ErrorAlert, KeyValue, Tag } from "../../components/common";
import { fmtCnic } from "../../components/ReferralLetter";

const SEX: Record<string, string> = { F: "Female", M: "Male", U: "Unknown", female: "Female", male: "Male" };
export const sexLabel = (s: string | null | undefined) => (s ? SEX[s] ?? s : "Not recorded");

function Match({ ok, label }: { ok: boolean; label: string }) {
  return (
    <Typography variant="body2" component="span" sx={{ mr: 2, fontWeight: ok ? 400 : 600 }}>
      {ok ? "✓" : "✗"} {label} {ok ? "matches" : "different"}
    </Typography>
  );
}

type LookupResult = { link: PatientLink; candidates: LookupCandidate[] };

/**
 * Confirm who an arriving (or requested) patient is at this institution: look the patient up in
 * this institution's own records, then match an existing record, register the patient as new
 * (arriving patients only) or say the patient cannot be confirmed. Each decision needs a note
 * saying how it was checked.
 */
export function ConfirmPatient({
  linkId,
  localPatientId,
  patient,
  kind = "intake",
  requester,
  autoStart = false,
  onDone,
  onCancel,
}: {
  linkId: number | null;
  localPatientId: string | null;
  patient: { name: string; birth_date: string | null; sex: string | null; cnic: string | null | undefined };
  /** intake: arriving with a referral or order; records: another institution asks for records */
  kind?: PatientLink["kind"];
  requester?: string;
  /** look the patient up straight away (e.g. inside a dialog) instead of showing "Confirm the patient" first */
  autoStart?: boolean;
  onDone: () => void;
  onCancel?: () => void;
}) {
  const qc = useQueryClient();
  const [result, setResult] = useState<LookupResult | null>(null);
  const [note, setNote] = useState("");
  const finish = () => {
    setResult(null);
    setNote("");
    qc.invalidateQueries({ queryKey: ["links-incoming"] });
    qc.invalidateQueries({ queryKey: ["work-queue"] });
    onDone();
  };
  const lookup = useMutation({
    mutationFn: () => api.post<LookupResult>(`/patient-links/${linkId}/lookup`),
    onSuccess: (r) => setResult(r),
  });
  const approve = useMutation({
    mutationFn: (body: { local_patient_id?: string; register_new?: boolean }) => api.post(`/patient-links/${linkId}/approve`, { ...body, note: note.trim() }),
    meta: { success: "Patient confirmed." },
    onSuccess: finish,
  });
  const reject = useMutation({
    mutationFn: (reason: string) => api.post(`/patient-links/${linkId}/reject`, { note: reason }),
    meta: { success: kind === "records" ? "Marked as no record here." : "Marked as not confirmed." },
    onSuccess: finish,
  });
  useEffect(() => {
    if (autoStart && linkId && !localPatientId) lookup.mutate();
  }, [autoStart, linkId]); // eslint-disable-line react-hooks/exhaustive-deps

  if (localPatientId) {
    return (
      <Stack direction="row" spacing={1} alignItems="center">
        <Tag tone="ok" label="done" />
        <Typography variant="body2">Patient confirmed: {localPatientId}</Typography>
      </Stack>
    );
  }
  if (!linkId) {
    return <Alert severity="warning">The patient is not confirmed here yet and there is no confirmation request for this patient. Ask an administrator.</Alert>;
  }

  const cands = result?.candidates ?? [];
  const noteOk = note.trim().length >= 3;
  const busy = approve.isPending || reject.isPending;
  const records = kind === "records";
  const rejectLabel = records ? "No record here" : "Cannot confirm";

  if (!result) {
    return (
      <Box>
        <ErrorAlert error={lookup.error} />
        <Button variant="contained" onClick={() => lookup.mutate()} disabled={lookup.isPending}>
          Confirm the patient
        </Button>
      </Box>
    );
  }

  return (
    <Stack spacing={2}>
      <Box>
        <Typography variant="subtitle2" gutterBottom>
          {requester ? `Details sent by ${requester}` : "Details sent with the request"}
        </Typography>
        <KeyValue
          items={[
            ["Name", patient.name],
            ["Born", patient.birth_date ?? "Not recorded"],
            ["Sex", sexLabel(patient.sex)],
            ["CNIC", fmtCnic(patient.cnic)],
          ]}
        />
      </Box>
      <Typography variant="subtitle2">Possible matches in your patient records</Typography>
      {cands.length === 0 && <Empty>No patient with this CNIC (or this name and date of birth) is registered here.</Empty>}
      {cands.map((c) => (
        <Paper key={c.local_patient_id} variant="outlined" sx={{ p: 1.5 }}>
          <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" spacing={1}>
            <Box>
              <Typography variant="subtitle2">
                {c.name} · our ID {c.local_patient_id}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Born {c.birth_date} · {sexLabel(c.sex)} · CNIC {fmtCnic(c.cnic)}
                {c.city ? ` · ${c.city}` : ""}
              </Typography>
              <Box sx={{ mt: 0.5 }}>
                <Match ok={c.compare.cnic} label="CNIC" />
                <Match ok={c.compare.name} label="name" />
                <Match ok={c.compare.birth_date} label="date of birth" />
                <Match ok={c.compare.sex} label="sex" />
              </Box>
            </Box>
            <Button
              variant="contained"
              sx={{ alignSelf: { sm: "center" }, flexShrink: 0 }}
              disabled={!noteOk || busy}
              onClick={() => approve.mutate({ local_patient_id: c.local_patient_id })}
            >
              Matches this record
            </Button>
          </Stack>
        </Paper>
      ))}
      <TextField
        label="How you checked (required)"
        placeholder="e.g. CNIC and date of birth checked with the patient's card"
        value={note}
        onChange={(e) => setNote(e.target.value)}
        helperText={noteOk ? " " : "At least 3 characters"}
        fullWidth
      />
      <ErrorAlert error={approve.error || reject.error} />
      <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
        {!records && (
          <Button variant="outlined" disabled={!noteOk || busy} onClick={() => approve.mutate({ register_new: true })}>
            Register as a new patient
          </Button>
        )}
        <Button color="error" disabled={!noteOk || busy} onClick={() => reject.mutate(note.trim())}>
          {rejectLabel}
        </Button>
        <Button onClick={() => (onCancel ? onCancel() : setResult(null))} disabled={busy}>
          Close
        </Button>
      </Stack>
      <Typography variant="caption" color="text.secondary">
        {records
          ? `"${rejectLabel}" tells the requesting institution, with your note, that this patient has no record here.`
          : `"${rejectLabel}" sends your note back; use it when the details do not fit any patient and you cannot register them.`}
      </Typography>
      {records && <Alert severity="info">Matching a record lets {requester ?? "the requesting institution"} see this patient's referral-relevant records held here.</Alert>}
    </Stack>
  );
}
