import { useMutation, useQuery } from "@tanstack/react-query";
import { Alert, Box, Button, Checkbox, Chip, FormControlLabel, Stack, Table, TableBody, TableCell, TableHead, TableRow, Tooltip, Typography } from "@mui/material";
import AutoAwesome from "@mui/icons-material/AutoAwesome";
import Sync from "@mui/icons-material/Sync";
import { api } from "../../api/client";
import type { Evidence, ReferralDetail, SelectionStatus } from "../../api/types";
import { EvidenceRef } from "../../components/EvidenceRef";
import { Empty, ErrorAlert, fmtDate, Loading, RetrievalStatus, Section } from "../../components/common";
import { isStaff, useMe, useRefData } from "../../hooks";
import { HoldNotice } from "./HoldNotice";
import { OtherPlaces } from "./LinksTab";
import { useInvalidateReferral } from "./ReferralWorkspace";

const GROUPS: [string, string, string][] = [
  ["condition", "Conditions", "All recorded conditions."],
  ["surgery", "Previous surgery", "All recorded operations."],
  ["visit", "Visits", "The last 6 months are included by default."],
  ["lab", "Test results", "Results from the last 6 months are included by default."],
  ["imaging", "Imaging reports", "The last 6 months are included by default."],
];

const AI_WORD = { include: "AI suggests including", exclude: "AI suggests leaving out", optional: "AI: might help" } as const;

