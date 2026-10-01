import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Paper, Table, TableBody, TableCell, TableHead, TableRow } from "@mui/material";
import { api } from "../../api/client";
import { ErrorAlert, fmtDate, Loading, PageHeader, ReasonDialog, Tag } from "../../components/common";
import { useMe } from "../../hooks";

type AdminUser = { id: string; username: string; name: string; enabled: boolean; central_status: string; roles: string[]; last_seen_at: string | null };

export function AdminUsers() {
  const { data: me } = useMe();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["admin-users"], queryFn: () => api.get<AdminUser[]>("/admin/users") });
  const [target, setTarget] = useState<{ user: AdminUser; enable: boolean } | null>(null);
  const change = useMutation({
    mutationFn: (reason: string) => api.post(`/admin/users/${target!.user.id}/${target!.enable ? "enable" : "disable"}`, { reason }),
    onSuccess: () => {
      setTarget(null);
      qc.invalidateQueries({ queryKey: ["admin-users"] });
    },
  });
  return (
    <>
      <PageHeader title="Accounts" subtitle={`Local accounts of ${me?.institution_name}`} />
      <Alert severity="info" sx={{ mb: 2 }}>
        Disabling an account ends its sessions and blocks access immediately at the central platform (and at source services within seconds), including
        to centrally retained data. Administrator access does not grant access to clinical records.
      </Alert>
      {q.isLoading && <Loading />}
      <ErrorAlert error={q.error || change.error} />
      {q.data && (
        <Paper>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>User</TableCell>
                <TableCell>Roles</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Last seen</TableCell>
                <TableCell />
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
                    <TableCell>{u.roles.join(", ")}</TableCell>
                    <TableCell>
                      <Tag tone={active ? "ok" : "off"} label={active ? "active" : "disabled"} />
                    </TableCell>
                    <TableCell>{fmtDate(u.last_seen_at)}</TableCell>
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
