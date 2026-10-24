import { Link as RouterLink } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Link, Paper, Table, TableBody, TableCell, TableHead, TableRow, Typography } from "@mui/material";
import { api } from "../../api/client";
import { Empty, ErrorAlert, fmtDate, Loading, PageHeader, Tag } from "../../components/common";

export type CaseSummary = {
  id: number;
  central_referral_id: string;
  sender_institution: string;
  patient_name: string;
  patient_birth_date: string | null;
  specialist_patient_id: string | null;
  priority: string;
  status: string;
  latest_version: number;
  acknowledged_by: string | null;
  acknowledged_at: string | null;
  decision: string | null;
  decision_by: string | null;
  decision_at: string | null;
  decline_reason: string | null;
  received_at: string;
  updated_at: string;
  open_clarifications?: number;
};

const TONE: Record<string, "warn" | "ok" | "info" | "off"> = { received: "warn", acknowledged: "info", accepted: "ok", declined: "off", responded: "ok" };

export function SpecialistInbox() {
  const q = useQuery({ queryKey: ["spec-cases"], queryFn: () => api.get<CaseSummary[]>("/specialist/cases", "specialist"), refetchInterval: 10000 });
  return (
    <>
      <PageHeader title="Incoming referrals" subtitle="Aga Khan University Hospital" />
      {q.isLoading && <Loading />}
      <ErrorAlert error={q.error} />
      {q.data && (
        <Paper>
          <Table size="small" aria-label="Incoming referrals">
            <TableHead>
              <TableRow>
                <TableCell>Referral</TableCell>
                <TableCell>Patient</TableCell>
                <TableCell>From</TableCell>
                <TableCell>Priority</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Version</TableCell>
                <TableCell>Received</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {q.data.map((c) => (
                <TableRow key={c.id} hover>
                  <TableCell>
                    <Link component={RouterLink} to={`/specialist/cases/${c.id}`}>
                      {c.central_referral_id}
                    </Link>
                  </TableCell>
                  <TableCell>
                    {c.patient_name}
                    <Typography variant="caption" display="block" color="text.secondary">
                      born {c.patient_birth_date} {c.specialist_patient_id ? `· our record ${c.specialist_patient_id}` : "· no linked local record"}
                    </Typography>
                  </TableCell>
                  <TableCell>{c.sender_institution}</TableCell>
                  <TableCell>{c.priority}</TableCell>
                  <TableCell>
                    <Tag tone={TONE[c.status] ?? "info"} label={c.status} />
                    {!!c.open_clarifications && <Tag tone="warn" label={`${c.open_clarifications} open question(s)`} />}
                  </TableCell>
                  <TableCell>v{c.latest_version}</TableCell>
                  <TableCell>{fmtDate(c.received_at)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {q.data.length === 0 && <Empty>No referrals received yet.</Empty>}
        </Paper>
      )}
    </>
  );
}
