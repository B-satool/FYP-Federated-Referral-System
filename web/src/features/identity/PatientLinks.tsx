import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, Paper, Stack, Tab, Tabs, Typography } from "@mui/material";
import { api } from "../../api/client";
import type { PatientLink } from "../../api/types";
import { Empty, ErrorAlert, fmtDate, Loading, PageHeader, ReasonDialog, Tag } from "../../components/common";
import { fmtCnic } from "../../components/ReferralLetter";
import { useMe } from "../../hooks";
import { ConfirmPatient } from "./ConfirmPatient";

/** Kept for existing importers; the shared formatter lives with the referral letter. */
export { fmtCnic };

const SEX: Record<string, string> = { F: "Female", M: "Male", U: "Unknown" };

const STATUS: Record<PatientLink["status"], { tone: "wait" | "ok" | "bad" | "off"; label: string }> = {
  requested: { tone: "wait", label: "waiting for them to check" },
  verified: { tone: "ok", label: "confirmed" },
  rejected: { tone: "bad", label: "not confirmed" },
  invalidated: { tone: "off", label: "invalidated" },
};

const KIND: Record<PatientLink["kind"], { label: string; help: string }> = {
  records: { label: "Records request", help: "They ask for this patient's records: match a record here, or say there is no record here." },
  intake: { label: "Arriving patient", help: "Sent with a referral or test order: match a record here, or register the patient as new." },
};

function CheckDialog({ link, onClose }: { link: PatientLink; onClose: () => void }) {
  const kind = KIND[link.kind] ?? KIND.records;
  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="md">
      <DialogTitle>
        Check: {link.patient_name} <Tag tone="info" label={kind.label} />
      </DialogTitle>
      <DialogContent dividers>
        <Stack spacing={2}>
          <Typography variant="body2">
            {link.requester_name}: {link.purpose}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {kind.help}
          </Typography>
          <ConfirmPatient
            linkId={link.id}
            localPatientId={null}
            kind={link.kind}
            requester={link.requester_name}
            patient={{ name: link.patient_name, birth_date: link.patient_birth_date, sex: link.patient_sex, cnic: link.patient_cnic }}
            autoStart
            onDone={onClose}
            onCancel={onClose}
          />
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
}

function Incoming() {
  const q = useQuery({ queryKey: ["links-incoming"], queryFn: () => api.get<PatientLink[]>("/patient-links/incoming?status=requested") });
  const [checking, setChecking] = useState<PatientLink | null>(null);
  if (q.isLoading) return <Loading />;
  return (
    <Stack spacing={1.5}>
      <ErrorAlert error={q.error} />
      {q.data?.length === 0 && <Empty>No requests to check.</Empty>}
      {q.data?.map((l) => (
        <Paper key={l.id} sx={{ p: 2 }}>
          <Stack direction={{ xs: "column", md: "row" }} justifyContent="space-between" spacing={1.5}>
            <Box>
              <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                <Typography variant="subtitle1">
                  {l.patient_name} <Typography component="span" color="text.secondary">from {l.requester_name}</Typography>
                </Typography>
                <Tag tone={l.kind === "intake" ? "info" : "neutral"} label={(KIND[l.kind] ?? KIND.records).label} />
              </Stack>
              <Typography variant="body2" color="text.secondary">
                Born {l.patient_birth_date ?? "not recorded"} · {SEX[l.patient_sex ?? ""] ?? "sex not recorded"} · CNIC {fmtCnic(l.patient_cnic)}
              </Typography>
              <Typography variant="body2">{l.purpose}</Typography>
              <Typography variant="caption" color="text.secondary">
                Requested by {l.requested_by}, {fmtDate(l.requested_at)}
              </Typography>
            </Box>
            <Button variant="contained" sx={{ alignSelf: { md: "center" } }} onClick={() => setChecking(l)}>
              Check
            </Button>
          </Stack>
        </Paper>
      ))}
      {checking && <CheckDialog link={checking} onClose={() => setChecking(null)} />}
    </Stack>
  );
}

function Outgoing() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["links-outgoing"], queryFn: () => api.get<PatientLink[]>("/patient-links/outgoing?status=all") });
  const [target, setTarget] = useState<PatientLink | null>(null);
  const invalidate = useMutation({
    mutationFn: (note: string) => api.post(`/patient-links/${target!.id}/invalidate`, { note }),
    meta: { success: "Link invalidated. Its history is kept." },
    onSuccess: () => {
      setTarget(null);
      qc.invalidateQueries({ queryKey: ["links-outgoing"] });
    },
  });
  if (q.isLoading) return <Loading />;
  return (
    <Stack spacing={1.5}>
      <ErrorAlert error={q.error || invalidate.error} />
      {q.data?.length === 0 && <Empty>You have not asked another institution to confirm a patient yet.</Empty>}
      {q.data?.map((l) => (
        <Paper key={l.id} sx={{ p: 2 }}>
          <Stack direction={{ xs: "column", md: "row" }} justifyContent="space-between" spacing={1.5}>
            <Box>
              <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                <Typography variant="subtitle1">
                  {l.patient_name} <Typography component="span" color="text.secondary">at {l.target_name}</Typography>
                </Typography>
                <Tag tone={STATUS[l.status].tone} label={STATUS[l.status].label} />
              </Stack>
              <Typography variant="body2" color="text.secondary">
                Our ID {l.requester_local_id}
                {l.status === "verified" && l.target_local_id ? ` · their ID ${l.target_local_id}${l.registered_new ? " (registered as new)" : ""}` : ""}
              </Typography>
              <Typography variant="body2">{l.purpose}</Typography>
              {l.decided_by && (
                <Typography variant="caption" display="block" color="text.secondary">
                  {l.status === "rejected" ? "Not confirmed" : "Checked"} by {l.decided_by}, {fmtDate(l.decided_at)}
                  {l.decision_note ? `: ${l.decision_note}` : ""}
                </Typography>
              )}
              {l.status === "invalidated" && (
                <Typography variant="caption" display="block" color="text.secondary">
                  Invalidated by {l.invalidated_by}, {fmtDate(l.invalidated_at)}: {l.invalidation_reason}
                </Typography>
              )}
            </Box>
            {l.status === "verified" && (
              <Button color="error" variant="outlined" sx={{ alignSelf: { md: "center" } }} onClick={() => setTarget(l)}>
                Invalidate
              </Button>
            )}
          </Stack>
        </Paper>
      ))}
      {target && (
        <ReasonDialog
          open
          title={`Invalidate the link with ${target.target_name}`}
          label="Reason"
          confirm="Invalidate"
          onClose={() => setTarget(null)}
          onConfirm={(r) => invalidate.mutate(r)}
          busy={invalidate.isPending}
        >
          <Alert severity="warning" sx={{ mb: 1 }}>
            Records from this link stop being used. The history is kept, and any referral that used them is flagged for review.
          </Alert>
        </ReasonDialog>
      )}
    </Stack>
  );
}

export function PatientLinks() {
  const { data: me } = useMe();
  const [tab, setTab] = useState<"incoming" | "outgoing">("incoming");
  return (
    <>
      <PageHeader
        title="Patient link requests"
        subtitle={`Another institution asks ${me?.institution_name ?? "you"} to confirm which of your patients a person is. Records are shared only after your staff confirm.`}
      />
      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 2 }}>
        <Tab value="incoming" label="Requests to check" />
        <Tab value="outgoing" label="Our requests" />
      </Tabs>
      {tab === "incoming" ? <Incoming /> : <Outgoing />}
    </>
  );
}
