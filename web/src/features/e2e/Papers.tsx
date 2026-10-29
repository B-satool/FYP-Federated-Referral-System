/**
 * Scanned papers for a referral (spec v4 10): read on this device, corrected by the doctor, encrypted with the image.
 *
 * 1. The doctor (or the patient, in the patient portal) chooses a photo or scan; it stays in this browser.
 * 2. "Read it on this device" runs OCR here; the lines that name a known medicine become suggestions.
 * 3. The doctor checks each medicine, strength, dose and frequency against the image and corrects them.
 * 4. Saving encrypts the image and the reading in one batch to the doctor's key. Staff see "Scanned paper" and a date.
 */
import { useEffect, useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Alert, Box, Button, IconButton, LinearProgress, Stack, Table, TableBody, TableCell, TableHead, TableRow, TextField,
  Typography } from "@mui/material";
import Delete from "@mui/icons-material/Delete";
import type { ReferralDetail } from "../../api/types";
import { Empty, ErrorAlert, fmtDate, Loading, Section } from "../../components/common";
import { useDeviceKeys } from "../../crypto/session";
import { DeviceKeyPanel } from "../keys/DeviceKey";
import { FileView, useOpenedRecords } from "../referrals/Records";
import { useInvalidateReferral } from "../referrals/ReferralWorkspace";
import { useMedBundle } from "./bundle";
import { nameIndex } from "./flags";
import { medicinesInText, OCR_ENGINE, OcrResult, readImage, ReadMedicine } from "./ocr";
import { latestById } from "./records";
import { uploadOwnItems } from "./upload";

const MAX_BYTES = 10 * 1024 * 1024;
const TYPES = ["image/jpeg", "image/png", "image/webp", "application/pdf"];

