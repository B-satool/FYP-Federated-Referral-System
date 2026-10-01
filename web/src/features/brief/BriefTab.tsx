import { useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Alert,
  AlertTitle,
  Autocomplete,
  Box,
  Button,
  Checkbox,
  Chip,
  Divider,
  FormControlLabel,
  Grid,
  IconButton,
  Paper,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import Delete from "@mui/icons-material/DeleteOutline";
import Add from "@mui/icons-material/Add";
import AutoAwesome from "@mui/icons-material/AutoAwesome";
import { api } from "../../api/client";
import type { Blocker, BriefResponse, BriefSection, Evidence, Job, MedicationsResponse, ReferralDetail } from "../../api/types";
import { ErrorAlert, fmtDate, Loading, Tag } from "../../components/common";
import { EvidenceRef } from "../../components/EvidenceRef";
import { FlagCard } from "../../components/FlagCard";
import { hasRole, useMe } from "../../hooks";
import { useInvalidateReferral } from "../referrals/ReferralWorkspace";

const VER_TONE: Record<string, "ok" | "warn" | "info" | "neutral"> = { verified: "ok", unverified: "warn", unresolved: "warn", mixed: "info", none: "neutral" };

function useJob(jobId: string | null) {
  return useQuery({
    queryKey: ["job", jobId],
    queryFn: () => api.get<Job>(`/jobs/${jobId}`),
    enabled: !!jobId,
    refetchInterval: (q) => (q.state.data && ["completed", "failed"].includes(q.state.data.status) ? false : 1500),
  });
}

export function BriefTab({ r }: { r: ReferralDetail }) {
  const { data: me } = useMe();
  const refresh = useInvalidateReferral(r.id);
  const brief = useQuery({ queryKey: ["referral", r.id, "brief"], queryFn: () => api.get<BriefResponse>(`/referrals/${r.id}/brief`) });
  const meds = useQuery({ queryKey: ["referral", r.id, "medications"], queryFn: () => api.get<MedicationsResponse>(`/referrals/${r.id}/medications`) });
  const evidence = useQuery({ queryKey: ["referral", r.id, "evidence", false], queryFn: () => api.get<Evidence[]>(`/referrals/${r.id}/evidence`) });
  const check = useQuery({ queryKey: ["referral", r.id, "approval-check"], queryFn: () => api.get<{ blockers: Blocker[] }>(`/referrals/${r.id}/approval-check`) });
  const [sections, setSections] = useState<BriefSection[]>([]);
  const [limitations, setLimitations] = useState<string[]>([]);
  const [dirty, setDirty] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [ackFailure, setAckFailure] = useState(false);
  const [manualNote, setManualNote] = useState("");
  const job = useJob(jobId);
  const latest = brief.data?.latest ?? null;

  useEffect(() => {
    if (latest) {
      setSections(latest.sections.map((s) => ({ ...s, statements: s.statements.map((st) => ({ ...st })) })));
      setLimitations(latest.limitations);
      setDirty(false);
    }
  }, [latest?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (job.data?.status === "completed") refresh();
  }, [job.data?.status]); // eslint-disable-line react-hooks/exhaustive-deps

  const generate = useMutation({ mutationFn: () => api.post<Job>(`/referrals/${r.id}/brief/generate`), onSuccess: (j) => setJobId(j.id) });
  const template = useMutation({ mutationFn: () => api.post(`/referrals/${r.id}/brief/template`), onSuccess: refresh });
  const save = useMutation({
    mutationFn: () =>
      api.put(`/referrals/${r.id}/brief`, {
        based_on_version: latest?.version ?? null,
        expected_version: r.row_version,
        limitations,
        sections: sections.map((s) => ({ key: s.key, statements: s.statements.map((st) => ({ id: st.id, text: st.text, evidence_ids: st.evidence_ids })) })),
      }),
    onSuccess: () => {
      setDirty(false);
      refresh();
    },
  });
  const approve = useMutation({
    mutationFn: () => api.post(`/referrals/${r.id}/approve`, { expected_version: r.row_version, acknowledge_evaluation_failure: ackFailure, manual_review_note: manualNote || null }),
    onSuccess: refresh,
  });
  const submit = useMutation({ mutationFn: () => api.post(`/referrals/${r.id}/submit`, { expected_version: r.row_version }), onSuccess: refresh });
  const retry = useMutation({ mutationFn: () => api.post(`/referrals/${r.id}/retry-delivery`), onSuccess: refresh });

  if (brief.isLoading) return <Loading />;
  const isClinician = hasRole(me, "clinician");
  const locked = ["response_returned", "followup_pending", "closed", "declined", "cancelled"].includes(r.status);
  const usable = (evidence.data ?? []).filter((e) => e.selected);
  const evalFailed = meds.data?.evaluation?.status === "failed";
  const blockers = (check.data?.blockers ?? []).filter((b) => !(b.type === "medication_evaluation_failed" && ackFailure));
  const canApprove = isClinician && (r.status === "awaiting_approval" || r.amendment_open) && !dirty;
  const sending = ["pending", "retrying"].includes(r.delivery_status);
  const canSend = !sending && r.current_package_version && (r.status === "approved" || (r.amendment_open && r.submitted_package_version !== r.current_package_version && !r.packages.find((p) => p.version === r.current_package_version)?.superseded));

  const update = (si: number, fn: (s: BriefSection) => BriefSection) => {
    setSections((prev) => prev.map((s, i) => (i === si ? fn(s) : s)));
    setDirty(true);
  };

  return (
    <Grid container spacing={2}>
      <Grid item xs={12} lg={8}>
        <Paper sx={{ p: 2 }}>
          <Stack direction={{ xs: "column", md: "row" }} justifyContent="space-between" spacing={1} sx={{ mb: 1 }}>
            <Box>
              <Typography variant="h6">Referral brief</Typography>
              {latest ? (
                <Typography variant="caption" color="text.secondary">
                  Version {latest.version} ({latest.kind}) by {latest.created_by}, {fmtDate(latest.created_at)}
                  {latest.model ? ` · model ${latest.model} · ${latest.prompt_version}` : ""}
                </Typography>
              ) : (
                <Typography variant="caption">No brief yet.</Typography>
              )}
            </Box>
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
              <Button
                variant="contained"
                startIcon={<AutoAwesome />}
                disabled={locked || !brief.data?.llm_configured || generate.isPending || (!!jobId && !["completed", "failed"].includes(job.data?.status ?? ""))}
                onClick={() => generate.mutate()}
                title={brief.data?.llm_configured ? `Draft with ${brief.data.llm_model}` : "No language model configured"}
              >
                Draft with AI
              </Button>
              <Button variant="outlined" disabled={locked || template.isPending} onClick={() => template.mutate()}>
                Start from evidence template
              </Button>
            </Stack>
          </Stack>
          {!brief.data?.llm_configured && (
            <Alert severity="info" sx={{ mb: 1 }}>
              No language model is configured. Use the evidence template or write the brief manually — preparation never depends on the model.
            </Alert>
          )}
          {jobId && job.data && job.data.status !== "completed" && (
            <Alert severity={job.data.status === "failed" ? "error" : "info"} sx={{ mb: 1 }}>
              {job.data.status === "failed" ? (
                <>
                  <AlertTitle>Draft generation failed</AlertTitle>
                  {job.data.error} — you can continue with the template or manual editor.
                </>
              ) : (
                `Generating draft (${job.data.status})…`
              )}
            </Alert>
          )}
          <ErrorAlert error={generate.error || template.error || save.error} />
          <Alert severity="warning" icon={false} sx={{ mb: 2 }}>
            AI-drafted text is a proposal until a clinician approves it. Every record-derived statement must keep its source references (E-chips).
            Medication flags are shown separately below from the deterministic rules — the model never writes them.
          </Alert>

          {sections.map((s, si) => (
            <Box key={s.key} sx={{ mb: 3 }}>
              <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                {s.title}
              </Typography>
              {s.statements.length === 0 && (
                <Typography variant="body2" color="text.secondary">
                  No statements.
                </Typography>
              )}
              {s.statements.map((st, ti) => (
                <Stack key={st.id} direction="row" spacing={1} alignItems="flex-start" sx={{ mt: 1 }}>
                  <Box sx={{ flex: 1 }}>
                    <TextField
                      fullWidth
                      multiline
                      size="small"
                      value={st.text}
                      disabled={locked}
                      onChange={(e) => update(si, (sec) => ({ ...sec, statements: sec.statements.map((x, i) => (i === ti ? { ...x, text: e.target.value } : x)) }))}
                      inputProps={{ "aria-label": `${s.title} statement ${ti + 1}` }}
                    />
                    <Stack direction="row" spacing={0.5} alignItems="center" sx={{ mt: 0.5 }} flexWrap="wrap" useFlexGap>
                      {st.evidence_ids.map((id) => (
                        <EvidenceRef key={id} id={id} />
                      ))}
                      <Tag tone={VER_TONE[st.verification] ?? "neutral"} label={st.verification === "none" ? "no record reference" : st.verification} />
                      <Typography variant="caption" color="text.secondary">
                        {st.author_kind === "model" ? "AI draft" : st.author_kind === "template" ? "template" : `written by ${st.author_name}`}
                        {st.edited_by ? ` · edited by ${st.edited_by}` : ""}
                      </Typography>
                    </Stack>
                    {!locked && (
                      <Autocomplete
                        multiple
                        size="small"
                        options={usable.map((e) => e.id)}
                        value={st.evidence_ids}
                        getOptionLabel={(id) => {
                          const e = usable.find((x) => x.id === id);
                          return e ? `E${id} ${e.display.slice(0, 70)}` : `E${id}`;
                        }}
                        onChange={(_, v) => update(si, (sec) => ({ ...sec, statements: sec.statements.map((x, i) => (i === ti ? { ...x, evidence_ids: v } : x)) }))}
                        renderTags={() => null}
                        renderInput={(params) => <TextField {...params} variant="standard" placeholder="Attach source references" />}
                        sx={{ mt: 0.5, maxWidth: 520 }}
                      />
                    )}
                  </Box>
                  {!locked && (
                    <IconButton aria-label="Remove statement" onClick={() => update(si, (sec) => ({ ...sec, statements: sec.statements.filter((_, i) => i !== ti) }))}>
                      <Delete />
                    </IconButton>
                  )}
                </Stack>
              ))}
              {!locked && (
                <Button
                  size="small"
                  startIcon={<Add />}
                  sx={{ mt: 1 }}
                  onClick={() =>
                    update(si, (sec) => ({
                      ...sec,
                      statements: [...sec.statements, { id: `new-${Date.now()}`, text: "", evidence_ids: [], author_kind: "clinician", author_name: me?.name ?? null, edited_by: null, verification: "none" }],
                    }))
                  }
                >
                  Add statement
                </Button>
              )}
            </Box>
          ))}

          <Divider sx={{ my: 2 }} />
          <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
            Medication flags (structured, from approved rules)
          </Typography>
          <Stack spacing={1} sx={{ mt: 1 }}>
            {(meds.data?.flags ?? []).map((f) => (
              <FlagCard key={f.id} flag={f} reviews={f.reviews} evidence={f.evidence_ids.map((id) => <EvidenceRef key={id} id={id} />)} />
            ))}
            {meds.data?.evaluation?.summary_message && <Alert severity="info">{meds.data.evaluation.summary_message}</Alert>}
          </Stack>

          <Divider sx={{ my: 2 }} />
          <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
            Limitations and outstanding information
          </Typography>
          {limitations.map((l, i) => (
            <Stack key={i} direction="row" spacing={1} sx={{ mt: 1 }}>
              <TextField fullWidth size="small" value={l} disabled={locked} onChange={(e) => { setLimitations(limitations.map((x, j) => (j === i ? e.target.value : x))); setDirty(true); }} />
              {!locked && (
                <IconButton aria-label="Remove limitation" onClick={() => { setLimitations(limitations.filter((_, j) => j !== i)); setDirty(true); }}>
                  <Delete />
                </IconButton>
              )}
            </Stack>
          ))}
          {!locked && (
            <Button size="small" startIcon={<Add />} onClick={() => { setLimitations([...limitations, ""]); setDirty(true); }}>
              Add limitation
            </Button>
          )}
          <Stack direction="row" spacing={1} sx={{ mt: 2 }}>
            <Button variant="contained" disabled={!dirty || locked || save.isPending || !latest && sections.length === 0} onClick={() => save.mutate()}>
              Save brief as new version
            </Button>
            {dirty && <Chip color="warning" label="Unsaved changes" />}
          </Stack>
        </Paper>
      </Grid>
      <Grid item xs={12} lg={4}>
        <Paper sx={{ p: 2, position: { lg: "sticky" }, top: { lg: 90 } }}>
          <Typography variant="h6" gutterBottom>
            Approval and submission
          </Typography>
          <ErrorAlert error={approve.error || submit.error || retry.error} />
          {blockers.length > 0 ? (
            <Alert severity="warning" sx={{ mb: 2 }}>
              <AlertTitle>Outstanding before approval</AlertTitle>
              <ul style={{ margin: 0, paddingLeft: 18 }}>
                {blockers.map((b, i) => (
                  <li key={i}>
                    {b.message}
                    <Typography variant="caption" display="block">
                      {b.how}
                    </Typography>
                  </li>
                ))}
              </ul>
            </Alert>
          ) : (
            <Alert severity="success" sx={{ mb: 2 }}>
              No outstanding blockers.
            </Alert>
          )}
          {evalFailed && (
            <Box sx={{ mb: 2 }}>
              <FormControlLabel control={<Checkbox checked={ackFailure} onChange={(e) => setAckFailure(e.target.checked)} />} label="I performed a manual medication review because rule evaluation failed" />
              {ackFailure && <TextField fullWidth size="small" label="Manual review note" value={manualNote} onChange={(e) => setManualNote(e.target.value)} />}
            </Box>
          )}
          {r.status !== "awaiting_approval" && !r.amendment_open && !r.current_package_version && (
            <Alert severity="info" sx={{ mb: 2 }}>
              Send the referral for clinician approval from the Overview tab first.
            </Alert>
          )}
          {dirty && <Alert severity="warning" sx={{ mb: 2 }}>Save the brief before approving.</Alert>}
          <Stack spacing={1}>
            <Button variant="contained" color="success" disabled={!canApprove || blockers.length > 0 || approve.isPending} onClick={() => approve.mutate()}>
              {isClinician ? "Approve this exact version" : "Clinician approval required"}
            </Button>
            <Button variant="contained" disabled={!canSend || submit.isPending} onClick={() => submit.mutate()}>
              {sending ? "Delivering…" : "Send approved version to specialist"}
            </Button>
            {r.delivery_status === "failed" && (
              <Button color="warning" variant="outlined" onClick={() => retry.mutate()}>
                Retry delivery (same delivery key)
              </Button>
            )}
          </Stack>
          <Divider sx={{ my: 2 }} />
          <Typography variant="subtitle2">Approved versions</Typography>
          {r.packages.length === 0 && <Typography variant="body2" color="text.secondary">None yet.</Typography>}
          {r.packages.map((p) => (
            <Box key={p.version} sx={{ mt: 1 }}>
              <Typography variant="body2">
                <strong>v{p.version}</strong> — {p.approved_by}, {fmtDate(p.approved_at)} {p.superseded && <Tag tone="neutral" label="superseded" />}
                {r.submitted_package_version === p.version && <Tag tone="ok" label="delivered" />}
              </Typography>
              <Typography variant="caption" color="text.secondary" sx={{ wordBreak: "break-all" }}>
                sha256 {p.content_hash.slice(0, 16)}… · {p.delivery_key}
              </Typography>
            </Box>
          ))}
        </Paper>
      </Grid>
    </Grid>
  );
}
