import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Paper, Table, TableBody, TableCell, TableHead, TableRow } from "@mui/material";
import { api } from "../../api/client";
import { ErrorAlert, fmtDate, Loading, PageHeader, ReasonDialog, Tag } from "../../components/common";
import { useMe, useRefData } from "../../hooks";

type AdminUser = { id: string; username: string; name: string; department: string | null; enabled: boolean; central_status: string; roles: string[]; last_seen_at: string | null };

const ROLE_LABELS: Record<string, string> = {
  clinician: "Doctor",
  clinic_staff: "Staff",
  diagnostics_staff: "Laboratory/imaging staff",
  institution_admin: "Administrator",
  rule_reviewer: "Clinical rule reviewer",
};

export function AdminUsers() {
  const { data: me } = useMe();
  const ref = useRefData();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["admin-users"], queryFn: () => api.get<AdminUser[]>("/admin/users") });
  const [target, setTarget] = useState<{ user: AdminUser; enable: boolean } | null>(null);
  const change = useMutation({
    mutationFn: (reason: string) => api.post(`/admin/users/${target!.user.id}/${target!.enable ? "enable" : "disable"}`, { reason }),
    meta: { success: "Account updated." },
    onSuccess: () => {
      setTarget(null);
      qc.invalidateQueries({ queryKey: ["admin-users"] });
    },
  });
  return (
    <>
      <PageHeader title="Accounts" subtitle={`Accounts of ${me?.institution_name ?? "your institution"}`} />
      <Alert severity="info" sx={{ mb: 2 }}>
        Disabling an account ends its sessions and blocks access straight away, including to records already copied into referrals. Administrator access
        does not give access to clinical records.
      </Alert>
      {q.isLoading && <Loading />}
      <ErrorAlert error={q.error || change.error} />
      {q.data && (
        <Paper>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>User</TableCell>
                <TableCell>Department</TableCell>
                <TableCell>Role</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Last seen</TableCell>
                <TableCell>
                  <span className="sr-only">Actions</span>
                </TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {q.data.map((u) => {
                const active = u.enabled && u.central_status !== "disabled";
                return (
                  <TableRow key={u.id}>
                    <TableCell>
                      {u.name} ({u.username})
                    </TableCell>
                    <TableCell>{u.department ? ref.data?.departments[u.department]?.name ?? u.department : "Not set"}</TableCell>
                    <TableCell>{u.roles.map((r) => ROLE_LABELS[r] ?? r).join(", ")}</TableCell>
                    <TableCell>
                      <Tag tone={active ? "ok" : "off"} label={active ? "active" : "disabled"} />
                    </TableCell>
                    <TableCell>{u.last_seen_at ? fmtDate(u.last_seen_at) : "Never signed in"}</TableCell>
                    <TableCell>
                      {u.id !== me?.id && (
                        <Button size="small" color={active ? "error" : "primary"} onClick={() => setTarget({ user: u, enable: !active })}>
                          {active ? "Disable" : "Enable"}
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </Paper>
      )}
      {target && (
        <ReasonDialog open title={`${target.enable ? "Enable" : "Disable"} ${target.user.username}`} label="Reason" confirm={target.enable ? "Enable" : "Disable"} onClose={() => setTarget(null)} onConfirm={(r) => change.mutate(r)} busy={change.isPending} />
      )}
    </>
  );
}
