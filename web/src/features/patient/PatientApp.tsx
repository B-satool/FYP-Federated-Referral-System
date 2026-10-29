import { ReactNode, useState } from "react";
import { useQueries, useQuery } from "@tanstack/react-query";
import { Alert, Box, Button, ButtonBase, Divider, Typography } from "@mui/material";
import { api, ApiError, Service } from "../../api/client";
import { useAuth } from "../../auth/AuthProvider";
import { BrandMark } from "../../components/Brand";
import { ErrorAlert, fmtDate, Loading, ReferralStatus, Tag } from "../../components/common";
import { useMe, usePageTitle } from "../../hooks";
import { tokens } from "../../theme";
import { DeviceKeyPanel } from "../keys/DeviceKey";
import { ConsentDetail, ConsentTab, usePendingConsents } from "./Consent";
import { AddPaper, MyCopy } from "./MyCopy";

/**
 * The patient's own view, laid out as a phone app (for the MVP it runs inside the website).
 *
 * Referrals come from the referral platform. The medical history is asked for from each institution
 * directly and only kept in this screen's memory: the platform never stores it (decision 2026-10-29).
 */

type Step = { at: string | null; text: string };
type PatientReferral = {
  reference: string;
  kind: "referral" | "test";
  status: string;
  status_label: string;
  open: boolean;
  from: { institution: string | null; department: string | null; doctor: string; doctor_id: string | null };
  to: { institution: string; department: string | null; doctor: string | null } | null;
  urgency: string;
  urgency_detail: string | null;
  reason: string;
  planned_procedure: string | null;
  tests: { test: string; where: string; status: string; status_label: string; scheduled_for: string | null }[];
  created_at: string | null;
  closed_at: string | null;
  copy_available: boolean;
  purged_at: string | null;
  timeline: Step[];
};
type Place = { institution_id: string; name: string; kind: string };
type Summary = { held: boolean; last_activity: string | null; counts: Record<string, number> };
type History = {
  institution_name: string;
  conditions: { display: string; status: string; onset: string | null }[];
  surgeries: { procedure: string; performed: string | null; location: string | null }[];
  medicines: { name: string; brand: string | null; dose: string | null; route: string | null; frequency: string | null;
    start_date: string | null; status: string; prescriber: string | null }[];
  visits: { date: string; setting: string; clinician: string | null; reason: string; summary: string }[];
  lab_results: { date: string; panel: string; test: string; value: string | null; unit: string | null;
    reference_range: string | null; flag: string | null }[];
  imaging: { date: string; study: string; body_part: string | null; findings: string; impression: string;
    reporter: string | null }[];
};

type Tab = "home" | "referrals" | "consent" | "records" | "profile";
const TABS: { key: Tab; label: string }[] = [
  { key: "home", label: "Home" },
  { key: "referrals", label: "Referrals" },
  { key: "consent", label: "Permissions" },
  { key: "records", label: "My records" },
  { key: "profile", label: "Profile" },
];
const KIND_WORD: Record<string, string> = { clinic: "Clinic", hospital: "Hospital", laboratory: "Laboratory" };

function useReferrals() {
  return useQuery({ queryKey: ["patient", "referrals"], queryFn: () => api.get<PatientReferral[]>("/patient-access/referrals") });
}

/** Asks every institution whether it holds records for this patient. A failed answer is never read as "no records". */
function usePlaces() {
  const places = useQuery({ queryKey: ["patient", "places"], queryFn: () => api.get<Place[]>("/patient-access/places") });
  const summaries = useQueries({
    queries: (places.data ?? []).map((p) => ({
      queryKey: ["patient", "summary", p.institution_id],
      queryFn: () => api.get<Summary>("/patient-access/summary", p.institution_id as Service),
      retry: 1,
    })),
  });
  return { places, summaries };
}

