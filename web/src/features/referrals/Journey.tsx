import { KeyboardEvent, useRef } from "react";
import { Box, Button, ButtonBase, Paper, Stack, Typography } from "@mui/material";
import ArrowBack from "@mui/icons-material/ArrowBack";
import ArrowForward from "@mui/icons-material/ArrowForward";
import type { ReferralDetail } from "../../api/types";
import { tokens } from "../../theme";
import { AUDIT_STEP, computeSteps, NextStep, PHASES, STATE_LABEL, StepKey, StepState, STEP_LABEL, STEP_ORDER } from "./steps";

const STATE_TEXT: Record<StepState, string> = {
  done: tokens.ok.text,
  attention: tokens.warn.text,
  todo: tokens.muted,
  waiting: tokens.info.text,
  optional: tokens.muted,
  later: tokens.muted,
  ended: tokens.muted,
};

function Marker({ n, state }: { n: number; state: StepState }) {
  const filled = state === "done";
  const alert = state === "attention";
  return (
    <Box
      aria-hidden
      sx={{
        width: 28,
        height: 28,
        flexShrink: 0,
        display: "grid",
        placeItems: "center",
        borderRadius: 1,
        fontWeight: 700,
        fontSize: "0.875rem",
        border: "1px solid",
        borderColor: filled ? tokens.brand : alert ? tokens.warn.text : tokens.field,
        backgroundColor: filled ? tokens.brand : alert ? tokens.warn.bg : "transparent",
        color: filled ? tokens.surface : alert ? tokens.warn.text : tokens.muted,
      }}
    >
      {n}
    </Box>
  );
}

/**
 * The referral journey: every section of a referral in workflow order, grouped by phase,
 * with a state for each so the user sees where they are and what is left.
 * It is a tab list, so the keyboard works as expected (arrow keys, Home, End).
 */
export function JourneyNav({ r, active, onSelect }: { r: ReferralDetail; active: StepKey; onSelect: (k: StepKey) => void }) {
  const steps = computeSteps(r);
  const refs = useRef<Partial<Record<StepKey, HTMLButtonElement | null>>>({});
  let counter = 0;

  const onKey = (e: KeyboardEvent<HTMLElement>, key: StepKey) => {
    const i = STEP_ORDER.indexOf(key);
    let n = i;
    if (e.key === "ArrowRight") n = (i + 1) % STEP_ORDER.length;
    else if (e.key === "ArrowLeft") n = (i - 1 + STEP_ORDER.length) % STEP_ORDER.length;
    else if (e.key === "Home") n = 0;
    else if (e.key === "End") n = STEP_ORDER.length - 1;
    else return;
    e.preventDefault();
    refs.current[STEP_ORDER[n]]?.focus();
  };

  const tab = (key: StepKey, label: string, n: number | null) => {
    const s = steps[key];
    const selected = active === key;
    return (
      <ButtonBase
        key={key}
        ref={(el) => {
          refs.current[key] = el;
        }}
        role="tab"
        id={`tab-${key}`}
        aria-selected={selected}
        aria-controls="journey-panel"
        tabIndex={selected ? 0 : -1}
        onClick={() => onSelect(key)}
        onKeyDown={(e) => onKey(e, key)}
        sx={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "flex-start",
          gap: 1.25,
          textAlign: "left",
          minWidth: { xs: "100%", sm: 168 },
          px: 1.5,
          py: 1,
          borderRadius: 1,
          border: "1px solid",
          borderColor: selected ? tokens.brand : tokens.line,
          outline: selected ? `1px solid ${tokens.brand}` : "none",
          backgroundColor: selected ? tokens.surface : "transparent",
          "&:hover": { backgroundColor: tokens.sunken },
        }}
      >
        {n !== null && <Marker n={n} state={s.state} />}
        <Box sx={{ minWidth: 0 }}>
          <Typography component="span" display="block" sx={{ fontWeight: selected ? 700 : 600, fontSize: "0.9375rem", color: tokens.ink }}>
            {label}
          </Typography>
          {(n !== null || s.note) && (
            <Typography component="span" display="block" sx={{ fontSize: "0.8125rem", lineHeight: 1.35, color: STATE_TEXT[s.state], fontWeight: s.state === "attention" ? 600 : 400 }}>
              {n !== null ? STATE_LABEL[s.state] : ""}
              {n !== null && s.note ? `: ${s.note}` : ""}
            </Typography>
          )}
        </Box>
      </ButtonBase>
    );
  };

  return (
    <Paper sx={{ p: 1.5, mb: 2 }} component="section" aria-label="Referral journey">
      <Box role="tablist" aria-label="Referral steps" sx={{ display: "flex", flexWrap: "wrap", gap: { xs: 1.5, md: 2.5 }, alignItems: "flex-start", overflow: "visible" }}>
        {PHASES.map((p) => (
          <Box key={p.title} sx={{ width: { xs: "100%", md: "auto" } }}>
            <Typography aria-hidden variant="overline" component="div" sx={{ color: tokens.muted, mb: 0.5 }}>
              {p.title}
            </Typography>
            <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>{p.steps.map(([key, label]) => tab(key, label, ++counter))}</Box>
          </Box>
        ))}
        <Box sx={{ width: { xs: "100%", md: "auto" }, ml: { md: "auto" } }}>
          <Typography aria-hidden variant="overline" component="div" sx={{ color: tokens.muted, mb: 0.5 }}>
            Record
          </Typography>
          {tab(AUDIT_STEP[0], AUDIT_STEP[1], null)}
        </Box>
      </Box>
    </Paper>
  );
}

