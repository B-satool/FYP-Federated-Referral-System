import { useParams, useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Box, Link, Paper, Stack, Typography } from "@mui/material";
import { Link as RouterLink } from "react-router-dom";
import ArrowBack from "@mui/icons-material/ArrowBack";
import { api } from "../../api/client";
import type { ReferralDetail } from "../../api/types";
import { ErrorAlert, Loading, ReferralStatus, Tag, UrgencyTag } from "../../components/common";
import { isDoctor, useMe, usePageTitle } from "../../hooks";
import { DocumentsTab } from "../documents/DocumentsTab";
import { AuditTab } from "./AuditTab";
import { JourneyNav, NextStepBanner, StepPager } from "./Journey";
import { MedicinesTab } from "./MedicinesTab";
import { DoctorRecords, StaffRecords } from "./Records";
import { RequestTab } from "./RequestTab";
import { ResponseTab } from "./ResponseTab";
import { SendTab, SummaryTab } from "./SendTab";
import { nextStep, Role, StepKey, stepOrder } from "./steps";
import { TestsTab } from "./TestsTab";

const WAITING_REMOTE = ["requested", "submitted", "acknowledged", "accepted", "response_returned"];

export function useReferral(id: number) {
  return useQuery({
    queryKey: ["referral", id],
    queryFn: () => api.get<ReferralDetail>(`/referrals/${id}`),
    // Poll while waiting on delivery, the other institution, or test results.
    refetchInterval: (q) => {
      const r = q.state.data;
      if (!r) return false;
      if (["pending", "retrying"].includes(r.delivery_status)) return 3000;
      return WAITING_REMOTE.includes(r.status) ? 8000 : false;
    },
  });
}

export function useInvalidateReferral(id: number) {
  const qc = useQueryClient();
  return () => {
    qc.invalidateQueries({ queryKey: ["referral", id] });
    qc.invalidateQueries({ queryKey: ["work-queue"] });
  };
}

export function ReferralWorkspace() {
  const id = Number(useParams().id);
  const [params, setParams] = useSearchParams();
  const { data: me } = useMe();
  const q = useReferral(id);
  usePageTitle(q.data ? `${q.data.reference} ${q.data.patient.name}` : "Referral");
  const role: Role = isDoctor(me) ? "doctor" : "staff";
  const order = stepOrder(role, q.data?.kind);
  const requested = params.get("tab") as StepKey | null;
  const tab: StepKey = requested && order.includes(requested) ? requested : "request";
  const go = (k: StepKey) => {
    setParams({ tab: k });
    window.scrollTo({ top: 0 });
  };

  if (q.isLoading || !me) return <Loading />;
  if (q.error) return <ErrorAlert error={q.error} />;
  const r = q.data!;
  const step = nextStep(r, role);

  return (
    <Box>
      <Link component={RouterLink} to="/referrals" underline="hover" sx={{ display: "inline-flex", alignItems: "center", gap: 0.5, mb: 1, fontSize: "0.875rem" }}>
        <ArrowBack fontSize="inherit" aria-hidden />
        All requests
      </Link>
      <Paper sx={{ p: { xs: 2, md: 2.5 }, mb: 2 }}>
        <Stack direction={{ xs: "column", md: "row" }} justifyContent="space-between" spacing={1.5}>
          <Box sx={{ minWidth: 0 }}>
            <Typography variant="h5" component="h1" sx={{ overflowWrap: "anywhere" }}>
              {r.reference} · {r.patient.name}
            </Typography>
            {r.kind === "test" ? (
              <Typography color="text.secondary">
                Tests and scans: {r.diagnostics.filter((d) => d.status !== "cancelled").map((d) => `${d.test} (${d.destination_name})`).join(", ")} · requested by {r.requesting_doctor_name}
              </Typography>
            ) : (
              <Typography color="text.secondary">
                Referral to {r.destination_name}, {r.destination_department_name}
                {r.destination_doctor ? ` (${r.destination_doctor})` : ""} · requested by {r.requesting_doctor_name}
              </Typography>
            )}
            <Typography color="text.secondary" variant="body2">
              {r.kind === "referral" ? `${r.procedure_label} · ` : ""}born {r.patient.birth_date ?? "not recorded"} · {r.patient.local_patient_id}
            </Typography>
          </Box>
          <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
            <Tag tone="neutral" label={r.kind === "test" ? "Test or scan" : "Referral"} />
            <ReferralStatus status={r.status} label={r.status_label} />
            <UrgencyTag urgency={r.urgency} label={`${r.urgency_label}`} />
            {r.submitted_package_version && <Tag tone="info" label={`sent v${r.submitted_package_version}`} />}
            {["pending", "retrying", "failed"].includes(r.delivery_status) && (
              <Tag tone={r.delivery_status === "failed" ? "bad" : "wait"} label={`delivery ${r.delivery_status}`} />
            )}
          </Stack>
        </Stack>
        {r.amendment_open && (
          <Alert severity="warning" sx={{ mt: 1.5 }}>
            Something changed after version {r.submitted_package_version} was sent. Staff must check and send the new version; the sent version stays unchanged.
          </Alert>
        )}
      </Paper>
      <NextStepBanner step={step} onGo={go} />
      <JourneyNav r={r} role={role} active={tab} onSelect={go} />
      <Box role="tabpanel" id="journey-panel" aria-labelledby={`tab-${tab}`}>
        {tab === "request" && <RequestTab r={r} role={role} />}
        {tab === "records" && (role === "doctor" ? <DoctorRecords r={r} /> : <StaffRecords r={r} />)}
        {tab === "papers" && <DocumentsTab r={r} />}
        {tab === "medicines" && <MedicinesTab r={r} role={role} />}
        {tab === "tests" && <TestsTab r={r} role={role} />}
        {tab === "send" && <SendTab r={r} />}
        {tab === "summary" && <SummaryTab r={r} />}
        {tab === "response" && <ResponseTab r={r} role={role} />}
        {tab === "audit" && <AuditTab r={r} />}
        <StepPager role={role} kind={r.kind} active={tab} onGo={go} />
      </Box>
    </Box>
  );
}