export function PatientApp() {
  const [tab, setTab] = useState<Tab>("home");
  const [referral, setReferral] = useState<PatientReferral | null>(null);
  const [place, setPlace] = useState<Place | null>(null);
  const [consent, setConsent] = useState<string | null>(null);
  usePageTitle("My health");

  const open = (t: Tab) => {
    setTab(t);
    setReferral(null);
    setPlace(null);
    setConsent(null);
  };
  let screen: ReactNode;
  if (referral) screen = <ReferralDetail referral={referral} onBack={() => setReferral(null)} />;
  else if (place) screen = <PlaceHistory place={place} onBack={() => setPlace(null)} />;
  else if (consent) screen = <ConsentDetail reference={consent} onBack={() => setConsent(null)} />;
  else if (tab === "home") screen = <HomeTab onReferral={setReferral} onTab={open} />;
  else if (tab === "referrals") screen = <ReferralsTab onReferral={setReferral} />;
  else if (tab === "consent") screen = <ConsentTab onOpen={setConsent} />;
  else if (tab === "records") screen = <RecordsTab onPlace={setPlace} />;
  else screen = <ProfileTab />;

  return (
    <PhoneFrame>
      <Box component="header" sx={{ bgcolor: tokens.nav, color: tokens.navText, px: 2, py: 1.5, display: "flex", alignItems: "center", gap: 1.25 }}>
        <BrandMark size={28} />
        <Box>
          <Typography sx={{ fontWeight: 700, fontSize: "1rem", lineHeight: 1.2 }}>My health</Typography>
          <Typography sx={{ fontSize: "0.75rem", color: tokens.navMuted }}>Referral Platform for patients</Typography>
        </Box>
      </Box>
      <Box component="main" id="main" sx={{ flex: 1, overflowY: "auto", px: 2, py: 2, bgcolor: tokens.page }}>
        {screen}
      </Box>
      <Box component="nav" aria-label="Patient app" sx={{ display: "flex", borderTop: `1px solid ${tokens.line}`, bgcolor: tokens.surface }}>
        {TABS.map((t) => {
          const active = tab === t.key && !referral && !place && !consent;
          return (
            <ButtonBase
              key={t.key}
              onClick={() => open(t.key)}
              aria-current={active ? "page" : undefined}
              sx={{ flex: 1, py: 1.25, fontSize: "0.8125rem", fontWeight: active ? 700 : 500, color: active ? tokens.brand : tokens.muted,
                borderTop: `3px solid ${active ? tokens.brand : "transparent"}` }}
            >
              {t.label}
            </ButtonBase>
          );
        })}
      </Box>
    </PhoneFrame>
  );
}

/** A phone-sized frame on a large screen; the whole screen on a phone. */
function PhoneFrame({ children }: { children: ReactNode }) {
  return (
    <Box sx={{ minHeight: "100vh", bgcolor: { xs: tokens.page, sm: tokens.sunken }, display: "flex", alignItems: "center", justifyContent: "center", py: { xs: 0, sm: 3 } }}>
      <Box
        data-testid="patient-phone"
        sx={{
          width: { xs: "100%", sm: 390 },
          height: { xs: "100vh", sm: 780 },
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
          bgcolor: tokens.surface,
          border: { xs: "none", sm: `10px solid ${tokens.ink}` },
          borderRadius: { xs: 0, sm: "36px" },
        }}
      >
        {children}
      </Box>
    </Box>
  );
}

function Card({ children, onClick, label }: { children: ReactNode; onClick?: () => void; label?: string }) {
  const sx = { display: "block", width: "100%", textAlign: "left" as const, p: 1.5, mb: 1.25, bgcolor: tokens.surface,
    border: `1px solid ${tokens.line}`, borderRadius: 2 };
  if (!onClick) return <Box sx={sx}>{children}</Box>;
  return (
    <ButtonBase onClick={onClick} aria-label={label} sx={{ ...sx, "&:hover": { borderColor: tokens.brand } }}>
      {children}
    </ButtonBase>
  );
}

