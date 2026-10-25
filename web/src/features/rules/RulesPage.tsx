import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Box,
  Button,
  Checkbox,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  FormGroup,
  FormLabel,
  MenuItem,
  Paper,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { api } from "../../api/client";
import type { Rule, RulesView } from "../../api/types";
import { Empty, ErrorAlert, fmtDate, KeyValue, Loading, PageHeader, Tag } from "../../components/common";

type RuleForm = { title: string; drug_class: string; procedure_tags: string[]; message: string; rationale: string; reference: string };

const STATUS_TONE: Record<Rule["status"], "ok" | "warn" | "bad" | "off" | "neutral"> = {
  approved: "ok",
  draft: "warn",
  rejected: "bad",
  retired: "off",
  superseded: "neutral",
};
const STATUS_LABEL: Record<Rule["status"], string> = {
  approved: "approved (in use)",
  draft: "draft (not in use)",
  rejected: "rejected",
  retired: "retired",
  superseded: "superseded",
};

function RuleDialog({ view, initial, ruleId, onClose }: { view: RulesView; initial?: Rule; ruleId?: string; onClose: () => void }) {
  const qc = useQueryClient();
  const [form, setForm] = useState<RuleForm>({
    title: initial?.title ?? "",
    drug_class: initial?.drug_class ?? "",
    procedure_tags: initial?.procedure_tags ?? [],
    message: initial?.message ?? "",
    rationale: initial?.rationale ?? "",
    reference: initial?.reference ?? "",
  });
  const save = useMutation({
    mutationFn: () => (ruleId ? api.put(`/rules/${ruleId}`, form) : api.post("/rules", form)),
    meta: { success: "Draft saved. A clinical reviewer must approve it before it raises flags." },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["rules"] });
      onClose();
    },
  });
  const valid = form.title.trim().length >= 5 && form.drug_class && form.procedure_tags.length > 0 && form.message.trim().length >= 10;
  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="md">
      <DialogTitle>{ruleId ? `Edit ${ruleId} (creates a new draft)` : "New medication rule"}</DialogTitle>
      <DialogContent dividers>
        <Stack spacing={2}>
          <Alert severity="info">
            A rule says: when the patient's current medicines include this drug class, and the planned procedure has any of these features, show a
            flag. The message asks for review; it must never advise starting, stopping or changing a medicine.
          </Alert>
          <TextField label="Title" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="Medication requires review: …" fullWidth />
          <TextField select label="Drug class" value={form.drug_class} onChange={(e) => setForm({ ...form, drug_class: e.target.value })} fullWidth>
            {Object.entries(view.drug_classes).map(([k, v]) => (
              <MenuItem key={k} value={k}>
                {v}
              </MenuItem>
            ))}
          </TextField>
          <Box component="fieldset" sx={{ border: 0, p: 0, m: 0 }}>
            <FormLabel component="legend">Procedures with any of these features</FormLabel>
            <FormGroup row>
              {Object.entries(view.procedure_tags).map(([k, v]) => (
                <FormControlLabel
                  key={k}
                  label={v}
                  control={
                    <Checkbox
                      checked={form.procedure_tags.includes(k)}
                      onChange={(e) =>
                        setForm({ ...form, procedure_tags: e.target.checked ? [...form.procedure_tags, k] : form.procedure_tags.filter((t) => t !== k) })
                      }
                    />
                  }
                />
              ))}
            </FormGroup>
          </Box>
          <TextField label="Flag message" multiline minRows={2} value={form.message} onChange={(e) => setForm({ ...form, message: e.target.value })} fullWidth />
          <TextField label="Why this matters (rationale)" multiline minRows={2} value={form.rationale} onChange={(e) => setForm({ ...form, rationale: e.target.value })} fullWidth />
          <TextField label="Reference (guideline)" value={form.reference} onChange={(e) => setForm({ ...form, reference: e.target.value })} fullWidth />
          <ErrorAlert error={save.error} />
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="contained" disabled={!valid || save.isPending} onClick={() => save.mutate()}>
          Save draft
        </Button>
      </DialogActions>
    </Dialog>
  );
}

function DecisionDialog({ rule, decision, onClose }: { rule: Rule; decision: "approve" | "reject" | "retire"; onClose: () => void }) {
  const qc = useQueryClient();
  const [ref, setRef] = useState(rule.reference);
  const [note, setNote] = useState("");
  const decide = useMutation({
    mutationFn: () => api.post(`/rules/${rule.rule_id}/versions/${rule.version}/decision`, { decision, reference_checked: ref, note }),
    meta: { success: decision === "approve" ? "Rule approved. Open referrals were checked again." : "Decision recorded." },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["rules"] });
      onClose();
    },
  });
  const verb = { approve: "Approve", reject: "Reject", retire: "Retire" }[decision];
  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>
        {verb} {rule.rule_id} version {rule.version}
      </DialogTitle>
      <DialogContent dividers>
        <Stack spacing={2}>
          {decision === "approve" && (
            <Alert severity="warning">Approving this exact version lets it raise flags for every open referral straight away.</Alert>
          )}
          {decision === "retire" && <Alert severity="warning">A retired rule stops raising flags for open referrals.</Alert>}
          <TextField
            label="Reference checked (required)"
            value={ref}
            onChange={(e) => setRef(e.target.value)}
            helperText={ref.trim().length < 5 ? "At least 5 characters" : " "}
            fullWidth
          />
          <TextField label="Note" value={note} onChange={(e) => setNote(e.target.value)} fullWidth />
          <ErrorAlert error={decide.error} />
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="contained" color={decision === "approve" ? "primary" : "error"} disabled={ref.trim().length < 5 || decide.isPending} onClick={() => decide.mutate()}>
          {verb}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

