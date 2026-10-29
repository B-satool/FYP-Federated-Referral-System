import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Alert, Box, Button, Checkbox, Chip, Collapse, FormControlLabel, FormGroup, IconButton, Stack, Table, TableBody,
  TableCell, TableHead, TableRow, Typography } from "@mui/material";
import ExpandMore from "@mui/icons-material/ExpandMore";
import { api } from "../../api/client";
import type { RecordRequestOut, ReferralDetail } from "../../api/types";
import { Empty, ErrorAlert, fmtDate, Loading, Section, Tag, Tone } from "../../components/common";
import { useDeviceKeys } from "../../crypto/session";
import { DeviceKeyPanel } from "../keys/DeviceKey";
import { CATEGORY_GROUPS, EncryptedResponse, latestById, openAll, OpenedItem, reportOpened, summary, Title } from "../e2e/records";
import { floor, isSelected, loadChoices, saveChoices } from "../e2e/selection";
import { OtherPlaces } from "./LinksTab";
import { useInvalidateReferral } from "./ReferralWorkspace";

const STATUS_TONE: Record<RecordRequestOut["status"], Tone> = {
  sent: "wait", answered: "ok", partial: "warn", refused: "bad", pending_manual_review: "wait", no_records: "neutral",
  unavailable: "bad", not_linked: "warn", failed: "bad",
};
const REASON_TEXT: Record<string, string> = {
  prohibited_by_law: "The law does not allow it",
  sensitive_category_no_specific_consent: "Sensitive: needs the patient's specific consent",
  request_incomplete_or_invalid: "Request incomplete or invalid",
  consent_expired_or_out_of_range: "Consent expired or does not cover it",
  pending_manual_review: "Waiting for their staff to review",
};