function Heading({ children }: { children: ReactNode }) {
  return <Typography component="h2" sx={{ fontSize: "1.0625rem", fontWeight: 700, mb: 1.25 }}>{children}</Typography>;
}

function Back({ onBack }: { onBack: () => void }) {
  return <Button size="small" onClick={onBack} sx={{ mb: 1, px: 0 }}>‹ Back</Button>;
}

function ReferralCard({ r, onOpen }: { r: PatientReferral; onOpen: () => void }) {
  const title = r.kind === "test" ? `Tests: ${r.tests.map((t) => t.test).join(", ") || "test request"}`
    : `${r.to?.department ?? "Referral"}, ${r.to?.institution ?? ""}`;
  return (
    <Card onClick={onOpen} label={`${title}, ${r.status_label}`}>
      <Box sx={{ display: "flex", justifyContent: "space-between", gap: 1, alignItems: "flex-start" }}>
        <Typography sx={{ fontWeight: 600, fontSize: "0.9375rem" }}>{title}</Typography>
        <ReferralStatus status={r.status} label={r.status_label} />
      </Box>
      <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
        From {r.from.doctor}, {r.from.institution} · {fmtDate(r.created_at, false)}
      </Typography>
      <Typography variant="body2" color="text.secondary">{r.reference} · {r.urgency}</Typography>
    </Card>
  );
}

function HomeTab({ onReferral, onTab }: { onReferral: (r: PatientReferral) => void; onTab: (t: Tab) => void }) {
  const { data: me } = useMe();
  const referrals = useReferrals();
  const { places, summaries } = usePlaces();
  const open = (referrals.data ?? []).filter((r) => r.open);
  const held = summaries.filter((s) => s.data?.held && Object.values(s.data.counts).some((n) => n > 0)).length;
  const pending = summaries.some((s) => s.isLoading);
  const failed = summaries.filter((s) => s.isError).length;
  return (
    <>
      <Typography sx={{ fontSize: "1.25rem", fontWeight: 700 }}>Hello, {me?.name ?? ""}</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>Your referrals and where your records are kept.</Typography>
      <Box sx={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 1.25, mb: 2 }}>
        <Card onClick={() => onTab("referrals")} label="Open referrals">
          <Typography sx={{ fontSize: "1.75rem", fontWeight: 700 }}>{referrals.isLoading ? "…" : open.length}</Typography>
          <Typography variant="body2">Open referrals and tests</Typography>
        </Card>
        <Card onClick={() => onTab("records")} label="Places with your records">
          <Typography sx={{ fontSize: "1.75rem", fontWeight: 700 }}>{places.isLoading || pending ? "…" : held}</Typography>
          <Typography variant="body2">Places with your records{failed ? ` (${failed} not reachable)` : ""}</Typography>
        </Card>
      </Box>
      <PendingConsentBanner onOpen={() => onTab("consent")} />
      <Heading>Latest</Heading>
      {referrals.error && <ErrorAlert error={referrals.error} />}
      {referrals.data && referrals.data.length === 0 && (
        <Typography variant="body2" color="text.secondary">No referrals or test requests have been made for you on this platform.</Typography>
      )}
      {(referrals.data ?? []).slice(0, 2).map((r) => <ReferralCard key={r.reference} r={r} onOpen={() => onReferral(r)} />)}
      <Alert severity="info" sx={{ mt: 1 }}>
        Your medical history is read from each hospital, clinic or laboratory when you open it, and shown only on this device. The referral platform does not keep a copy.
      </Alert>
    </>
  );
}

function PendingConsentBanner({ onOpen }: { onOpen: () => void }) {
  const pending = usePendingConsents();
  if (!pending.length) return null;
  return (
    <Alert severity="warning" sx={{ mb: 2 }} action={<Button color="inherit" size="small" onClick={onOpen}>Answer</Button>}>
      {pending.length === 1 ? "A clinic is asking for your permission to fetch your records." : `${pending.length} requests for your permission.`}
    </Alert>
  );
}

