import { ReactNode } from "react";
import { Link as RouterLink, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Box, Button, Link, Paper, Stack, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Typography, useMediaQuery } from "@mui/material";
import { useTheme } from "@mui/material/styles";
import { api } from "../../api/client";
import type { Case, Me } from "../../api/types";
import { ErrorAlert, fmtDate, Loading, OrderStatus, PageHeader, ReferralStatus, Section, Tag, UrgencyTag } from "../../components/common";
import { hasRole, isDoctor, ownService, useMe } from "../../hooks";
import { NewRequestButton } from "../referrals/NewReferral";
import { actionableCount, Queue } from "./queue";

type Row = { key: string; reference: string; patient: string; what: ReactNode; status?: ReactNode; when: string | null; to: string; urgency?: { u: string; label: string } };

function Rows({ rows, heading }: { rows: Row[]; heading: string }) {
  const theme = useTheme();
  const wide = useMediaQuery(theme.breakpoints.up("md"), { noSsr: true });
  if (!wide)
    return (
      <Stack component="ul" spacing={1.5} sx={{ listStyle: "none", m: 0, p: 0 }}>
        {rows.map((i) => (
          <Paper component="li" key={i.key} variant="outlined" sx={{ p: 1.5 }}>
            <Stack direction="row" justifyContent="space-between" spacing={1}>
              <Typography sx={{ fontWeight: 700 }}>{i.reference}</Typography>
              {i.status}
            </Stack>
            <Typography>{i.patient}</Typography>
            <Typography variant="body2" component="div">{i.what}</Typography>
            <Link component={RouterLink} to={i.to}>Open</Link>
          </Paper>
        ))}
      </Stack>
    );
  return (
    <TableContainer>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Reference</TableCell>
            <TableCell>Patient</TableCell>
            <TableCell>{heading}</TableCell>
            <TableCell>Status</TableCell>
            <TableCell>Updated</TableCell>
            <TableCell><span className="sr-only">Open</span></TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map((i) => (
            <TableRow key={i.key} hover>
              <TableCell sx={{ fontWeight: 600, whiteSpace: "nowrap" }}>{i.reference}</TableCell>
              <TableCell>{i.patient}</TableCell>
              <TableCell>{i.what}</TableCell>
              <TableCell>
                <Stack direction="row" spacing={0.5} alignItems="center">
                  {i.urgency && <UrgencyTag urgency={i.urgency.u} label={i.urgency.label} />}
                  {i.status}
                </Stack>
              </TableCell>
              <TableCell sx={{ whiteSpace: "nowrap" }}>{fmtDate(i.when)}</TableCell>
              <TableCell align="right">
                <Link component={RouterLink} to={i.to} aria-label={`Open ${i.reference}`}>Open</Link>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}

function Group({ title, rows, heading = "What to do" }: { title: string; rows: Row[]; heading?: string }) {
  if (!rows.length) return null;
  return (
    <Section title={`${title} (${rows.length})`}>
      <Rows rows={rows} heading={heading} />
    </Section>
  );
}

/** Incoming referrals at this institution that need the signed-in person (staff: take in; doctor: decide or respond). */
function useIncoming(me: Me | undefined) {
  const enabled = !!me && me.institution_kind !== "laboratory" && hasRole(me, "clinician", "clinic_staff");
  return useQuery({ queryKey: ["incoming"], queryFn: () => api.get<Case[]>("/cases", ownService(me)), enabled, refetchInterval: 15000 });
}

const INTAKE_TODO: Record<string, string> = {
  received: "Acknowledge, confirm the patient, assign a doctor",
  acknowledged: "Confirm the patient and assign a doctor",
};
const DOCTOR_TODO: Record<string, string> = { assigned: "Accept, decline or ask for information", accepted: "Write and send your response" };

export function WorkQueue() {
  const { data: me } = useMe();
  const nav = useNavigate();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["work-queue"], queryFn: () => api.get<Queue>("/work-queue"), refetchInterval: 15000 });
  const incoming = useIncoming(me);
  const readAll = useMutation({
    mutationFn: () => api.post("/notifications/read-all"),
    meta: { silent: true },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["work-queue"] }),
  });
  if (q.isLoading || !me) return <Loading />;
  if (q.error) return <ErrorAlert error={q.error} />;
  const d = q.data!;
  const doctor = isDoctor(me);
  const total = actionableCount(d);
  const R = (r: { id: number; reference: string; patient: { name: string }; updated_at: string; status: string; status_label: string; urgency: string; urgency_label: string }, what: ReactNode, tab?: string): Row => ({
    key: `${r.id}-${tab}`, reference: r.reference, patient: r.patient.name, what, when: r.updated_at,
    status: <ReferralStatus status={r.status} label={r.status_label} />, urgency: { u: r.urgency, label: r.urgency_label },
    to: `/referrals/${r.id}${tab ? `?tab=${tab}` : ""}`,
  });

  const todo = doctor ? DOCTOR_TODO : INTAKE_TODO;
  const cases: Row[] = (incoming.data ?? []).filter((c) => todo[c.status] && !(c.status === "accepted" && c.decision !== "accepted")).map((c) => ({
    key: `case-${c.id}`, reference: c.central_referral_id, patient: c.patient_name, when: c.received_at,
    what: <>{todo[c.status]} <Typography component="span" variant="caption" color="text.secondary">· from {c.sender_name}</Typography></>,
    status: <Tag tone="info" label={c.status} />, to: `/incoming/${c.id}`,
  }));

  const info: Row[] = d.info_requests.map((c) => ({
    key: `info-${c.id}`, reference: c.referral_reference, patient: c.patient_name, when: c.asked_at,
    what: <><strong>{c.asked_by}</strong> asks: {c.question}</>, status: <Tag tone="warn" label="question" />,
    to: `/referrals/${c.referral_id}?tab=response`,
  }));

  return (
    <>
      <PageHeader
        title="Work queue"
        subtitle={total + cases.length ? `${total + cases.length} ${total + cases.length === 1 ? "item needs" : "items need"} you, ${me.name}.` : `Nothing needs you right now, ${me.name}.`}
        actions={doctor && me.institution_kind !== "laboratory" ? (
          <>
            <NewRequestButton />
            <Button variant="outlined" onClick={() => nav("/referrals")}>All requests</Button>
          </>
        ) : <Button variant="outlined" onClick={() => nav("/referrals")}>All requests</Button>}
      />
      <Stack spacing={2.5}>
        <Group title={doctor ? "Referrals assigned to you" : "Incoming referrals to take in"} heading="What to do" rows={cases} />
        {doctor ? (
          <>
            <Group title="Medication flags to review" rows={(d.flags_to_acknowledge ?? []).map((r) => R(r, `${r.unacknowledged} flag(s): staff have gathered the records and medicines`, "medicines"))} />
            <Group title="Test results ready" heading="Result" rows={(d.results_to_see ?? []).map((x) => ({
              key: `dx-${x.id}`, reference: x.referral_reference ?? x.reference, patient: x.patient_name ?? "", when: x.updated_at ?? x.created_at,
              what: `${x.test} from ${x.destination_name}`, status: <OrderStatus status={x.status} />, to: `/referrals/${x.referral_id}?tab=tests`,
            }))} />
            <Group title="Specialist responses to review" rows={(d.responses_to_review ?? []).map((r) => R(r, `Response from ${r.specialist_name}`, "response"))} />
            <Group title="Questions from the receiving side" rows={info} />
            <Group title="Your drafts" rows={(d.drafts ?? []).map((r) => R(r, "Finish and submit the request", "request"))} />
            <Group title="Your requests in progress" heading="Where it is" rows={(d.in_progress ?? []).map((r) => R(r,
              r.kind === "test" ? "Tests with the departments"
                : r.status === "requested" ? (r.prepared_at ? "Flags reviewed; staff will send it" : "Staff are gathering the records")
                : `With ${r.destination_name}`, r.kind === "test" ? "tests" : undefined))} />
          </>
        ) : (
          <>
            <Group title="Referrals to prepare and send" heading="Next step" rows={(d.to_prepare ?? []).map((r) => R(r,
              r.ready ? <strong>Ready to send</strong> : <>{r.next_step?.label}{r.next_step?.who === "doctor" ? " (doctor)" : ""} <Typography component="span" variant="caption" color="text.secondary">· {r.done} of {r.total} done</Typography></>,
              r.ready ? "send" : (r.next_step?.tab ?? undefined)))} />
            <Group title="Records requests from other places" heading="From" rows={(d.link_requests ?? []).map((l) => ({
              key: `link-${l.id}`, reference: `Link #${l.id}`, patient: l.patient_name, when: l.requested_at, what: l.purpose,
              status: <Tag tone="wait" label="to check" />, to: "/patient-links",
            }))} />
            <Group title="Tests and scans to send" heading="Test" rows={(d.tests_to_send ?? []).map((x) => ({
              key: `dx-${x.id}`, reference: x.referral_reference ?? x.reference, patient: x.patient_name ?? "", when: x.created_at,
              what: `${x.test} to ${x.destination_name}${x.status === "rejected" ? ` (not accepted: ${x.reject_reason})` : ""}`,
              status: <OrderStatus status={x.status} />, to: `/referrals/${x.referral_id}?tab=tests`,
            }))} />
            <Group title="Questions from the receiving side" rows={info} />
            <Group title="Follow-up" rows={(d.follow_up ?? []).map((r) => R(r,
              !r.patient_informed ? "Tell the patient the outcome" : r.open_tasks ? `${r.open_tasks} task(s) open` : "Close it", r.kind === "test" ? "tests" : "response"))} />
            <Group title="Delivery problems" rows={(d.delivery_problems ?? []).map((r) => R(r, "Sending failed: retry", "send"))} />
          </>
        )}
        {d.notifications.length > 0 && (
          <Section title="Updates" actions={<Button size="small" onClick={() => readAll.mutate()}>Mark all read</Button>}>
            <Stack spacing={1}>
              {d.notifications.map((n) => (
                <Box key={n.id}>
                  <Typography variant="body2">
                    {n.link ? <Link component={RouterLink} to={n.link}>{n.title}</Link> : n.title}
                    {n.body ? ` · ${n.body}` : ""}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">{fmtDate(n.created_at)}</Typography>
                </Box>
              ))}
            </Stack>
          </Section>
        )}
        {total + cases.length === 0 && d.notifications.length === 0 && (
          <Section title="All clear">
            <Typography color="text.secondary">There is nothing for you to do. New requests, flags and results will appear here.</Typography>
          </Section>
        )}
      </Stack>
    </>
  );
}
