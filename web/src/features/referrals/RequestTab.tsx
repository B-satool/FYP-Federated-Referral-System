import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Alert, Box, Button, Grid, Stack, Typography } from "@mui/material";
import { api } from "../../api/client";
import type { ReferralDetail } from "../../api/types";
import { ErrorAlert, fmtDate, KeyValue, Loading, OrderStatus, ReasonDialog, Section } from "../../components/common";
import { fmtCnic } from "../../components/ReferralLetter";
import { useMe, useRefData } from "../../hooks";
import { FormValues, procedurePayload, ReferralFields } from "./ReferralForm";
import { useInvalidateReferral } from "./ReferralWorkspace";
import type { Role } from "./steps";

const LOCKED = ["response_returned", "followup_pending", "closed", "declined", "cancelled"];

function toValues(r: ReferralDetail): FormValues {
  return {
    source_department: r.source_department ?? "", destination_institution: r.destination_institution ?? "",
    destination_department: r.destination_department ?? "", destination_doctor: r.destination_doctor ?? "", reason: r.reason,
    urgency: r.urgency, procedure_status: r.procedure_status, planned_procedure: r.planned_procedure ?? "",
    procedure_tags: r.procedure_tags, tags_touched: true,
  };
}

function PatientCard({ r }: { r: ReferralDetail }) {
  return (
    <Section title="Patient">
      <KeyValue
        items={[
          ["Name", r.patient.name],
          ["Date of birth", r.patient.birth_date ?? "Not recorded"],
          ["Sex", r.patient.sex === "F" ? "Female" : r.patient.sex === "M" ? "Male" : r.patient.sex ?? "Not recorded"],
          ["CNIC", fmtCnic(r.patient.cnic)],
          [`${r.source_institution_name} ID`, r.patient.local_patient_id],
        ]}
      />
    </Section>
  );
}

/** Only the requesting doctor's side can withdraw a request; staff cannot stop it. */
function Withdraw({ r, role }: { r: ReferralDetail; role: Role }) {
  const refresh = useInvalidateReferral(r.id);
  const [open, setOpen] = useState(false);
  const cancel = useMutation({
    mutationFn: (reason: string) => api.post(`/referrals/${r.id}/cancel`, { expected_version: r.row_version, reason }),
    meta: { success: "Request withdrawn." },
    onSuccess: () => {
      setOpen(false);
      refresh();
    },
  });
  if (role !== "doctor" || LOCKED.includes(r.status)) return null;
  return (
    <Section title="Withdraw this request">
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
        Withdrawing keeps the full history. If it was already sent, the receiving side is not told automatically.
      </Typography>
      <ErrorAlert error={cancel.error} />
      <Button color="error" variant="outlined" onClick={() => setOpen(true)}>
        Withdraw request
      </Button>
      <ReasonDialog open={open} title="Withdraw request" label="Reason" confirm="Withdraw request"
        onClose={() => setOpen(false)} onConfirm={(t) => cancel.mutate(t)} busy={cancel.isPending} />
    </Section>
  );
}

function TestRequestView({ r, role }: { r: ReferralDetail; role: Role }) {
  return (
    <Grid container spacing={2}>
      <Grid item xs={12} lg={8}>
        <Section title="Test request" description={r.requested_at ? `Submitted by ${r.requesting_doctor_name}, ${fmtDate(r.requested_at)}` : "Not submitted yet"}>
          <Stack spacing={1.5}>
            {r.diagnostics.map((d) => (
              <Box key={d.id}>
                <Typography variant="subtitle2">
                  {d.test}
                  {d.body_area ? ` (${d.body_area})` : ""} <OrderStatus status={d.status} />
                </Typography>
                <Typography variant="body2">
                  {d.category_label} at {d.destination_name}, {d.destination_department_name} · {d.urgency_label}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Question: {d.clinical_question}
                </Typography>
              </Box>
            ))}
            {r.reason && (
              <Typography variant="body2">
                <strong>Clinical details:</strong> {r.reason}
              </Typography>
            )}
          </Stack>
        </Section>
      </Grid>
      <Grid item xs={12} lg={4}>
        <Stack spacing={2}>
          <PatientCard r={r} />
          <Withdraw r={r} role={role} />
        </Stack>
      </Grid>
    </Grid>
  );
}