function RuleVersion({ r, view, onDecide }: { r: Rule; view: RulesView; onDecide: (d: "approve" | "reject" | "retire") => void }) {
  return (
    <Box>
      <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap sx={{ mb: 1 }}>
        <Typography variant="subtitle1">{r.title}</Typography>
        <Tag tone={STATUS_TONE[r.status]} label={`v${r.version} ${STATUS_LABEL[r.status]}`} />
        {!r.intact && <Tag tone="bad" label="content changed outside the app: not used" />}
      </Stack>
      <Typography variant="body2" sx={{ mb: 1 }}>
        {r.message}
      </Typography>
      <KeyValue
        items={[
          ["When the patient takes", r.drug_class_label],
          ["And the procedure has", r.procedure_tag_labels.join(", ")],
          ["Procedures covered", r.matching_procedures.length ? r.matching_procedures.join(", ") : "None in the procedure list"],
          ["Why", r.rationale || "Not recorded"],
          ["Reference", r.reference || "Not recorded"],
          ["Drafted by", `${r.created_by}, ${fmtDate(r.created_at)}`],
          ...(r.decided_by
            ? ([[r.status === "rejected" ? "Rejected by" : "Approved by", `${r.decided_by}, ${fmtDate(r.decided_at)}${r.decision_note ? `: ${r.decision_note}` : ""}`]] as [string, string][])
            : []),
        ]}
      />
      {view.can_approve && (
        <Stack direction="row" spacing={1} sx={{ mt: 1.5 }}>
          {r.status === "draft" && (
            <>
              <Button size="small" variant="contained" onClick={() => onDecide("approve")}>
                Approve
              </Button>
              <Button size="small" color="error" onClick={() => onDecide("reject")}>
                Reject
              </Button>
            </>
          )}
          {r.status === "approved" && (
            <Button size="small" color="error" onClick={() => onDecide("retire")}>
              Retire
            </Button>
          )}
        </Stack>
      )}
    </Box>
  );
}

export function RulesPage() {
  const q = useQuery({ queryKey: ["rules"], queryFn: () => api.get<RulesView>("/rules") });
  const [editing, setEditing] = useState<{ ruleId?: string; initial?: Rule } | null>(null);
  const [deciding, setDeciding] = useState<{ rule: Rule; decision: "approve" | "reject" | "retire" } | null>(null);
  const view = q.data;
  return (
    <>
      <PageHeader
        title="Medication rules"
        subtitle="Drug-against-procedure rules. A rule raises flags only after a clinical reviewer approves that exact version. Flags never advise changing a medicine."
        actions={
          view?.can_edit && (
            <Button variant="contained" onClick={() => setEditing({})}>
              New rule
            </Button>
          )
        }
      />
      {q.isLoading && <Loading />}
      <ErrorAlert error={q.error} />
      {view && view.rules.length === 0 && <Empty>No rules yet.</Empty>}
      <Stack spacing={2}>
        {view?.rules.map(({ rule_id, versions }) => {
          const current = versions.find((v) => v.status === "approved");
          const drafts = versions.filter((v) => v.status === "draft");
          const shown = [...drafts, ...(current ? [current] : [])];
          const history = versions.filter((v) => !shown.includes(v));
          const latest = versions[0];
          return (
            <Paper key={rule_id} component="section" aria-label={rule_id} sx={{ p: { xs: 2, md: 2.5 } }}>
              <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
                <Typography variant="overline">{rule_id}</Typography>
                {view.can_edit && (
                  <Button size="small" onClick={() => setEditing({ ruleId: rule_id, initial: latest })}>
                    Edit (creates a new draft)
                  </Button>
                )}
              </Stack>
              {!current && <Alert severity="warning" sx={{ mb: 1.5 }}>No approved version: this rule raises no flags.</Alert>}
              <Stack spacing={2.5}>
                {(shown.length ? shown : [latest]).map((r) => (
                  <RuleVersion key={r.id} r={r} view={view} onDecide={(decision) => setDeciding({ rule: r, decision })} />
                ))}
              </Stack>
              {history.length > 0 && (
                <details style={{ marginTop: 16 }}>
                  <summary>
                    <Typography component="span" variant="body2">
                      Version history ({history.length})
                    </Typography>
                  </summary>
                  <Stack spacing={1} sx={{ mt: 1 }}>
                    {history.map((h) => (
                      <Typography key={h.id} variant="body2">
                        v{h.version} · {STATUS_LABEL[h.status]} · {h.title} · drafted by {h.created_by}, {fmtDate(h.created_at)}
                        {h.decided_by ? ` · ${h.status} by ${h.decided_by}, ${fmtDate(h.decided_at)}` : ""}
                      </Typography>
                    ))}
                  </Stack>
                </details>
              )}
            </Paper>
          );
        })}
      </Stack>
      {editing && view && <RuleDialog view={view} ruleId={editing.ruleId} initial={editing.initial} onClose={() => setEditing(null)} />}
      {deciding && <DecisionDialog rule={deciding.rule} decision={deciding.decision} onClose={() => setDeciding(null)} />}
    </>
  );
}
