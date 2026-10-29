import { ReactNode, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Box, Button, Checkbox, FormControlLabel, Radio, RadioGroup, TextField, Typography } from "@mui/material";
import { api, errorMessage } from "../../api/client";
import { ErrorAlert, fmtDate, Loading, Tag } from "../../components/common";
import { useDeviceKeys } from "../../crypto/session";
import { signObject } from "../../crypto/suite";
import { tokens } from "../../theme";
import { DeviceKeyPanel } from "../keys/DeviceKey";

/**
 * The patient's permissions (spec v4 6.4). Staff ask; only the patient answers, here. Granting and revoking are
 * signed on this device with the patient's own key, and each hospital, clinic or laboratory checks the signature
 * itself before releasing anything.
 */

type Place = { institution_id: string; name: string };
export type ConsentRequest = {
  reference: string; referral_reference: string | null; status: string; purpose: string;
  requesting_org_name: string; requesting_practitioner: string; destination_name: string | null;
  custodians_requested: Place[]; custodians_granted: Place[]; categories: string[]; sensitive_offered: string[];
  sensitive_specific: string[]; data_period_start: string | null; requested_by: string; requested_at: string;
  period_start: string | null; period_end: string | null; decided_at: string | null; revoked_at: string | null;
  durations: number[]; sensitive_labels: Record<string, string>;
};

const STATUS: Record<string, [string, "ok" | "warn" | "off" | "bad" | "info"]> = {
  requested: ["Waiting for your answer", "warn"], granted: ["You agreed", "ok"], declined: ["You said no", "off"],
  revoked: ["You withdrew it", "off"], expired: ["Ended", "off"],
};
const DURATION_LABEL: Record<number, string> = { 1: "1 day", 7: "1 week", 30: "30 days" };
const CATEGORY_LABEL: Record<string, string> = {
  conditions: "Diagnoses", surgeries: "Operations", visits: "Visits", medications: "Medicines", labs: "Test results",
  imaging: "Scans",
};

export function useConsents() {
  return useQuery({ queryKey: ["patient", "consents"], queryFn: () => api.get<ConsentRequest[]>("/patient-access/consents") });
}

export function usePendingConsents(): ConsentRequest[] {
  return (useConsents().data ?? []).filter((c) => c.status === "requested");
}

function Box1({ children }: { children: ReactNode }) {
  return <Box sx={{ p: 1.5, mb: 1.25, bgcolor: tokens.surface, border: `1px solid ${tokens.line}`, borderRadius: 2 }}>{children}</Box>;
}

export function ConsentTab({ onOpen }: { onOpen: (reference: string) => void }) {
  const q = useConsents();
  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorAlert error={q.error} />;
  const rows = q.data ?? [];
  return (
    <>
      <Typography component="h2" sx={{ fontSize: "1.0625rem", fontWeight: 700, mb: 1 }}>Your permissions</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
        A clinic asks here before it fetches your records from other places. Only you can say yes, and you can withdraw it later.
      </Typography>
      {!rows.length && <Typography variant="body2" color="text.secondary">No requests yet.</Typography>}
      {rows.map((c) => {
        const [label, tone] = STATUS[c.status] ?? [c.status, "info"];
        return (
          <Box key={c.reference} role="button" tabIndex={0} onClick={() => onOpen(c.reference)}
            onKeyDown={(e) => e.key === "Enter" && onOpen(c.reference)} sx={{ cursor: "pointer" }}>
            <Box1>
              <Box sx={{ display: "flex", justifyContent: "space-between", gap: 1 }}>
                <Typography sx={{ fontWeight: 600 }}>{c.requesting_org_name}</Typography>
                <Tag tone={tone} label={label} />
              </Box>
              <Typography variant="body2" color="text.secondary">
                For referral {c.referral_reference ?? ""}{c.destination_name ? ` to ${c.destination_name}` : ""} · asked {fmtDate(c.requested_at, false)}
              </Typography>
              {c.status === "granted" && c.period_end && <Typography variant="body2">Until {fmtDate(c.period_end)}</Typography>}
            </Box1>
          </Box>
        );
      })}
    </>
  );
}