/** One clear next action, so nobody has to work out where the referral stands. */
export function NextStepBanner({ step, onGo }: { step: NextStep; onGo: (k: StepKey) => void }) {
  const tone = step.tone === "warn" ? tokens.warn : step.tone === "ok" ? tokens.ok : tokens.info;
  return (
    <Paper component="section" aria-labelledby="next-step-title" sx={{ p: { xs: 2, md: 2.5 }, mb: 2, backgroundColor: tone.bg, borderColor: tone.text }}>
      <Stack direction={{ xs: "column", md: "row" }} spacing={2} justifyContent="space-between" alignItems={{ md: "center" }}>
        <Box sx={{ minWidth: 0 }}>
          <Typography variant="overline" component="div" sx={{ color: tone.text }}>
            Next step
          </Typography>
          <Typography variant="h6" component="h2" id="next-step-title">
            {step.heading}
          </Typography>
          <Typography variant="body2" sx={{ mt: 0.5, maxWidth: 760 }}>
            {step.body}
          </Typography>
        </Box>
        {step.tab && step.action && (
          <Button variant="contained" sx={{ flexShrink: 0 }} onClick={() => onGo(step.tab!)}>
            {step.action}
          </Button>
        )}
      </Stack>
    </Paper>
  );
}

/** Previous and next buttons at the end of each step keep the journey linear. */
export function StepPager({ active, onGo }: { active: StepKey; onGo: (k: StepKey) => void }) {
  const i = STEP_ORDER.indexOf(active);
  const prev = i > 0 ? STEP_ORDER[i - 1] : null;
  const next = i < STEP_ORDER.length - 1 ? STEP_ORDER[i + 1] : null;
  if (!prev && !next) return null;
  return (
    <Stack direction="row" justifyContent="space-between" spacing={1} sx={{ mt: 3 }}>
      {prev ? (
        <Button variant="outlined" startIcon={<ArrowBack />} onClick={() => onGo(prev)}>
          Previous: {STEP_LABEL[prev]}
        </Button>
      ) : (
        <span />
      )}
      {next ? (
        <Button variant="outlined" endIcon={<ArrowForward />} onClick={() => onGo(next)}>
          Next: {STEP_LABEL[next]}
        </Button>
      ) : (
        <span />
      )}
    </Stack>
  );
}