/** How this record came to be ticked or not: the rule-based default, the AI recommendation, or staff. */
function SelectionBadges({ e }: { e: Evidence }) {
  return (
    <Stack direction="row" spacing={0.5} sx={{ mt: 0.5, flexWrap: "wrap", rowGap: 0.5 }}>
      {e.in_default && <Chip size="small" variant="outlined" label="Included by default" />}
      {e.ai_recommendation && (
        <Tooltip title={e.ai_reason ? `${e.ai_reason} (AI suggestion, not verified)` : "AI suggestion, not verified"}>
          <Chip size="small" variant="outlined" color={e.ai_recommendation === "include" ? "primary" : "default"} icon={<AutoAwesome />}
            label={`${AI_WORD[e.ai_recommendation]}${e.ai_relevance ? ` · ${e.ai_relevance} relevance` : ""}`} />
        </Tooltip>
      )}
      {e.selection_source === "staff" && e.selected_by && (
        <Chip size="small" variant="outlined" label={`${e.selected ? "Added" : "Left out"} by ${e.selected_by}`} />
      )}
    </Stack>
  );
}

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
        <SelectionBadges e={e} />
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
  const { data: me } = useMe();
  const staff = isStaff(me);
  const selection = useQuery({
    queryKey: ["referral", r.id, "selection"],
    queryFn: () => api.get<SelectionStatus>(`/referrals/${r.id}/selection`),
    // while the AI recommendation runs in the background, check back now and then
    refetchInterval: (q) => (q.state.data?.llm_configured && !q.state.data.run && used.length ? 4000 : false),
  });
  const toggle = useMutation({
    mutationFn: ({ id, selected }: { id: number; selected: boolean }) => api.post(`/evidence/${id}/select`, { selected }),
    meta: { silent: true },
    onSuccess: () => {
      evidence.refetch();
      selection.refetch();
    },
  });
  const recommend = useMutation({
    mutationFn: () => api.post(`/referrals/${r.id}/recommend`),
    meta: { success: "Asked for the AI recommendation." },
    onSuccess: () => setTimeout(() => { selection.refetch(); evidence.refetch(); }, 4000),
  });
  const used = r.sources.filter((s) => s.latest);
  const locked = ["response_returned", "followup_pending", "closed", "declined", "cancelled"].includes(r.status);
  const window = rd.data?.referral_window_days;
  const run = selection.data?.run;
  const purged = !!r.working_set_purged_at;

  if (purged) {
    return (
      <Stack spacing={2}>
        <Alert severity="info">
          These records are no longer held. Content has been removed. Reference and fingerprint kept. The records stay at the
          places they came from, and your clinic keeps its own copy of what was sent.
        </Alert>
      </Stack>
    );
  }
  const ending = evidence.data?.filter((e) => !e.selected && e.ai_recommendation === "exclude") ?? [];

  return (
    <Stack spacing={2}>
      <HoldNotice r={r} />
      <OtherPlaces r={r} />
      <Section
        title="Where the records come from"
        description={`Your own record, plus every linked institution (up to five, the most recently visited first). Conditions and current medicines whatever their date; visits, results and imaging from the years set for this specialty; those from the last ${window ? Math.round(window / 30.4) : 6} months are ticked by default. Current medicines only.`}
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
      {used.length > 0 && (
        <Section
          title="What goes in the referral"
          description={staff ? "You decide. Ticked items are sent. The AI recommendation is only a suggestion and never removes an item that is included by default." : "Staff decide what is sent."}
          actions={staff && selection.data?.llm_configured ? (
            <Button variant="outlined" startIcon={<AutoAwesome />} disabled={recommend.isPending || locked} onClick={() => recommend.mutate()}>
              Ask AI again
            </Button>
          ) : undefined}
        >
          <ErrorAlert error={recommend.error} />
          {selection.data && (
            <Typography variant="body2" sx={{ mb: 1 }}>
              {selection.data.counts.selected} of {selection.data.counts.retrieved} records ticked
              {selection.data.counts.staff_overrides_of_ai ? ` · ${selection.data.counts.staff_overrides_of_ai} changed by staff from the AI suggestion` : ""}
            </Typography>
          )}
          {!run && selection.data?.llm_configured && <Alert severity="info">AI recommendation in progress. The default selection applies meanwhile.</Alert>}
          {run && run.status !== "completed" && (
            <Alert severity={run.status === "rejected" ? "warning" : "info"}>
              AI recommendation unavailable. The default selection applies
              {run.status === "rejected" ? " (the answer did not pass the checks and was not used)." : "."}
            </Alert>
          )}
          {run?.status === "completed" && (
            <Typography variant="caption" color="text.secondary" display="block">
              AI suggestion, not verified · {run.model} · {run.prompt_version} · {fmtDate(run.created_at)}
              {run.truncated ? ` · only the first ${run.item_count} records were reviewed` : ""}
            </Typography>
          )}
          {run?.status === "completed" && run.missing.length > 0 && (
            <Alert severity="info" sx={{ mt: 1 }}>
              The AI thinks this may be needed but did not find it in the records: {run.missing.join("; ")}. AI suggestion, not verified.
            </Alert>
          )}
        </Section>
      )}
      {evidence.isLoading && <Loading />}
      <ErrorAlert error={evidence.error || toggle.error} />
      {evidence.data &&
        GROUPS.map(([cat, title, note]) => {
          const items = evidence.data!.filter((e) => (e.category === cat || (cat === "lab" && e.category === "lab_report")) && !ending.includes(e));
          return (
            <Section key={cat} title={`${title} (${items.length})`} description={note || undefined}>
              {items.length === 0 ? (
                <Empty>None in the retrieved records.</Empty>
              ) : (
                <Table size="small">
                  <TableBody>
                    {items.map((e) => (
                      <EvidenceRow key={e.id} e={e} busy={toggle.isPending || locked || !staff} onToggle={(selected) => toggle.mutate({ id: e.id, selected })} />
                    ))}
                  </TableBody>
                </Table>
              )}
            </Section>
          );
        })}
      {ending.length > 0 && (
        <Section title={`Not included (${ending.length})`} description="The AI suggested leaving these out. Nothing is hidden: tick any to include it.">
          <Table size="small">
            <TableBody>
              {ending.map((e) => (
                <EvidenceRow key={e.id} e={e} busy={toggle.isPending || locked || !staff} onToggle={(selected) => toggle.mutate({ id: e.id, selected })} />
              ))}
            </TableBody>
          </Table>
        </Section>
      )}
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
