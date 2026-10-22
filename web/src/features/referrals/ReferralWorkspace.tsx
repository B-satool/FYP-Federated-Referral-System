import { useParams, useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Box, Link, Paper, Stack, Typography } from "@mui/material";
import { Link as RouterLink } from "react-router-dom";
import ArrowBack from "@mui/icons-material/ArrowBack";
import { api } from "../../api/client";
import type { ReferralDetail } from "../../api/types";
import { ErrorAlert, Loading, ReferralStatus, Tag } from "../../components/common";
import { hasRole, useMe, usePageTitle } from "../../hooks";
import { OverviewTab } from "./OverviewTab";
import { SourcesTab } from "./SourcesTab";
import { DocumentsTab } from "../documents/DocumentsTab";
import { MedicationsTab } from "../medications/MedicationsTab";
import { ReviewTab } from "../reviews/ReviewTab";
import { BriefTab } from "../brief/BriefTab";
import { FollowThroughTab } from "./FollowThroughTab";
import { AuditTab } from "./AuditTab";
import { JourneyNav, NextStepBanner, StepPager } from "./Journey";
import { nextStep, STEP_ORDER, StepKey } from "./steps";

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

export function ReferralWorkspace() {
  const id = Number(useParams().id);
  const [params, setParams] = useSearchParams();
  const { data: me } = useMe();
  const q = useReferral(id);
  usePageTitle(q.data ? `${q.data.reference} ${q.data.patient.name}` : "Referral");
  const requested = params.get("tab") as StepKey | null;
  const tab: StepKey = requested && STEP_ORDER.includes(requested) ? requested : "overview";
  const go = (k: StepKey) => {
    setParams({ tab: k });
    // Move to the top of the new step so the person always starts at its beginning.
    window.scrollTo({ top: 0 });
  };

  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorAlert error={q.error} />;
  const r = q.data!;
  const step = nextStep(r, hasRole(me, "clinician"));

  return (
    <Box>
      <Link component={RouterLink} to="/referrals" underline="hover" sx={{ display: "inline-flex", alignItems: "center", gap: 0.5, mb: 1, fontSize: "0.875rem" }}>
        <ArrowBack fontSize="inherit" aria-hidden />
        All referrals
      </Link>
      <Paper sx={{ p: { xs: 2, md: 2.5 }, mb: 2 }}>
        <Stack direction={{ xs: "column", md: "row" }} justifyContent="space-between" spacing={1.5}>
          <Box sx={{ minWidth: 0 }}>
            <Typography variant="h5" component="h1" sx={{ overflowWrap: "anywhere" }}>
              {r.reference} · {r.patient.name}
            </Typography>
            <Typography color="text.secondary" className="tabular">
              {r.patient.institution_id} / {r.patient.local_patient_id} · born {r.patient.birth_date} · to {r.destination_name}
            </Typography>
          </Box>
          <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
            <ReferralStatus status={r.status} label={r.status_label} />
            {r.current_package_version && <Tag tone="ok" label={`approved v${r.current_package_version}`} />}
            {r.submitted_package_version && <Tag tone="info" label={`delivered v${r.submitted_package_version}`} />}
            {r.delivery_status !== "none" && <Tag tone={r.delivery_status === "failed" ? "bad" : r.delivery_status === "delivered" ? "ok" : "wait"} label={`delivery: ${r.delivery_status}`} />}
          </Stack>
        </Stack>
        {r.amendment_open && (
          <Alert severity="warning" sx={{ mt: 1.5 }}>
            Clinical content changed after version {r.submitted_package_version} was submitted. A new version must be approved and sent; the
            submitted version stays unchanged.
          </Alert>
        )}
      </Paper>
      <NextStepBanner step={step} onGo={go} />
      <JourneyNav r={r} active={tab} onSelect={go} />
      <Box role="tabpanel" id="journey-panel" aria-labelledby={`tab-${tab}`}>
        {tab === "overview" && <OverviewTab r={r} />}
        {tab === "sources" && <SourcesTab r={r} />}
        {tab === "documents" && <DocumentsTab r={r} />}
        {tab === "medications" && <MedicationsTab r={r} />}
        {tab === "review" && <ReviewTab r={r} />}
        {tab === "brief" && <BriefTab r={r} />}
        {tab === "followthrough" && <FollowThroughTab r={r} />}
        {tab === "audit" && <AuditTab r={r} />}
        <StepPager active={tab} onGo={go} />
      </Box>
    </Box>
  );
}
