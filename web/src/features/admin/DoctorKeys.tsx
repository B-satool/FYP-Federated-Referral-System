import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Paper, Stack, Table, TableBody, TableCell, TableHead, TableRow, Typography } from "@mui/material";
import { api } from "../../api/client";
import { ErrorAlert, fmtDate, Loading, PageHeader, ReasonDialog, Tag, Tone } from "../../components/common";
import { ownService, useMe, useRefData } from "../../hooks";

type DoctorKey = {
  id: number; subject_id: string; username: string; display_name: string; department: string | null;
  key_version: number; enc_key_id: string; fingerprint: string; status: "pending" | "active" | "revoked" | "rejected";
  recovery: boolean; approved_by: string | null; revoked_by: string | null; revoked_at: string | null;
  created_at: string; published: boolean;
};

const TONE: Record<DoctorKey["status"], Tone> = { active: "ok", pending: "wait", revoked: "off", rejected: "bad" };

/** An institution administrator signs, revokes and rotates keys in the institution's own system. */
export function DoctorKeys() {
  const { data: me } = useMe();
  const ref = useRefData();
  const service = ownService(me);
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["doctor-keys", service], queryFn: () => api.get<DoctorKey[]>("/e2e/keys/doctors", service),
    enabled: service !== "central" });
  const [revoking, setRevoking] = useState<DoctorKey | null>(null);
  const [rotating, setRotating] = useState<string | null>(null);
  const done = () => qc.invalidateQueries({ queryKey: ["doctor-keys", service] });
  const approve = useMutation({ mutationFn: (id: number) => api.post(`/e2e/keys/doctors/${id}/approve`, undefined, service),
    meta: { success: "Key signed by the hospital." }, onSuccess: done });
  const revoke = useMutation({ mutationFn: (reason: string) => api.post(`/e2e/keys/doctors/${revoking!.id}/revoke`, { reason }, service),
    meta: { success: "Key revoked; the department key was rotated." }, onSuccess: () => { setRevoking(null); done(); } });
  const rotate = useMutation({ mutationFn: (reason: string) => api.post(`/e2e/keys/departments/${rotating}/rotate`, { reason }, service),
    meta: { success: "Department key rotated." }, onSuccess: () => { setRotating(null); done(); } });
  if (service === "central") return <Alert severity="info">Keys are managed in each hospital's own system.</Alert>;
  if (q.isLoading) return <Loading />;
  const rows = q.data ?? [];
  const departments = [...new Set(rows.filter((r) => r.department).map((r) => r.department!))].sort();
  const deptName = (d: string | null) => (d ? ref.data?.departments[d]?.name ?? d : "No department");
  return (
    <>
      <PageHeader title="Doctors' keys" subtitle={`${me?.institution_name ?? ""} signs its doctors' public keys. Private keys stay on each doctor's device.`} />
      <Alert severity="info" sx={{ mb: 2 }}>
        A signed key lets other institutions encrypt records to that doctor, and gives the doctor their department's group key. Revoking a
        key (a doctor left, or lost a device) rotates the department key, so new referrals use a version the doctor never had. Anything the
        doctor could already open stays readable to them.
      </Alert>
      <ErrorAlert error={q.error || approve.error || revoke.error || rotate.error} />
      <Paper sx={{ mb: 2, overflowX: "auto" }}>
        <Table size="small">
          <TableHead>
            <TableRow><TableCell>Doctor</TableCell><TableCell>Department</TableCell><TableCell>Key</TableCell><TableCell>Status</TableCell><TableCell>Registered</TableCell><TableCell /></TableRow>
          </TableHead>
          <TableBody>
            {rows.map((k) => (
              <TableRow key={k.id}>
                <TableCell>{k.display_name}<Typography variant="caption" display="block" color="text.secondary">{k.username}</Typography></TableCell>
                <TableCell>{deptName(k.department)}</TableCell>
                <TableCell><code>{k.fingerprint}</code><Typography variant="caption" display="block">version {k.key_version}{k.recovery ? ", replaces a lost key" : ""}</Typography></TableCell>
                <TableCell><Tag tone={TONE[k.status]} label={k.status} />{!k.published && k.status !== "pending" && <Typography variant="caption" display="block">not yet in the platform directory</Typography>}</TableCell>
                <TableCell>{fmtDate(k.created_at)}</TableCell>
                <TableCell align="right">
                  <Stack direction="row" spacing={1} justifyContent="flex-end">
                    {k.status === "pending" && <Button size="small" variant="contained" onClick={() => approve.mutate(k.id)}>Sign</Button>}
                    {k.status !== "revoked" && <Button size="small" color="warning" onClick={() => setRevoking(k)}>Revoke</Button>}
                  </Stack>
                </TableCell>
              </TableRow>
            ))}
            {!rows.length && <TableRow><TableCell colSpan={6}>No doctor has registered a device key yet.</TableCell></TableRow>}
          </TableBody>
        </Table>
      </Paper>
      {departments.length > 0 && (
        <Paper sx={{ p: 2 }}>
          <Typography variant="h6" gutterBottom>Department group keys</Typography>
          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
            {departments.map((d) => <Button key={d} variant="outlined" size="small" onClick={() => setRotating(d)}>Rotate {deptName(d)}</Button>)}
          </Stack>
        </Paper>
      )}
      <ReasonDialog open={!!revoking} title={`Revoke ${revoking?.display_name}'s key`} label="Reason (recorded)" confirm="Revoke"
        onClose={() => setRevoking(null)} onConfirm={(r) => revoke.mutate(r)} busy={revoke.isPending} />
      <ReasonDialog open={!!rotating} title={`Rotate the ${deptName(rotating)} key`} label="Reason (recorded)" confirm="Rotate"
        onClose={() => setRotating(null)} onConfirm={(r) => rotate.mutate(r)} busy={rotate.isPending} />
    </>
  );
}
