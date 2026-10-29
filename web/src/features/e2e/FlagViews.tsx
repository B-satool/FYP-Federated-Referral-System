/**
 * Medication flags on screen (spec v4 9.5): each flag shows the medicines, the explanation, its source (or "AI
 * suggestion, not verified"), "automatically generated, not clinically reviewed", and Ignore / Research. Both clicks
 * are logged (who, which flag, what, when); there is no confirmation step. Nothing here advises a change or says safe.
 */
import { Alert, AlertTitle, Box, Button, Chip, Paper, Stack, Typography } from "@mui/material";
import { api } from "../../api/client";
import { Empty } from "../../components/common";
import { sha256Hex } from "../../crypto/suite";
import type { Evaluation, Flag } from "./flags";

export type Decision = "ignore" | "research";
export type AiFlag = { drug: string; other_drug_or_procedure: string; concern: string; severity_estimate: string; reason: string;
  confidence: string; evidence_hint: string | null; about: "medicine" | "procedure"; label: string };

/** Logged with a hash of the flag key: the audit trail holds ids and hashes, never medicine names (spec v4 11.5). */
export function logDecision(referral: number | string, flagKey: string, layer: 1 | 2, decision: Decision) {
  void sha256Hex(flagKey).then((h) => api.post("/e2e/client-events", { action: `flag.${decision}`, target_type: "flag",
    target_id: h.slice(0, 16), referral_id: typeof referral === "number" ? referral : null,
    detail: { flag_key: h, layer } })).catch(() => undefined);
}

function researchUrl(f: Flag): string {
  const first = f.sourceRef.split("-")[0];
  return first.startsWith("DDInter") ? `${f.sourceUrl}/ddinter/drug-detail/${first}/` : f.sourceUrl;
}

function Buttons({ referral, flagKey, layer, decided, onDecide, research }: {
  referral: number | string; flagKey: string; layer: 1 | 2; decided?: Decision; onDecide: (d: Decision) => void; research: string;
}) {
  const click = (d: Decision) => {
    logDecision(referral, flagKey, layer, d);
    onDecide(d);
    if (d === "research") window.open(research, "_blank", "noopener");
  };
  return (
    <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
      <Button size="small" variant={decided === "ignore" ? "contained" : "outlined"} onClick={() => click("ignore")}>Ignore</Button>
      <Button size="small" variant={decided === "research" ? "contained" : "outlined"} onClick={() => click("research")}>Research</Button>
      {decided && <Typography variant="caption" color="text.secondary" sx={{ alignSelf: "center" }}>
        {decided === "ignore" ? "Ignored by you (logged). This is your acknowledgment, not treatment clearance." : "Marked for research (logged)."}
      </Typography>}
    </Stack>
  );
}

const TONE: Record<string, "error" | "warning" | "info" | "default"> = { Major: "error", Moderate: "warning", Minor: "info", high: "error", moderate: "warning", low: "info" };

export function Layer1Flags({ ev, referral, decisions, onDecide }: {
  ev: Evaluation; referral: number | string; decisions: Record<string, Decision>; onDecide?: (key: string, d: Decision) => void;
}) {
  return (
    <Stack spacing={1.5}>
      {!ev.flags.length && <Empty>No pair on file in the interaction data for the medicines that could be checked. This is not treatment clearance, and medicines that could not be assessed are listed separately.</Empty>}
      {ev.flags.map((f) => (
        <Paper key={f.key} variant="outlined" sx={{ p: 1.5 }} data-testid="flag">
          <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
            <Typography variant="subtitle2">{f.meds[0]} and {f.meds[1]}</Typography>
            <Chip size="small" color={TONE[f.severity] ?? "default"} label={f.severity === "Unknown" ? "severity not stated" : f.severity} />
            <Chip size="small" variant="outlined" label="automatically generated, not clinically reviewed" />
            {f.approximate && <Chip size="small" color="warning" variant="outlined" label="name matched approximately" />}
          </Stack>
          <Typography variant="body2" sx={{ mt: 0.5 }}>
            {f.ingredients[0]} with {f.ingredients[1]}: listed as an interaction in {f.source} ({f.sourceRef}{f.datasetVersion ? `, ${f.datasetVersion}` : ""}).
          </Typography>
          {f.quote && <Typography variant="body2" sx={{ mt: 0.5, fontStyle: "italic" }}>“{f.quote}” {f.labelSource ? `(${f.labelSource})` : ""}</Typography>}
          {onDecide && <Buttons referral={referral} flagKey={f.key} layer={1} decided={decisions[f.key]} onDecide={(d) => onDecide(f.key, d)} research={researchUrl(f)} />}
        </Paper>
      ))}
    </Stack>
  );
}

export function NotAssessed({ ev }: { ev: Evaluation }) {
  if (!ev.notAssessed.length) return null;
  return (
    <Alert severity="warning">
      <AlertTitle>Could not be assessed</AlertTitle>
      <Box component="ul" sx={{ m: 0, pl: 2.5 }}>
        {ev.notAssessed.map(({ med, reason }) => <li key={med.id}><b>{med.name}</b>: {reason}{med.mapping.note && med.mapping.status !== "unmapped" ? `. ${med.mapping.note}` : ""}</li>)}
      </Box>
      Not assessed is not "no issues". You can ask the AI about these below.
    </Alert>
  );
}

export function Layer2Flags({ items, referral, decisions, onDecide }: {
  items: AiFlag[]; referral: number | string; decisions: Record<string, Decision>; onDecide: (key: string, d: Decision) => void;
}) {
  if (!items.length) return <Empty>The AI suggested nothing further. This is not treatment clearance.</Empty>;
  return (
    <Stack spacing={1.5}>
      {items.map((s) => {
        const key = `ai|${s.drug}|${s.other_drug_or_procedure}`.toLowerCase();
        return (
          <Paper key={key} variant="outlined" sx={{ p: 1.5, borderStyle: "dashed" }} data-testid="ai-flag">
            <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
              <Typography variant="subtitle2">{s.drug} {s.about === "procedure" ? "and the procedure" : "and"} {s.about === "procedure" ? `(${s.other_drug_or_procedure})` : s.other_drug_or_procedure}</Typography>
              <Chip size="small" color="warning" label={s.label} />
              <Chip size="small" variant="outlined" label={`estimated ${s.severity_estimate}, confidence ${s.confidence}`} />
            </Stack>
            <Typography variant="body2" sx={{ mt: 0.5 }}><b>{s.concern}.</b> {s.reason}</Typography>
            {s.evidence_hint && <Typography variant="caption" color="text.secondary">Where to check: {s.evidence_hint}</Typography>}
            <Buttons referral={referral} flagKey={key} layer={2} decided={decisions[key]} onDecide={(d) => onDecide(key, d)}
              research={`https://dailymed.nlm.nih.gov/dailymed/search.cfm?query=${encodeURIComponent(s.drug)}`} />
          </Paper>
        );
      })}
    </Stack>
  );
}
