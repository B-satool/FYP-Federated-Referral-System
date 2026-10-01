import { useParams, useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Box, Paper, Stack, Tab, Tabs, Typography } from "@mui/material";
import { api } from "../../api/client";
import type { ReferralDetail } from "../../api/types";
import { ErrorAlert, Loading, ReferralStatus, Tag } from "../../components/common";
import { OverviewTab } from "./OverviewTab";
import { SourcesTab } from "./SourcesTab";
import { DocumentsTab } from "../documents/DocumentsTab";
import { MedicationsTab } from "../medications/MedicationsTab";
import { ReviewTab } from "../reviews/ReviewTab";
import { BriefTab } from "../brief/BriefTab";
import { FollowThroughTab } from "./FollowThroughTab";
import { AuditTab } from "./AuditTab";

const AWAITING_REMOTE = ["submitted", "acknowledged", "accepted"];

export function useReferral(id: number) {
  return useQuery({
    queryKey: ["referral", id],
    queryFn: () => api.get<ReferralDetail>(`/referrals/${id}`),
    // Poll while waiting on the delivery worker or on specialist activity.
    refetchInterval: (q) => {
      const r = q.state.data;
      if (!r) return false;
      if (["pending", "retrying"].includes(r.delivery_status)) return 3000;
      return AWAITING_REMOTE.includes(r.status) ? 8000 : false;
    },
  });
}

export function useInvalidateReferral(id: number) {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: ["referral", id] });
}

const TABS = [
  ["overview", "Overview"],
  ["sources", "Sources & evidence"],
  ["documents", "Documents"],
  ["medications", "Medications & flags"],
  ["review", "Checklist & clarifications"],
  ["brief", "Brief & approval"],
  ["followthrough", "Specialist & follow-up"],
  ["audit", "Audit trail"],
] as const;

export function ReferralWorkspace() {
  const id = Number(useParams().id);
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") ?? "overview";
  const q = useReferral(id);
  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorAlert error={q.error} />;
  const r = q.data!;
  return (
    <Box>
      <Paper sx={{ p: 2, mb: 2 }}>
        <Stack direction={{ xs: "column", md: "row" }} justifyContent="space-between" spacing={1}>
          <Box>
            <Typography variant="h5" component="h1">
              {r.reference} · {r.patient.name}
            </Typography>
            <Typography color="text.secondary">
              {r.patient.institution_id} / {r.patient.local_patient_id} · born {r.patient.birth_date} · to {r.destination_name}
            </Typography>
          </Box>
          <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
            <ReferralStatus status={r.status} label={r.status_label} />
            {r.current_package_version && <Tag tone="ok" label={`approved v${r.current_package_version}`} />}
            {r.submitted_package_version && <Tag tone="info" label={`delivered v${r.submitted_package_version}`} />}
            {r.delivery_status !== "none" && <Tag tone={r.delivery_status === "failed" ? "bad" : r.delivery_status === "delivered" ? "ok" : "wait"} label={`delivery: ${r.delivery_status}`} />}
          </Stack>
        </Stack>
        {r.amendment_open && (
          <Alert severity="warning" sx={{ mt: 1 }}>
            Clinical content changed after version {r.submitted_package_version} was submitted. A new version must be approved and sent; the
            submitted version stays unchanged.
          </Alert>
        )}
      </Paper>
      <Tabs value={tab} onChange={(_, v) => setParams({ tab: v })} variant="scrollable" scrollButtons="auto" aria-label="Referral sections" sx={{ mb: 2 }}>
        {TABS.map(([k, label]) => (
          <Tab key={k} value={k} label={label} />
        ))}
      </Tabs>
      {tab === "overview" && <OverviewTab r={r} />}
      {tab === "sources" && <SourcesTab r={r} />}
      {tab === "documents" && <DocumentsTab r={r} />}
      {tab === "medications" && <MedicationsTab r={r} />}
      {tab === "review" && <ReviewTab r={r} />}
      {tab === "brief" && <BriefTab r={r} />}
      {tab === "followthrough" && <FollowThroughTab r={r} />}
      {tab === "audit" && <AuditTab r={r} />}
    </Box>
  );
}
