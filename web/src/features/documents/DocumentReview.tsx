import { useEffect, useMemo, useState } from "react";
import { Link as RouterLink, useParams, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Grid,
  MenuItem,
  Pagination,
  Paper,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import ArrowBack from "@mui/icons-material/ArrowBack";
import { api, fetchBlobUrl } from "../../api/client";
import type { DocumentDetail, Evidence, Job } from "../../api/types";
import { ErrorAlert, fmtDate, KeyValue, Loading, PageHeader, ReasonDialog, Tag, VerificationTag } from "../../components/common";
import { hasRole, useMe } from "../../hooks";

const FIELD_SETS: Record<string, string[]> = {
  medication: ["medication", "strength", "dosage_text", "route", "frequency", "start", "end"],
  lab: ["test", "value", "unit", "collected", "reference_range"],
  condition: ["condition", "onset", "clinical_status"],
  note: ["text"],
};

function PageImage({ docId, page, fields, focus, lines, revision }: { docId: number; page: number; fields: Evidence[]; focus: number | null; lines: { bbox: { x: number; y: number; w: number; h: number } | null }[]; revision: string }) {
  const [url, setUrl] = useState<string | null>(null);
  const [err, setErr] = useState<unknown>(null);
  useEffect(() => {
    let revoked = "";
    setUrl(null);
    setErr(null);
    fetchBlobUrl(`/documents/${docId}/pages/${page}`)
      .then((u) => {
        revoked = u;
        setUrl(u);
      })
      .catch(setErr);
    return () => {
      if (revoked) URL.revokeObjectURL(revoked);
    };
  }, [docId, page, revision]);
  if (err) return <ErrorAlert error={err} />;
  if (!url) return <Loading label="Loading page…" />;
  return (
    <Box sx={{ position: "relative", border: 1, borderColor: "divider", bgcolor: "white" }}>
      <img src={url} alt={`Original document page ${page}`} style={{ width: "100%", display: "block" }} />
      {lines.map((l, i) => l.bbox && <div key={`l${i}`} className="region-line" style={{ left: `${l.bbox.x * 100}%`, top: `${l.bbox.y * 100}%`, width: `${l.bbox.w * 100}%`, height: `${l.bbox.h * 100}%` }} />)}
      {fields
        .filter((f) => f.page === page && f.region && (focus === null || f.id === focus))
        .map((f) => (
          <div key={f.id} className="region-highlight" title={`E${f.id}`} style={{ left: `${f.region!.x * 100}%`, top: `${f.region!.y * 100}%`, width: `${f.region!.w * 100}%`, height: `${f.region!.h * 100}%` }} />
        ))}
    </Box>
  );
}

function CorrectDialog({ field, onClose, onSave, busy }: { field: Evidence; onClose: () => void; onSave: (fields: Record<string, unknown>, note: string) => void; busy: boolean }) {
  const keys = FIELD_SETS[field.category] ?? Object.keys(field.current);
  const [values, setValues] = useState<Record<string, string>>(() => Object.fromEntries(keys.map((k) => [k, field.current[k] == null ? "" : String(field.current[k])])));
  const [note, setNote] = useState("");
  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>Correct E{field.id}</DialogTitle>
      <DialogContent>
        <Alert severity="info" sx={{ mb: 2 }}>
          The original extracted value is kept in the history. Leave a field empty if it is not present in the document — do not guess.
        </Alert>
        <Typography variant="body2" sx={{ mb: 1 }}>
          Source text: <em>{field.source_text}</em>
        </Typography>
        <Stack spacing={1.5}>
          {keys.map((k) => (
            <TextField key={k} size="small" label={k.replace(/_/g, " ")} value={values[k]} onChange={(e) => setValues({ ...values, [k]: e.target.value })} />
          ))}
          <TextField size="small" label="Note (why corrected)" value={note} onChange={(e) => setNote(e.target.value)} />
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button
          variant="contained"
          disabled={busy}
          onClick={() =>
            onSave(
              Object.fromEntries(
                Object.entries(values).map(([k, v]) => [k, v === "" ? null : k === "value" && !Number.isNaN(Number(v)) ? Number(v) : v]),
              ),
              note,
            )
          }
        >
          Save correction
        </Button>
      </DialogActions>
    </Dialog>
  );
}

