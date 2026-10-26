import { useMutation } from "@tanstack/react-query";
import { Button, Table, TableBody, TableCell, TableHead, TableRow, Typography } from "@mui/material";
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
  if (link?.kind === "intake" && link.status === "verified")
    return <Tag tone="ok" label={link.registered_new ? "new patient there" : "matched on arrival"} />;
  if (link?.kind === "intake" && link.status === "requested") return <Tag tone="wait" label="confirms when it arrives" />;
  if (s.linked) return <Tag tone="ok" label="records shared" />;
  if (link?.status === "requested") return <Tag tone="wait" label="waiting for them to check" />;
  if (link?.status === "rejected") return <Tag tone="bad" label="no record there" />;
  if (link?.status === "invalidated") return <Tag tone="off" label="link withdrawn" />;
  return <Tag tone="neutral" label="not asked" />;
}

/**
 * Other places the patient has been. Staff ask a place for its records; that place's staff match
 * the patient to their record (records then open) or say they have no record. The receiving
 * institution is not asked here: it confirms the patient when the referral arrives.
 */
export function OtherPlaces({ r }: { r: ReferralDetail }) {
  const { data: me } = useMe();
  const refresh = useInvalidateReferral(r.id);
  const ask = useMutation({
    mutationFn: (target: string) => api.post(`/referrals/${r.id}/links`, { target_institution: target }),
    meta: { success: "Records request sent." },
    onSuccess: refresh,
  });
  const staff = isStaff(me);
  const rows = [...r.sources].sort((a, b) => Number(b.own) - Number(a.own) || Number(a.destination) - Number(b.destination));

  return (
    <Section
      title="Records from other places"
      description="Ask a place only if the patient says they have been seen there. Their staff match the patient to their record, or say they have no record. Records are never matched on names or IDs alone."
    >
      <ErrorAlert error={ask.error} />
      <Table size="small" aria-label="Other places">
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
            const canAsk = staff && !s.own && !s.linked && link?.status !== "requested" && r.status === "requested";
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
                <TableCell>{s.own ? r.patient.local_patient_id : s.local_patient_id ?? link?.target_local_id ?? "None"}</TableCell>
                <TableCell>
                  <Typography variant="caption" display="block">
                    {link?.status === "verified" && `${link.decided_by}, ${fmtDate(link.decided_at)}${link.registered_new ? ". They had no earlier record; registered when the referral arrived." : ""}`}
                    {link?.status === "requested" && `Asked by ${link.requested_by}, ${fmtDate(link.requested_at)}`}
                    {link?.status === "rejected" && `Their answer: ${link.decision_note}`}
                  </Typography>
                </TableCell>
                <TableCell align="right">
                  {canAsk && (
                    <Button size="small" variant="outlined" disabled={ask.isPending} onClick={() => ask.mutate(s.institution_id)}>
                      Ask for records
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
      <Typography variant="body2" color="text.secondary" sx={{ mt: 1.5 }}>
        Only the most recently visited hospital, clinic and laboratory are used for the referral.
      </Typography>
    </Section>
  );
}
