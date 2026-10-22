import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link as RouterLink } from "react-router-dom";
import {
  Alert,
  Button,
  MenuItem,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
  Link,
} from "@mui/material";
import UploadFile from "@mui/icons-material/UploadFile";
import { api } from "../../api/client";
import type { DocumentSummary, Job, ReferralDetail } from "../../api/types";
import { Empty, ErrorAlert, fmtDate, Tag } from "../../components/common";
import { useRefData } from "../../hooks";
import { useInvalidateReferral } from "../referrals/ReferralWorkspace";

const STATUS_TONE: Record<string, "ok" | "warn" | "bad" | "wait" | "neutral"> = {
  queued: "wait",
  processing: "wait",
  extracted: "ok",
  failed: "bad",
  unreadable: "warn",
  uploaded: "neutral",
};

export function DocumentsTab({ r }: { r: ReferralDetail }) {
  const refData = useRefData();
  const refresh = useInvalidateReferral(r.id);
  const [inputKey, setInputKey] = useState(0);
  const [docType, setDocType] = useState("prescription");
  const [file, setFile] = useState<File | null>(null);
  const docs = useQuery({
    queryKey: ["referral", r.id, "documents"],
    queryFn: () => api.get<DocumentSummary[]>(`/referrals/${r.id}/documents`),
    refetchInterval: (q) => ((q.state.data ?? []).some((d) => ["queued", "processing"].includes(d.status)) ? 2000 : false),
  });
  const upload = useMutation({
    mutationFn: async (selected: File) => {
      const form = new FormData();
      form.append("file", selected);
      form.append("doc_type", docType);
      return api.upload<{ document: DocumentSummary; job: Job }>(`/referrals/${r.id}/documents`, form);
    },
    onSuccess: (_data, uploaded) => {
      // Only clear the picker if the user has not already chosen another file meanwhile.
      setFile((current) => {
        if (current !== uploaded) return current;
        setInputKey((k) => k + 1);
        return null;
      });
      refresh();
    },
  });
  const locked = ["response_returned", "followup_pending", "closed", "declined", "cancelled"].includes(r.status);
  const limits = refData.data?.limits;

  return (
    <Stack spacing={2}>
      <Paper sx={{ p: 2 }}>
        <Typography variant="h6" gutterBottom>
          Upload a paper record
        </Typography>
        <Typography variant="body2" color="text.secondary" gutterBottom>
          Supported: {limits?.formats.join(", ")} up to {limits?.max_upload_mb} MB and {limits?.max_pages} pages, {limits?.language} records. Text is
          extracted asynchronously; proposed fields start unverified and you review them beside the original page.
        </Typography>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={2} alignItems={{ sm: "center" }}>
          <Button variant="outlined" component="label" startIcon={<UploadFile />} disabled={locked}>
            {file ? file.name : "Choose file"}
            <input key={inputKey} hidden type="file" accept=".pdf,.png,.jpg,.jpeg" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          </Button>
          <TextField select size="small" label="Document type" value={docType} onChange={(e) => setDocType(e.target.value)} sx={{ minWidth: 200 }}>
            <MenuItem value="prescription">Prescription</MenuItem>
            <MenuItem value="lab_report">Laboratory report</MenuItem>
            <MenuItem value="referral_note">Referral / clinic note</MenuItem>
            <MenuItem value="other">Other</MenuItem>
          </TextField>
          <Button variant="contained" disabled={!file || upload.isPending || locked} onClick={() => file && upload.mutate(file)}>
            {upload.isPending ? "Uploading…" : "Upload"}
          </Button>
        </Stack>
        <ErrorAlert error={upload.error} title="Upload rejected" />
      </Paper>
      <Paper sx={{ p: 2 }}>
        <Typography variant="h6" gutterBottom>
          Documents
        </Typography>
        <ErrorAlert error={docs.error} />
        {docs.data?.length === 0 && <Empty>No documents uploaded.</Empty>}
        {!!docs.data?.length && (
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>File</TableCell>
                <TableCell>Type</TableCell>
                <TableCell>Pages</TableCell>
                <TableCell>Processing</TableCell>
                <TableCell>Uploaded</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {docs.data.map((d) => (
                <TableRow key={d.id}>
                  <TableCell>
                    <Link component={RouterLink} to={`/documents/${d.id}`}>
                      {d.original_filename}
                    </Link>
                    <Typography variant="caption" display="block" color="text.secondary">
                      {d.detected_type} · {(d.size_bytes / 1024).toFixed(0)} KB
                    </Typography>
                  </TableCell>
                  <TableCell>{d.doc_type.replace("_", " ")}</TableCell>
                  <TableCell>{d.page_count || "Not recorded"}</TableCell>
                  <TableCell>
                    <Tag tone={STATUS_TONE[d.status] ?? "neutral"} label={d.status} />
                    {d.error && (
                      <Typography variant="caption" display="block">
                        {d.error}
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell>
                    {fmtDate(d.created_at)} · {d.uploaded_by}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
        {docs.data?.some((d) => ["failed", "unreadable"].includes(d.status)) && (
          <Alert severity="info" sx={{ mt: 2 }}>
            If extraction fails you can retry, upload a clearer copy, or open the document and transcribe the information manually with a page
            reference.
          </Alert>
        )}
      </Paper>
    </Stack>
  );
}
