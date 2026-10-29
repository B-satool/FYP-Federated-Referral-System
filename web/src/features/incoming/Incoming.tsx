import { ReactNode, useEffect, useState } from "react";
import { Link as RouterLink, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Box,
  Button,
  FormControlLabel,
  Link,
  ListSubheader,
  MenuItem,
  Paper,
  Stack,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import { api } from "../../api/client";
import type { Case, CaseDetail, ConsultationResponse, Practitioner } from "../../api/types";
import { Empty, ErrorAlert, fmtDate, KeyValue, Loading, PageHeader, ReasonDialog, Section, Tag, UrgencyTag } from "../../components/common";
import { ReceivedPackage } from "../e2e/ReceivedPackage";
import { ResultReport } from "../../components/ResultReport";
import { hasRole, isDoctor, ownService, useMe, useRefData } from "../../hooks";
import { ConfirmPatient } from "../identity/ConfirmPatient";

const CASE_STATUS: Record<string, string> = {
  received: "new",
  acknowledged: "acknowledged",
  assigned: "assigned",
  accepted: "accepted",
  declined: "declined",
  responded: "response sent",
  completed: "complete",
};

const NEEDS_INTAKE = ["received", "acknowledged"];

function CaseStatusTag({ status }: { status: string }) {
  const tone = status === "received" ? "warn" : status === "declined" ? "off" : ["responded", "completed"].includes(status) ? "ok" : "info";
  return <Tag tone={tone} label={CASE_STATUS[status] ?? status} />;
}

export function IncomingList() {
  const { data: me } = useMe();
  const ref = useRefData();
  const service = ownService(me);
  const staff = hasRole(me, "clinic_staff", "institution_admin");
  const [intakeOnly, setIntakeOnly] = useState(false);
  const q = useQuery({
    queryKey: ["cases", service],
    queryFn: () => api.get<Case[]>("/cases", service),
    enabled: !!me,
    refetchInterval: 15000,
  });
  const instName = (id: string) => ref.data?.institutions[id]?.name ?? id;
  const deptName = (code: string) => ref.data?.departments[code]?.name ?? code;
  const intakeCount = (q.data ?? []).filter((c) => NEEDS_INTAKE.includes(c.status)).length;
  const rows = (q.data ?? []).filter((c) => !(staff && intakeOnly) || NEEDS_INTAKE.includes(c.status));
  return (
    <>
      <PageHeader
        title="Incoming referrals"
        subtitle={
          staff
            ? `All referrals sent to ${me?.institution_name ?? "your institution"}. Acknowledge each one, confirm the patient and assign a doctor.`
            : `Referrals assigned to you at ${me?.institution_name ?? "your institution"}.`
        }
      />
      {q.isLoading && <Loading />}
      <ErrorAlert error={q.error} />
      {staff && q.data && intakeCount > 0 && (
        <Alert severity="info" sx={{ mb: 2 }}>
          {intakeCount} referral{intakeCount === 1 ? " needs" : "s need"} intake: acknowledge, confirm the patient and assign a doctor.
        </Alert>
      )}
      {staff && !!q.data?.length && (
        <FormControlLabel sx={{ mb: 1 }} control={<Switch checked={intakeOnly} onChange={(e) => setIntakeOnly(e.target.checked)} />} label="Needs intake only" />
      )}
      {q.data && q.data.length === 0 && (
        <Empty>{staff ? "No referrals have been received yet." : "No referrals have been assigned to you yet."}</Empty>
      )}
      {q.data && q.data.length > 0 && rows.length === 0 && <Empty>No referrals need intake.</Empty>}
      {rows.length > 0 && (
        <Paper>
          <Table size="small" aria-label="Incoming referrals">
            <TableHead>
              <TableRow>
                <TableCell>Referral</TableCell>
                <TableCell>Patient</TableCell>
                <TableCell>From</TableCell>
                <TableCell>Department</TableCell>
                <TableCell>Urgency</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Doctor</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {rows.map((c) => (
                <TableRow key={c.id} hover>
                  <TableCell>
                    <Link component={RouterLink} to={`/incoming/${c.id}`}>
                      {c.central_referral_id}
                    </Link>
                    <Typography variant="caption" display="block" color="text.secondary">
                      {fmtDate(c.received_at)}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    {c.patient_name}
                    {c.patient_birth_date && (
                      <Typography variant="caption" display="block" color="text.secondary">
                        born {c.patient_birth_date}
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell>{c.sender_name || instName(c.sender_institution)}</TableCell>
                  <TableCell>{deptName(c.department)}</TableCell>
                  <TableCell>
                    <UrgencyTag urgency={c.urgency} label={ref.data?.urgencies[c.urgency]?.label} />
                  </TableCell>
                  <TableCell>
                    <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                      <CaseStatusTag status={c.status} />
                      {staff && NEEDS_INTAKE.includes(c.status) && <Tag tone="warn" label="needs intake" />}
                      {c.open_info_requests > 0 && <Tag tone="wait" label={`${c.open_info_requests} question(s) open`} />}
                    </Stack>
                  </TableCell>
                  <TableCell>
                    {c.assigned_doctor ?? (
                      <Typography variant="body2" color="text.secondary">
                        Not assigned
                      </Typography>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Paper>
      )}
    </>
  );
}


function ResponseView({ content }: { content: ConsultationResponse["content"] }) {
  return (
    <KeyValue
      items={[
        ["Assessment", content.assessment || "Not recorded"],
        ["Plan", content.plan || "Not recorded"],
        ["Instructions for the referring clinic", content.instructions_for_clinic || "Not recorded"],
        ["Appointment", content.appointment || "Not recorded"],
      ]}
    />
  );
}

/** One numbered intake step with its done / next / waiting state. */
function Step({ n, title, state, children }: { n: number; title: string; state: "done" | "next" | "waiting"; children?: ReactNode }) {
  const tag = state === "done" ? <Tag tone="ok" label="done" /> : state === "next" ? <Tag tone="warn" label="next" /> : <Tag tone="wait" label="waiting" />;
  return (
    <Paper variant="outlined" component="li" sx={{ p: 1.5, listStyle: "none" }}>
      <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: children ? 1 : 0 }}>
        <Typography variant="subtitle2">
          {n}. {title}
        </Typography>
        {tag}
      </Stack>
      {children}
    </Paper>
  );
}

function AssignForm({ c, onAssigned }: { c: Case; onAssigned: () => void }) {
  const { data: me } = useMe();
  const ref = useRefData();
  const service = ownService(me);
  const doctors: Practitioner[] = (ref.data?.practitioners ?? []).filter((p) => p.institution === me?.institution_id);
  const deptName = (code: string) => ref.data?.departments[code]?.name ?? code;
  const preferred = c.requested_doctor && doctors.some((d) => d.name === c.requested_doctor) ? c.requested_doctor : null;
  const [doctor, setDoctor] = useState<string>(c.assigned_doctor ?? preferred ?? "");
  const [note, setNote] = useState(c.assign_note ?? "");
  useEffect(() => {
    if (!doctor && (c.assigned_doctor || preferred)) setDoctor(c.assigned_doctor ?? preferred ?? "");
  }, [preferred]); // eslint-disable-line react-hooks/exhaustive-deps
  const assign = useMutation({
    mutationFn: () => api.post(`/cases/${c.id}/assign`, { doctor, note: note.trim() }, service),
    meta: { success: "Doctor assigned. They will see this referral in their list." },
    onSuccess: onAssigned,
  });
  // the case's department first, then the other departments of this institution
  const sameDept = doctors.filter((d) => d.department === c.department);
  const otherDepts = Array.from(new Set(doctors.filter((d) => d.department !== c.department).map((d) => d.department)));
  const options: ReactNode[] = [];
  if (sameDept.length) {
    options.push(<ListSubheader key="h-own">{deptName(c.department)}</ListSubheader>);
    sameDept.forEach((d) =>
      options.push(
        <MenuItem key={`d-${d.name}`} value={d.name}>
          {d.name}
        </MenuItem>,
      ),
    );
  }
  otherDepts.forEach((dept) => {
    options.push(<ListSubheader key={`h-${dept}`}>{deptName(dept)}</ListSubheader>);
    doctors
      .filter((d) => d.department === dept)
      .forEach((d) =>
        options.push(
          <MenuItem key={`d-${d.name}`} value={d.name}>
            {d.name}
          </MenuItem>,
        ),
      );
  });
  return (
    <Stack spacing={1.5}>
      {c.requested_doctor && (
        <Typography variant="body2" color="text.secondary">
          The referring doctor asked for {c.requested_doctor}
          {preferred ? "; they are preselected." : ", who is not on this institution's list of doctors."}
        </Typography>
      )}
      <TextField select label="Assign to doctor" value={doctor} onChange={(e) => setDoctor(e.target.value)} sx={{ maxWidth: 420 }}>
        {options}
      </TextField>
      {doctors.length === 0 && <Alert severity="warning">No doctors are listed for this institution.</Alert>}
      <TextField label="Note for the doctor" value={note} onChange={(e) => setNote(e.target.value)} multiline minRows={2} sx={{ maxWidth: 620 }} />
      <ErrorAlert error={assign.error} />
      <Box>
        <Button variant="contained" onClick={() => assign.mutate()} disabled={!doctor || assign.isPending}>
          Assign
        </Button>
      </Box>
    </Stack>
  );
}

export function IncomingCase() {
  const id = Number(useParams().id);
  const { data: me } = useMe();
  const ref = useRefData();
  const qc = useQueryClient();
  const service = ownService(me);
  const staff = hasRole(me, "clinic_staff", "institution_admin");
  const doctor = isDoctor(me);
  const q = useQuery({
    queryKey: ["case", service, id],
    queryFn: () => api.get<CaseDetail>(`/cases/${id}`, service),
    enabled: !!me,
    refetchInterval: 15000,
  });
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["case", service, id] });
    qc.invalidateQueries({ queryKey: ["cases", service] });
  };
  const [declineOpen, setDeclineOpen] = useState(false);
  const [askOpen, setAskOpen] = useState(false);
  const [version, setVersion] = useState<number | null>(null);

  const draft = q.data?.responses.length ? q.data.responses[q.data.responses.length - 1] : null;

  const accepted = q.data?.case.decision === "accepted";

  const acknowledge = useMutation({
    mutationFn: () => api.post(`/cases/${id}/acknowledge`, {}, service),
    meta: { success: "Receipt acknowledged. The referring clinic is told." },
    onSuccess: refresh,
  });
  const decide = useMutation({
    mutationFn: (body: { decision: "accept" | "decline"; reason?: string }) => api.post(`/cases/${id}/decision`, body, service),
    meta: { success: "Decision recorded. The referring doctor is told." },
    onSuccess: () => {
      setDeclineOpen(false);
      refresh();
    },
  });
  const ask = useMutation({
    mutationFn: (question: string) => api.post(`/cases/${id}/info-requests`, { question }, service),
    meta: { success: "Question sent to the referring clinic." },
    onSuccess: () => {
      setAskOpen(false);
      refresh();
    },
  });
  const [extendOpen, setExtendOpen] = useState(false);
  const [ownAdded, setOwnAdded] = useState(0);
  const addOwn = useMutation({
    mutationFn: () => api.post<{ items: number; held_back: number }>(`/cases/${id}/own-records`, {}, service),
    meta: { success: "Added, encrypted for the department's doctors." },
    onSuccess: (x) => setOwnAdded(x.items),
  });
  const complete = useMutation({
    mutationFn: () => api.post(`/cases/${id}/complete`, {}, service),
    meta: { success: "Closed. The referring clinic and the patient are told; the encrypted referral is purged in a week." },
    onSuccess: refresh,
  });
  const extend = useMutation({
    mutationFn: (reason: string) => api.post(`/cases/${id}/extend-hold`, { reason }, service),
    meta: { success: "Extended by 30 days. The next reminder moves with it." },
    onSuccess: () => {
      setExtendOpen(false);
      refresh();
    },
  });

  if (q.isLoading || !me) return <Loading />;
  if (q.error) return <ErrorAlert error={q.error} />;
  const { case: c, packages, info_requests, results } = q.data!;
  const shown = packages.find((p) => p.version === version) ?? packages[0];
  const removed = !!c.shared_removed_at || !!shown?.envelope?.purged;
  const env = removed ? undefined : shown?.envelope ?? undefined;
  const redacted = !!q.data!.redacted;
  const urgency = ref.data?.urgencies[c.urgency];
  const deptName = (code: string | null | undefined) => (code ? ref.data?.departments[code]?.name ?? code : null);
  const from = env ? `${env.requesting_doctor.name}, ${env.requesting_doctor.institution}` : c.sender_name;
  const decided = !!c.decision;
  const canDecide = doctor && c.status === "assigned" && !decided;
  const canAsk = doctor && !!c.assigned_doctor && !["responded", "declined", "completed"].includes(c.status);

  // ---- intake steps (staff)
  const acked = !!c.acknowledged_at;
  const confirmed = !!c.local_patient_id;
  const assignedStep = !!c.assigned_doctor;

  // the referral needs no response from here (2026-10-28); one sent before that stays visible
  const sentResponse = draft?.status === "returned" ? draft : null;
  const responseSection = sentResponse && (
    <Section title="Your response" description={`Sent by ${sentResponse.returned_by} on ${fmtDate(sentResponse.returned_at)}.`}>
      <ResponseView content={sentResponse.content} />
    </Section>
  );

  const infoRequests = info_requests.length > 0 && (
    <Section title="Questions to the referring clinic">
      <Stack spacing={1}>
        {info_requests.map((ir) => (
          <Paper key={ir.id} variant="outlined" sx={{ p: 1.5 }}>
            <Typography variant="body2">
              <strong>Q:</strong> {ir.question ?? "Visible to doctors only"}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {ir.created_by}, {fmtDate(ir.created_at)}
            </Typography>
            {ir.answer ? (
              <Typography variant="body2" sx={{ mt: 0.5 }}>
                <strong>A:</strong> {ir.answer} <em>({ir.answered_by}, {fmtDate(ir.answered_at)})</em>
              </Typography>
            ) : (
              <Box sx={{ mt: 0.5 }}>
                <Tag tone="wait" label="waiting for an answer" />
              </Box>
            )}
          </Paper>
        ))}
      </Stack>
    </Section>
  );

  // The notice: who, from where, why and how urgent (administrative data). The content is decrypted on the doctor's
  // device from the platform (ReceivedPackage); this hospital's system never holds it (spec v4, D2).
  const notice = env && (
    <Section title="Referral" description={`Version ${env.package_version}, sent by ${env.sent_by} on ${fmtDate(env.sent_at)}.`}>
      {packages.length > 1 && (
        <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} alignItems={{ sm: "center" }} sx={{ mb: 1.5 }}>
          <TextField select size="small" label="Version" value={shown.version} onChange={(e) => setVersion(Number(e.target.value))} sx={{ minWidth: 220 }}>
            {packages.map((p, i) => (
              <MenuItem key={p.version} value={p.version}>
                Version {p.version}
                {i === 0 ? " (newest)" : ""}, received {fmtDate(p.received_at)}
              </MenuItem>
            ))}
          </TextField>
          {shown.version !== packages[0].version && <Alert severity="warning">You are reading an older version. The newest is version {packages[0].version}.</Alert>}
        </Stack>
      )}
      <KeyValue items={[
        ["From", `${env.requesting_doctor.name}, ${env.requesting_doctor.institution}`],
        ["To", `${deptName(env.destination_department)}, ${me.institution_name}`],
        ["Patient", `${env.patient.name}${env.patient.birth_date ? `, born ${fmtDate(env.patient.birth_date, false)}` : ""}${env.patient.sex ? `, ${env.patient.sex}` : ""}`],
        ["Urgency", ref.data?.urgencies[env.urgency]?.label ?? env.urgency],
        ["Reason", env.reason],
      ]} />
    </Section>
  );
  const letter = (
    <>
      {notice}
      {doctor && !redacted && !removed && !!env && (
        <ReceivedPackage c={c} hospital={me.institution_id ?? ""} />
      )}
    </>
  );

  const isAssignedDoctor = doctor && !!c.assigned_doctor;
  const holdSection = (accepted || removed) && (
    <Section title="Close or extend" description="The encrypted referral stays on the platform while you need it. Your decision and questions are this hospital's own record and are kept.">
      {removed ? (
        <Alert severity="info">
          The encrypted referral was purged{c.shared_removed_at ? ` on ${fmtDate(c.shared_removed_at)}` : ""}. Reference and fingerprint kept; the patient keeps their own copy.
        </Alert>
      ) : c.completed_at ? (
        <Alert severity="success">
          Closed by {c.completed_by} on {fmtDate(c.completed_at)}. The encrypted referral is purged on {fmtDate(c.hold_until)}.
        </Alert>
      ) : (
        <Stack spacing={1.5}>
          <Typography variant="body2">
            You are reminded on <strong>{fmtDate(c.hold_until)}</strong> to close it or extend it (30 days after you accepted, or after an
            extension; at most 180 days in all). Close it when you have finished: it is purged a week later.
          </Typography>
          <ErrorAlert error={complete.error || extend.error} />
          {isAssignedDoctor ? (
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
              <Button variant="contained" onClick={() => complete.mutate()} disabled={complete.isPending}>
                Close referral
              </Button>
              <Button variant="outlined" onClick={() => setExtendOpen(true)} disabled={extend.isPending}>
                Extend by 30 days
              </Button>
            </Stack>
          ) : (
            <Typography variant="body2" color="text.secondary">
              Only the assigned doctor can close or extend it.
            </Typography>
          )}
        </Stack>
      )}
    </Section>
  );

  const shownResults = results.filter((r) => !r.purged);
  const resultsSection = shownResults.length > 0 && (
    <Section title="Results received" description="Test and scan reports for this referral, sent on to you when they are ready.">
      <Stack spacing={1.5}>
        {shownResults.map((r) => (
          <ResultReport
            key={r.id}
            title={r.test}
            subtitle={`${ref.data?.institutions[r.performed_by_institution]?.name ?? r.performed_by_institution} · ${r.order_ref}`}
            values={r.values}
            findings={r.report_text || null}
            reportedBy={r.reported_by}
            reportedAt={r.reported_at}
            service={service}
          />
        ))}
      </Stack>
    </Section>
  );

  return (
    <>
      <PageHeader
        title={`${c.central_referral_id} · ${c.patient_name}`}
        back={{ to: "/incoming", label: "Incoming referrals" }}
        subtitle={
          <Stack spacing={0.75}>
            <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
              <CaseStatusTag status={c.status} />
              <UrgencyTag urgency={c.urgency} label={urgency?.label} />
              {c.latest_version > 1 && <Tag tone="info" label={`updated: version ${c.latest_version}`} />}
            </Stack>
            <span>
              From {from} · to {deptName(c.department)} · received {fmtDate(c.received_at)}
              {c.assigned_doctor ? ` · assigned to ${c.assigned_doctor}` : ""}
            </span>
          </Stack>
        }
      />
      <Stack spacing={2}>
        {staff && (
          <Section title="Intake" description="Take the referral in: acknowledge receipt, confirm who the patient is here, then assign a doctor.">
            <Stack component="ol" spacing={1.5} sx={{ m: 0, p: 0 }}>
              <Step n={1} title="Acknowledge receipt" state={acked ? "done" : "next"}>
                {acked ? (
                  <Typography variant="body2" color="text.secondary">
                    {c.acknowledged_by}, {fmtDate(c.acknowledged_at)}
                  </Typography>
                ) : (
                  <>
                    <ErrorAlert error={acknowledge.error} />
                    <Button variant="contained" onClick={() => acknowledge.mutate()} disabled={acknowledge.isPending}>
                      Acknowledge receipt
                    </Button>
                  </>
                )}
              </Step>
              <Step n={2} title="Confirm the patient" state={confirmed ? "done" : acked ? "next" : "waiting"}>
                <ConfirmPatient
                  linkId={c.link_request_id}
                  localPatientId={c.local_patient_id}
                  patient={{ name: c.patient_name, birth_date: c.patient_birth_date, sex: c.patient_sex, cnic: c.patient_cnic }}
                  requester={c.sender_name}
                  onDone={refresh}
                />
              </Step>
              <Step n={3} title="Assign to a doctor" state={assignedStep ? "done" : acked && confirmed ? "next" : "waiting"}>
                {assignedStep && (
                  <Typography variant="body2" sx={{ mb: decided ? 0 : 1.5 }}>
                    Assigned to <strong>{c.assigned_doctor}</strong> by {c.assigned_by}, {fmtDate(c.assigned_at)}
                    {c.assign_note ? `. Note: ${c.assign_note}` : ""}
                  </Typography>
                )}
                {!decided && acked && confirmed && <AssignForm key={c.assigned_doctor ?? "none"} c={c} onAssigned={refresh} />}
                {!decided && !(acked && confirmed) && (
                  <Typography variant="body2" color="text.secondary">
                    Acknowledge receipt and confirm the patient first.
                  </Typography>
                )}
                {decided && (
                  <Typography variant="body2" color="text.secondary">
                    {c.decision === "accepted" ? "Accepted" : "Declined"} by {c.decision_by}, {fmtDate(c.decision_at)}
                    {c.decline_reason ? `. Reason: ${c.decline_reason}` : ""}
                  </Typography>
                )}
              </Step>
              <Step n={4} title="Add our own records for the doctor (optional)" state={ownAdded ? "done" : confirmed ? "next" : "waiting"}>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                  This hospital's records for the patient are encrypted for the department's doctors. You will not see them.
                </Typography>
                <ErrorAlert error={addOwn.error} />
                <Button variant="outlined" disabled={!confirmed || addOwn.isPending || c.decision === "declined" || !!c.completed_at}
                  onClick={() => addOwn.mutate()}>
                  Add our records
                </Button>
                {ownAdded && <Typography variant="body2" sx={{ mt: 1 }}>{ownAdded} record(s) added, encrypted for the department.</Typography>}
              </Step>
            </Stack>
          </Section>
        )}


        {doctor && (canDecide || canAsk || decided) && (
          <Section
            title="Decision"
            description={canDecide ? "Accept or decline the referral (with a reason). The referring doctor is told either way. You can also ask the referring clinic for more information." : undefined}
          >
            <ErrorAlert error={decide.error || ask.error} />
            {c.assign_note && !decided && (
              <Alert severity="info" sx={{ mb: 1.5 }}>
                Note from {c.assigned_by}: {c.assign_note}
              </Alert>
            )}
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
              {canDecide && (
                <>
                  <Button variant="contained" onClick={() => decide.mutate({ decision: "accept" })} disabled={decide.isPending}>
                    Accept referral
                  </Button>
                  <Button variant="outlined" color="error" onClick={() => setDeclineOpen(true)}>
                    Decline
                  </Button>
                </>
              )}
              {canAsk && (
                <Button variant="outlined" onClick={() => setAskOpen(true)}>
                  Ask for more information
                </Button>
              )}
            </Stack>
            {decided && (
              <Typography variant="body2" color="text.secondary" sx={{ mt: canAsk ? 1.5 : 0 }}>
                {c.decision === "accepted" ? "Accepted" : "Declined"} by {c.decision_by}, {fmtDate(c.decision_at)}
                {c.decline_reason ? `. Reason: ${c.decline_reason}` : ""}
              </Typography>
            )}
          </Section>
        )}

        {doctor && !c.assigned_doctor && (
          <Alert severity="info">This referral has not been assigned to a doctor yet. Staff assign it after intake.</Alert>
        )}

        {infoRequests}

        {responseSection}

        {holdSection}

        {letter}
        {redacted && !removed && shown && (
          <Section title="Records attached" description="What the referral contains, by title. Its clinical content is visible to the doctors here.">
            <Box component="ul" sx={{ m: 0, pl: 2.5 }}>
              {shown.record_titles.map((t, i) => (
                <li key={i}>
                  <Typography variant="body2">
                    {t.title}
                    {t.date ? ` · ${fmtDate(t.date, false)}` : ""}
                  </Typography>
                </li>
              ))}
            </Box>
            {shown.record_titles.length === 0 && <Empty>No records attached.</Empty>}
          </Section>
        )}
        {!env && !removed && !redacted && <Empty>The referral letter has not been received yet.</Empty>}

        {resultsSection}

        {packages.length > 0 && (
          <Section title="Versions received">
            <Table size="small" aria-label="Versions received">
              <TableHead>
                <TableRow>
                  <TableCell>Version</TableCell>
                  <TableCell>Sent by</TableCell>
                  <TableCell>Sent</TableCell>
                  <TableCell>Received</TableCell>
                  <TableCell>Content hash</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {packages.map((p) => (
                  <TableRow key={p.version}>
                    <TableCell>v{p.version}</TableCell>
                    <TableCell>{!p.envelope ? "-" : p.envelope.purged ? "removed" : p.envelope.sent_by}</TableCell>
                    <TableCell>{!p.envelope ? "-" : p.envelope.purged ? "removed" : fmtDate(p.envelope.sent_at)}</TableCell>
                    <TableCell>{fmtDate(p.received_at)}</TableCell>
                    <TableCell>
                      <code title={p.content_hash}>{p.content_hash.slice(0, 12)}…</code>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Section>
        )}
      </Stack>

      <ReasonDialog
        open={declineOpen}
        title="Decline referral"
        label="Reason (the referring clinic will see this)"
        confirm="Decline referral"
        onClose={() => setDeclineOpen(false)}
        onConfirm={(reason) => decide.mutate({ decision: "decline", reason })}
        busy={decide.isPending}
      />
      <ReasonDialog
        open={extendOpen}
        title="Extend the referral by 30 days"
        label="Why do you need them for longer?"
        confirm="Extend by 30 days"
        onClose={() => setExtendOpen(false)}
        onConfirm={(reason) => extend.mutate(reason)}
        busy={extend.isPending}
      />
      <ReasonDialog
        open={askOpen}
        title="Ask the referring clinic for more information"
        label="Your question"
        confirm="Send question"
        onClose={() => setAskOpen(false)}
        onConfirm={(question) => ask.mutate(question)}
        busy={ask.isPending}
      />
    </>
  );
}