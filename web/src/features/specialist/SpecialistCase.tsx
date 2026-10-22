import { useEffect, useState } from "react";
import { Link as RouterLink, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  Grid,
  MenuItem,
  Paper,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import ArrowBack from "@mui/icons-material/ArrowBack";
import { api } from "../../api/client";
import type { BriefSection } from "../../api/types";
import { ErrorAlert, fmtDate, KeyValue, Loading, PageHeader, ReasonDialog, Tag } from "../../components/common";
import { ValuesTable } from "../../components/EvidenceRef";
import { FlagCard, FlagLike } from "../../components/FlagCard";
import type { CaseSummary } from "./SpecialistInbox";

type Snapshot = {
  evidence_id: number;
  category: string;
  display: string;
  original: Record<string, unknown>;
  origin: string;
  source_institution: string;
  source_record_type: string | null;
  source_record_id: string | null;
  source_record_version: string | null;
  clinical_time: string | null;
  verification_status: string;
  document_ref: { document_id: number; page: number; source_text: string } | null;
};
type Envelope = {
  referral_id: string;
  package_version: number;
  sender_institution: string;
  priority: string;
  reason: string;
  planned_procedure: string | null;
  procedure_known: boolean;
  patient: { name: string; birth_date: string; sex: string };
  referring_clinician: { name: string; institution: string };
  brief_sections: BriefSection[];
  medication_flags: (FlagLike & { flag_id: number; clinic_review: { reviewer: string; reviewed_at: string } | null })[];
  medication_evaluation: { status: string; outcome: string | null; summary: string | null; rule_versions: Record<string, number>; mapping_version: string | null };
  evidence: Snapshot[];
  limitations: string[];
  checklist: { id: string; title: string; state: string }[];
  approved_by: string;
  approved_at: string;
  content_hash: string;
  contract_note: string;
};
type CaseDetail = {
  case: CaseSummary;
  packages: { version: number; received_at: string; content_hash: string; envelope: Envelope }[];
  flag_reviews: { id: number; package_version: number; flag_id: number; flag_version: number; action: string; reviewer: string; created_at: string; clarification_id: number | null }[];
  clarifications: { id: number; package_version: number; flag_id: number | null; question: string; status: string; created_by: string; created_at: string; answer: string | null; answered_by: string | null; answered_at: string | null }[];
  responses: { id: number; content: Record<string, string>; status: string; drafted_by: string; row_version: number; approved_by: string | null; approved_at: string | null; returned_at: string | null }[];
  local_history: { id: string; seen_at: string; clinician: string; summary: string; diagnosis: string | null }[];
  outbox: { id: number; event_type: string; status: string; attempts: number; last_error: string | null; created_at: string; sent_at: string | null }[];
};

function SnapshotRef({ ev }: { ev?: Snapshot }) {
  const [open, setOpen] = useState(false);
  if (!ev) return null;
  return (
    <>
      <Chip size="small" variant="outlined" label={`E${ev.evidence_id}`} onClick={() => setOpen(true)} clickable sx={{ mr: 0.5, height: 20, fontSize: 11 }} />
      <Dialog open={open} onClose={() => setOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>Supporting evidence E{ev.evidence_id}</DialogTitle>
        <DialogContent dividers>
          <Typography variant="subtitle1" gutterBottom>
            {ev.display}
          </Typography>
          <KeyValue
            items={[
              ["Source", ev.origin === "source" ? `${ev.source_institution} ${ev.source_record_type}/${ev.source_record_id} v${ev.source_record_version}` : ev.origin === "document" ? `uploaded document page ${ev.document_ref?.page}` : "clinician entry"],
              ["Clinical date", fmtDate(ev.clinical_time, false)],
              ["Verification", ev.verification_status.replace("_", " ")],
              ["Source text", ev.document_ref?.source_text ?? "Not recorded"],
            ]}
          />
          <Divider sx={{ my: 1 }} />
          <ValuesTable values={ev.original} />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>Close</Button>
        </DialogActions>
      </Dialog>
    </>
  );
}

export function SpecialistCase() {
  const id = Number(useParams().id);
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["spec-case", id], queryFn: () => api.get<CaseDetail>(`/specialist/cases/${id}`, "specialist"), refetchInterval: 10000 });
  const [version, setVersion] = useState<number | null>(null);
  const [decline, setDecline] = useState(false);
  const [question, setQuestion] = useState<{ flag?: { flag_id: number; version: number } } | null>(null);
  const [resp, setResp] = useState({ findings: "", assessment: "", recommendations: "", follow_up_advice: "" });
  const refresh = () => qc.invalidateQueries({ queryKey: ["spec-case", id] });
  const act = useMutation({
    mutationFn: ({ path, body, method = "post" }: { path: string; body?: unknown; method?: "post" | "put" }) =>
      method === "put" ? api.put(path, body, "specialist") : api.post(path, body, "specialist"),
    onSuccess: () => {
      setDecline(false);
      setQuestion(null);
      refresh();
    },
  });
  const current = q.data?.responses.at(-1);
  useEffect(() => {
    if (current) setResp({ findings: current.content.findings ?? "", assessment: current.content.assessment ?? "", recommendations: current.content.recommendations ?? "", follow_up_advice: current.content.follow_up_advice ?? "" });
  }, [current?.id, current?.row_version]); // eslint-disable-line react-hooks/exhaustive-deps
  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorAlert error={q.error} />;
  const d = q.data!;
  const c = d.case;
  const pkg = d.packages.find((p) => p.version === (version ?? c.latest_version)) ?? d.packages[0];
  const env = pkg.envelope;
  const isLatest = pkg.version === c.latest_version;
  const evidenceById = Object.fromEntries(env.evidence.map((e) => [e.evidence_id, e]));
  const reviewsFor = (flagId: number, flagVersion: number) => d.flag_reviews.filter((r) => r.flag_id === flagId && r.flag_version === flagVersion);
  const acked = !!c.acknowledged_at;
  const responseLocked = current && current.status !== "draft";

  return (
    <>
      <PageHeader
        title={`${c.central_referral_id} · ${c.patient_name}`}
        subtitle={`From ${env.referring_clinician.name} (${env.referring_clinician.institution}) · priority ${c.priority} (clinician-selected) · received ${fmtDate(c.received_at)}`}
        actions={
          <Button component={RouterLink} to="/specialist" startIcon={<ArrowBack />}>
            Inbox
          </Button>
        }
      />
      <ErrorAlert error={act.error} />
      <Paper sx={{ p: 2, mb: 2 }}>
        <Stack direction={{ xs: "column", md: "row" }} spacing={2} justifyContent="space-between" alignItems={{ md: "center" }}>
          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
            <Tag tone="ok" label={`delivered (v${c.latest_version})`} />
            <Tag tone={acked ? "ok" : "warn"} label={acked ? `acknowledged by ${c.acknowledged_by}` : "not acknowledged"} />
            <Tag tone={c.decision === "accepted" ? "ok" : c.decision === "declined" ? "off" : "wait"} label={c.decision ? `${c.decision} by ${c.decision_by}` : "no decision"} />
          </Stack>
          <Stack direction="row" spacing={1}>
            {!acked && (
              <Button variant="contained" onClick={() => act.mutate({ path: `/specialist/cases/${id}/acknowledge` })}>
                Acknowledge receipt
              </Button>
            )}
            {acked && !c.decision && (
              <>
                <Button variant="contained" color="success" onClick={() => act.mutate({ path: `/specialist/cases/${id}/decision`, body: { decision: "accept" } })}>
                  Accept referral
                </Button>
                <Button color="error" variant="outlined" onClick={() => setDecline(true)}>
                  Decline
                </Button>
              </>
            )}
            {acked && (
              <Button variant="outlined" onClick={() => setQuestion({})}>
                Request clarification
              </Button>
            )}
          </Stack>
        </Stack>
        {c.decline_reason && <Alert severity="info" sx={{ mt: 1 }}>Declined: {c.decline_reason}</Alert>}
      </Paper>

      <Grid container spacing={2}>
        <Grid item xs={12} lg={8}>
          <Paper sx={{ p: 2 }}>
            <Stack direction="row" justifyContent="space-between" alignItems="center">
              <Typography variant="h6">Approved referral package</Typography>
              <TextField select size="small" label="Version" value={pkg.version} onChange={(e) => setVersion(Number(e.target.value))}>
                {d.packages.map((p) => (
                  <MenuItem key={p.version} value={p.version}>
                    v{p.version} {p.version === c.latest_version ? "(latest)" : "(superseded)"}
                  </MenuItem>
                ))}
              </TextField>
            </Stack>
            {!isLatest && <Alert severity="warning" sx={{ my: 1 }}>You are viewing a superseded version. Flag reviews apply to the latest version.</Alert>}
            <Typography variant="caption" color="text.secondary" display="block" gutterBottom>
              Approved by {env.approved_by}, {fmtDate(env.approved_at)} · sha256 {env.content_hash.slice(0, 16)}… · {env.contract_note}
            </Typography>
            <KeyValue
              items={[
                ["Reason", env.reason],
                ["Planned procedure", env.procedure_known ? env.planned_procedure?.replace(/_/g, " ") : "unknown (recorded explicitly)"],
                ["Patient", `${env.patient.name}, born ${env.patient.birth_date}, ${env.patient.sex}`],
              ]}
            />
            <Divider sx={{ my: 2 }} />
            <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
              Medication flags
            </Typography>
            {env.medication_evaluation.summary && (
              <Alert severity={env.medication_evaluation.status === "failed" ? "error" : "info"} sx={{ my: 1 }}>
                {env.medication_evaluation.summary}
                <Typography variant="caption" display="block">
                  rules {Object.entries(env.medication_evaluation.rule_versions).map(([k, v]) => `${k} v${v}`).join(", ") || "none"} · mapping {env.medication_evaluation.mapping_version}
                </Typography>
              </Alert>
            )}
            <Stack spacing={1.5}>
              {env.medication_flags.map((f) => {
                const mine = reviewsFor(f.flag_id, f.version);
                const reviewed = mine.some((r) => r.action === "reviewed");
                return (
                  <FlagCard
                    key={`${f.flag_id}-${f.version}`}
                    flag={f}
                    evidence={f.evidence_ids.map((eid) => <SnapshotRef key={eid} ev={evidenceById[eid]} />)}
                    reviews={[
                      ...(f.clinic_review ? [{ side: "referring", action: "reviewed", reviewer: f.clinic_review.reviewer, flag_version: f.version, created_at: f.clinic_review.reviewed_at }] : []),
                      ...mine.map((r) => ({ side: "specialist", action: r.action, reviewer: r.reviewer, flag_version: r.flag_version, created_at: r.created_at, package_version: r.package_version })),
                    ]}
                    actions={
                      isLatest && acked ? (
                        <>
                          <Button size="small" variant={reviewed ? "outlined" : "contained"} disabled={reviewed} onClick={() => act.mutate({ path: `/specialist/cases/${id}/flags/${f.flag_id}/review`, body: { flag_version: f.version, action: "reviewed" } })}>
                            {reviewed ? "Reviewed" : "Reviewed"}
                          </Button>
                          <Button size="small" onClick={() => setQuestion({ flag: { flag_id: f.flag_id, version: f.version } })}>
                            Request clarification
                          </Button>
                        </>
                      ) : undefined
                    }
                  />
                );
              })}
              {env.medication_flags.length === 0 && <Typography color="text.secondary">No flags or prompts in this version.</Typography>}
            </Stack>
            <Divider sx={{ my: 2 }} />
            {env.brief_sections.map((s) => (
              <Box key={s.key} sx={{ mb: 2 }}>
                <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                  {s.title}
                </Typography>
                {s.statements.length === 0 && <Typography variant="body2" color="text.secondary">None</Typography>}
                {s.statements.map((st) => (
                  <Typography key={st.id} variant="body2" sx={{ mt: 0.5 }}>
                    {st.text} {st.evidence_ids.map((eid) => <SnapshotRef key={eid} ev={evidenceById[eid]} />)}
                    {st.verification !== "verified" && st.verification !== "none" && <Tag tone="warn" label={st.verification} />}
                  </Typography>
                ))}
              </Box>
            ))}
            {env.limitations.length > 0 && (
              <Alert severity="warning">
                <strong>Limitations</strong>
                <ul style={{ margin: 0, paddingLeft: 18 }}>
                  {env.limitations.map((l, i) => (
                    <li key={i}>{l}</li>
                  ))}
                </ul>
              </Alert>
            )}
          </Paper>
        </Grid>
        <Grid item xs={12} lg={4}>
          <Stack spacing={2}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="h6" gutterBottom>
                Consultation response
              </Typography>
              {c.decision !== "accepted" ? (
                <Typography variant="body2" color="text.secondary">
                  Accept the referral to draft a response.
                </Typography>
              ) : (
                <Stack spacing={1.5}>
                  {(["findings", "assessment", "recommendations", "follow_up_advice"] as const).map((k) => (
                    <TextField key={k} label={k.replace(/_/g, " ")} multiline minRows={2} value={resp[k]} disabled={!!responseLocked} onChange={(e) => setResp({ ...resp, [k]: e.target.value })} />
                  ))}
                  {current && (
                    <Typography variant="caption">
                      Status: {current.status}
                      {current.approved_by ? ` · approved by ${current.approved_by} ${fmtDate(current.approved_at)}` : ""}
                      {current.returned_at ? ` · returned ${fmtDate(current.returned_at)}` : ""}
                    </Typography>
                  )}
                  <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                    {!responseLocked && (
                      <Button variant="outlined" onClick={() => act.mutate({ method: "put", path: `/specialist/cases/${id}/response`, body: { ...resp, expected_row_version: current?.row_version ?? null } })}>
                        Save draft
                      </Button>
                    )}
                    {current?.status === "draft" && (
                      <Button variant="contained" onClick={() => act.mutate({ path: `/specialist/cases/${id}/response/approve`, body: { expected_row_version: current.row_version } })}>
                        Approve response
                      </Button>
                    )}
                    {current?.status === "approved" && (
                      <Button variant="contained" color="success" onClick={() => act.mutate({ path: `/specialist/cases/${id}/response/return` })}>
                        Return to referring clinic
                      </Button>
                    )}
                  </Stack>
                  <Typography variant="caption" color="text.secondary">
                    A response is returned only after specialist approval.
                  </Typography>
                </Stack>
              )}
            </Paper>
            <Paper sx={{ p: 2 }}>
              <Typography variant="h6" gutterBottom>
                Clarifications
              </Typography>
              {d.clarifications.length === 0 && <Typography variant="body2" color="text.secondary">None.</Typography>}
              {d.clarifications.map((cl) => (
                <Box key={cl.id} sx={{ mb: 1.5 }}>
                  <Stack direction="row" justifyContent="space-between">
                    <Typography variant="body2">
                      <strong>Q:</strong> {cl.question}
                    </Typography>
                    <Tag tone={cl.status === "open" ? "warn" : "ok"} label={cl.status} />
                  </Stack>
                  {cl.answer && (
                    <Typography variant="body2">
                      <strong>A ({cl.answered_by}):</strong> {cl.answer}
                    </Typography>
                  )}
                </Box>
              ))}
            </Paper>
            {d.local_history.length > 0 && (
              <Paper sx={{ p: 2 }}>
                <Typography variant="h6" gutterBottom>
                  Our records ({c.specialist_patient_id})
                </Typography>
                {d.local_history.map((h) => (
                  <Typography key={h.id} variant="body2">
                    {fmtDate(h.seen_at, false)}: {h.summary} {h.diagnosis ? `(${h.diagnosis})` : ""}
                  </Typography>
                ))}
              </Paper>
            )}
            <Paper sx={{ p: 2 }}>
              <Typography variant="h6" gutterBottom>
                Messages to the clinic
              </Typography>
              {d.outbox.map((o) => (
                <Stack key={o.id} direction="row" spacing={1} alignItems="center" sx={{ mb: 0.5 }}>
                  <Tag tone={o.status === "sent" ? "ok" : o.status === "failed" ? "bad" : "wait"} label={o.status} />
                  <Typography variant="caption">
                    {o.event_type.replace(/_/g, " ")} · {o.attempts} attempt(s){o.last_error ? ` · ${o.last_error.slice(0, 60)}` : ""}
                  </Typography>
                  {o.status === "failed" && (
                    <Button size="small" onClick={() => act.mutate({ path: `/specialist/outbox/${o.id}/retry` })}>
                      Retry
                    </Button>
                  )}
                </Stack>
              ))}
            </Paper>
          </Stack>
        </Grid>
      </Grid>
      <ReasonDialog open={decline} title="Decline referral" label="Reason" confirm="Decline" onClose={() => setDecline(false)} onConfirm={(reason) => act.mutate({ path: `/specialist/cases/${id}/decision`, body: { decision: "decline", reason } })} />
      <ReasonDialog
        open={!!question}
        title={question?.flag ? "Request clarification about this flag" : "Request clarification from the referring clinic"}
        label="Question"
        confirm="Send"
        minLength={5}
        onClose={() => setQuestion(null)}
        onConfirm={(text) =>
          question?.flag
            ? act.mutate({ path: `/specialist/cases/${id}/flags/${question.flag.flag_id}/review`, body: { flag_version: question.flag.version, action: "request_clarification", question: text } })
            : act.mutate({ path: `/specialist/cases/${id}/clarifications`, body: { question: text } })
        }
      />
    </>
  );
}