function ManualDialog({ docId, referralId, page, onClose, onDone }: { docId: number; referralId: number; page: number; onClose: () => void; onDone: () => void }) {
  const [category, setCategory] = useState("medication");
  const [values, setValues] = useState<Record<string, string>>({});
  const [note, setNote] = useState("");
  const save = useMutation({
    mutationFn: () =>
      api.post(`/referrals/${referralId}/evidence/manual`, {
        category,
        document_id: docId,
        page,
        note,
        fields: Object.fromEntries(Object.entries(values).filter(([, v]) => v !== "").map(([k, v]) => [k, k === "value" && !Number.isNaN(Number(v)) ? Number(v) : v])),
      }),
    onSuccess: onDone,
  });
  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>Manual transcription (page {page})</DialogTitle>
      <DialogContent>
        <Stack spacing={1.5} sx={{ mt: 1 }}>
          <TextField select size="small" label="Field type" value={category} onChange={(e) => { setCategory(e.target.value); setValues({}); }}>
            <MenuItem value="medication">Medication</MenuItem>
            <MenuItem value="lab">Laboratory result</MenuItem>
            <MenuItem value="condition">Condition</MenuItem>
            <MenuItem value="note">Note</MenuItem>
          </TextField>
          {FIELD_SETS[category].map((k) => (
            <TextField key={k} size="small" label={k.replace(/_/g, " ")} value={values[k] ?? ""} onChange={(e) => setValues({ ...values, [k]: e.target.value })} />
          ))}
          <TextField size="small" label="Note" value={note} onChange={(e) => setNote(e.target.value)} />
          <ErrorAlert error={save.error} />
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="contained" onClick={() => save.mutate()} disabled={save.isPending || Object.values(values).every((v) => !v)}>
          Add field
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export function DocumentReview() {
  const id = Number(useParams().id);
  const [params] = useSearchParams();
  const qc = useQueryClient();
  const { data: me } = useMe();
  const [page, setPage] = useState(Number(params.get("page") ?? 1));
  const [focus, setFocus] = useState<number | null>(params.get("focus") ? Number(params.get("focus")) : null);
  const [correcting, setCorrecting] = useState<Evidence | null>(null);
  const [stateDialog, setStateDialog] = useState<{ field: Evidence; action: "unresolve" | "exclude" } | null>(null);
  const [manual, setManual] = useState(false);
  const q = useQuery({
    queryKey: ["document", id],
    queryFn: () => api.get<DocumentDetail>(`/documents/${id}`),
    refetchInterval: (query) => (["queued", "processing"].includes(query.state.data?.document.status ?? "") ? 2000 : false),
  });
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["document", id] });
    if (q.data) qc.invalidateQueries({ queryKey: ["referral", q.data.document.referral_id] });
  };
  const act = useMutation({
    mutationFn: ({ path, body }: { path: string; body: unknown }) => api.post(path, body),
    onSuccess: () => {
      setCorrecting(null);
      setStateDialog(null);
      refresh();
    },
  });
  const reprocess = useMutation({ mutationFn: () => api.post<Job>(`/documents/${id}/reprocess`), onSuccess: refresh });
  const pageLines = useMemo(() => q.data?.extraction?.pages.find((p) => p.page === page)?.lines ?? [], [q.data, page]);
  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorAlert error={q.error} />;
  const { document: doc, extraction, fields } = q.data!;
  const isClinician = hasRole(me, "clinician");

  return (
    <>
      <PageHeader
        title={doc.original_filename}
        subtitle={`${doc.doc_type.replace("_", " ")} · ${doc.page_count} page(s) · uploaded ${fmtDate(doc.created_at)} by ${doc.uploaded_by}`}
        actions={
          <>
            <Button component={RouterLink} to={`/referrals/${doc.referral_id}?tab=documents`} startIcon={<ArrowBack />}>
              Back to referral
            </Button>
            <Button variant="outlined" onClick={() => setManual(true)}>
              Transcribe manually
            </Button>
            <Button variant="outlined" onClick={() => reprocess.mutate()} disabled={["queued", "processing"].includes(doc.status)}>
              Retry extraction
            </Button>
          </>
        }
      />
      <ErrorAlert error={act.error || reprocess.error} />
      {["queued", "processing"].includes(doc.status) && <Loading label={`Processing (${doc.status})…`} />}
      {doc.error && <Alert severity={doc.status === "failed" ? "error" : "warning"} sx={{ mb: 2 }}>{doc.error}</Alert>}
      <Grid container spacing={2}>
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 1 }}>
            <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ px: 1 }}>
              <Typography variant="subtitle1">Original document</Typography>
              {doc.page_count > 1 && <Pagination count={doc.page_count} page={page} onChange={(_, p) => setPage(p)} size="small" />}
            </Stack>
            {["queued", "processing"].includes(doc.status) ? (
              <Loading label="Rendering pages…" />
            ) : (
              doc.page_count > 0 && <PageImage docId={id} page={page} fields={fields} focus={focus} lines={pageLines} revision={`${doc.status}-${extraction?.id ?? 0}`} />
            )}
            <Button size="small" sx={{ mt: 1 }} onClick={async () => window.open(await fetchBlobUrl(`/documents/${id}/file`), "_blank")}>
              Open original file
            </Button>
          </Paper>
        </Grid>
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              Proposed fields
            </Typography>
            {extraction && (
              <KeyValue
                items={[
                  ["Text source", extraction.text_source === "embedded" ? "embedded PDF text" : extraction.text_source === "ocr" ? "OCR" : extraction.text_source],
                  ["OCR engine", extraction.ocr_engine ? `${extraction.ocr_engine} ${extraction.ocr_engine_version}` : "—"],
                  ["Field extractor", `${extraction.extractor ?? "—"} ${extraction.extractor_version ?? ""}`],
                  ["Processing time", `${extraction.duration_ms} ms`],
                ]}
              />
            )}
            {extraction?.notes?.map((n, i) => (
              <Alert key={i} severity="info" sx={{ mt: 1 }}>
                {n}
              </Alert>
            ))}
            <Alert severity="warning" sx={{ my: 2 }}>
              Extracted values are proposals. Correct, mark unresolved or exclude anything unclear; clinical fields need clinician verification.
              OCR confidence is tool metadata, not a clinical probability.
            </Alert>
            {fields.length === 0 && <Typography color="text.secondary">No fields proposed for this document.</Typography>}
            <Stack spacing={1.5}>
              {fields.map((f) => (
                <Paper key={f.id} sx={{ p: 1.5, borderColor: focus === f.id ? "warning.main" : undefined, borderWidth: focus === f.id ? 2 : 1 }} onMouseEnter={() => { setFocus(f.id); if (f.page) setPage(f.page); }}>
                  <Stack direction="row" justifyContent="space-between" spacing={1}>
                    <Typography variant="subtitle2">
                      E{f.id} · {f.display}
                    </Typography>
                    <VerificationTag status={f.verification_status} reviewState={f.review_state} />
                  </Stack>
                  <Typography variant="caption" color="text.secondary" display="block">
                    page {f.page} · "{f.source_text}"{f.confidence?.ocr_line_confidence != null ? ` · OCR line confidence ${String(f.confidence.ocr_line_confidence)}` : ""}
                    {f.origin === "manual" ? ` · manual entry by ${f.author}` : ""}
                  </Typography>
                  {f.review_state === "corrected" && <Tag tone="info" label="corrected" />}
                  <Stack direction="row" spacing={1} sx={{ mt: 1 }} flexWrap="wrap" useFlexGap>
                    {f.review_state !== "excluded" && f.review_state !== "unresolved" && (
                      <Button size="small" onClick={() => setCorrecting(f)}>
                        Correct
                      </Button>
                    )}
                    {f.review_state !== "unresolved" && f.review_state !== "excluded" && (
                      <Button size="small" onClick={() => setStateDialog({ field: f, action: "unresolve" })}>
                        Mark unresolved
                      </Button>
                    )}
                    {f.review_state !== "excluded" ? (
                      <Button size="small" onClick={() => setStateDialog({ field: f, action: "exclude" })}>
                        Exclude
                      </Button>
                    ) : null}
                    {["excluded", "unresolved"].includes(f.review_state) && (
                      <Button size="small" onClick={() => act.mutate({ path: `/evidence/${f.id}/restore`, body: { note: "Restored" } })}>
                        Restore
                      </Button>
                    )}
                    {isClinician && f.verification_status !== "verified" && !["excluded", "unresolved"].includes(f.review_state) && (
                      <Button size="small" variant="contained" onClick={() => act.mutate({ path: `/evidence/${f.id}/verify`, body: { expected_row_version: f.row_version } })}>
                        Verify (clinician)
                      </Button>
                    )}
                  </Stack>
                </Paper>
              ))}
            </Stack>
            {extraction?.raw_text && (
              <details style={{ marginTop: 16 }}>
                <summary>Raw extracted text</summary>
                <Box component="pre" sx={{ whiteSpace: "pre-wrap", fontSize: 12, bgcolor: "grey.100", p: 1 }}>
                  {extraction.raw_text}
                </Box>
              </details>
            )}
          </Paper>
        </Grid>
      </Grid>
      {correcting && (
        <CorrectDialog
          field={correcting}
          busy={act.isPending}
          onClose={() => setCorrecting(null)}
          onSave={(values, note) => act.mutate({ path: `/evidence/${correcting.id}/correct`, body: { fields: values, note, expected_row_version: correcting.row_version } })}
        />
      )}
      {stateDialog && (
        <ReasonDialog
          open
          title={stateDialog.action === "exclude" ? "Exclude field" : "Mark field unresolved"}
          label="Reason"
          confirm={stateDialog.action === "exclude" ? "Exclude" : "Mark unresolved"}
          onClose={() => setStateDialog(null)}
          onConfirm={(note) => act.mutate({ path: `/evidence/${stateDialog.field.id}/${stateDialog.action}`, body: { note } })}
          busy={act.isPending}
        />
      )}
      {manual && <ManualDialog docId={id} referralId={doc.referral_id} page={page} onClose={() => setManual(false)} onDone={() => { setManual(false); refresh(); }} />}
    </>
  );
}
