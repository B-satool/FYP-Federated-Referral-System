import { useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link as RouterLink, useSearchParams } from "react-router-dom";
import {
  Alert,
  Box,
  Button,
  Divider,
  FormControlLabel,
  Grid,
  Link,
  List,
  ListItem,
  ListItemText,
  MenuItem,
  Radio,
  RadioGroup,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { api } from "../../api/client";
import type { ReferralDetail, ReferralEvent } from "../../api/types";
import { ErrorAlert, fmtDate, KeyValue, ReasonDialog, Section, Tag } from "../../components/common";
import { hasRole, useMe, useRefData } from "../../hooks";
import { useInvalidateReferral } from "./ReferralWorkspace";
import { STEP_LABEL, StepKey } from "./steps";

const BLOCKER_STEP: Record<string, StepKey> = {
  review_item: "review",
  brief: "brief",
  medication_evaluation: "medications",
  medication_evaluation_failed: "medications",
  flag_review: "medications",
};

export function OverviewTab({ r }: { r: ReferralDetail }) {
  const { data: me } = useMe();
  const ref = useRefData();
  const refresh = useInvalidateReferral(r.id);
  const locked = ["response_returned", "followup_pending", "closed", "declined", "cancelled"].includes(r.status);
  const [form, setForm] = useState({ reason: r.reason, priority: r.priority ?? "", procedure_status: r.procedure_status, planned_procedure: r.planned_procedure ?? "" });
  const [cancelOpen, setCancelOpen] = useState(false);
  useEffect(() => {
    setForm({ reason: r.reason, priority: r.priority ?? "", procedure_status: r.procedure_status, planned_procedure: r.planned_procedure ?? "" });
  }, [r.row_version]); // eslint-disable-line react-hooks/exhaustive-deps

  const events = useQuery({ queryKey: ["referral", r.id, "events", r.row_version], queryFn: () => api.get<ReferralEvent[]>(`/referrals/${r.id}/events`) });
  const save = useMutation({
    mutationFn: () =>
      api.patch(`/referrals/${r.id}`, {
        expected_version: r.row_version,
        reason: form.reason,
        priority: form.priority || undefined,
        procedure_status: form.procedure_status,
        planned_procedure: form.procedure_status === "known" ? form.planned_procedure : null,
      }),
    onSuccess: refresh,
  });
  const assign = useMutation({ mutationFn: () => api.patch(`/referrals/${r.id}`, { expected_version: r.row_version, assign_me_as_clinician: true }), onSuccess: refresh });
  const requestApproval = useMutation({ mutationFn: () => api.post(`/referrals/${r.id}/request-approval`, { expected_version: r.row_version }), onSuccess: refresh });
  const toDraft = useMutation({ mutationFn: () => api.post(`/referrals/${r.id}/return-to-draft`, { expected_version: r.row_version }), onSuccess: refresh });
  const cancel = useMutation({ mutationFn: (reason: string) => api.post(`/referrals/${r.id}/cancel`, { expected_version: r.row_version, reason }), onSuccess: () => { setCancelOpen(false); refresh(); } });
  const isClinician = hasRole(me, "clinician");
  const dirty = form.reason !== r.reason || (form.priority || null) !== r.priority || form.procedure_status !== r.procedure_status || (form.procedure_status === "known" && form.planned_procedure !== (r.planned_procedure ?? ""));

  const [, setParams] = useSearchParams();
  const done = r.checklist.filter((c) => ["present", "not_applicable", "limitation_recorded"].includes(c.state)).length;
  const recent = (events.data ?? []).slice(-6).reverse();

  return (
    <Grid container spacing={2}>
      <Grid item xs={12} lg={7}>
        <Stack spacing={2}>
          <Section title="Referral details" description="What the specialist is being asked, and for which procedure.">
            <Stack spacing={2}>
              <TextField label="Reason for referral" multiline minRows={3} value={form.reason} disabled={locked} onChange={(e) => setForm({ ...form, reason: e.target.value })} />
              <TextField select label="Priority (clinician-selected)" value={form.priority} disabled={locked || !isClinician} onChange={(e) => setForm({ ...form, priority: e.target.value })} helperText={isClinician ? "The system never assigns urgency." : "Only a clinician can set priority."}>
                <MenuItem value="">Not set</MenuItem>
                {ref.data?.priorities.map((p) => (
                  <MenuItem key={p} value={p}>
                    {p}
                  </MenuItem>
                ))}
              </TextField>
              <div>
                <Typography variant="body2" color="text.secondary" id="proc">
                  Planned procedure
                </Typography>
                <RadioGroup row aria-labelledby="proc" value={form.procedure_status} onChange={(e) => setForm({ ...form, procedure_status: e.target.value as typeof form.procedure_status })}>
                  <FormControlLabel value="known" control={<Radio />} label="Known" disabled={locked} />
                  <FormControlLabel value="unknown" control={<Radio />} label="Explicitly unknown" disabled={locked} />
                  <FormControlLabel value="not_stated" control={<Radio />} label="Not yet stated" disabled={locked} />
                </RadioGroup>
                {form.procedure_status === "known" && (
                  <TextField select fullWidth label="Procedure" value={form.planned_procedure} disabled={locked} onChange={(e) => setForm({ ...form, planned_procedure: e.target.value })}>
                    {Object.entries(ref.data?.procedures ?? {}).map(([k, v]) => (
                      <MenuItem key={k} value={k}>
                        {v}
                      </MenuItem>
                    ))}
                  </TextField>
                )}
                {form.procedure_status !== "known" && (
                  <Alert severity="info" sx={{ mt: 1 }}>
                    Procedure-dependent medication rules stay unevaluated until the procedure is known. The system never guesses it.
                  </Alert>
                )}
              </div>
              <ErrorAlert error={save.error} />
              <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                <Button variant="contained" disabled={!dirty || locked || save.isPending} onClick={() => save.mutate()}>
                  Save details
                </Button>
                {r.current_package_version && dirty && <Typography variant="caption" color="warning.main">Saving changes approved content and requires renewed approval.</Typography>}
              </Stack>
              <Divider />
              <KeyValue
                items={[
                  ["Specialty", "Orthodontics"],
                  ["Destination", r.destination_name],
                  ["Created by", `${r.created_by}, ${fmtDate(r.created_at)}`],
                  ["Referring clinician", r.referring_clinician_name ?? <Tag tone="warn" label="not assigned" />],
                  ["Cancel / decline reason", r.cancel_reason || r.decline_reason || "None"],
                ]}
              />
              {!r.referring_clinician_id && isClinician && (
                <Button variant="outlined" onClick={() => assign.mutate()} sx={{ alignSelf: "start" }}>
                  Assign me as referring clinician
                </Button>
              )}
            </Stack>
          </Section>
          <Section title="Referral actions" description="Move the referral forward, or stop it.">
            <ErrorAlert error={requestApproval.error || toDraft.error || cancel.error || assign.error} />
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
              {["draft", "awaiting_information"].includes(r.status) && (
                <Button variant="contained" onClick={() => requestApproval.mutate()} disabled={requestApproval.isPending}>
                  Send for clinician approval
                </Button>
              )}
              {["awaiting_information", "awaiting_approval"].includes(r.status) && (
                <Button variant="outlined" onClick={() => toDraft.mutate()}>
                  Return to draft
                </Button>
              )}
              {!["closed", "declined", "cancelled"].includes(r.status) && (
                <Button color="error" variant="outlined" onClick={() => setCancelOpen(true)}>
                  Cancel referral
                </Button>
              )}
            </Stack>
          </Section>
        </Stack>
      </Grid>
      <Grid item xs={12} lg={5}>
        <Stack spacing={2}>
          <Section
            title="Before approval"
            description={r.approval_blockers.length ? `${r.approval_blockers.length} ${r.approval_blockers.length === 1 ? "item needs" : "items need"} attention before a clinician can approve.` : "Nothing is blocking approval."}
          >
            {r.approval_blockers.length > 0 && (
              <Box component="ul" sx={{ listStyle: "none", m: 0, p: 0 }}>
                {r.approval_blockers.map((b, i) => {
                  const target = BLOCKER_STEP[b.type];
                  return (
                    <Box component="li" key={i} sx={{ py: 1.25, borderTop: i === 0 ? "none" : "1px solid", borderColor: "divider" }}>
                      <Typography variant="body2" sx={{ fontWeight: 600 }}>
                        {b.message}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        {b.how}.
                      </Typography>
                      {target && (
                        <Link component="button" type="button" variant="body2" onClick={() => setParams({ tab: target })} sx={{ mt: 0.5 }}>
                          Go to {STEP_LABEL[target]}
                        </Link>
                      )}
                    </Box>
                  );
                })}
              </Box>
            )}
            <Typography variant="body2" color="text.secondary" sx={{ mt: r.approval_blockers.length ? 1 : 0 }}>
              Completeness checklist (orthodontics v1): {done} of {r.checklist.length} items complete.{" "}
              <Link component="button" type="button" variant="body2" onClick={() => setParams({ tab: "review" })}>
                Open checklist items
              </Link>
            </Typography>
          </Section>
          <Section title="Recent activity" actions={<Link component={RouterLink} to="?tab=audit" variant="body2">Full history</Link>}>
            {recent.length === 0 && <Typography color="text.secondary">No activity yet.</Typography>}
            <List dense disablePadding>
              {recent.map((e) => (
                <ListItem key={e.id} alignItems="flex-start" disableGutters>
                  <ListItemText
                    primary={e.event_type === "status_change" ? `Status: ${e.from_status ?? "new"} → ${e.to_status}` : e.event_type.replace(/_/g, " ")}
                    secondary={`${fmtDate(e.created_at)} · ${e.actor}${e.institution_name ? ` (${e.institution_name})` : ""}${e.detail?.reason ? ` · ${String(e.detail.reason)}` : ""}`}
                  />
                </ListItem>
              ))}
            </List>
          </Section>
        </Stack>
      </Grid>
      <ReasonDialog open={cancelOpen} title="Cancel referral" label="Reason for cancellation" confirm="Cancel referral" onClose={() => setCancelOpen(false)} onConfirm={(t) => cancel.mutate(t)} busy={cancel.isPending} />
    </Grid>
  );
}