/** Each institution's answer. Refused, waiting or unreachable is said as such, never as "no records" (T-REFUSAL-1). */
export function SourceOutcomes({ r }: { r: ReferralDetail }) {
  const rows = r.record_requests;
  if (!rows.length) return <Empty>No records requested yet.</Empty>;
  return (
    <Table size="small">
      <TableHead>
        <TableRow><TableCell>Institution</TableCell><TableCell>Outcome</TableCell><TableCell>Records</TableCell><TableCell>When</TableCell></TableRow>
      </TableHead>
      <TableBody>
        {rows.map((x) => (
          <TableRow key={x.id} data-testid={`outcome-${x.custodian}`}>
            <TableCell>{x.custodian_name}</TableCell>
            <TableCell>
              <Tag tone={STATUS_TONE[x.status]} label={x.status_text} />
              {x.refusals.map((f, i) => (
                <Typography key={i} variant="body2" sx={{ mt: 0.5 }}>
                  <b>{REASON_TEXT[f.reason] ?? f.reason}</b>{f.categories.length ? ` (${f.categories.join(", ")})` : ""}: {f.message}
                </Typography>
              ))}
              {["unavailable", "not_linked", "failed"].includes(x.status) && <Typography variant="body2" sx={{ mt: 0.5 }}>{x.message}</Typography>}
            </TableCell>
            <TableCell>{x.status === "no_records" ? "None matching" : x.item_count || (["answered", "partial"].includes(x.status) ? 0 : "–")}</TableCell>
            <TableCell>{fmtDate(x.answered_at ?? x.requested_at)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

const CONSENT_TEXT: Record<string, [string, Tone]> = {
  requested: ["Waiting for the patient", "wait"], granted: ["Patient agreed", "ok"], declined: ["Patient declined", "bad"],
  revoked: ["Patient withdrew consent", "bad"], expired: ["Consent ended", "warn"], withdrawn: ["Replaced", "off"],
};

/** Staff ask the patient (in the patient portal) for consent; only the patient can give it. */
export function ConsentPanel({ r, staff }: { r: ReferralDetail; staff: boolean }) {
  const refresh = useInvalidateReferral(r.id);
  const linkable = r.sources.filter((s) => s.linked);
  const [chosen, setChosen] = useState<string[] | null>(null);
  const picked = chosen ?? linkable.map((s) => s.institution_id);
  const ask = useMutation({
    mutationFn: () => api.post(`/referrals/${r.id}/consents`, { custodians: picked }),
    meta: { success: "Consent requested. The patient answers in their patient portal." }, onSuccess: refresh,
  });
  const c = r.consent;
  const [label, tone] = c ? CONSENT_TEXT[c.status] ?? [c.status, "info" as Tone] : ["Not requested", "off" as Tone];
  const canAsk = staff && !["draft", "closed", "declined", "cancelled"].includes(r.status) && (!c || c.status !== "granted");
  return (
    <Section title="Patient's consent" description="Records are requested only with the patient's consent, given in the patient portal and signed on the patient's own device.">
      <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
        <Tag tone={tone} label={label} />
        {c && <Typography variant="body2">{c.reference} · asked by {c.requested_by}, {fmtDate(c.requested_at)}</Typography>}
      </Stack>
      {c?.status === "granted" && (
        <Typography variant="body2">
          For {c.custodians_granted.map((x) => x.name).join(", ")} until {fmtDate(c.period_end)}
          {c.sensitive_specific.length ? ` · including ${c.sensitive_specific.join(", ")}` : ""}
        </Typography>
      )}
      {c?.status === "declined" && c.decline_reason && <Typography variant="body2">Reason: {c.decline_reason}</Typography>}
      <ErrorAlert error={ask.error} />
      {canAsk && (
        <Box sx={{ mt: 1 }}>
          <Typography variant="body2" sx={{ mb: 0.5 }}>Ask for permission to request records from:</Typography>
          <FormGroup row>
            {linkable.map((s) => (
              <FormControlLabel key={s.institution_id} label={s.own ? `${s.name} (your record)` : s.name}
                control={<Checkbox checked={picked.includes(s.institution_id)}
                  onChange={() => setChosen(picked.includes(s.institution_id) ? picked.filter((x) => x !== s.institution_id) : [...picked, s.institution_id])} />} />
            ))}
          </FormGroup>
          <Button variant="contained" onClick={() => ask.mutate()} disabled={!picked.length || ask.isPending}>
            {c ? "Ask the patient again" : "Ask the patient for consent"}
          </Button>
        </Box>
      )}
    </Section>
  );
}

function RequestButton({ r }: { r: ReferralDetail }) {
  const refresh = useInvalidateReferral(r.id);
  const send = useMutation({
    mutationFn: () => api.post(`/referrals/${r.id}/record-requests`),
    meta: { success: "Records requested from the institutions the patient agreed to." }, onSuccess: refresh,
  });
  const granted = r.consent?.status === "granted";
  return (
    <Box>
      <ErrorAlert error={send.error} />
      <Button variant="contained" onClick={() => send.mutate()} disabled={!granted || send.isPending}>
        {r.record_requests.length ? "Request records again" : "Request records"}
      </Button>
      {!granted && <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>Needs the patient's consent first.</Typography>}
    </Box>
  );
}

/** Staff: consent, requests and their outcomes, and record titles only (the server sends nothing else). */
export function StaffRecords({ r }: { r: ReferralDetail }) {
  const titles = useQuery({ queryKey: ["referral", r.id, "titles"], queryFn: () => api.get<Title[]>(`/referrals/${r.id}/titles`) });
  return (
    <Stack spacing={2}>
      <OtherPlaces r={r} />
      <ConsentPanel r={r} staff />
      <Section title="Records requests" description="Each institution checks the consent and its own rules, then answers with encrypted records only the doctor can open." actions={<RequestButton r={r} />}>
        <SourceOutcomes r={r} />
      </Section>
      <Section title="Records received" description="Titles only. The content is encrypted for the doctor; staff never see it.">
        {titles.isLoading ? <Loading /> : <TitleList titles={titles.data ?? []} />}
      </Section>
    </Stack>
  );
}

export function TitleList({ titles }: { titles: Title[] }) {
  if (!titles.length) return <Empty>Nothing received yet.</Empty>;
  return (
    <Table size="small">
      <TableHead><TableRow><TableCell>Record</TableCell><TableCell>From</TableCell><TableCell>Date</TableCell></TableRow></TableHead>
      <TableBody>
        {titles.map((t) => (
          <TableRow key={`${t.batch_id}:${t.item_id}`}>
            <TableCell>{t.label}{t.sensitive && <Chip size="small" sx={{ ml: 1 }} label="restricted" />}</TableCell>
            <TableCell>{t.source_name ?? t.source_institution}</TableCell>
            <TableCell>{t.date ? fmtDate(t.date, false) : ""}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

/** The doctor's decrypted records for this referral, opened on this device. */
export function useOpenedRecords(r: ReferralDetail) {
  const dk = useDeviceKeys();
  const reported = useRef(false);
  const q = useQuery({
    queryKey: ["referral", r.id, "opened", dk.keys?.encKeyId, r.encrypted_item_count],
    enabled: dk.status === "unlocked" && !r.working_set_purged_at,
    queryFn: async () => {
      const resp = await api.get<EncryptedResponse>(`/referrals/${r.id}/encrypted`);
      return latestById(await openAll(resp, dk.keys!));
    },
    gcTime: 0,
    staleTime: Infinity,
  });
  useEffect(() => {
    if (q.data && !reported.current) {
      reported.current = true;
      reportOpened(r.id, q.data);
    }
  }, [q.data, r.id]);
  return q;
}

function Detail({ item }: { item: OpenedItem }) {
  const rec = item.content?.record ?? {};
  return (
    <Box component="dl" sx={{ m: 0, display: "grid", gridTemplateColumns: "max-content 1fr", columnGap: 2, rowGap: 0.5 }}>
      {Object.entries(rec).filter(([, v]) => v !== null && v !== "").map(([k, v]) => (
        <Box key={k} sx={{ display: "contents" }}>
          <Typography component="dt" variant="body2" color="text.secondary">{k.replace(/_/g, " ")}</Typography>
          <Typography component="dd" variant="body2" sx={{ m: 0, whiteSpace: "pre-wrap" }}>{String(v)}</Typography>
        </Box>
      ))}
    </Box>
  );
}

function ItemRow({ item, selected, onToggle, locked }: { item: OpenedItem; selected: boolean; onToggle: (v: boolean) => void; locked: boolean }) {
  const [open, setOpen] = useState(false);
  const f = floor(item);
  const ok = item.state === "ok" && !!item.content;
  return (
    <>
      <TableRow>
        <TableCell sx={{ width: 48 }}>
          <Checkbox checked={selected && ok} disabled={!ok || locked} onChange={(e) => onToggle(e.target.checked)}
            inputProps={{ "aria-label": `Include in the package: ${item.content?.label ?? item.title.label}` }} />
        </TableCell>
        <TableCell>
          <Typography variant="body2">{ok ? summary(item.content!) : item.title.label}</Typography>
          <Typography variant="caption" color="text.secondary">
            {item.content?.source_name ?? item.title.source_name ?? item.title.source_institution}
            {item.title.date ? ` · ${fmtDate(item.title.date, false)}` : ""} · {f.reason}
          </Typography>
          {item.content?.sensitive_category && <Chip size="small" color="warning" sx={{ ml: 1 }} label={item.content.sensitive_category.replace(/_/g, " ")} />}
          {item.state === "no_key" && (
            <Typography variant="caption" display="block" color="warning.main">
              {item.origin === "custodian" ? "Encrypted to another key of yours: request the records again to read it."
                : "Encrypted to a key you no longer have. It can be recovered only from the patient's own copy."}
            </Typography>
          )}
          {item.state === "failed" && <Typography variant="caption" display="block" color="error">Could not be decrypted (altered or damaged).</Typography>}
        </TableCell>
        <TableCell align="right" sx={{ width: 48 }}>
          {ok && <IconButton size="small" aria-label="Show the full record" onClick={() => setOpen(!open)}><ExpandMore /></IconButton>}
        </TableCell>
      </TableRow>
      {ok && (
        <TableRow>
          <TableCell colSpan={3} sx={{ py: 0, borderBottom: open ? undefined : "none" }}>
            <Collapse in={open} unmountOnExit><Box sx={{ py: 1.5 }}><Detail item={item} /></Box></Collapse>
          </TableCell>
        </TableRow>
      )}
    </>
  );
}

export function DoctorRecords({ r }: { r: ReferralDetail }) {
  const dk = useDeviceKeys();
  const opened = useOpenedRecords(r);
  const [choices, setChoices] = useState<Record<string, boolean>>(() => loadChoices(r.id));
  const locked = !["draft", "requested"].includes(r.status) && !r.amendment_open;
  const items = opened.data ?? [];
  const groups = useMemo(() => CATEGORY_GROUPS.map(([cat, label]) => [label, items.filter((i) =>
    (i.content?.category ?? i.title.category ?? "other") === cat)] as const).filter(([, list]) => list.length), [items]);
  const other = items.filter((i) => !CATEGORY_GROUPS.some(([cat]) => (i.content?.category ?? i.title.category) === cat));
  const toggle = (id: string, v: boolean) => {
    const next = { ...choices, [id]: v };
    setChoices(next);
    saveChoices(r.id, next);
  };
  const chosen = items.filter((i) => i.state === "ok" && isSelected(i, choices)).length;
  if (r.working_set_purged_at) {
    return <Alert severity="info">This referral's encrypted records were purged. The records stay at the places they came from; the patient keeps their own copy.</Alert>;
  }
  return (
    <Stack spacing={2}>
      {dk.status !== "unlocked" && <DeviceKeyPanel compact />}
      <ConsentPanel r={r} staff={false} />
      <Section title="Records requests" description="Each institution decided under the patient's consent and its own rules." actions={<RequestButton r={r} />}>
        <SourceOutcomes r={r} />
      </Section>
      <Section title={`Records (${chosen} chosen for the package)`}
        description="Decrypted on this device only. Tick what the specialist needs; the ticks start from the default selection.">
        {dk.status !== "unlocked" ? <Empty>Unlock your device key to read the records.</Empty>
          : opened.isLoading ? <Loading label="Decrypting on this device…" />
          : opened.error ? <ErrorAlert error={opened.error} />
          : !items.length ? <Empty>No records received yet.</Empty>
          : (
            <Stack spacing={2}>
              {[...groups, ...(other.length ? [["Other", other] as const] : [])].map(([label, list]) => (
                <Box key={label}>
                  <Typography variant="subtitle2" sx={{ mb: 0.5 }}>{label} ({list.length})</Typography>
                  <Table size="small"><TableBody>
                    {list.map((i) => <ItemRow key={i.title.item_id} item={i} selected={isSelected(i, choices)} locked={locked}
                      onToggle={(v) => toggle(i.title.item_id, v)} />)}
                  </TableBody></Table>
                </Box>
              ))}
            </Stack>
          )}
      </Section>
    </Stack>
  );
}
