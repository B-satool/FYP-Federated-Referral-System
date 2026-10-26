import { useMutation, useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { Box, Button, Link, List, ListItem, ListItemIcon, ListItemText, Stack, Table, TableBody, TableCell, TableHead, TableRow, Typography } from "@mui/material";
import CheckCircle from "@mui/icons-material/CheckCircle";
import InfoOutlined from "@mui/icons-material/InfoOutlined";
import RadioButtonUnchecked from "@mui/icons-material/RadioButtonUnchecked";
import { api } from "../../api/client";
import type { BriefPreview, LetterFlag, MedicationView, PackageEnvelope, ReferralDetail } from "../../api/types";
import { EvidenceRef } from "../../components/EvidenceRef";
import { ReferralLetter } from "../../components/ReferralLetter";
import { ErrorAlert, fmtDate, Loading, Section, Tag } from "../../components/common";
import { useInvalidateReferral } from "./ReferralWorkspace";

type Delivery = { id: number; kind: string; target_institution: string; status: string; attempts: number; last_error: string | null; created_at: string; sent_at: string | null };

const KIND_LABEL: Record<string, string> = {
  deliver_package: "Referral",
  deliver_order: "Test or scan order",
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
            {!i.blocking ? <InfoOutlined color="info" titleAccess="For information" />
              : i.ok ? <CheckCircle color="success" titleAccess="Done" /> : <RadioButtonUnchecked titleAccess="Not done" />}
          </ListItemIcon>
          <ListItemText
            primary={<><span>{i.label}</span>{i.blocking && !i.ok && <Tag tone={i.who === "doctor" ? "info" : "warn"} label={i.who === "doctor" ? "doctor" : "staff"} />}</>}
            secondary={
              <>
                {i.detail}
                {i.blocking && !i.ok && i.tab && i.tab !== "send" && (
                  <>
                    {" "}
                    <Link component="button" type="button" variant="body2" onClick={() => setParams({ tab: i.tab! })}>
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

const cite = (ids: number[]) => ids.map((id) => <EvidenceRef key={id} id={id} />);

function header(r: ReferralDetail, date: string | null) {
  return {
    reference: r.reference,
    date,
    to: { institution: r.destination_name, department: r.destination_department_name, doctor: r.destination_doctor },
    from: { doctor: r.requesting_doctor_name, department: r.source_department_name, institution: r.source_institution_name },
    patient: { name: r.patient.name, birth_date: r.patient.birth_date, sex: r.patient.sex, cnic: r.patient.cnic, id: `${r.patient.local_patient_id} (${r.source_institution_name})` },
    urgency: r.urgency_label,
    urgencyDetail: r.urgency_detail,
  };
}

/** The letter as it would be sent now (built from the checked records). */
export function LetterPreview({ r }: { r: ReferralDetail }) {
  const brief = useQuery({ queryKey: ["referral", r.id, "brief", r.row_version], queryFn: () => api.get<BriefPreview>(`/referrals/${r.id}/brief-preview`) });
  const meds = useQuery({ queryKey: ["referral", r.id, "medications"], queryFn: () => api.get<MedicationView>(`/referrals/${r.id}/medications`) });
  if (brief.isLoading || meds.isLoading) return <Loading />;
  if (brief.error || meds.error) return <ErrorAlert error={brief.error || meds.error} />;
  const flags: LetterFlag[] = meds.data!.flags.map((f) => {
    const a = f.acknowledgements.find((x) => x.side === "referring");
    return { flag_id: f.id, version: f.version, kind: f.kind, title: f.title, message: f.message, medication: f.medication, source_label: f.source_label,
      rule_id: f.rule_id, acknowledged: a ? { by: a.by, at: a.created_at } : null };
  });
  return (
    <ReferralLetter header={header(r, null)} sections={brief.data!.sections} flags={flags} flagSummary={meds.data!.evaluation?.summary_message} cite={cite}
      footer={`Requested by ${r.requesting_doctor_name}${r.requested_at ? `, ${fmtDate(r.requested_at)}` : ""}. Not sent yet.`} />
  );
}

/** A version exactly as it was sent. */
export function SentLetter({ r, version }: { r: ReferralDetail; version: number }) {
  const q = useQuery({ queryKey: ["referral", r.id, "package", version], queryFn: () => api.get<{ envelope: PackageEnvelope }>(`/referrals/${r.id}/packages/${version}`) });
  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorAlert error={q.error} />;
  const env = q.data!.envelope;
  return (
    <ReferralLetter header={header(r, env.sent_at)} sections={env.brief_sections} flags={env.medication_flags} flagSummary={env.medication_evaluation.summary} cite={cite}
      footer={`Requested by ${env.requesting_doctor.name}; compiled and sent by ${env.sent_by}, ${fmtDate(env.sent_at)}. Version ${version}.`} />
  );
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

/** Staff: gather, mark ready for the doctor, then (after the doctor reviews the flags) send. */
export function SendTab({ r }: { r: ReferralDetail }) {
  const refresh = useInvalidateReferral(r.id);
  const prepare = useMutation({
    mutationFn: () => api.post(`/referrals/${r.id}/prepared`, { expected_version: r.row_version }),
    meta: { success: "The doctor has been asked to review the medication flags." },
    onSuccess: refresh,
  });
  const send = useMutation({
    mutationFn: () => api.post(`/referrals/${r.id}/send`, { expected_version: r.row_version }),
    meta: { success: "Referral is being sent." },
    onSuccess: refresh,
  });
  const canSend = r.status === "requested" || r.amendment_open;
  const items = r.readiness ?? [];
  const staffKeys = ["records", "documents", "meds_checked", "dose_differences", "evaluation"];
  const staffDone = items.filter((i) => staffKeys.includes(i.key)).every((i) => i.ok);
  const ready = items.every((i) => !i.blocking || i.ok);
  const latest = r.packages[0]?.version;
  return (
    <Stack spacing={2}>
      {canSend && (
        <Section title={r.amendment_open ? "Check and send the new version" : "Before sending"}
          description="Gather the records, papers and medicines, then mark it ready. The doctor reviews the medication flags; then you send it.">
          <Readiness r={r} />
          <ErrorAlert error={prepare.error || send.error} />
          <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} sx={{ mt: 1 }}>
            {!r.prepared_at && r.status === "requested" && (
              <Button variant="contained" size="large" disabled={!staffDone || prepare.isPending} onClick={() => prepare.mutate()}>
                Ready for the doctor's review
              </Button>
            )}
            {(r.prepared_at || r.amendment_open) && (
              <Button variant="contained" size="large" disabled={!ready || send.isPending} onClick={() => send.mutate()}>
                {r.amendment_open ? "Send the new version" : `Send to ${r.destination_name}`}
              </Button>
            )}
          </Stack>
          {r.prepared_at && !ready && (
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
              Marked ready by {r.prepared_by}, {fmtDate(r.prepared_at)}. Sending becomes available once the doctor has reviewed every flag.
            </Typography>
          )}
        </Section>
      )}
      {r.packages.length > 0 && <Sent r={r} />}
      <Section title={latest && !r.amendment_open ? `Referral letter (version ${latest} as sent)` : "What will be sent"}
        description="Built from the checked records. Medication flags are shown exactly as the approved rules produced them.">
        {latest && !r.amendment_open ? <SentLetter r={r} version={latest} /> : <LetterPreview r={r} />}
      </Section>
    </Stack>
  );
}

/** The doctor's view of the letter (what will be or was sent) and where it stands. */
export function SummaryTab({ r }: { r: ReferralDetail }) {
  const latest = r.packages[0]?.version;
  return (
    <Stack spacing={2}>
      {r.readiness && r.status === "requested" && (
        <Section title="Progress before sending" description="Staff prepare and send the referral. Items marked 'doctor' need you.">
          <Readiness r={r} />
        </Section>
      )}
      {latest ? <SentLetter r={r} version={latest} /> : <LetterPreview r={r} />}
    </Stack>
  );
}