export function ConsentDetail({ reference, onBack }: { reference: string; onBack: () => void }) {
  const q = useConsents();
  const qc = useQueryClient();
  const dk = useDeviceKeys();
  const c = (q.data ?? []).find((x) => x.reference === reference);
  const [places, setPlaces] = useState<string[] | null>(null);
  const [sensitive, setSensitive] = useState<string[]>([]);
  const [days, setDays] = useState(7);
  const [declineReason, setDeclineReason] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const done = () => qc.invalidateQueries({ queryKey: ["patient", "consents"] });
  const grant = useMutation({
    mutationFn: async () => {
      if (!c || !dk.keys) throw new Error("Unlock your device key first");
      const chosen = places ?? c.custodians_requested.map((p) => p.institution_id);
      const doc = await api.post<Record<string, unknown>>(`/patient-access/consents/${reference}/prepare`,
        { custodians: chosen, sensitive, duration_days: days });
      const signed = await signObject(dk.keys.sigPrivate, doc);
      return api.post(`/patient-access/consents/${reference}/decision`, { decision: "grant", document: signed });
    },
    meta: { success: "Thank you. Your permission was signed on this phone and sent." },
    onSuccess: done, onError: (e) => setErr(errorMessage(e)),
  });
  const decline = useMutation({
    mutationFn: () => api.post(`/patient-access/consents/${reference}/decision`, { decision: "decline", reason: declineReason }),
    meta: { success: "You said no. The clinic has been told." }, onSuccess: done,
  });
  const revoke = useMutation({
    mutationFn: async () => {
      if (!dk.keys) throw new Error("Unlock your device key first");
      const revocation = await signObject(dk.keys.sigPrivate, { type: "refx.consent.revocation/v1", consent: reference,
        revoked_at: new Date().toISOString() });
      return api.post(`/patient-access/consents/${reference}/revoke`, { revocation });
    },
    meta: { success: "Permission withdrawn. No more records will be released for this referral." },
    onSuccess: done, onError: (e) => setErr(errorMessage(e)),
  });
  if (q.isLoading) return <Loading />;
  if (!c) return <><Button size="small" onClick={onBack}>‹ Back</Button><Alert severity="info">Not found.</Alert></>;
  const chosen = places ?? c.custodians_requested.map((p) => p.institution_id);
  const toggle = (list: string[], v: string) => (list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);
  const [label, tone] = STATUS[c.status] ?? [c.status, "info"];
  return (
    <>
      <Button size="small" onClick={onBack} sx={{ mb: 1, px: 0 }}>‹ Back</Button>
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 1 }}>
        <Typography component="h2" sx={{ fontSize: "1.125rem", fontWeight: 700 }}>Permission {c.reference}</Typography>
        <Tag tone={tone} label={label} />
      </Box>
      <Box1>
        <Typography variant="body2" color="text.secondary">Who asks</Typography>
        <Typography>{c.requesting_org_name}, for {c.requesting_practitioner} (asked by {c.requested_by})</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>Why</Typography>
        <Typography>Referral {c.referral_reference}{c.destination_name ? ` to ${c.destination_name}` : ""}: treatment and referral</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>What</Typography>
        <Typography>{c.categories.map((k) => CATEGORY_LABEL[k] ?? k).join(", ")}{c.data_period_start ? ` from ${fmtDate(c.data_period_start, false)}` : ""}</Typography>
      </Box1>
      {c.status === "requested" && (
        <>
          {dk.status !== "unlocked" && <DeviceKeyPanel compact />}
          <Typography sx={{ fontWeight: 700, mt: 1 }}>Which places may send your records?</Typography>
          {c.custodians_requested.map((p) => (
            <FormControlLabel key={p.institution_id} label={p.name}
              control={<Checkbox checked={chosen.includes(p.institution_id)} onChange={() => setPlaces(toggle(chosen, p.institution_id))} />} />
          ))}
          <Typography sx={{ fontWeight: 700, mt: 1 }}>Sensitive records</Typography>
          <Typography variant="body2" color="text.secondary">Not sent unless you tick them here.</Typography>
          {c.sensitive_offered.map((k) => (
            <FormControlLabel key={k} label={c.sensitive_labels[k] ?? k}
              control={<Checkbox checked={sensitive.includes(k)} onChange={() => setSensitive(toggle(sensitive, k))} />} />
          ))}
          <Typography sx={{ fontWeight: 700, mt: 1 }}>For how long?</Typography>
          <RadioGroup row value={days} onChange={(e) => setDays(Number(e.target.value))}>
            {c.durations.map((d) => <FormControlLabel key={d} value={d} control={<Radio />} label={DURATION_LABEL[d] ?? `${d} days`} />)}
          </RadioGroup>
          {err && <Alert severity="error" sx={{ my: 1 }}>{err}</Alert>}
          <Button fullWidth variant="contained" sx={{ mt: 1 }} disabled={!chosen.length || dk.status !== "unlocked" || grant.isPending}
            onClick={() => { setErr(null); grant.mutate(); }}>
            Agree and sign
          </Button>
          <TextField fullWidth size="small" label="Reason for saying no (optional)" value={declineReason}
            onChange={(e) => setDeclineReason(e.target.value)} sx={{ mt: 2 }} />
          <Button fullWidth variant="outlined" color="warning" sx={{ mt: 1 }} onClick={() => decline.mutate()} disabled={decline.isPending}>
            Say no
          </Button>
        </>
      )}
      {c.status === "granted" && (
        <>
          <Box1>
            <Typography variant="body2" color="text.secondary">You agreed for</Typography>
            <Typography>{c.custodians_granted.map((p) => p.name).join(", ")}</Typography>
            {c.sensitive_specific.length > 0 && <Typography variant="body2">Including: {c.sensitive_specific.map((k) => c.sensitive_labels[k] ?? k).join(", ")}</Typography>}
            <Typography variant="body2">From {fmtDate(c.period_start)} until {fmtDate(c.period_end)}</Typography>
          </Box1>
          <Alert severity="info" sx={{ mb: 1 }}>
            Withdrawing stops any further release. It cannot take back records a doctor has already opened on their device.
          </Alert>
          {dk.status !== "unlocked" && <DeviceKeyPanel compact />}
          {err && <Alert severity="error" sx={{ my: 1 }}>{err}</Alert>}
          <Button fullWidth variant="outlined" color="warning" disabled={dk.status !== "unlocked" || revoke.isPending}
            onClick={() => { setErr(null); revoke.mutate(); }}>
            Withdraw permission
          </Button>
        </>
      )}
    </>
  );
}
