import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Paper,
  Stack,
  Tab,
  Tabs,
  TextField,
  Typography,
} from "@mui/material";
import { api } from "../../api/client";
import type { LookupCandidate, PatientLink } from "../../api/types";
import { Empty, ErrorAlert, fmtDate, KeyValue, Loading, PageHeader, ReasonDialog, Tag } from "../../components/common";
import { useMe } from "../../hooks";

/** 4210112345671 -> 42101-1234567-1 (display only). */
export function fmtCnic(cnic: string | null | undefined): string {
  if (!cnic) return "Not recorded";
  const d = cnic.replace(/\D/g, "");
  return d.length === 13 ? `${d.slice(0, 5)}-${d.slice(5, 12)}-${d.slice(12)}` : cnic;
}

const SEX: Record<string, string> = { F: "Female", M: "Male", U: "Unknown" };

const STATUS: Record<PatientLink["status"], { tone: "wait" | "ok" | "bad" | "off"; label: string }> = {
  requested: { tone: "wait", label: "waiting for them to check" },
  verified: { tone: "ok", label: "confirmed" },
  rejected: { tone: "bad", label: "not confirmed" },
  invalidated: { tone: "off", label: "invalidated" },
};

function Match({ ok, label }: { ok: boolean; label: string }) {
  return (
    <Typography variant="body2" component="span" sx={{ mr: 2, fontWeight: ok ? 400 : 600 }}>
      {ok ? "✓" : "✗"} {label} {ok ? "matches" : "different"}
    </Typography>
  );
}

function CheckDialog({ link, onClose }: { link: PatientLink; onClose: () => void }) {
  const qc = useQueryClient();
  const [note, setNote] = useState("");
  const [rejecting, setRejecting] = useState(false);
  const lookup = useQuery({
    queryKey: ["link-lookup", link.id],
    queryFn: () => api.post<{ link: PatientLink; candidates: LookupCandidate[] }>(`/patient-links/${link.id}/lookup`),
  });
  const done = () => {
    qc.invalidateQueries({ queryKey: ["links-incoming"] });
    qc.invalidateQueries({ queryKey: ["work-queue"] });
    onClose();
  };
  const approve = useMutation({
    mutationFn: (body: { local_patient_id?: string; register_new?: boolean }) => api.post(`/patient-links/${link.id}/approve`, { ...body, note }),
    meta: { success: "Link confirmed. The requesting institution can now see this patient's referral records." },
    onSuccess: done,
  });
  const reject = useMutation({
    mutationFn: (reason: string) => api.post(`/patient-links/${link.id}/reject`, { note: reason }),
    meta: { success: "Request marked as not confirmed." },
    onSuccess: done,
  });
  const cands = lookup.data?.candidates ?? [];
  const cnicMatch = cands.some((c) => c.compare.cnic);
  const noteOk = note.trim().length >= 3;
  const busy = approve.isPending || reject.isPending;

  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="md">
      <DialogTitle>Check: {link.patient_name}</DialogTitle>
      <DialogContent dividers>
        <Stack spacing={2}>
          <Box>
            <Typography variant="subtitle2" gutterBottom>
              {link.requester_name} asks which of your patients this is
            </Typography>
            <KeyValue
              items={[
                ["Name", link.patient_name],
                ["Date of birth", link.patient_birth_date ?? "Not recorded"],
                ["Sex", SEX[link.patient_sex ?? ""] ?? link.patient_sex ?? "Not recorded"],
                ["CNIC", fmtCnic(link.patient_cnic)],
                ["Purpose", link.purpose],
              ]}
            />
          </Box>
          <Typography variant="subtitle2">Possible matches in your patient records</Typography>
          {lookup.isLoading && <Loading label="Searching your records…" />}
          <ErrorAlert error={lookup.error} />
          {lookup.data && cands.length === 0 && <Empty>No patient with this CNIC (or this name and date of birth) is registered here.</Empty>}
          {cands.map((c) => (
            <Paper key={c.local_patient_id} variant="outlined" sx={{ p: 1.5 }}>
              <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" spacing={1}>
                <Box>
                  <Typography variant="subtitle2">
                    {c.name} · our ID {c.local_patient_id}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Born {c.birth_date} · {SEX[c.sex] ?? c.sex} · CNIC {fmtCnic(c.cnic)}
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
                  This is the same person
                </Button>
              </Stack>
            </Paper>
          ))}
          <TextField
            label="How you checked (required)"
            placeholder="e.g. CNIC and date of birth checked"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            helperText={noteOk ? " " : "At least 3 characters"}
            fullWidth
          />
          <Alert severity="info">Confirming lets {link.requester_name} see this patient's referral-relevant records held here.</Alert>
          <ErrorAlert error={approve.error || reject.error} />
        </Stack>
      </DialogContent>
      <DialogActions sx={{ flexWrap: "wrap", gap: 1 }}>
        <Button onClick={onClose}>Close</Button>
        <Button color="error" onClick={() => setRejecting(true)} disabled={busy}>
          Cannot confirm
        </Button>
        {lookup.data && !cnicMatch && (
          <Button variant="outlined" disabled={!noteOk || busy} onClick={() => approve.mutate({ register_new: true })}>
            Not registered here: register as a new patient
          </Button>
        )}
      </DialogActions>
      {rejecting && (
        <ReasonDialog
          open
          title="Cannot confirm this patient"
          label="Reason (sent to the requesting institution)"
          confirm="Send"
          onClose={() => setRejecting(false)}
          onConfirm={(r) => reject.mutate(r)}
          busy={reject.isPending}
        />
      )}
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
              <Typography variant="subtitle1">
                {l.patient_name} <Typography component="span" color="text.secondary">from {l.requester_name}</Typography>
              </Typography>
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
