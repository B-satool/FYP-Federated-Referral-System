import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, MenuItem, Paper, Stack, Table, TableBody, TableCell, TableHead, TableRow, TextField, Typography } from "@mui/material";
import { api } from "../../api/client";
import { ErrorAlert, fmtDate, Loading, PageHeader, ReasonDialog, Tag } from "../../components/common";
import { useMe, useRefData } from "../../hooks";
import type { RoleTemplate } from "../../api/types";

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
  const templates = useQuery({ queryKey: ["role-templates"], queryFn: () => api.get<RoleTemplate[]>("/admin/role-templates") });
  const [target, setTarget] = useState<{ user: AdminUser; enable: boolean } | null>(null);
  const [assign, setAssign] = useState<{ user: AdminUser; template: RoleTemplate } | null>(null);
  const apply = useMutation({
    mutationFn: (reason: string) => api.post(`/admin/users/${assign!.user.id}/apply-template`, { template_id: assign!.template.template_id, reason }),
    meta: { success: "Role changed. It applies when the user next signs in, or within about 5 minutes if they are signed in now." },
    onSuccess: () => {
      setAssign(null);
      qc.invalidateQueries({ queryKey: ["admin-users"] });
    },
  });
  const current = (u: AdminUser) => templates.data?.find((t) => t.roles.length === u.roles.filter((r) => r in ROLE_LABELS).length && t.roles.every((r) => u.roles.includes(r)));
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
      <ErrorAlert error={q.error || change.error || apply.error || templates.error} />
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
                    <TableCell>
                      {u.id !== me?.id && templates.data?.length ? (
                        <TextField select size="small" label="Role" value={current(u)?.template_id ?? ""} sx={{ minWidth: 220 }}
                          onChange={(e) => { const t = templates.data!.find((x) => x.template_id === e.target.value); if (t) setAssign({ user: u, template: t }); }}>
                          {!current(u) && <MenuItem value="" disabled>{u.roles.map((r) => ROLE_LABELS[r] ?? r).join(", ") || "No role"}</MenuItem>}
                          {templates.data.map((t) => <MenuItem key={t.template_id} value={t.template_id}>{t.name}</MenuItem>)}
                        </TextField>
                      ) : (
                        u.roles.map((r) => ROLE_LABELS[r] ?? r).join(", ")
                      )}
                    </TableCell>
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
      {assign && (
        <ReasonDialog open title={`Make ${assign.user.name} ${assign.template.name}`} label="Reason" confirm="Change role"
          onClose={() => setAssign(null)} onConfirm={(r) => apply.mutate(r)} busy={apply.isPending}>
          <Stack spacing={0.5} sx={{ mb: 1 }}>
            <Typography variant="body2">{assign.template.description}</Typography>
            <Typography variant="caption" color="text.secondary">Records shared by this role last {assign.template.default_grant_days} days by default.</Typography>
          </Stack>
        </ReasonDialog>
      )}
      {target && (
        <ReasonDialog open title={`${target.enable ? "Enable" : "Disable"} ${target.user.username}`} label="Reason" confirm={target.enable ? "Enable" : "Disable"} onClose={() => setTarget(null)} onConfirm={(r) => change.mutate(r)} busy={change.isPending} />
      )}
    </>
  );
}
