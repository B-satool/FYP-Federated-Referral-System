import { ReactNode, useState } from "react";
import { Link as RouterLink } from "react-router-dom";
import {
  Alert,
  AlertTitle,
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Link,
  Paper,
  Skeleton,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import ArrowBack from "@mui/icons-material/ArrowBack";
import { errorMessage } from "../api/client";
import { usePageTitle } from "../hooks";
import { tokens } from "../theme";

export function fmtDate(value: string | null | undefined, withTime = true): string {
  if (!value) return "Not recorded";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return withTime
    ? d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })
    : d.toLocaleDateString(undefined, { dateStyle: "medium" });
}

/** Skeleton placeholder that keeps the page layout stable while data loads. */
export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <Box role="status" aria-live="polite" aria-busy="true" sx={{ py: 1 }}>
      <span className="sr-only">{label}</span>
      <Stack spacing={1.5} aria-hidden>
        <Skeleton variant="rounded" height={30} width="38%" />
        <Skeleton variant="rounded" height={96} />
        <Skeleton variant="rounded" height={96} />
      </Stack>
    </Box>
  );
}

export function ErrorAlert({ error, title }: { error: unknown; title?: string }) {
  if (!error) return null;
  const detail = (error as { detail?: { blockers?: { message: string; how: string }[] } }).detail;
  return (
    <Alert severity="error" sx={{ my: 1 }} role="alert">
      {title && <AlertTitle>{title}</AlertTitle>}
      {errorMessage(error)}
      {detail?.blockers && (
        <ul style={{ margin: "4px 0 0", paddingLeft: 18 }}>
          {detail.blockers.map((b, i) => (
            <li key={i}>
              {b.message}. <em>{b.how}.</em>
            </li>
          ))}
        </ul>
      )}
    </Alert>
  );
}

export function PageHeader({
  title,
  subtitle,
  actions,
  back,
}: {
  title: string;
  subtitle?: ReactNode;
  actions?: ReactNode;
  back?: { to: string; label: string };
}) {
  usePageTitle(title);
  return (
    <Box sx={{ mb: 3 }}>
      {back && (
        <Link component={RouterLink} to={back.to} underline="hover" sx={{ display: "inline-flex", alignItems: "center", gap: 0.5, mb: 1, fontSize: "0.875rem" }}>
          <ArrowBack fontSize="inherit" aria-hidden />
          {back.label}
        </Link>
      )}
      <Stack direction={{ xs: "column", md: "row" }} justifyContent="space-between" alignItems={{ md: "flex-end" }} spacing={1.5}>
        <Box sx={{ minWidth: 0 }}>
          <Typography variant="h5" component="h1" sx={{ overflowWrap: "anywhere" }}>
            {title}
          </Typography>
          {subtitle && (
            <Typography color="text.secondary" component="div" sx={{ mt: 0.5 }}>
              {subtitle}
            </Typography>
          )}
        </Box>
        {actions && (
          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
            {actions}
          </Stack>
        )}
      </Stack>
    </Box>
  );
}

/** A titled block of related content. Replaces ad hoc Paper + heading pairs. */
export function Section({
  title,
  description,
  actions,
  children,
  id,
}: {
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  id?: string;
}) {
  return (
    <Paper component="section" aria-labelledby={id ? `${id}-title` : undefined} sx={{ p: { xs: 2, md: 2.5 } }}>
      <Stack direction="row" justifyContent="space-between" alignItems="flex-start" spacing={2} sx={{ mb: description || children ? 1.5 : 0 }}>
        <Box>
          <Typography variant="h6" id={id ? `${id}-title` : undefined}>
            {title}
          </Typography>
          {description && (
            <Typography variant="body2" color="text.secondary" component="div">
              {description}
            </Typography>
          )}
        </Box>
        {actions && <Box sx={{ flexShrink: 0 }}>{actions}</Box>}
      </Stack>
      {children}
    </Paper>
  );
}

export type Tone = "ok" | "warn" | "bad" | "info" | "neutral" | "wait" | "off";
const toneStyle: Record<Tone, { text: string; bg: string; border: string; dashed?: boolean }> = {
  ok: { ...tokens.ok, border: tokens.ok.text },
  warn: { ...tokens.warn, border: tokens.warn.text },
  bad: { ...tokens.bad, border: tokens.bad.text },
  info: { ...tokens.info, border: tokens.info.text },
  neutral: { ...tokens.neutral, border: tokens.field },
  wait: { ...tokens.neutral, border: tokens.field },
  off: { ...tokens.neutral, border: tokens.field, dashed: true },
};