function ReferralsTab({ onReferral }: { onReferral: (r: PatientReferral) => void }) {
  const referrals = useReferrals();
  const [showClosed, setShowClosed] = useState(false);
  if (referrals.isLoading) return <Loading />;
  if (referrals.error) return <ErrorAlert error={referrals.error} />;
  const all = referrals.data ?? [];
  const list = showClosed ? all : all.filter((r) => r.open);
  return (
    <>
      <Heading>Referrals and tests</Heading>
      <Box sx={{ display: "flex", gap: 1, mb: 1.5 }}>
        <Button size="small" variant={showClosed ? "outlined" : "contained"} onClick={() => setShowClosed(false)}>Open ({all.filter((r) => r.open).length})</Button>
        <Button size="small" variant={showClosed ? "contained" : "outlined"} onClick={() => setShowClosed(true)}>All ({all.length})</Button>
      </Box>
      {list.length === 0 && <Typography variant="body2" color="text.secondary">{showClosed ? "Nothing yet." : "No open referrals or tests."}</Typography>}
      {list.map((r) => <ReferralCard key={r.reference} r={r} onOpen={() => onReferral(r)} />)}
    </>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <Box sx={{ mb: 1.25 }}>
      <Typography variant="body2" color="text.secondary">{label}</Typography>
      <Typography sx={{ fontSize: "0.9375rem" }}>{children}</Typography>
    </Box>
  );
}

function ReferralDetail({ referral: r, onBack }: { referral: PatientReferral; onBack: () => void }) {
  return (
    <>
      <Back onBack={onBack} />
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 1.5 }}>
        <Typography component="h2" sx={{ fontSize: "1.125rem", fontWeight: 700 }}>{r.kind === "test" ? "Test request" : "Referral"} {r.reference}</Typography>
        <ReferralStatus status={r.status} label={r.status_label} />
      </Box>
      <Card>
        {r.to && <Field label="Referred to">{[r.to.department, r.to.institution].filter(Boolean).join(", ")}{r.to.doctor ? ` (${r.to.doctor})` : ""}</Field>}
        <Field label="Referred by">{r.from.doctor}, {r.from.institution}</Field>
        <Field label="Urgency">{r.urgency}{r.urgency_detail ? `: ${r.urgency_detail.toLowerCase()}` : ""}</Field>
        {r.reason && <Field label="Reason">{r.reason}</Field>}
        {r.planned_procedure && <Field label="Planned procedure">{r.planned_procedure}</Field>}
      </Card>
      {r.tests.length > 0 && (
        <>
          <Heading>Tests and scans</Heading>
          {r.tests.map((t, i) => (
            <Card key={i}>
              <Box sx={{ display: "flex", justifyContent: "space-between", gap: 1 }}>
                <Typography sx={{ fontWeight: 600 }}>{t.test}</Typography>
                <Tag tone={t.status === "rejected" ? "off" : t.status === "reported" ? "ok" : "info"} label={t.status_label} />
              </Box>
              <Typography variant="body2" color="text.secondary">{t.where}{t.scheduled_for ? ` · booked for ${fmtDate(t.scheduled_for)}` : ""}</Typography>
            </Card>
          ))}
        </>
      )}
      {r.kind === "referral" && (
        <>
          <Heading>Your copy</Heading>
          <Card><MyCopy reference={r.reference} available={r.copy_available} purgedAt={r.purged_at} /></Card>
          {r.open && !r.purged_at && <><Heading>Add a paper</Heading><Card><AddPaper reference={r.reference} doctorId={r.from.doctor_id} /></Card></>}
        </>
      )}
      <Heading>What has happened</Heading>
      <Box component="ol" sx={{ listStyle: "none", p: 0, m: 0 }}>
        {r.timeline.map((s, i) => (
          <Box component="li" key={i} sx={{ display: "flex", gap: 1.25, pb: 1.5 }}>
            <Box sx={{ width: 10, height: 10, mt: 0.75, borderRadius: "50%", flexShrink: 0, bgcolor: i === r.timeline.length - 1 ? tokens.brand : tokens.field }} aria-hidden />
            <Box>
              <Typography sx={{ fontSize: "0.9375rem" }}>{s.text}</Typography>
              <Typography variant="body2" color="text.secondary">{fmtDate(s.at)}</Typography>
            </Box>
          </Box>
        ))}
      </Box>
    </>
  );
}

