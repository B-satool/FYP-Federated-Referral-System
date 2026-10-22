import { useQuery } from "@tanstack/react-query";
import { Paper, Table, TableBody, TableCell, TableHead, TableRow, Typography } from "@mui/material";
import { api } from "../../api/client";
import type { AuditEvent, ReferralDetail } from "../../api/types";
import { ErrorAlert, fmtDate, Loading, Tag } from "../../components/common";

export function AuditTable({ rows }: { rows: AuditEvent[] }) {
  return (
    <Table size="small" aria-label="Audit events">
      <TableHead>
        <TableRow>
          <TableCell>Time</TableCell>
          <TableCell>Actor</TableCell>
          <TableCell>Institution</TableCell>
          <TableCell>Action</TableCell>
          <TableCell>Target</TableCell>
          <TableCell>Outcome</TableCell>
        </TableRow>
      </TableHead>
      <TableBody>
        {rows.map((a) => (
          <TableRow key={a.id}>
            <TableCell sx={{ whiteSpace: "nowrap" }}>{fmtDate(a.created_at)}</TableCell>
            <TableCell>{a.actor_name}</TableCell>
            <TableCell>{a.institution_id ?? "None"}</TableCell>
            <TableCell>
              {a.action}
              {Object.keys(a.detail ?? {}).length > 0 && (
                <Typography variant="caption" display="block" color="text.secondary" sx={{ maxWidth: 420, overflow: "hidden", textOverflow: "ellipsis" }}>
                  {Object.entries(a.detail)
                    .slice(0, 4)
                    .map(([k, v]) => `${k}: ${typeof v === "object" ? JSON.stringify(v) : String(v)}`)
                    .join(" · ")}
                </Typography>
              )}
            </TableCell>
            <TableCell>
              {a.target_type} {a.target_id}
            </TableCell>
            <TableCell>
              <Tag tone={a.outcome === "success" ? "ok" : a.outcome === "denied" || a.outcome === "rejected" ? "off" : "warn"} label={a.outcome} />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

export function AuditTab({ r }: { r: ReferralDetail }) {
  const q = useQuery({ queryKey: ["referral", r.id, "audit"], queryFn: () => api.get<AuditEvent[]>(`/referrals/${r.id}/audit`) });
  return (
    <Paper sx={{ p: 2 }}>
      <Typography variant="h6" gutterBottom>
        Audit trail
      </Typography>
      <Typography variant="body2" color="text.secondary" gutterBottom>
        Access, retrieval, identity linking, corrections, approvals, submissions and status changes, with actor, institution, target, time and outcome.
      </Typography>
      {q.isLoading && <Loading />}
      <ErrorAlert error={q.error} />
      {q.data && <AuditTable rows={[...q.data].reverse()} />}
    </Paper>
  );
}