/** A status label. The meaning is always in the text; colour and border style only reinforce it. */
export function Tag({ tone, label, title }: { tone: Tone; label: string; title?: string }) {
  const t = toneStyle[tone];
  return (
    <Chip
      size="small"
      variant="outlined"
      label={label}
      title={title}
      sx={{ backgroundColor: t.bg, color: t.text, borderColor: t.border, borderStyle: t.dashed ? "dashed" : "solid", maxWidth: "100%" }}
    />
  );
}

const REFERRAL_TONES: Record<string, Tone> = {
  draft: "neutral",
  requested: "info",
  submitted: "ok",
  acknowledged: "ok",
  accepted: "ok",
  response_returned: "info",
  followup_pending: "warn",
  closed: "neutral",
  declined: "off",
  cancelled: "off",
};

export function ReferralStatus({ status, label }: { status: string; label?: string }) {
  return <Tag tone={REFERRAL_TONES[status] ?? "neutral"} label={label ?? status.replace(/_/g, " ")} />;
}

export function RetrievalStatus({ status }: { status: string }) {
  const tones: Record<string, Tone> = {
    successful: "ok",
    empty: "neutral",
    partial: "warn",
    denied: "off",
    unavailable: "bad",
    invalid: "bad",
    not_retrieved: "wait",
    skipped: "off",
  };
  const labels: Record<string, string> = { skipped: "not the most recent", successful: "retrieved" };
  return <Tag tone={tones[status] ?? "neutral"} label={labels[status] ?? status.replace(/_/g, " ")} />;
}

export function VerificationTag({ status, reviewState }: { status: string; reviewState?: string }) {
  if (reviewState === "unresolved") return <Tag tone="warn" label="unresolved" />;
  if (reviewState === "excluded") return <Tag tone="off" label="excluded" />;
  const map: Record<string, [Tone, string]> = {
    source_record: ["ok", "from the source"],
    verified: ["ok", "checked"],
    unverified: ["warn", "to check"],
    invalidated: ["off", "link invalidated"],
    access_revoked: ["off", "access revoked"],
  };
  const [tone, label] = map[status] ?? ["neutral", status];
  return <Tag tone={tone} label={label} />;
}

export function ReasonDialog({
  open,
  title,
  label,
  confirm,
  onClose,
  onConfirm,
  minLength = 3,
  busy,
  children,
}: {
  open: boolean;
  title: string;
  label: string;
  confirm: string;
  onClose: () => void;
  onConfirm: (text: string) => void;
  minLength?: number;
  busy?: boolean;
  children?: ReactNode;
}) {
  const [text, setText] = useState("");
  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>{title}</DialogTitle>
      <DialogContent>
        {children}
        <TextField
          autoFocus
          fullWidth
          multiline
          minRows={3}
          margin="dense"
          label={label}
          value={text}
          onChange={(e) => setText(e.target.value)}
          helperText={text.trim().length < minLength ? `At least ${minLength} characters` : " "}
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button
          variant="contained"
          disabled={busy || text.trim().length < minLength}
          onClick={() => {
            onConfirm(text.trim());
            setText("");
          }}
        >
          {confirm}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export function KeyValue({ items }: { items: [string, ReactNode][] }) {
  return (
    <Box component="dl" sx={{ display: "grid", gridTemplateColumns: "max-content 1fr", columnGap: 2, rowGap: 0.75, m: 0 }}>
      {items.map(([k, v]) => (
        <Box key={k} sx={{ display: "contents" }}>
          <Typography component="dt" color="text.secondary" variant="body2">
            {k}
          </Typography>
          <Typography component="dd" variant="body2" sx={{ m: 0, wordBreak: "break-word" }}>
            {v ?? "Not recorded"}
          </Typography>
        </Box>
      ))}
    </Box>
  );
}

const ORDER_TONES: Record<string, Tone> = {
  draft: "neutral",
  requested: "wait",
  accepted: "info",
  scheduled: "info",
  done: "info",
  reported: "ok",
  rejected: "bad",
  cancelled: "off",
};
const ORDER_LABELS: Record<string, string> = { draft: "not sent yet", reported: "result ready" };

/** Status of a test or scan order (draft -> requested -> accepted/rejected -> scheduled -> done -> reported). */
export function OrderStatus({ status }: { status: string }) {
  return <Tag tone={ORDER_TONES[status] ?? "neutral"} label={ORDER_LABELS[status] ?? status} />;
}

export function UrgencyTag({ urgency, label }: { urgency: string; label?: string }) {
  const tone: Tone = urgency === "urgent" ? "bad" : urgency === "soon" ? "warn" : "neutral";
  return <Tag tone={tone} label={label ?? urgency} />;
}

export function Empty({ children }: { children: ReactNode }) {
  return (
    <Typography color="text.secondary" sx={{ py: 2 }}>
      {children}
    </Typography>
  );
}
