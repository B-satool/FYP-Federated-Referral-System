import { useEffect, useState } from "react";
import { Link as RouterLink, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  AlertTitle,
  Box,
  Button,
  Link,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import { api } from "../../api/client";
import type { Case, CaseDetail, ConsultationResponse } from "../../api/types";
import { Empty, ErrorAlert, fmtDate, KeyValue, Loading, OrderStatus, PageHeader, ReasonDialog, Section, Tag, UrgencyTag } from "../../components/common";
import { FlagCard } from "../../components/FlagCard";
import { ownService, useMe, useRefData } from "../../hooks";

const CASE_STATUS: Record<string, string> = {
  received: "new",
  acknowledged: "acknowledged",
  accepted: "accepted",
  declined: "declined",
  responded: "response sent",
};

function CaseStatusTag({ status }: { status: string }) {
  const tone = status === "received" ? "warn" : status === "declined" ? "off" : status === "responded" ? "ok" : "info";
  return <Tag tone={tone} label={CASE_STATUS[status] ?? status} />;
}

export function IncomingList() {
  const { data: me } = useMe();
  const ref = useRefData();
  const service = ownService(me);
  const q = useQuery({
    queryKey: ["cases", service],
    queryFn: () => api.get<Case[]>("/cases", service),
    enabled: !!me,
    refetchInterval: 15000,
  });
  const dept = me?.department_name ?? me?.department ?? "your department";
  const instName = (id: string) => ref.data?.institutions[id]?.name ?? id;
  return (
    <>
      <PageHeader title="Incoming referrals" subtitle={`Referrals sent to ${dept} at ${me?.institution_name ?? "your hospital"}, and referrals that name you.`} />
      {q.isLoading && <Loading />}
      <ErrorAlert error={q.error} />
      {q.data && q.data.length === 0 && <Empty>No referrals have been received for your department yet.</Empty>}
      {!!q.data?.length && (
        <Paper>
          <Table size="small" aria-label="Incoming referrals">
            <TableHead>
              <TableRow>
                <TableCell>Referral</TableCell>
                <TableCell>Patient</TableCell>
                <TableCell>From</TableCell>
                <TableCell>Urgency</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Received</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {q.data.map((c) => (
                <TableRow key={c.id} hover>
                  <TableCell>
                    <Link component={RouterLink} to={`/incoming/${c.id}`}>
                      {c.central_referral_id}
                    </Link>
                  </TableCell>
                  <TableCell>
                    {c.patient_name}
                    {c.patient_birth_date && (
                      <Typography variant="caption" display="block" color="text.secondary">
                        born {c.patient_birth_date}
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell>{c.sender_name || instName(c.sender_institution)}</TableCell>
                  <TableCell>
                    <UrgencyTag urgency={c.urgency} label={ref.data?.urgencies[c.urgency]?.label} />
                  </TableCell>
                  <TableCell>
                    <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                      <CaseStatusTag status={c.status} />
                      {c.open_info_requests > 0 && <Tag tone="wait" label={`${c.open_info_requests} question(s) open`} />}
                    </Stack>
                  </TableCell>
                  <TableCell>{fmtDate(c.received_at)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Paper>
      )}
    </>
  );
}

type ResponseForm = { assessment: string; plan: string; instructions_for_clinic: string; appointment: string };
const EMPTY_FORM: ResponseForm = { assessment: "", plan: "", instructions_for_clinic: "", appointment: "" };

function ResponseView({ content }: { content: ConsultationResponse["content"] }) {
  return (
    <KeyValue
      items={[
        ["Assessment", content.assessment || "Not recorded"],
        ["Plan", content.plan || "Not recorded"],
        ["Instructions for the referring clinic", content.instructions_for_clinic || "Not recorded"],
        ["Appointment", content.appointment || "Not recorded"],
      ]}
    />
  );
}

export function IncomingCase() {
  const id = Number(useParams().id);
  const { data: me } = useMe();
  const ref = useRefData();
  const qc = useQueryClient();
  const service = ownService(me);
  const q = useQuery({
    queryKey: ["case", service, id],
    queryFn: () => api.get<CaseDetail>(`/cases/${id}`, service),
    enabled: !!me,
    refetchInterval: 15000,
  });
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["case", service, id] });
    qc.invalidateQueries({ queryKey: ["cases", service] });
  };
  const [declineOpen, setDeclineOpen] = useState(false);
  const [askOpen, setAskOpen] = useState(false);
  const [form, setForm] = useState<ResponseForm>(EMPTY_FORM);

  const draft = q.data?.responses.length ? q.data.responses[q.data.responses.length - 1] : null;
  useEffect(() => {
    if (draft) setForm({ ...EMPTY_FORM, ...(draft.content as Partial<ResponseForm>) } as ResponseForm);
  }, [draft?.id, draft?.row_version]); // eslint-disable-line react-hooks/exhaustive-deps

  const acknowledge = useMutation({
    mutationFn: () => api.post(`/cases/${id}/acknowledge`, {}, service),
    meta: { success: "Referral acknowledged." },
    onSuccess: refresh,
  });
  const decide = useMutation({
    mutationFn: (body: { decision: "accept" | "decline"; reason?: string }) => api.post(`/cases/${id}/decision`, body, service),
    meta: { success: "Decision recorded and sent to the referring clinic." },
    onSuccess: () => {
      setDeclineOpen(false);
      refresh();
    },
  });
  const ask = useMutation({
    mutationFn: (question: string) => api.post(`/cases/${id}/info-requests`, { question }, service),
    meta: { success: "Question sent to the referring clinic." },
    onSuccess: () => {
      setAskOpen(false);
      refresh();
    },
  });
  const save = useMutation({
    mutationFn: () => api.put<{ row_version: number }>(`/cases/${id}/response`, { ...form, expected_row_version: draft?.row_version ?? null }, service),
    meta: { success: "Draft saved." },
    onSuccess: refresh,
  });
  const send = useMutation({
    mutationFn: async () => {
      const saved = await api.put<{ row_version: number }>(`/cases/${id}/response`, { ...form, expected_row_version: draft?.row_version ?? null }, service);
      return api.post(`/cases/${id}/response/send`, { expected_row_version: saved.row_version }, service);
    },
    meta: { success: "Response sent to the referring clinic." },
    onSuccess: refresh,
  });

  if (q.isLoading || !me) return <Loading />;
  if (q.error) return <ErrorAlert error={q.error} />;
  const { case: c, packages, info_requests, results } = q.data!;
  const latest = packages[0];
  const env = latest?.envelope;
  const deptName = (code: string | null | undefined) => (code ? ref.data?.departments[code]?.name ?? code : null);
  const sent = draft?.status === "returned";
  const hasContent = Object.values(form).some((v) => v.trim());

  return (
    <>
      <PageHeader
        title={`${c.central_referral_id} · ${c.patient_name}`}
        back={{ to: "/incoming", label: "Incoming referrals" }}
        subtitle={
          <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
            <CaseStatusTag status={c.status} />
            <UrgencyTag urgency={c.urgency} label={ref.data?.urgencies[c.urgency]?.label} />
            <span>version {c.latest_version}</span>
          </Stack>
        }
      />
      <Stack spacing={2}>
        <Section title="Referral">
          <KeyValue
            items={[
              ["Patient", `${c.patient_name}${c.patient_birth_date ? `, born ${c.patient_birth_date}` : ""}${env?.patient.sex ? `, ${env.patient.sex}` : ""}`],
              ["Your record", c.local_patient_id ?? "Not linked"],
              ["From", env ? `${env.requesting_doctor.name}, ${env.requesting_doctor.institution}${env.requesting_doctor.department ? ` (${env.requesting_doctor.department})` : ""}` : c.sender_name],
              ["To", `${deptName(c.department)}${c.requested_doctor ? `, requested doctor ${c.requested_doctor}` : ""}`],
              ["Urgency", ref.data?.urgencies[c.urgency] ? `${ref.data.urgencies[c.urgency].label}: ${ref.data.urgencies[c.urgency].detail}` : c.urgency],
              ["Planned procedure", env?.procedure_label ?? "Not recorded"],
              ["Received", fmtDate(c.received_at)],
            ]}
          />
          {env && (
            <Box sx={{ mt: 2 }}>
              <Typography variant="subtitle2">Reason for referral</Typography>
              <Typography sx={{ whiteSpace: "pre-wrap" }}>{env.reason || "Not recorded"}</Typography>
            </Box>
          )}
        </Section>

        <Section title="What happens next" description="Acknowledge the referral, then accept it, decline it with a reason, or ask the clinic for more information.">
          <ErrorAlert error={acknowledge.error || decide.error || ask.error} />
          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
            {!c.acknowledged_at && (
              <Button variant="contained" onClick={() => acknowledge.mutate()} disabled={acknowledge.isPending}>
                Acknowledge receipt
              </Button>
            )}
            {c.acknowledged_at && !c.decision && (
              <>
                <Button variant="contained" onClick={() => decide.mutate({ decision: "accept" })} disabled={decide.isPending}>
                  Accept referral
                </Button>
                <Button variant="outlined" color="error" onClick={() => setDeclineOpen(true)}>
                  Decline
                </Button>
              </>
            )}
            {c.acknowledged_at && c.status !== "responded" && (
              <Button variant="outlined" onClick={() => setAskOpen(true)}>
                Ask for more information
              </Button>
            )}
          </Stack>
          <Box sx={{ mt: 1.5 }}>
            <KeyValue
              items={[
                ["Acknowledged", c.acknowledged_at ? `${c.acknowledged_by}, ${fmtDate(c.acknowledged_at)}` : "Not yet"],
                ["Decision", c.decision ? `${c.decision} by ${c.decision_by}, ${fmtDate(c.decision_at)}${c.decline_reason ? `. Reason: ${c.decline_reason}` : ""}` : "Not yet"],
              ]}
            />
          </Box>
          {info_requests.length > 0 && (
            <Box sx={{ mt: 2 }}>
              <Typography variant="subtitle2">Questions to the referring clinic</Typography>
              {info_requests.map((ir) => (
                <Paper key={ir.id} variant="outlined" sx={{ p: 1.5, mt: 1 }}>
                  <Typography variant="body2">
                    <strong>Q:</strong> {ir.question}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {ir.created_by}, {fmtDate(ir.created_at)}
                  </Typography>
                  {ir.answer ? (
                    <Typography variant="body2" sx={{ mt: 0.5 }}>
                      <strong>A:</strong> {ir.answer} <em>({ir.answered_by}, {fmtDate(ir.answered_at)})</em>
                    </Typography>
                  ) : (
                    <Box sx={{ mt: 0.5 }}>
                      <Tag tone="wait" label="waiting for an answer" />
                    </Box>
                  )}
                </Paper>
              ))}
            </Box>
          )}
        </Section>

        {env && (
          <Section title="Referral summary" description={`Version ${latest.version}, sent by ${env.sent_by} on ${fmtDate(env.sent_at)}. Built from the records checked at the referring clinic.`}>
            <Stack spacing={2}>
              {env.brief_sections
                .filter((s) => s.key !== "reason")
                .map((s) => (
                  <Box key={s.key}>
                    <Typography variant="subtitle2">{s.title}</Typography>
                    {s.statements.length === 0 && <Typography color="text.secondary">None recorded.</Typography>}
                    <Box component="ul" sx={{ m: 0, pl: 2.5 }}>
                      {s.statements.map((st) => (
                        <li key={st.id}>
                          <Typography variant="body2">
                            {st.text}
                            {st.evidence_ids.length > 0 && (
                              <Typography component="span" variant="caption" color="text.secondary">
                                {" "}
                                (from the records)
                              </Typography>
                            )}
                          </Typography>
                        </li>
                      ))}
                    </Box>
                  </Box>
                ))}
            </Stack>
          </Section>
        )}

        {env && (
          <Section title="Medication flags" description={env.medication_evaluation.summary ?? "Checked against the approved medication rules."}>
            {env.medication_flags.length === 0 ? (
              <Empty>No medication flags for this referral.</Empty>
            ) : (
              <Stack spacing={1.5}>
                {env.medication_flags.map((f) => (
                  <FlagCard key={`${f.flag_id}-${f.version}`} flag={{ ...f, rule_version: null }} acknowledged={f.acknowledged} />
                ))}
              </Stack>
            )}
          </Section>
        )}

        {env && env.limitations.length > 0 && (
          <Alert severity="info">
            <AlertTitle>Not available or outstanding</AlertTitle>
            <Box component="ul" sx={{ m: 0, pl: 2.5 }}>
              {env.limitations.map((l, i) => (
                <li key={i}>{l}</li>
              ))}
            </Box>
          </Alert>
        )}

        {env && env.diagnostic_requests.length > 0 && (
          <Section title="Tests and scans requested with this referral">
            <Table size="small" aria-label="Tests and scans">
              <TableHead>
                <TableRow>
                  <TableCell>Test or scan</TableCell>
                  <TableCell>Where</TableCell>
                  <TableCell>Question</TableCell>
                  <TableCell>Status when sent</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {env.diagnostic_requests.map((d) => (
                  <TableRow key={d.reference}>
                    <TableCell>{d.test}</TableCell>
                    <TableCell>{d.where}</TableCell>
                    <TableCell>{d.clinical_question}</TableCell>
                    <TableCell>
                      <OrderStatus status={d.status} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Section>
        )}

        <Section title="Results received" description="Test and scan reports for this referral, sent on to you when they are ready.">
          {results.length === 0 && <Empty>No results received yet.</Empty>}
          <Stack spacing={1.5}>
            {results.map((r) => (
              <Paper key={r.id} variant="outlined" sx={{ p: 1.5 }}>
                <Typography variant="subtitle2">{r.test}</Typography>
                <Typography variant="caption" color="text.secondary" display="block">
                  {ref.data?.institutions[r.performed_by_institution]?.name ?? r.performed_by_institution} · reported by {r.reported_by}, {fmtDate(r.reported_at)}
                </Typography>
                {r.report_text && <Typography sx={{ whiteSpace: "pre-wrap", mt: 1 }}>{r.report_text}</Typography>}
                {r.values.length > 0 && (
                  <Table size="small" sx={{ mt: 1 }} aria-label={`${r.test} results`}>
                    <TableHead>
                      <TableRow>
                        <TableCell>Test</TableCell>
                        <TableCell>Value</TableCell>
                        <TableCell>Reference</TableCell>
                        <TableCell>Flag</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {r.values.map((v, i) => (
                        <TableRow key={i}>
                          <TableCell>{v.test}</TableCell>
                          <TableCell>
                            {v.value} {v.unit ?? ""}
                          </TableCell>
                          <TableCell>{v.reference ?? ""}</TableCell>
                          <TableCell>{v.flag ?? ""}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </Paper>
            ))}
          </Stack>
        </Section>

        {c.decision === "accepted" && (
          <Section
            title="Your response"
            description={sent ? `Sent by ${draft?.returned_by} on ${fmtDate(draft?.returned_at)}. It cannot be changed.` : "Write your assessment and plan. Sending signs it off and returns it to the referring clinic."}
          >
            {sent ? (
              <ResponseView content={draft!.content} />
            ) : (
              <Stack spacing={1.5}>
                <TextField label="Assessment" multiline minRows={3} value={form.assessment} onChange={(e) => setForm({ ...form, assessment: e.target.value })} />
                <TextField label="Plan" multiline minRows={2} value={form.plan} onChange={(e) => setForm({ ...form, plan: e.target.value })} />
                <TextField
                  label="Instructions for the referring clinic"
                  multiline
                  minRows={2}
                  value={form.instructions_for_clinic}
                  onChange={(e) => setForm({ ...form, instructions_for_clinic: e.target.value })}
                />
                <TextField label="Appointment" placeholder="For example: surgical clinic in 2 weeks" value={form.appointment} onChange={(e) => setForm({ ...form, appointment: e.target.value })} />
                <ErrorAlert error={save.error || send.error} />
                <Stack direction="row" spacing={1}>
                  <Button variant="outlined" onClick={() => save.mutate()} disabled={save.isPending || !hasContent}>
                    Save draft
                  </Button>
                  <Button variant="contained" onClick={() => send.mutate()} disabled={send.isPending || !hasContent}>
                    Send response to the referring clinic
                  </Button>
                </Stack>
                {draft && (
                  <Typography variant="caption" color="text.secondary">
                    Draft saved by {draft.drafted_by}.
                  </Typography>
                )}
              </Stack>
            )}
          </Section>
        )}

        {packages.length > 0 && (
          <Section title="Versions received">
            <Table size="small" aria-label="Versions received">
              <TableHead>
                <TableRow>
                  <TableCell>Version</TableCell>
                  <TableCell>Sent by</TableCell>
                  <TableCell>Sent</TableCell>
                  <TableCell>Received</TableCell>
                  <TableCell>Content hash</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {packages.map((p) => (
                  <TableRow key={p.version}>
                    <TableCell>v{p.version}</TableCell>
                    <TableCell>{p.envelope.sent_by}</TableCell>
                    <TableCell>{fmtDate(p.envelope.sent_at)}</TableCell>
                    <TableCell>{fmtDate(p.received_at)}</TableCell>
                    <TableCell>
                      <code title={p.content_hash}>{p.content_hash.slice(0, 12)}…</code>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Section>
        )}
      </Stack>

      <ReasonDialog
        open={declineOpen}
        title="Decline referral"
        label="Reason (the referring clinic will see this)"
        confirm="Decline referral"
        onClose={() => setDeclineOpen(false)}
        onConfirm={(reason) => decide.mutate({ decision: "decline", reason })}
        busy={decide.isPending}
      />
      <ReasonDialog
        open={askOpen}
        title="Ask the referring clinic for more information"
        label="Your question"
        confirm="Send question"
        onClose={() => setAskOpen(false)}
        onConfirm={(question) => ask.mutate(question)}
        busy={ask.isPending}
      />
    </>
  );
}
