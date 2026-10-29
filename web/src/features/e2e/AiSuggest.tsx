/**
 * "Suggest with AI" on the doctor's Records step (spec v4 8.2 to 8.6): a mandatory "What is sent to the AI" preview,
 * then the answer labelled "AI suggestion, unverified", with a "Not included" list and what may be missing.
 */
import { useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Alert, AlertTitle, Box, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle, Stack, TextField,
  Typography } from "@mui/material";
import type { ReferralDetail } from "../../api/types";
import { ErrorAlert, Section } from "../../components/common";
import { useRefData } from "../../hooks";
import { askSelection, buildSelectionPayload, SelectionPayload, Suggestion, SuggestionAnswer } from "./ai";
import type { OpenedItem } from "./records";

export type AiResult = { byItem: Map<string, Suggestion>; answer: SuggestionAnswer };

export function AiSuggest({ r, items, onResult, onApply }: {
  r: ReferralDetail; items: OpenedItem[]; onResult: (x: AiResult) => void; onApply: (ticks: Record<string, boolean>) => void;
}) {
  const ref = useRefData();
  const places = useMemo(() => Object.values(ref.data?.institutions ?? {}).map((i) => ({ name: i.name, kind: i.kind })), [ref.data]);
  const [preview, setPreview] = useState<{ text: string; ids: Map<number, string> } | null>(null);
  const [result, setResult] = useState<AiResult | null>(null);
  const send = useMutation({
    mutationFn: async () => {
      const payload = JSON.parse(preview!.text) as SelectionPayload;
      const answer = await askSelection(r.id, payload);
      return { answer, ids: preview!.ids };
    },
    meta: { silent: true },
    onSuccess: ({ answer, ids }) => {
      const byItem = new Map<string, Suggestion>();
      for (const s of answer.recommendations) {
        const id = ids.get(s.id);
        if (id) byItem.set(id, s);
      }
      const x = { byItem, answer };
      setResult(x);
      onResult(x);
      setPreview(null);
    },
  });
  const open = () => {
    const { payload, ids } = buildSelectionPayload(r, items, places);
    setPreview({ text: JSON.stringify(payload, null, 2), ids });
  };
  let parseError: string | null = null;
  if (preview) {
    try { JSON.parse(preview.text); } catch (e) { parseError = (e as Error).message; }
  }
  const excluded = result ? items.filter((i) => result.byItem.get(i.title.item_id)?.recommendation === "exclude") : [];
  const apply = () => {
    const ticks: Record<string, boolean> = {};
    for (const [id, s] of result!.byItem) ticks[id] = s.recommendation === "include" && s.relevance !== "low";
    onApply(ticks);
  };
  return (
    <Section title="AI suggestion" description="Optional. Only de-identified text is sent, only when you ask, and you see it first. The AI does not decide: your ticks do.">
      <Stack direction="row" spacing={1} alignItems="center">
        <Button variant="outlined" onClick={open} disabled={!items.length}>Suggest with AI</Button>
        {result && <Chip color="warning" variant="outlined" label="AI suggestion, unverified" />}
      </Stack>
      {result && (
        <Box sx={{ mt: 1.5 }}>
          <Typography variant="body2" sx={{ mb: 1 }}>
            {result.answer.recommendations.length} records ranked by {result.answer.model}.
            {result.answer.withheld ? ` ${result.answer.withheld} reason(s) were withheld for treatment wording.` : ""}
            {result.answer.dropped_ids ? ` ${result.answer.dropped_ids} answer(s) named records that do not exist and were dropped.` : ""}
          </Typography>
          <Button size="small" variant="contained" onClick={apply}>Tick what the AI suggests</Button>
          {excluded.length > 0 && (
            <Alert severity="info" sx={{ mt: 1.5 }}>
              <AlertTitle>Not included (AI suggestion)</AlertTitle>
              <Box component="ul" sx={{ m: 0, pl: 2.5 }}>
                {excluded.map((i) => <li key={i.title.item_id}>{i.content?.label ?? i.title.label}: {result.byItem.get(i.title.item_id)?.reason}</li>)}
              </Box>
            </Alert>
          )}
          {result.answer.missing.length > 0 && (
            <Alert severity="info" sx={{ mt: 1.5 }}>
              <AlertTitle>Possibly missing (AI suggestion)</AlertTitle>
              <Box component="ul" sx={{ m: 0, pl: 2.5 }}>{result.answer.missing.map((m) => <li key={m}>{m}</li>)}</Box>
            </Alert>
          )}
        </Box>
      )}
      <Dialog open={!!preview} onClose={() => setPreview(null)} maxWidth="md" fullWidth>
        <DialogTitle>What is sent to the AI</DialogTitle>
        <DialogContent>
          <Alert severity="warning" sx={{ mb: 1.5 }}>
            Names, ID numbers, record numbers, places and dates were replaced on this device. Automatic de-identification can
            miss things: read it and remove anything that identifies the patient before sending. It passes through our server
            to the model and is not stored.
          </Alert>
          <TextField value={preview?.text ?? ""} onChange={(e) => setPreview(preview && { ...preview, text: e.target.value })}
            multiline fullWidth minRows={12} maxRows={24} inputProps={{ "aria-label": "Text sent to the AI", style: { fontFamily: "monospace", fontSize: 12 } }}
            error={!!parseError} helperText={parseError ?? " "} />
          <ErrorAlert error={send.error} />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPreview(null)}>Cancel</Button>
          <Button variant="contained" disabled={!!parseError || send.isPending} onClick={() => send.mutate()}>Send to the AI</Button>
        </DialogActions>
      </Dialog>
    </Section>
  );
}

export function AiChip({ s }: { s: Suggestion | undefined }) {
  if (!s) return null;
  return <Chip size="small" variant="outlined" color={s.recommendation === "include" ? "success" : s.recommendation === "exclude" ? "default" : "info"}
    sx={{ ml: 1 }} label={`AI: ${s.recommendation}, ${s.relevance}`} title={`AI suggestion, unverified: ${s.reason}`} />;
}