function NewPaper({ r, onSaved }: { r: ReferralDetail; onSaved: () => void }) {
  const dk = useDeviceKeys();
  const bundle = useMedBundle();
  const idx = useMemo(() => (bundle.data ? nameIndex(bundle.data.content) : null), [bundle.data]);
  const [file, setFile] = useState<File | null>(null);
  const [url, setUrl] = useState<string | null>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [reading, setReading] = useState<OcrResult | null>(null);
  const [meds, setMeds] = useState<ReadMedicine[]>([]);
  const [problem, setProblem] = useState<string | null>(null);
  useEffect(() => {
    if (!file) return;
    const u = URL.createObjectURL(file);
    setUrl(u);
    return () => URL.revokeObjectURL(u);
  }, [file]);
  const choose = (f: File | undefined) => {
    setReading(null); setMeds([]); setProblem(null);
    if (!f) return;
    if (!TYPES.includes(f.type)) return setProblem("Choose a JPEG, PNG or WebP image, or a PDF");
    if (f.size > MAX_BYTES) return setProblem("At most 10 MB");
    setFile(f);
  };
  const read = useMutation({
    mutationFn: async () => {
      setProgress(0);
      const out = await readImage(file!, setProgress);
      setReading(out);
      setMeds(idx ? medicinesInText(out.lines, idx) : []);
    },
    meta: { silent: true },
    onSettled: () => setProgress(null),
  });
  const save = useMutation({
    mutationFn: async () => {
      const bytes = new Uint8Array(await file!.arrayBuffer());
      await uploadOwnItems(r.id, r.reference, dk.keys!, [
        { category: "scan", kind: "scan", label: "Scanned paper", bytes, mime: file!.type },
        ...(reading ? [{ category: "scan_reading", kind: "note" as const, label: "Reading of a scanned paper", record: {
          text: reading.text, medicines: meds.filter((m) => m.name.trim()), engine: OCR_ENGINE, confidence: reading.confidence,
          checked_by_doctor: true } }] : []),
      ]);
    },
    meta: { success: "Saved, encrypted on this device. Staff see only that a scanned paper was added." },
    onSuccess: () => { setFile(null); setReading(null); setMeds([]); onSaved(); },
  });
  const set = (n: number, patch: Partial<ReadMedicine>) => setMeds(meds.map((m, i) => (i === n ? { ...m, ...patch } : m)));
  return (
    <Stack spacing={1.5}>
      <Box>
        <Button variant="outlined" component="label">
          Choose a photo or scan
          <input hidden type="file" accept={TYPES.join(",")} onChange={(e) => choose(e.target.files?.[0])} data-testid="paper-file" />
        </Button>
      </Box>
      {problem && <Alert severity="warning">{problem}</Alert>}
      {file && (
        <Stack direction={{ xs: "column", md: "row" }} spacing={2} alignItems="flex-start">
          {file.type.startsWith("image/") && url && (
            <Box component="img" src={url} alt="The chosen paper" sx={{ maxWidth: { xs: "100%", md: 420 }, border: 1, borderColor: "divider" }} />
          )}
          <Stack spacing={1.5} sx={{ flex: 1, minWidth: 0 }}>
            {file.type.startsWith("image/") && !reading && (
              <Box>
                <Button variant="contained" onClick={() => read.mutate()} disabled={read.isPending || !idx}>Read it on this device</Button>
                <Typography variant="caption" display="block" color="text.secondary" sx={{ mt: 0.5 }}>
                  The image is read in this browser; it is not sent anywhere. Handwriting is often read wrongly: check every field.
                </Typography>
                {progress !== null && <LinearProgress variant="determinate" value={progress * 100} sx={{ mt: 1 }} />}
              </Box>
            )}
            <ErrorAlert error={read.error} />
            {reading && (
              <>
                <Typography variant="subtitle2">Medicines found ({reading.confidence}% average confidence): check each against the image</Typography>
                {meds.length ? (
                  <Table size="small">
                    <TableHead><TableRow><TableCell>Medicine</TableCell><TableCell>Strength</TableCell><TableCell>Dose</TableCell><TableCell>How often</TableCell><TableCell /></TableRow></TableHead>
                    <TableBody>
                      {meds.map((m, n) => (
                        <TableRow key={n}>
                          <TableCell><TextField size="small" value={m.name} onChange={(e) => set(n, { name: e.target.value })} inputProps={{ "aria-label": `Read medicine ${n + 1}` }} />
                            <Typography variant="caption" display="block" color="text.secondary">Line: “{m.line}” ({m.confidence}%)</Typography></TableCell>
                          <TableCell><TextField size="small" value={m.strength} onChange={(e) => set(n, { strength: e.target.value })} sx={{ width: 100 }} /></TableCell>
                          <TableCell><TextField size="small" value={m.dose} onChange={(e) => set(n, { dose: e.target.value })} sx={{ width: 100 }} /></TableCell>
                          <TableCell><TextField size="small" value={m.frequency} onChange={(e) => set(n, { frequency: e.target.value })} sx={{ width: 110 }} /></TableCell>
                          <TableCell><IconButton aria-label="Remove" onClick={() => setMeds(meds.filter((_, i) => i !== n))}><Delete /></IconButton></TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                ) : <Empty>No known medicine name was read. Add them on the Medicines step by hand.</Empty>}
                <Button size="small" onClick={() => setMeds([...meds, { name: "", strength: "", dose: "", frequency: "", line: "(added by hand)", confidence: 100, ingredient: null }])}>
                  Add a medicine the reading missed
                </Button>
              </>
            )}
            <ErrorAlert error={save.error} />
            <Box>
              <Button variant="contained" onClick={() => save.mutate()} disabled={save.isPending || dk.status !== "unlocked"}>
                {reading ? "Save the paper and the checked reading" : "Save the paper"}
              </Button>
            </Box>
          </Stack>
        </Stack>
      )}
    </Stack>
  );
}

export function PapersTab({ r }: { r: ReferralDetail }) {
  const dk = useDeviceKeys();
  const refresh = useInvalidateReferral(r.id);
  const opened = useOpenedRecords(r);
  const items = latestById(opened.data ?? []).filter((i) => i.state === "ok");
  const scans = items.filter((i) => i.title.category === "scan" || i.content?.category === "scan");
  const readings = new Map(items.filter((i) => i.content?.category === "scan_reading").map((i) => [i.title.batch_id, i]));
  const locked = !["draft", "requested"].includes(r.status) && !r.amendment_open;
  if (r.working_set_purged_at) return <Alert severity="info">This referral's encrypted content was purged.</Alert>;
  if (dk.status !== "unlocked") return <DeviceKeyPanel compact />;
  return (
    <Stack spacing={2}>
      {!locked && (
        <Section title="Add a paper" description="A prescription, a lab slip or a letter the patient brought. Our servers never see the image or what it says.">
          <NewPaper r={r} onSaved={async () => { await opened.refetch(); refresh(); }} />
        </Section>
      )}
      <Section title="Papers" description="Decrypted on this device. Papers the patient added in their app appear here too.">
        {opened.isLoading ? <Loading label="Decrypting on this device…" /> : !scans.length ? <Empty>No papers yet.</Empty> : (
          <Stack spacing={2}>
            {scans.map((s) => {
              const rd = readings.get(s.title.batch_id);
              const meds = (rd?.content?.record?.medicines as ReadMedicine[] | undefined) ?? [];
              return (
                <Box key={s.title.item_id} sx={{ borderTop: 1, borderColor: "divider", pt: 1.5 }}>
                  <Typography variant="subtitle2">{s.origin === "patient" ? "Added by the patient" : "Added by you"} · {fmtDate(s.title.date, false)}</Typography>
                  <Stack direction={{ xs: "column", md: "row" }} spacing={2} sx={{ mt: 1 }}>
                    <Box sx={{ maxWidth: { md: 420 } }}><FileView item={s} /></Box>
                    <Box>{meds.length ? (
                      <Box component="ul" sx={{ m: 0, pl: 2.5 }}>{meds.map((m, i) => <li key={i}><Typography variant="body2">{[m.name, m.strength, m.dose, m.frequency].filter(Boolean).join(" · ")}</Typography></li>)}</Box>
                    ) : <Typography variant="body2" color="text.secondary">{rd ? "No medicines recorded from this paper." : "Not read on a device yet."}</Typography>}</Box>
                  </Stack>
                </Box>
              );
            })}
          </Stack>
        )}
      </Section>
    </Stack>
  );
}