function RecordsTab({ onPlace }: { onPlace: (p: Place) => void }) {
  const { places, summaries } = usePlaces();
  if (places.isLoading) return <Loading />;
  if (places.error) return <ErrorAlert error={places.error} />;
  return (
    <>
      <Heading>Where your records are kept</Heading>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
        Each place was asked just now, using your CNIC. Open one to read your records from it.
      </Typography>
      {(places.data ?? []).map((p, i) => {
        const s = summaries[i];
        const total = s?.data ? Object.values(s.data.counts).reduce((a, b) => a + b, 0) : 0;
        let tag: ReactNode = <Tag tone="wait" label="Asking…" />;
        if (s?.isError) tag = <Tag tone="bad" label="Could not reach" />;
        else if (s?.data?.held && total > 0) tag = <Tag tone="ok" label="Holds your records" />;
        else if (s?.data?.held) tag = <Tag tone="info" label="Registered, no records yet" />;
        else if (s?.data) tag = <Tag tone="neutral" label="No record of you" />;
        const body = (
          <>
            <Box sx={{ display: "flex", justifyContent: "space-between", gap: 1, alignItems: "flex-start" }}>
              <Typography sx={{ fontWeight: 600 }}>{p.name}</Typography>
              {tag}
            </Box>
            <Typography variant="body2" color="text.secondary">
              {KIND_WORD[p.kind] ?? p.kind}
              {s?.data?.held && total > 0 ? ` · ${total} records` : ""}
              {s?.data?.last_activity ? ` · last visit ${fmtDate(s.data.last_activity, false)}` : ""}
              {s?.isError ? ` · ${(s.error as ApiError)?.message ?? "try again later"}. This does not mean it holds nothing.` : ""}
            </Typography>
          </>
        );
        return s?.data?.held && total > 0
          ? <Card key={p.institution_id} onClick={() => onPlace(p)} label={`Open records from ${p.name}`}>{body}</Card>
          : <Card key={p.institution_id}>{body}</Card>;
      })}
    </>
  );
}

function Section({ title, count, children }: { title: string; count: number; children: ReactNode }) {
  return (
    <Box sx={{ mb: 2 }}>
      <Typography component="h3" sx={{ fontSize: "1rem", fontWeight: 700, mb: 0.75 }}>{title} ({count})</Typography>
      {count === 0 ? <Typography variant="body2" color="text.secondary">None recorded here.</Typography> : children}
    </Box>
  );
}

function Row({ title, sub, right }: { title: string; sub?: ReactNode; right?: ReactNode }) {
  return (
    <Box sx={{ py: 0.75 }}>
      <Box sx={{ display: "flex", justifyContent: "space-between", gap: 1 }}>
        <Typography sx={{ fontSize: "0.9375rem", fontWeight: 600 }}>{title}</Typography>
        {right}
      </Box>
      {sub && <Typography variant="body2" color="text.secondary">{sub}</Typography>}
      <Divider sx={{ mt: 0.75 }} />
    </Box>
  );
}

