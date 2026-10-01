import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Box, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle, Divider, Stack, Typography } from "@mui/material";
import { Link as RouterLink } from "react-router-dom";
import { api } from "../api/client";
import type { EvidenceDetail } from "../api/types";
import { ErrorAlert, fmtDate, KeyValue, Loading, VerificationTag } from "./common";

export function ValuesTable({ values }: { values: Record<string, unknown> }) {
  const entries = Object.entries(values).filter(([k, v]) => v !== null && v !== undefined && v !== "" && k !== "coding" && k !== "identifier");
  if (!entries.length) return <Typography variant="body2">No values</Typography>;
  return (
    <KeyValue
      items={entries.map(([k, v]) => [k.replace(/_/g, " "), typeof v === "object" ? JSON.stringify(v) : String(v)])}
    />
  );
}

export function EvidenceDialog({ id, open, onClose }: { id: number; open: boolean; onClose: () => void }) {
  const q = useQuery({ queryKey: ["evidence", id], queryFn: () => api.get<EvidenceDetail>(`/evidence/${id}`), enabled: open });
  const e = q.data;
  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="md" aria-labelledby={`ev-${id}-title`}>
      <DialogTitle id={`ev-${id}-title`}>Evidence E{id}</DialogTitle>
      <DialogContent dividers>
        {q.isLoading && <Loading />}
        <ErrorAlert error={q.error} />
        {e && (
          <Stack spacing={2}>
            <Typography variant="subtitle1">{e.display}</Typography>
            <Stack direction="row" spacing={1}>
              <VerificationTag status={e.verification_status} reviewState={e.review_state} />
              <Chip size="small" label={`origin: ${e.origin}`} />
              <Chip size="small" label={e.category} />
            </Stack>
            <KeyValue
              items={[
                ["Source", e.source_name],
                ["Patient record", `${e.patient_ref.institution_id} / ${e.patient_ref.local_patient_id}`],
                ["Record", e.source_record_id ? `${e.source_record_type}/${e.source_record_id} (version ${e.source_record_version})` : "—"],
                ["Clinical date", fmtDate(e.clinical_time, false)],
                ["Retrieved / uploaded", fmtDate(e.retrieved_at)],
                ["Verified by", e.verified_by ? `${e.verified_by}, ${fmtDate(e.verified_at)}` : "—"],
                ["Source text", e.source_text],
              ]}
            />
            {e.document && (
              <Button component={RouterLink} to={`/documents/${e.document.id}?page=${e.page ?? 1}&focus=${e.id}`} onClick={onClose} variant="outlined" sx={{ alignSelf: "start" }}>
                Open {e.document.filename} at page {e.page ?? 1}
              </Button>
            )}
            <Divider />
            <Typography variant="subtitle2">Original values (as recorded at source)</Typography>
            <ValuesTable values={e.original} />
            {JSON.stringify(e.original) !== JSON.stringify(e.current) && (
              <>
                <Typography variant="subtitle2">Current (corrected) values</Typography>
                <ValuesTable values={e.current} />
              </>
            )}
            {e.revisions.length > 0 && (
              <>
                <Divider />
                <Typography variant="subtitle2">History</Typography>
                {e.revisions.map((r) => (
                  <Typography key={r.id} variant="body2">
                    {fmtDate(r.created_at)} — <strong>{r.action}</strong> by {r.editor}
                    {r.note ? `: ${r.note}` : ""}
                  </Typography>
                ))}
              </>
            )}
            {e.versions.length > 1 && (
              <>
                <Typography variant="subtitle2">Source record versions</Typography>
                {e.versions.map((v) => (
                  <Typography key={v.id} variant="body2">
                    v{v.version}: {v.display} {v.superseded_by ? "(superseded)" : "(current)"}
                  </Typography>
                ))}
              </>
            )}
            {e.fhir && (
              <details>
                <summary>
                  <Typography component="span" variant="body2">FHIR resource as received</Typography>
                </summary>
                <Box component="pre" sx={{ fontSize: 12, overflow: "auto", maxHeight: 240, bgcolor: "grey.100", p: 1 }}>
                  {JSON.stringify(e.fhir, null, 2)}
                </Box>
              </details>
            )}
          </Stack>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
}

export function EvidenceRef({ id }: { id: number }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Chip
        size="small"
        label={`E${id}`}
        onClick={() => setOpen(true)}
        variant="outlined"
        clickable
        aria-label={`Open evidence ${id}`}
        sx={{ mr: 0.5, height: 20, fontSize: 11 }}
      />
      {open && <EvidenceDialog id={id} open={open} onClose={() => setOpen(false)} />}
    </>
  );
}
