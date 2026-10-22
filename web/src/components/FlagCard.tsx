import { ReactNode } from "react";
import { Alert, AlertTitle, Box, Stack, Typography } from "@mui/material";
import Medication from "@mui/icons-material/Medication";
import HelpOutline from "@mui/icons-material/HelpOutline";
import ReportProblemOutlined from "@mui/icons-material/ReportProblemOutlined";
import Info from "@mui/icons-material/InfoOutlined";
import { fmtDate } from "./common";

export type FlagLike = {
  id?: number;
  flag_id?: number;
  version: number;
  kind: string;
  title: string;
  message: string;
  medication: string | null;
  drug_class: string | null;
  current_use_status: string | null;
  source_label: string | null;
  rule_id: string | null;
  rule_version: number | null;
  evidence_ids: number[];
};

const KIND: Record<string, { severity: "error" | "warning" | "info"; label: string; icon: JSX.Element }> = {
  confirmed: { severity: "error", label: "Medication flag", icon: <Medication /> },
  possible_use: { severity: "warning", label: "Possible medication use", icon: <HelpOutline /> },
  procedure_context_required: { severity: "warning", label: "Procedure context required", icon: <HelpOutline /> },
  ambiguous_mapping: { severity: "warning", label: "Mapping needs clarification", icon: <HelpOutline /> },
  history_incomplete: { severity: "info", label: "Incomplete medication history", icon: <ReportProblemOutlined /> },
};

/** Structured flag display, independent of any AI wording (FR-65, FR-68). Kind is conveyed by text and icon, not colour alone. */
export function FlagCard({
  flag,
  evidence,
  reviews,
  actions,
}: {
  flag: FlagLike;
  evidence?: ReactNode;
  reviews?: { side: string; action: string; reviewer: string; flag_version: number; created_at: string; package_version?: number | null }[];
  actions?: ReactNode;
}) {
  const k = KIND[flag.kind] ?? { severity: "info" as const, label: flag.kind, icon: <Info /> };
  return (
    <Alert severity={k.severity} icon={k.icon} variant="outlined" sx={{ "& .MuiAlert-message": { width: "100%" } }}>
      <AlertTitle>
        <Typography component="span" variant="overline" sx={{ display: "block", lineHeight: 1.4 }}>
          {k.label} · v{flag.version}
        </Typography>
        {flag.title}
      </AlertTitle>
      <Typography variant="body2">{flag.message}</Typography>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2} sx={{ mt: 1 }} flexWrap="wrap" useFlexGap>
        {flag.medication && (
          <Typography variant="body2">
            <strong>Medication:</strong> {flag.medication}
            {flag.drug_class ? ` (${flag.drug_class.replace(/_/g, " ")})` : ""}
          </Typography>
        )}
        {flag.current_use_status && (
          <Typography variant="body2">
            <strong>Current use:</strong> {flag.current_use_status.replace(/_/g, " ")}
          </Typography>
        )}
        {flag.source_label && (
          <Typography variant="body2">
            <strong>Source:</strong> {flag.source_label}
          </Typography>
        )}
        {flag.rule_id && (
          <Typography variant="body2">
            <strong>Rule:</strong> {flag.rule_id} v{flag.rule_version}
          </Typography>
        )}
      </Stack>
      {evidence && <Box sx={{ mt: 1 }}>{evidence}</Box>}
      {!!reviews?.length && (
        <Box sx={{ mt: 1 }}>
          {reviews.map((r, i) => (
            <Typography key={i} variant="caption" display="block">
              {r.side === "specialist" ? "Specialist" : "Referring clinician"}: <strong>{r.action === "reviewed" ? "Reviewed" : "Requested clarification"}</strong> by {r.reviewer}, flag v
              {r.flag_version}
              {r.package_version ? `, package v${r.package_version}` : ""}, {fmtDate(r.created_at)}
            </Typography>
          ))}
        </Box>
      )}
      {actions && (
        <Stack direction="row" spacing={1} sx={{ mt: 1.5 }}>
          {actions}
        </Stack>
      )}
      <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>
        "Reviewed" records acknowledgment only. It is not treatment clearance and does not close the referral.
      </Typography>
    </Alert>
  );
}