function PlaceHistory({ place, onBack }: { place: Place; onBack: () => void }) {
  // read straight from the institution; not cached once the screen closes
  const history = useQuery({
    queryKey: ["patient", "history", place.institution_id],
    queryFn: () => api.get<History>("/patient-access/records", place.institution_id as Service),
    gcTime: 0,
    staleTime: 0,
  });
  return (
    <>
      <Back onBack={onBack} />
      <Typography component="h2" sx={{ fontSize: "1.125rem", fontWeight: 700 }}>{place.name}</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>Read directly from {place.name}. Not stored by the referral platform.</Typography>
      {history.isLoading && <Loading label={`Asking ${place.name}…`} />}
      {history.error && <ErrorAlert error={history.error} title={`${place.name} could not be read`} />}
      {history.data && <HistoryBody h={history.data} />}
    </>
  );
}

function HistoryBody({ h }: { h: History }) {
  const current = h.medicines.filter((m) => m.status === "active");
  const past = h.medicines.filter((m) => m.status !== "active");
  const med = (m: History["medicines"][number]) => [m.dose, m.route, m.frequency].filter(Boolean).join(", ");
  return (
    <>
      <Section title="Conditions" count={h.conditions.length}>
        {h.conditions.map((c, i) => <Row key={i} title={c.display} sub={c.onset ? `Since ${c.onset}` : undefined}
          right={<Tag tone={c.status === "active" ? "info" : "neutral"} label={c.status} />} />)}
      </Section>
      <Section title="Current medicines" count={current.length}>
        {current.map((m, i) => <Row key={i} title={m.brand ? `${m.brand} (${m.name})` : m.name}
          sub={[med(m), m.prescriber && `by ${m.prescriber}`].filter(Boolean).join(" · ")} />)}
      </Section>
      {past.length > 0 && (
        <Section title="Past medicines" count={past.length}>
          {past.map((m, i) => <Row key={i} title={m.brand ? `${m.brand} (${m.name})` : m.name} sub={med(m)} right={<Tag tone="off" label={m.status} />} />)}
        </Section>
      )}
      <Section title="Visits" count={h.visits.length}>
        {h.visits.map((v, i) => <Row key={i} title={`${fmtDate(v.date, false)} · ${v.reason || v.setting}`}
          sub={[v.clinician, v.summary].filter(Boolean).join(" · ")} />)}
      </Section>
      <Section title="Test results" count={h.lab_results.length}>
        {h.lab_results.map((r, i) => <Row key={i} title={`${r.test}: ${r.value ?? "–"}${r.unit ? ` ${r.unit}` : ""}`}
          sub={`${r.panel} · ${fmtDate(r.date, false)}${r.reference_range ? ` · normal ${r.reference_range}` : ""}`}
          right={r.flag && r.flag !== "normal" ? <Tag tone="warn" label={r.flag} /> : undefined} />)}
      </Section>
      <Section title="Scans" count={h.imaging.length}>
        {h.imaging.map((s, i) => <Row key={i} title={`${s.study} · ${fmtDate(s.date, false)}`} sub={s.impression || s.findings} />)}
      </Section>
      <Section title="Operations" count={h.surgeries.length}>
        {h.surgeries.map((s, i) => <Row key={i} title={s.procedure} sub={[s.performed, s.location].filter(Boolean).join(" · ")} />)}
      </Section>
    </>
  );
}

function ProfileTab() {
  const { data: me } = useMe();
  const { logout } = useAuth();
  return (
    <>
      <Heading>Profile</Heading>
      <DeviceKeyPanel compact />
      <Card>
        <Field label="Name">{me?.name}</Field>
        <Field label="Account">{me?.username}</Field>
        <Field label="How your records are found">By your CNIC, which your hospital or clinic confirmed. You cannot change it here.</Field>
      </Card>
      <Alert severity="info" sx={{ mb: 2 }}>
        Each hospital, clinic and laboratory decides what you can see and records every time you look. Ask them to correct anything that is wrong.
      </Alert>
      <Button variant="outlined" fullWidth onClick={() => void logout()}>Sign out</Button>
    </>
  );
}
