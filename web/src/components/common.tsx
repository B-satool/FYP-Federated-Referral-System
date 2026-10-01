import { ReactNode, useState } from "react";
import {
  Alert,
  AlertTitle,
  Box,
  Button,
  Chip,
  ChipProps,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import CheckCircleOutline from "@mui/icons-material/CheckCircleOutline";
import ErrorOutline from "@mui/icons-material/ErrorOutline";
import HelpOutline from "@mui/icons-material/HelpOutline";
import HourglassEmpty from "@mui/icons-material/HourglassEmpty";
import Block from "@mui/icons-material/Block";
import WarningAmber from "@mui/icons-material/WarningAmber";
import RemoveCircleOutline from "@mui/icons-material/RemoveCircleOutline";
import CloudOff from "@mui/icons-material/CloudOff";
import { errorMessage } from "../api/client";

export function fmtDate(value: string | null | undefined, withTime = true): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return withTime
    ? d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })
    : d.toLocaleDateString(undefined, { dateStyle: "medium" });
}

export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <Stack direction="row" spacing={1.5} alignItems="center" sx={{ p: 3 }} role="status" aria-live="polite">
      <CircularProgress size={20} />
      <Typography color="text.secondary">{label}</Typography>
    </Stack>
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
              {b.message} — <em>{b.how}</em>
            </li>
          ))}
        </ul>
      )}
    </Alert>
  );
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <Stack direction={{ xs: "column", md: "row" }} justifyContent="space-between" alignItems={{ md: "center" }} spacing={1} sx={{ mb: 2 }}>
      <Box>
        <Typography variant="h5" component="h1">
          {title}
        </Typography>
        {subtitle && (
          <Typography color="text.secondary" component="div">
            {subtitle}
          </Typography>
        )}
      </Box>
      {actions && <Stack direction="row" spacing={1} flexWrap="wrap">{actions}</Stack>}
    </Stack>
  );
}

type Tone = "ok" | "warn" | "bad" | "info" | "neutral" | "wait" | "off";
const toneProps: Record<Tone, { color: ChipProps["color"]; icon: JSX.Element }> = {
  ok: { color: "success", icon: <CheckCircleOutline /> },
  warn: { color: "warning", icon: <WarningAmber /> },
  bad: { color: "error", icon: <ErrorOutline /> },
  info: { color: "info", icon: <HelpOutline /> },
  neutral: { color: "default", icon: <RemoveCircleOutline /> },
  wait: { color: "default", icon: <HourglassEmpty /> },
  off: { color: "default", icon: <Block /> },
};

/** A status label that never relies on colour alone (icon + text). */
export function Tag({ tone, label, title }: { tone: Tone; label: string; title?: string }) {
  const p = toneProps[tone];
  return <Chip size="small" variant="outlined" color={p.color} icon={p.icon} label={label} title={title} />;
}

const REFERRAL_TONES: Record<string, Tone> = {
  draft: "neutral",
  awaiting_information: "warn",
  awaiting_approval: "info",
  approved: "ok",
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
  };
  const icon = status === "unavailable" ? <CloudOff /> : undefined;
  if (icon) return <Chip size="small" variant="outlined" color="error" icon={icon} label="unavailable" />;
  return <Tag tone={tones[status] ?? "neutral"} label={status.replace(/_/g, " ")} />;
}

export function VerificationTag({ status, reviewState }: { status: string; reviewState?: string }) {
  if (reviewState === "unresolved") return <Tag tone="warn" label="unresolved" />;
  if (reviewState === "excluded") return <Tag tone="off" label="excluded" />;
  const map: Record<string, [Tone, string]> = {
    source_record: ["ok", "source record"],
    verified: ["ok", "clinician-verified"],
    unverified: ["warn", "unverified"],
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
            {v ?? "—"}
          </Typography>
        </Box>
      ))}
    </Box>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return (
    <Typography color="text.secondary" sx={{ py: 2 }}>
      {children}
    </Typography>
  );
}