export function RequestTab({ r, role }: { r: ReferralDetail; role: Role }) {
  const { data: me } = useMe();
  const rd = useRefData();
  const refresh = useInvalidateReferral(r.id);
  const [editing, setEditing] = useState(r.status === "draft" && role === "doctor");
  const [values, setValues] = useState<FormValues>(() => toValues(r));
  const save = useMutation({
    mutationFn: (submit: boolean) =>
      api.patch(`/referrals/${r.id}`, {
        expected_version: r.row_version, source_department: values.source_department, destination_institution: values.destination_institution,
        destination_department: values.destination_department, destination_doctor: values.destination_doctor || null,
        reason: values.reason, urgency: values.urgency, ...procedurePayload(values), submit,
      }),
    meta: { success: "Request saved." },
    onSuccess: () => {
      setEditing(false);
      refresh();
    },
  });
  if (!rd.data || !me) return <Loading />;
  if (r.kind === "test") return <TestRequestView r={r} role={role} />;
  const locked = LOCKED.includes(r.status);
  const sent = !!r.submitted_package_version;

  return (
    <Grid container spacing={2}>
      <Grid item xs={12} lg={8}>
        <Section
          title="The doctor's request"
          description={r.requested_at ? `Submitted by ${r.requesting_doctor_name}, ${fmtDate(r.requested_at)}` : "Not submitted yet"}
          actions={role === "doctor" && !locked && !editing ? <Button variant="outlined" onClick={() => setEditing(true)}>Edit request</Button> : undefined}
        >
          {editing ? (
            <Stack spacing={2}>
              {sent && (
                <Alert severity="warning">
                  This referral was already sent. Saving a change means staff must check and send a new version; the sent version is kept unchanged.
                </Alert>
              )}
              <ReferralFields rd={rd.data} me={me} values={values} onChange={setValues} />
              <ErrorAlert error={save.error} />
              <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                {r.status === "draft" && (
                  <Button variant="contained" disabled={save.isPending || values.reason.trim().length < 10} onClick={() => save.mutate(true)}>
                    Submit request
                  </Button>
                )}
                <Button variant={r.status === "draft" ? "outlined" : "contained"} disabled={save.isPending} onClick={() => save.mutate(false)}>
                  Save changes
                </Button>
                <Button onClick={() => { setValues(toValues(r)); setEditing(r.status === "draft"); }}>Discard changes</Button>
              </Stack>
            </Stack>
          ) : (
            <KeyValue
              items={[
                ["Reason", <Box component="span" sx={{ whiteSpace: "pre-wrap" }}>{r.reason || "Not written yet"}</Box>],
                ["Urgency", `${r.urgency_label}${r.urgency_detail ? ` - ${r.urgency_detail}` : ""}`],
                ["Planned procedure", r.procedure_label],
                ...(r.procedure_status === "planned"
                  ? [["What it involves", r.procedure_tag_labels.length ? r.procedure_tag_labels.join(", ") : "Not recorded (procedure checks not run)"] as [string, string]]
                  : []),
                ["Referring to", `${r.destination_name}, ${r.destination_department_name}`],
                ["Doctor preferred", r.destination_doctor ?? "Any doctor in the department"],
                ["Referring from", `${r.source_institution_name}${r.source_department_name ? `, ${r.source_department_name}` : ""}`],
                ["Requested by", r.requesting_doctor_name],
              ]}
            />
          )}
        </Section>
      </Grid>
      <Grid item xs={12} lg={4}>
        <Stack spacing={2}>
          <PatientCard r={r} />
          <Withdraw r={r} role={role} />
        </Stack>
      </Grid>
    </Grid>
  );
}
