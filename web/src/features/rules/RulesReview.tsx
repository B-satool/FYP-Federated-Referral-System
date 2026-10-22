import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Dialog, DialogActions, DialogContent, DialogTitle, Paper, Stack, TextField, Typography } from "@mui/material";
import { api } from "../../api/client";
import { ErrorAlert, fmtDate, KeyValue, Loading, PageHeader, Tag } from "../../components/common";

type Rule = {
  rule_id: string;
  version: number;
  drug_class: string;
  specialty: string;
  requires_procedure: boolean;
  procedures: string[];
  title: string;
  message: string;
  rationale: string;
  reference: string;
  proposed_by: string;
  content_hash: string;
  approval_state: string;
  active: boolean;
  reviewer: string | null;
  reference_checked: string | null;
  decided_at: string | null;
  approval_note: string | null;
};
type Ruleset = { ruleset_id: string; version: string; governance: string; supported_classes: string[]; supported_procedures: string[]; rules: Rule[]; can_approve: boolean };

const STATE_TONE: Record<string, "ok" | "warn" | "off" | "bad"> = { approved: "ok", draft: "warn", retired: "off", rejected: "off", approval_invalid_content_changed: "bad" };

export function RulesReview() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["rules"], queryFn: () => api.get<Ruleset>("/rules") });
  const [deciding, setDeciding] = useState<{ rule: Rule; decision: "approve" | "retire" | "reject" } | null>(null);
  const [reference, setReference] = useState("");
  const [note, setNote] = useState("");
  const decide = useMutation({
    mutationFn: () => api.post(`/rules/${deciding!.rule.rule_id}/versions/${deciding!.rule.version}/decision`, { decision: deciding!.decision, reference_checked: reference, note }),
    onSuccess: () => {
      setDeciding(null);
      qc.invalidateQueries({ queryKey: ["rules"] });
    },
  });
  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorAlert error={q.error} />;
  const rs = q.data!;
  return (
    <>
      <PageHeader title="Medication rules (orthodontics)" subtitle={`${rs.ruleset_id} ${rs.version} · supported classes: ${rs.supported_classes.join(", ")}`} />
      <Alert severity="info" sx={{ mb: 2 }}>
        {rs.governance} {rs.can_approve ? "" : "You can view rules; only a clinical rule reviewer can approve them."}
      </Alert>
      <Stack spacing={2}>
        {rs.rules.map((r) => (
          <Paper key={r.rule_id} sx={{ p: 2 }}>
            <Stack direction="row" justifyContent="space-between" spacing={1}>
              <Typography variant="h6">
                {r.rule_id} v{r.version}
              </Typography>
              <Tag tone={STATE_TONE[r.approval_state] ?? "warn"} label={r.approval_state === "approval_invalid_content_changed" ? "content changed, approval invalid" : r.active ? "active (approved)" : r.approval_state} />
            </Stack>
            <Typography variant="subtitle1">{r.title}</Typography>
            <Typography variant="body2" sx={{ mb: 1 }}>
              {r.message}
            </Typography>
            <KeyValue
              items={[
                ["Medication class", r.drug_class.replace(/_/g, " ")],
                ["Applies to", r.requires_procedure ? `procedures: ${r.procedures.join(", ")}` : "specialty-level attention prompt (no procedure risk asserted)"],
                ["Rationale", r.rationale],
                ["Reference", r.reference],
                ["Proposed by", r.proposed_by],
                ["Content hash", <code key="h">{r.content_hash.slice(0, 20)}…</code>],
                ["Decision", r.reviewer ? `${r.approval_state} by ${r.reviewer}, ${fmtDate(r.decided_at)}, reference checked: ${r.reference_checked}` : "awaiting clinical review"],
              ]}
            />
            {rs.can_approve && (
              <Stack direction="row" spacing={1} sx={{ mt: 1.5 }}>
                {!r.active && (
                  <Button variant="contained" onClick={() => { setDeciding({ rule: r, decision: "approve" }); setReference(r.reference); }}>
                    Approve and activate
                  </Button>
                )}
                {r.active && (
                  <Button color="warning" variant="outlined" onClick={() => { setDeciding({ rule: r, decision: "retire" }); setReference(r.reference_checked ?? ""); }}>
                    Retire
                  </Button>
                )}
                {r.approval_state === "draft" && (
                  <Button onClick={() => { setDeciding({ rule: r, decision: "reject" }); setReference(r.reference); }}>
                    Reject
                  </Button>
                )}
              </Stack>
            )}
          </Paper>
        ))}
      </Stack>
      {deciding && (
        <Dialog open onClose={() => setDeciding(null)} fullWidth maxWidth="sm">
          <DialogTitle>
            {deciding.decision} {deciding.rule.rule_id} v{deciding.rule.version}
          </DialogTitle>
          <DialogContent>
            <Alert severity="warning" sx={{ mb: 2 }}>
              Approving activates this rule for all open orthodontic referrals; they are re-evaluated immediately. You confirm the clinical meaning, not only the code.
            </Alert>
            <TextField fullWidth multiline minRows={2} label="Reference you checked" value={reference} onChange={(e) => setReference(e.target.value)} sx={{ mb: 2 }} />
            <TextField fullWidth label="Note" value={note} onChange={(e) => setNote(e.target.value)} />
            <ErrorAlert error={decide.error} />
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setDeciding(null)}>Cancel</Button>
            <Button variant="contained" disabled={reference.trim().length < 5 || decide.isPending} onClick={() => decide.mutate()}>
              Confirm
            </Button>
          </DialogActions>
        </Dialog>
      )}
    </>
  );
}
