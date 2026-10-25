import { useMutation } from "@tanstack/react-query";
import { Alert, Button, Stack, Table, TableBody, TableCell, TableHead, TableRow, Typography } from "@mui/material";
import { api } from "../../api/client";
import type { PatientLink, ReferralDetail, SourceOverview } from "../../api/types";
import { ErrorAlert, fmtDate, Section, Tag } from "../../components/common";
import { isStaff, useMe } from "../../hooks";
import { useInvalidateReferral } from "./ReferralWorkspace";

function latestLink(r: ReferralDetail, inst: string): PatientLink | undefined {
  return [...r.links].reverse().find((l) => l.target_institution === inst || l.requester_institution === inst);
}

function State({ s, link }: { s: SourceOverview; link?: PatientLink }) {
  if (s.own) return <Tag tone="ok" label="your own record" />;
  if (s.linked) return <Tag tone="ok" label="confirmed" />;
  if (link?.status === "requested") return <Tag tone="wait" label="waiting for them to check" />;
  if (link?.status === "rejected") return <Tag tone="bad" label="they could not confirm" />;
  if (link?.status === "invalidated") return <Tag tone="off" label="link withdrawn" />;
  return <Tag tone="neutral" label="not linked" />;
}

export function LinksTab({ r }: { r: ReferralDetail }) {
  const { data: me } = useMe();
  const refresh = useInvalidateReferral(r.id);
  const ask = useMutation({
    mutationFn: (target: string) => api.post(`/referrals/${r.id}/links`, { target_institution: target }),
    meta: { success: "Link request sent." },
    onSuccess: refresh,
  });
  const staff = isStaff(me);
  const rows = [...r.sources].sort((a, b) => Number(b.destination) - Number(a.destination) || Number(b.own) - Number(a.own));
  const dest = r.sources.find((s) => s.destination);

  return (
    <Stack spacing={2}>
      {dest && !dest.linked && (
        <Alert severity="info">
          {dest.name} must confirm which of their patient records is {r.patient.name} before the referral can be sent. A request was sent when the
          doctor submitted the referral; their staff check it against their own records (CNIC, name and date of birth).
        </Alert>
      )}
      <Section
        title="Patient links"
        description="Records from another institution open only after that institution's staff confirm the patient. Records are never matched on names or IDs alone."
      >
        <ErrorAlert error={ask.error} />
        <Table size="small" aria-label="Patient links">
          <TableHead>
            <TableRow>
              <TableCell>Institution</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Their record</TableCell>
              <TableCell>Details</TableCell>
              <TableCell />
            </TableRow>
          </TableHead>
          <TableBody>
            {rows.map((s) => {
              const link = latestLink(r, s.institution_id);
              const canAsk = staff && !s.own && !s.linked && link?.status !== "requested";
              return (
                <TableRow key={s.institution_id}>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>
                      {s.name}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {s.kind}
                      {s.destination ? " · receiving the referral" : ""}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <State s={s} link={link} />
                  </TableCell>
                  <TableCell>{s.own ? r.patient.local_patient_id : s.local_patient_id ?? "None"}</TableCell>
                  <TableCell>
                    <Typography variant="caption" display="block">
                      {link?.status === "verified" && `Confirmed by ${link.decided_by}, ${fmtDate(link.decided_at)}${link.registered_new ? " (registered as a new patient)" : ""}`}
                      {link?.status === "requested" && `Requested by ${link.requested_by}, ${fmtDate(link.requested_at)}`}
                      {link?.status === "rejected" && `Reason: ${link.decision_note}`}
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    {canAsk && (
                      <Button size="small" variant="outlined" disabled={ask.isPending} onClick={() => ask.mutate(s.institution_id)}>
                        Ask them to confirm
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 1.5 }}>
          Ask an institution only if the patient says they have been seen there. For records, only the most recently visited hospital, clinic and
          laboratory are used.
        </Typography>
      </Section>
    </Stack>
  );
}
