import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { MenuItem, Paper, Stack, Tab, Tabs, TextField } from "@mui/material";
import { api } from "../../api/client";
import type { AuditEvent } from "../../api/types";
import { ErrorAlert, Loading, PageHeader } from "../../components/common";
import { ownService, useMe } from "../../hooks";
import { AuditTable } from "../referrals/AuditTab";

type SourceAudit = { id: number; actor_name: string; institution_id: string | null; action: string; target_type: string; target_id: string; outcome: string; referral_context: string | null; detail: Record<string, unknown>; created_at: string };

export function AuditLog() {
  const { data: me } = useMe();
  const [tab, setTab] = useState("central");
  const [action, setAction] = useState("");
  const [outcome, setOutcome] = useState("");
  const own = ownService(me);
  const service = own === "central" ? undefined : own;
  const central = useQuery({
    queryKey: ["admin-audit", action, outcome],
    queryFn: () => api.get<AuditEvent[]>(`/admin/audit?action=${encodeURIComponent(action)}${outcome ? `&outcome=${outcome}` : ""}`),
    enabled: tab === "central",
  });
  const source = useQuery({ queryKey: ["source-audit", service], queryFn: () => api.get<SourceAudit[]>("/admin/audit", service), enabled: tab === "source" && !!service });
  const rows: AuditEvent[] =
    tab === "central"
      ? central.data ?? []
      : (source.data ?? []).map((s) => ({ ...s, actor_id: "", referral_id: null, target_id: `${s.target_id}${s.referral_context ? ` (${s.referral_context})` : ""}` }));
  return (
    <>
      <PageHeader title="Audit log" subtitle="Who did what, where, when and with what outcome. Metadata only; no clinical content." />
      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 2 }}>
        <Tab value="central" label="Central platform" />
        {service && <Tab value="source" label={`${me?.institution_name} own system`} />}
      </Tabs>
      {tab === "central" && (
        <Stack direction="row" spacing={2} sx={{ mb: 2 }}>
          <TextField size="small" label="Action contains" value={action} onChange={(e) => setAction(e.target.value)} />
          <TextField size="small" select label="Outcome" value={outcome} onChange={(e) => setOutcome(e.target.value)} sx={{ minWidth: 160 }}>
            <MenuItem value="">Any</MenuItem>
            {["success", "denied", "failed", "rejected", "unavailable"].map((o) => (
              <MenuItem key={o} value={o}>
                {o}
              </MenuItem>
            ))}
          </TextField>
        </Stack>
      )}
      {(central.isLoading || source.isLoading) && <Loading />}
      <ErrorAlert error={central.error || source.error} />
      <Paper sx={{ p: 1 }}>
        <AuditTable rows={rows} />
      </Paper>
    </>
  );
}
