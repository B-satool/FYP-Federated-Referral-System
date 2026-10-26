import { ReactNode } from "react";
import { Alert, AlertTitle, Box, Stack, Typography } from "@mui/material";
import Medication from "@mui/icons-material/Medication";
import HelpOutline from "@mui/icons-material/HelpOutline";
import ReportProblemOutlined from "@mui/icons-material/ReportProblemOutlined";
import CompareArrows from "@mui/icons-material/CompareArrows";
import Description from "@mui/icons-material/DescriptionOutlined";
import Info from "@mui/icons-material/InfoOutlined";
import type { FlagDecision, FlagSource } from "../api/types";
import { fmtDate, Tag, Tone } from "./common";

export type FlagLike = FlagSource & {
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
  confirmed: { severity: "error", label: "Medication flag (approved rule)", icon: <Medication /> },
  interaction: { severity: "warning", label: "Drug interaction", icon: <CompareArrows /> },
  label_warning: { severity: "warning", label: "Drug label", icon: <Description /> },
  unrecognised_medicine: { severity: "warning", label: "Medicine not recognised", icon: <HelpOutline /> },
  interactions_not_checked: { severity: "info", label: "Not checked", icon: <HelpOutline /> },
  procedure_not_checked: { severity: "warning", label: "Procedure not checked", icon: <HelpOutline /> },
  records_incomplete: { severity: "info", label: "Records incomplete", icon: <ReportProblemOutlined /> },
};

const SEVERITY_TONE: Record<string, Tone> = { Major: "bad", high: "bad", Moderate: "warn", moderate: "warn", Minor: "neutral", low: "neutral", Unknown: "neutral" };
const SEVERITY_TEXT: Record<string, string> = { Unknown: "severity not graded", high: "boxed warning or contraindication", moderate: "warning", low: "precaution" };
const DECISION_TEXT: Record<FlagDecision, string> = { reviewed: "Reviewed", ignore: "Ignored (not relevant for this patient)", research: "Research (needs follow-up)" };

/** Where a flag came from: approved manual rule, DDInter, or a drug label (with the exact sentence). */
export function FlagSourceLine({ flag }: { flag: FlagSource & { rule_id?: string | null; rule_version?: number | null } }) {
  if (!flag.source_type || flag.source_type === "system") return null;
  return (
    <Box sx={{ mt: 1 }}>
      <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap alignItems="center">
        {flag.auto_generated ? <Tag tone="warn" label="Automatically generated, not clinically reviewed" /> : <Tag tone="ok" label="Approved by a clinical reviewer" />}
        {flag.severity && (
          <Tag tone={SEVERITY_TONE[flag.severity] ?? "neutral"} label={`${flag.source_type === "drug_label" ? "Label" : "Severity"}: ${SEVERITY_TEXT[flag.severity] ?? flag.severity.toLowerCase()}`} />
        )}
      </Stack>
      <Typography variant="body2" sx={{ mt: 0.75 }}>
        <strong>Source:</strong> {flag.source_name}
        {flag.source_version ? `, ${flag.source_version}` : ""}
        {flag.source_type === "ddinter" && flag.source_ref ? ` (entry ${flag.source_ref})` : ""}
        {flag.source_type === "drug_label" && flag.source_ref ? (
          <>
            {" "}(<a href={`https://dailymed.nlm.nih.gov/dailymed/lookup.cfm?setid=${flag.source_ref}`} target="_blank" rel="noopener noreferrer">open the label</a>)
          </>
        ) : null}
      </Typography>
      {flag.source_quote && (
        <Box component="blockquote" sx={{ m: 0, mt: 0.75, pl: 1.5, borderLeft: "3px solid", borderColor: "divider" }}>
          <Typography variant="body2" sx={{ fontStyle: "italic" }}>
            "{flag.source_quote}"
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Quoted from the US drug label for reference. It is the label's wording, not advice from this platform.
          </Typography>
        </Box>
      )}
    </Box>
  );
}

/** A flag shown as structured data with its source. The kind is in the text and icon, not colour alone. */
export function FlagCard({
  flag,
  acknowledged,
  actions,
  footer,
}: {
  flag: FlagLike;
  acknowledged?: { by: string; at: string; decision?: FlagDecision; note?: string } | null;
  actions?: ReactNode;
  footer?: ReactNode;
}) {
  const k = KIND[flag.kind] ?? { severity: "info" as const, label: flag.kind, icon: <Info /> };
  const severity = flag.kind === "interaction" && flag.severity !== "Major" ? "info" : flag.kind === "label_warning" && flag.severity !== "high" ? "info" : k.severity;
  return (
    <Alert severity={severity} icon={k.icon} variant="outlined" sx={{ "& .MuiAlert-message": { width: "100%" } }}>
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
        {!!flag.ingredients?.length && flag.kind !== "confirmed" && (
          <Typography variant="body2">
            <strong>Ingredients:</strong> {flag.ingredients.join(", ")}
          </Typography>
        )}
        {flag.source_label && (
          <Typography variant="body2">
            <strong>Recorded by:</strong> {flag.source_label}
          </Typography>
        )}
      </Stack>
      <FlagSourceLine flag={flag} />
      {acknowledged && (
        <Typography variant="body2" sx={{ mt: 1 }}>
          <strong>{DECISION_TEXT[acknowledged.decision ?? "reviewed"]}</strong> by {acknowledged.by}, {fmtDate(acknowledged.at)}
          {acknowledged.note ? `: ${acknowledged.note}` : ""}
        </Typography>
      )}
      {footer && <Box sx={{ mt: 1 }}>{footer}</Box>}
      {actions && (
        <Stack direction="row" spacing={1} sx={{ mt: 1.5 }} flexWrap="wrap" useFlexGap>
          {actions}
        </Stack>
      )}
    </Alert>
  );
}
