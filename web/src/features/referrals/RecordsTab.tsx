import { useMutation, useQuery } from "@tanstack/react-query";
import { Alert, Box, Button, Checkbox, FormControlLabel, Stack, Table, TableBody, TableCell, TableHead, TableRow, Typography } from "@mui/material";
import Sync from "@mui/icons-material/Sync";
import { api } from "../../api/client";
import type { Evidence, ReferralDetail } from "../../api/types";
import { EvidenceRef } from "../../components/EvidenceRef";
import { Empty, ErrorAlert, fmtDate, Loading, RetrievalStatus, Section } from "../../components/common";
import { useRefData } from "../../hooks";
import { OtherPlaces } from "./LinksTab";
import { useInvalidateReferral } from "./ReferralWorkspace";

const GROUPS: [string, string, string][] = [
  ["condition", "Conditions", "All recorded conditions."],
  ["surgery", "Previous surgery", "All recorded operations."],
  ["visit", "Visits in the last 6 months", ""],
  ["lab", "Test results", "Latest result of each test in the last 6 months."],
  ["imaging", "Imaging reports", "Last 6 months."],
];

function EvidenceRow({ e, onToggle, busy }: { e: Evidence; onToggle: (sel: boolean) => void; busy: boolean }) {
  return (
    <TableRow>
      <TableCell sx={{ width: 48 }}>
        <Checkbox checked={e.selected} disabled={busy || ["access_revoked", "invalidated"].includes(e.verification_status)}
          onChange={(ev) => onToggle(ev.target.checked)} inputProps={{ "aria-label": `Include in the referral: ${e.display}` }} />
      </TableCell>
      <TableCell>
        <Typography variant="body2">{e.display}</Typography>
        <Typography variant="caption" color="text.secondary">
          {e.origin === "source" ? e.source_name : e.origin === "document" ? "Paper from the patient" : "Told by the patient"}
          {e.clinical_time && ["lab", "visit", "imaging"].includes(e.category) ? ` · ${fmtDate(e.clinical_time, false)}` : ""}
        </Typography>
      </TableCell>
      <TableCell align="right">
        <EvidenceRef id={e.id} />
      </TableCell>
    </TableRow>
  );
}

export function RecordsTab({ r }: { r: ReferralDetail }) {
  const rd = useRefData();
  const refresh = useInvalidateReferral(r.id);
  const evidence = useQuery({ queryKey: ["referral", r.id, "evidence"], queryFn: () => api.get<Evidence[]>(`/referrals/${r.id}/evidence`) });
  const retrieve = useMutation({
    mutationFn: () => api.post(`/referrals/${r.id}/retrieve`),
    meta: { success: "Records retrieved." },
    onSuccess: () => {
      refresh();
      evidence.refetch();
    },
  });
  const toggle = useMutation({
    mutationFn: ({ id, selected }: { id: number; selected: boolean }) => api.post(`/evidence/${id}/select`, { selected }),
    meta: { silent: true },
    onSuccess: () => evidence.refetch(),
  });
  const used = r.sources.filter((s) => s.latest);
  const locked = ["response_returned", "followup_pending", "closed", "declined", "cancelled"].includes(r.status);
  const window = rd.data?.referral_window_days;

  return (
    <Stack spacing={2}>
      <OtherPlaces r={r} />
      <Section
        title="Where the records come from"
        description={`Your own record, plus the most recently visited hospital, clinic and laboratory among the linked ones. Visits, results and imaging from the last ${window ? Math.round(window / 30.4) : 6} months; current medicines only.`}
        actions={
          <Button variant="contained" startIcon={<Sync />} disabled={retrieve.isPending || locked || r.status === "draft"} onClick={() => retrieve.mutate()}>
            {used.length ? "Retrieve again" : "Retrieve records"}
          </Button>
        }
      >
        <ErrorAlert error={retrieve.error} />
        {used.length === 0 ? (
          <Empty>No records retrieved yet.</Empty>
        ) : (
          <Table size="small" aria-label="Sources">
            <TableHead>
              <TableRow>
                <TableCell>Institution</TableCell>
                <TableCell>Last seen there</TableCell>
                <TableCell>Result</TableCell>
                <TableCell>Details</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {used.map((s) => (
                <TableRow key={s.institution_id}>
                  <TableCell>
                    {s.name}
                    <Typography variant="caption" display="block" color="text.secondary">
                      {s.kind}
                      {s.own ? " · your institution" : ""}
                    </Typography>
                  </TableCell>
                  <TableCell>{s.own ? "Your own record" : s.latest!.last_activity ?? "Nothing recorded"}</TableCell>
                  <TableCell>
                    <RetrievalStatus status={s.latest!.status} />
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2">{s.latest!.message}</Typography>
                    <Typography variant="caption" color="text.secondary">
                      {s.latest!.requested_by}, {fmtDate(s.latest!.requested_at)}
                    </Typography>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
        {used.some((s) => ["unavailable", "denied", "invalid"].includes(s.latest!.status)) && (
          <Alert severity="warning" sx={{ mt: 1.5 }}>
            Some records could not be retrieved. The referral says so; it never treats missing records as "no history".
          </Alert>
        )}
      </Section>
      {evidence.isLoading && <Loading />}
      <ErrorAlert error={evidence.error || toggle.error} />
      {evidence.data &&
        GROUPS.map(([cat, title, note]) => {
          const items = evidence.data!.filter((e) => e.category === cat || (cat === "lab" && e.category === "lab_report"));
          return (
            <Section key={cat} title={`${title} (${items.length})`} description={note || undefined}>
              {items.length === 0 ? (
                <Empty>None in the retrieved records.</Empty>
              ) : (
                <Table size="small">
                  <TableBody>
                    {items.map((e) => (
                      <EvidenceRow key={e.id} e={e} busy={toggle.isPending || locked} onToggle={(selected) => toggle.mutate({ id: e.id, selected })} />
                    ))}
                  </TableBody>
                </Table>
              )}
            </Section>
          );
        })}
      {evidence.data && (
        <Box>
          <FormControlLabel control={<Checkbox checked disabled />} label="Ticked items are included in the summary sent to the specialist." />
          <Typography variant="body2" color="text.secondary">
            Current medicines are listed on Medicines & flags, where duplicates from different places are merged.
          </Typography>
        </Box>
      )}
    </Stack>
  );
}
