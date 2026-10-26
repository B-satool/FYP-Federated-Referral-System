import { ReactNode } from "react";
import { Alert, AlertTitle, Box, Stack, Typography } from "@mui/material";
import Medication from "@mui/icons-material/Medication";
import HelpOutline from "@mui/icons-material/HelpOutline";
import ReportProblemOutlined from "@mui/icons-material/ReportProblemOutlined";
import Info from "@mui/icons-material/InfoOutlined";
import { fmtDate } from "./common";

export type FlagLike = {
  version: number;
  kind: string;
  title: string;
  message: string;
  medication: string | null;
  drug_class?: string | null;
  drug_class_label?: string | null;
  source_label: string | null;
  rule_id: string | null;
  rule_version?: number | null;
};

const KIND: Record<string, { severity: "error" | "warning" | "info"; label: string; icon: JSX.Element }> = {
  confirmed: { severity: "error", label: "Medication flag", icon: <Medication /> },
  unrecognised_medicine: { severity: "warning", label: "Medicine not recognised", icon: <HelpOutline /> },
  procedure_not_checked: { severity: "warning", label: "Procedure not checked", icon: <HelpOutline /> },
  records_incomplete: { severity: "info", label: "Records incomplete", icon: <ReportProblemOutlined /> },
};

/** A flag from the approved rules, shown as structured data. The kind is in the text and icon, not colour alone. */
export function FlagCard({
  flag,
  acknowledged,
  actions,
  footer,
}: {
  flag: FlagLike;
  acknowledged?: { by: string; at: string } | null;
  actions?: ReactNode;
  footer?: ReactNode;
}) {
  const k = KIND[flag.kind] ?? { severity: "info" as const, label: flag.kind, icon: <Info /> };
  return (
    <Alert severity={k.severity} icon={k.icon} variant="outlined" sx={{ "& .MuiAlert-message": { width: "100%" } }}>
      <AlertTitle>
        <Typography component="span" variant="overline" sx={{ display: "block", lineHeight: 1.4 }}>
          {k.label}
        </Typography>
        {flag.title}
      </AlertTitle>
      <Typography variant="body2">{flag.message}</Typography>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2} sx={{ mt: 1 }} flexWrap="wrap" useFlexGap>
        {flag.medication && (
          <Typography variant="body2">
            <strong>Medicine:</strong> {flag.medication}
            {flag.drug_class_label || flag.drug_class ? ` (${(flag.drug_class_label ?? flag.drug_class ?? "").toLowerCase()})` : ""}
          </Typography>
        )}
        {flag.source_label && (
          <Typography variant="body2">
            <strong>Recorded by:</strong> {flag.source_label}
          </Typography>
        )}
        {flag.rule_id && (
          <Typography variant="body2">
            <strong>Rule:</strong> {flag.rule_id}
            {flag.rule_version ? ` v${flag.rule_version}` : ""}
          </Typography>
        )}
      </Stack>
      {acknowledged && (
        <Typography variant="body2" sx={{ mt: 1 }}>
          <strong>Reviewed</strong> by {acknowledged.by}, {fmtDate(acknowledged.at)}
        </Typography>
      )}
      {footer && <Box sx={{ mt: 1 }}>{footer}</Box>}
      {actions && (
        <Stack direction="row" spacing={1} sx={{ mt: 1.5 }}>
          {actions}
        </Stack>
      )}
      <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>
        Reviewed means the doctor has seen this for this patient. It is not treatment clearance and never advises changing a medicine.
      </Typography>
    </Alert>
  );
}
