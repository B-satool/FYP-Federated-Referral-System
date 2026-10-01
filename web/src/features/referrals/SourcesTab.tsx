import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link as RouterLink } from "react-router-dom";
import {
  Alert,
  Button,
  Card,
  CardActions,
  CardContent,
  Checkbox,
  FormControlLabel,
  Grid,
  Paper,
  Stack,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from "@mui/material";
import Refresh from "@mui/icons-material/Refresh";
import { api } from "../../api/client";
import type { Evidence, ReferralDetail } from "../../api/types";
import { Empty, ErrorAlert, fmtDate, Loading, RetrievalStatus, Tag, VerificationTag } from "../../components/common";
import { EvidenceRef } from "../../components/EvidenceRef";
import { useInvalidateReferral } from "./ReferralWorkspace";

const CATEGORY_LABELS: Record<string, string> = {
  condition: "Conditions",
  consultation: "Prior specialist consultations",
  encounter: "Encounters",
  medication: "Medications",
  lab: "Laboratory results",
  lab_report: "Laboratory reports",
  document: "Source document references",
  demographics: "Demographics (identity confirmation)",
  note: "Notes",
};

export function SourcesTab({ r }: { r: ReferralDetail }) {
  const refresh = useInvalidateReferral(r.id);
  const [showSuperseded, setShowSuperseded] = useState(false);
  const evidence = useQuery({
    queryKey: ["referral", r.id, "evidence", showSuperseded],
    queryFn: () => api.get<Evidence[]>(`/referrals/${r.id}/evidence?include_superseded=${showSuperseded}`),
  });
  const retrieve = useMutation({
    mutationFn: (source?: string) => api.post(`/referrals/${r.id}/retrieve${source ? `?source=${source}` : ""}`),
    onSuccess: refresh,
  });
  const select = useMutation({
    mutationFn: ({ id, selected }: { id: number; selected: boolean }) => api.post(`/evidence/${id}/select`, { selected }),
    onSuccess: refresh,
  });
  const locked = ["response_returned", "followup_pending", "closed", "declined", "cancelled"].includes(r.status);
  const groups: Record<string, Evidence[]> = {};
  for (const e of evidence.data ?? []) (groups[e.category] ??= []).push(e);

  return (
    <Stack spacing={2}>
      <Paper sx={{ p: 2 }}>
        <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
          <Typography variant="h6">Participating systems</Typography>
          <Button variant="contained" startIcon={<Refresh />} onClick={() => retrieve.mutate(undefined)} disabled={retrieve.isPending || locked}>
            {retrieve.isPending ? "Retrieving…" : "Retrieve permitted records"}
          </Button>
        </Stack>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Each source checks your authorization itself. Records are requested only through verified patient links; an unavailable or denied
          source is shown as such and never treated as "no history".
        </Typography>
        <ErrorAlert error={retrieve.error || select.error} />
        <Grid container spacing={2}>
          {r.sources.map((s) => (
            <Grid item xs={12} md={4} key={s.source_institution}>
              <Card variant="outlined" sx={{ height: "100%" }}>
                <CardContent>
                  <Typography variant="subtitle1">{s.source_name}</Typography>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    {s.linked ? `Patient record ${s.local_patient_id}${s.link_id ? ` (verified link #${s.link_id})` : " (own record)"}` : "No verified patient link"}
                  </Typography>
                  {s.latest ? (
                    <Stack spacing={0.5}>
                      <RetrievalStatus status={s.latest.status} />
                      <Typography variant="body2">{s.latest.message}</Typography>
                      {s.latest.withheld.length > 0 && (
                        <Alert severity="warning" sx={{ py: 0 }}>
                          {s.latest.withheld.join("; ")}
                        </Alert>
                      )}
                      <Typography variant="caption" color="text.secondary">
                        {fmtDate(s.latest.requested_at)} · {s.latest.attempts} attempt(s) · {s.latest.duration_ms} ms · by {s.latest.requested_by}
                      </Typography>
                    </Stack>
                  ) : s.linked ? (
                    <Tag tone="wait" label="not retrieved yet" />
                  ) : (
                    <Typography variant="body2">{s.message}{s.link_states?.length ? ` (link state: ${s.link_states.join(", ")})` : ""}</Typography>
                  )}
                </CardContent>
                <CardActions>
                  {s.linked ? (
                    <Button size="small" onClick={() => retrieve.mutate(s.source_institution)} disabled={retrieve.isPending || locked}>
                      {s.latest?.retryable ? "Retry" : "Retrieve"}
                    </Button>
                  ) : (
                    <Button size="small" component={RouterLink} to={`/patient-links?patient=${r.patient.local_patient_id}`}>
                      Manage patient links
                    </Button>
                  )}
                </CardActions>
              </Card>
            </Grid>
          ))}
        </Grid>
      </Paper>

      <Paper sx={{ p: 2 }}>
        <Stack direction="row" justifyContent="space-between" alignItems="center">
          <Typography variant="h6">Evidence</Typography>
          <FormControlLabel control={<Switch checked={showSuperseded} onChange={(e) => setShowSuperseded(e.target.checked)} />} label="Show superseded record versions" />
        </Stack>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          Selected items are offered to the brief. Original values, units and clinical dates are preserved as recorded at the source.
        </Typography>
        {evidence.isLoading && <Loading />}
        <ErrorAlert error={evidence.error} />
        {evidence.data?.length === 0 && <Empty>No evidence yet. Retrieve records or upload documents.</Empty>}
        {Object.entries(groups).map(([cat, items]) => (
          <div key={cat}>
            <Typography variant="subtitle1" sx={{ mt: 2 }}>
              {CATEGORY_LABELS[cat] ?? cat} ({items.length})
            </Typography>
            <Table size="small" aria-label={CATEGORY_LABELS[cat] ?? cat}>
              <TableHead>
                <TableRow>
                  <TableCell padding="checkbox">Use</TableCell>
                  <TableCell>Ref</TableCell>
                  <TableCell>Content (original)</TableCell>
                  <TableCell>Source</TableCell>
                  <TableCell>Clinical date</TableCell>
                  <TableCell>Status</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {items.map((e) => (
                  <TableRow key={e.id} sx={{ opacity: e.superseded_by ? 0.55 : 1 }}>
                    <TableCell padding="checkbox">
                      <Checkbox
                        checked={e.selected}
                        disabled={locked || !!e.superseded_by || ["invalidated", "access_revoked"].includes(e.verification_status) || e.review_state === "excluded"}
                        onChange={(ev) => select.mutate({ id: e.id, selected: ev.target.checked })}
                        inputProps={{ "aria-label": `Use evidence ${e.id} in the brief` }}
                      />
                    </TableCell>
                    <TableCell>
                      <EvidenceRef id={e.id} />
                    </TableCell>
                    <TableCell>{e.display}</TableCell>
                    <TableCell>
                      {e.source_name}
                      <Typography variant="caption" display="block" color="text.secondary">
                        {e.origin === "source" ? `${e.source_record_type}/${e.source_record_id} v${e.source_record_version}` : e.origin === "document" ? `document #${e.document_id} p.${e.page}` : `entered by ${e.author}`}
                      </Typography>
                    </TableCell>
                    <TableCell>{fmtDate(e.clinical_time, false)}</TableCell>
                    <TableCell>
                      <Stack direction="row" spacing={0.5}>
                        <VerificationTag status={e.verification_status} reviewState={e.review_state} />
                        {e.superseded_by && <Tag tone="neutral" label="superseded" />}
                      </Stack>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        ))}
      </Paper>
    </Stack>
  );
}
