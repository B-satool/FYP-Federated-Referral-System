import { useMutation, useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { Alert, Box, Button, Link, List, ListItem, ListItemIcon, ListItemText, Stack, Table, TableBody, TableCell, TableHead, TableRow, Typography } from "@mui/material";
import CheckCircle from "@mui/icons-material/CheckCircle";
import RadioButtonUnchecked from "@mui/icons-material/RadioButtonUnchecked";
import { api } from "../../api/client";
import type { BriefPreview, ReferralDetail } from "../../api/types";
import { EvidenceRef } from "../../components/EvidenceRef";
import { ErrorAlert, fmtDate, Loading, Section, Tag } from "../../components/common";
import { useInvalidateReferral } from "./ReferralWorkspace";

type Delivery = { id: number; kind: string; target_institution: string; status: string; attempts: number; last_error: string | null; created_at: string; sent_at: string | null };

const KIND_LABEL: Record<string, string> = {
  deliver_package: "Referral",
  deliver_order: "Test or scan order",
  forward_result: "Result forwarded to the specialist",
  clarification_answer: "Answer to a question",
};

export function Readiness({ r }: { r: ReferralDetail }) {
  const [, setParams] = useSearchParams();
  const items = r.readiness ?? [];
  return (
    <List dense aria-label="Before sending">
      {items.map((i) => (
        <ListItem key={i.key} disableGutters alignItems="flex-start">
          <ListItemIcon sx={{ minWidth: 36, mt: 0.5 }}>
            {i.ok ? <CheckCircle color="success" titleAccess="Done" /> : <RadioButtonUnchecked titleAccess="Not done" />}
          </ListItemIcon>
          <ListItemText
            primary={<><span>{i.label}</span>{!i.ok && <Tag tone={i.who === "doctor" ? "info" : "warn"} label={i.who === "doctor" ? "doctor" : "staff"} />}</>}
            secondary={
              <>
                {i.detail}
                {!i.ok && i.tab && (
                  <>
                    {" "}
                    <Link component="button" type="button" variant="body2" onClick={() => setParams({ tab: i.tab === "papers" ? "papers" : i.tab! })}>
                      Go there
                    </Link>
                  </>
                )}
              </>
            }
          />
        </ListItem>
      ))}
    </List>
  );
}

export function BriefView({ brief }: { brief: BriefPreview }) {
  return (
    <Stack spacing={2}>
      {brief.sections.map((s) => (
        <Box key={s.key}>
          <Typography variant="subtitle1" component="h3" sx={{ fontWeight: 600 }}>
            {s.title}
          </Typography>
          <Box component="ul" sx={{ m: 0, pl: 2.5 }}>
            {s.statements.map((st) => (
              <li key={st.id}>
                <Typography variant="body2" component="span" sx={{ whiteSpace: "pre-wrap" }}>
                  {st.text}
                </Typography>{" "}
                {st.evidence_ids.slice(0, 4).map((id) => <EvidenceRef key={id} id={id} />)}
              </li>
            ))}
          </Box>
        </Box>
      ))}
    </Stack>
  );
}

function Preview({ r }: { r: ReferralDetail }) {
  const q = useQuery({ queryKey: ["referral", r.id, "brief", r.row_version], queryFn: () => api.get<BriefPreview>(`/referrals/${r.id}/brief-preview`) });
  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorAlert error={q.error} />;
  return <BriefView brief={q.data!} />;
}

function Sent({ r }: { r: ReferralDetail }) {
  const refresh = useInvalidateReferral(r.id);
  const delivery = useQuery({ queryKey: ["referral", r.id, "delivery", r.row_version], queryFn: () => api.get<Delivery[]>(`/referrals/${r.id}/delivery`) });
  const retry = useMutation({ mutationFn: () => api.post(`/referrals/${r.id}/retry-delivery`), meta: { success: "Retrying." }, onSuccess: refresh });
  return (
    <Section title="Sent versions and delivery" description="Each sent version is kept exactly as sent, with its content fingerprint.">
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Version</TableCell>
            <TableCell>Sent by</TableCell>
            <TableCell>Fingerprint</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {r.packages.map((p) => (
            <TableRow key={p.version}>
              <TableCell>v{p.version}{p.superseded ? " (replaced)" : ""}</TableCell>
              <TableCell>{p.sent_by}, {fmtDate(p.sent_at)}</TableCell>
              <TableCell sx={{ fontFamily: "monospace", fontSize: 12 }}>{p.content_hash.slice(0, 16)}…</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      {!!delivery.data?.length && (
        <Box sx={{ mt: 2 }}>
          <Typography variant="subtitle2">Deliveries</Typography>
          {delivery.data.map((d) => (
            <Typography key={d.id} variant="body2">
              {KIND_LABEL[d.kind] ?? d.kind}: <Tag tone={d.status === "sent" ? "ok" : d.status === "failed" ? "bad" : "wait"} label={d.status} />{" "}
              {d.sent_at ? fmtDate(d.sent_at) : `${d.attempts} attempt(s)`}{d.last_error ? ` · ${d.last_error}` : ""}
            </Typography>
          ))}
        </Box>
      )}
      {r.delivery_status === "failed" && (
        <Button variant="contained" sx={{ mt: 1.5 }} onClick={() => retry.mutate()} disabled={retry.isPending}>
          Retry delivery
        </Button>
      )}
    </Section>
  );
}

export function SendTab({ r }: { r: ReferralDetail }) {
  const refresh = useInvalidateReferral(r.id);
  const send = useMutation({
    mutationFn: () => api.post(`/referrals/${r.id}/send`, { expected_version: r.row_version }),
    meta: { success: "Referral is being sent." },
    onSuccess: refresh,
  });
  const canSend = r.status === "requested" || r.amendment_open;
  const ready = (r.readiness ?? []).every((i) => !i.blocking || i.ok);
  return (
    <Stack spacing={2}>
      {canSend && (
        <Section title={r.amendment_open ? "Check and send the new version" : "Before sending"}
          description="Staff send the referral once every check is done. The doctor's part is acknowledging the medication flags.">
          <Readiness r={r} />
          <ErrorAlert error={send.error} />
          <Button variant="contained" size="large" disabled={!ready || send.isPending} onClick={() => send.mutate()} sx={{ mt: 1 }}>
            {r.amendment_open ? "Send the new version" : `Send to ${r.destination_name}`}
          </Button>
          {!ready && (
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
              Sending becomes available when every item above is ticked.
            </Typography>
          )}
        </Section>
      )}
      {r.packages.length > 0 && <Sent r={r} />}
      <Section title="What the hospital will receive" description="Built from the checked records. Medication flags travel separately, exactly as the rules produced them.">
        <Preview r={r} />
      </Section>
    </Stack>
  );
}

export function SummaryTab({ r }: { r: ReferralDetail }) {
  return (
    <Stack spacing={2}>
      {r.readiness && (
        <Section title="Progress before sending" description="Staff prepare and send the referral. Items marked 'doctor' need you.">
          <Readiness r={r} />
        </Section>
      )}
      {r.packages.length > 0 && (
        <Alert severity="info">
          Version {r.submitted_package_version ?? r.current_package_version} was sent by {r.packages[0].sent_by}, {fmtDate(r.packages[0].sent_at)}.
        </Alert>
      )}
      <Section title="Summary for the specialist" description="What is (or will be) sent, built from the checked records.">
        <Preview r={r} />
      </Section>
    </Stack>
  );
}
