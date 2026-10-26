import { useEffect, useState } from "react";
import { Box, Link, Paper, Stack, Table, TableBody, TableCell, TableHead, TableRow, Typography } from "@mui/material";
import { fetchBlobUrl, Service } from "../api/client";
import type { ResultValue } from "../api/types";
import { tokens } from "../theme";
import { fmtDate } from "./common";

export type ReportFile = { key: string | number; filename: string; content_type: string; path: string };

/** One image or file from a report, fetched with the signed-in user's token. */
function Attachment({ file, service }: { file: ReportFile; service: Service }) {
  const [url, setUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let revoked = false;
    let made: string | null = null;
    fetchBlobUrl(file.path, service)
      .then((u) => {
        made = u;
        if (!revoked) setUrl(u);
      })
      .catch(() => setFailed(true));
    return () => {
      revoked = true;
      if (made) URL.revokeObjectURL(made);
    };
  }, [file.path, service]);
  const image = file.content_type.startsWith("image/");
  return (
    <Box sx={{ width: image ? 220 : "auto" }}>
      {failed && <Typography variant="body2">{file.filename} could not be loaded</Typography>}
      {!failed && image && url && (
        <Link href={url} target="_blank" rel="noopener" aria-label={`Open ${file.filename} full size`}>
          <Box component="img" src={url} alt={file.filename} sx={{ width: "100%", height: 160, objectFit: "cover", border: `1px solid ${tokens.line}`, borderRadius: 1, backgroundColor: "#000" }} />
        </Link>
      )}
      {!failed && !image && url && (
        <Link href={url} target="_blank" rel="noopener">
          {file.filename}
        </Link>
      )}
      {!url && !failed && <Box sx={{ width: "100%", height: image ? 160 : 20, backgroundColor: tokens.sunken, borderRadius: 1 }} />}
      {image && (
        <Typography variant="caption" component="div" sx={{ color: tokens.muted, overflowWrap: "anywhere" }}>
          {file.filename}
        </Typography>
      )}
    </Box>
  );
}

/** A returned test or scan report, laid out as a report: values, findings, impression, images. */
export function ResultReport({
  title,
  subtitle,
  values,
  findings,
  impression,
  reportedBy,
  reportedAt,
  files = [],
  service = "central",
}: {
  title: string;
  subtitle?: string;
  values?: ResultValue[] | null;
  findings?: string | null;
  impression?: string | null;
  reportedBy?: string | null;
  reportedAt?: string | null;
  files?: ReportFile[];
  service?: Service;
}) {
  return (
    <Paper variant="outlined" component="article" aria-label={`Report: ${title}`} sx={{ p: { xs: 1.5, md: 2.5 } }}>
      <Typography variant="overline" sx={{ color: tokens.muted }}>
        Report
      </Typography>
      <Typography variant="subtitle1" component="h3" sx={{ fontWeight: 700 }}>
        {title}
      </Typography>
      {subtitle && (
        <Typography variant="body2" sx={{ color: tokens.muted }}>
          {subtitle}
        </Typography>
      )}
      <Stack spacing={1.5} sx={{ mt: 1.5 }}>
        {!!values?.length && (
          <Table size="small" aria-label="Results">
            <TableHead>
              <TableRow>
                <TableCell>Test</TableCell>
                <TableCell>Result</TableCell>
                <TableCell>Reference range</TableCell>
                <TableCell>Flag</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {values.map((v, i) => (
                <TableRow key={i}>
                  <TableCell>{v.test}</TableCell>
                  <TableCell sx={{ fontWeight: v.flag ? 700 : 400 }}>
                    {v.value} {v.unit ?? ""}
                  </TableCell>
                  <TableCell>{v.reference ?? ""}</TableCell>
                  <TableCell>{v.flag ?? ""}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
        {findings && (
          <Box>
            <Typography variant="subtitle2" component="h4">
              Findings
            </Typography>
            <Typography variant="body2" sx={{ whiteSpace: "pre-wrap" }}>
              {findings}
            </Typography>
          </Box>
        )}
        {impression && (
          <Box>
            <Typography variant="subtitle2" component="h4">
              Impression
            </Typography>
            <Typography variant="body2" sx={{ whiteSpace: "pre-wrap", fontWeight: 600 }}>
              {impression}
            </Typography>
          </Box>
        )}
        {files.length > 0 && (
          <Box>
            <Typography variant="subtitle2" component="h4" sx={{ mb: 0.5 }}>
              Images and files
            </Typography>
            <Stack direction="row" spacing={1.5} flexWrap="wrap" useFlexGap>
              {files.map((f) => (
                <Attachment key={f.key} file={f} service={service} />
              ))}
            </Stack>
          </Box>
        )}
        {(reportedBy || reportedAt) && (
          <Typography variant="body2" sx={{ color: tokens.muted }}>
            Reported by {reportedBy ?? "not recorded"}
            {reportedAt ? `, ${fmtDate(reportedAt)}` : ""}
          </Typography>
        )}
      </Stack>
    </Paper>
  );
}
