import { useState } from "react";
import { Link as RouterLink } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Grid, Link, List, ListItem, ListItemText, Paper, Button, Stack, Typography } from "@mui/material";
import { api } from "../../api/client";
import type { Clarification, FollowupTask, Referral } from "../../api/types";
import { Empty, ErrorAlert, fmtDate, Loading, PageHeader, ReasonDialog, ReferralStatus, Tag } from "../../components/common";
import { useMe } from "../../hooks";

type Queue = {
  clarifications: Clarification[];
  tasks?: FollowupTask[];
  awaiting_approval?: Referral[];
  awaiting_information?: Referral[];
  responses_to_review?: { referral_id: number; referral_reference: string; specialist_name: string; received_at: string }[];
  delivery_problems?: Referral[];
  drafts?: Referral[];
};

function RefList({ title, rows, empty }: { title: string; rows?: Referral[]; empty: string }) {
  return (
    <Paper sx={{ p: 2, height: "100%" }}>
      <Typography variant="h6" gutterBottom>
        {title} ({rows?.length ?? 0})
      </Typography>
      {!rows?.length && <Empty>{empty}</Empty>}
      <List dense>
        {rows?.map((r) => (
          <ListItem key={r.id} secondaryAction={<ReferralStatus status={r.status} label={r.status_label} />}>
            <ListItemText
              primary={
                <Link component={RouterLink} to={`/referrals/${r.id}`}>
                  {r.reference} · {r.patient.name}
                </Link>
              }
              secondary={`updated ${fmtDate(r.updated_at)}${r.amendment_open ? " · amendment open" : ""}`}
            />
          </ListItem>
        ))}
      </List>
    </Paper>
  );
}

export function WorkQueue() {
  const { data: me } = useMe();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["work-queue"], queryFn: () => api.get<Queue>("/work-queue"), refetchInterval: 15000 });
  const [answering, setAnswering] = useState<Clarification | null>(null);
  const answer = useMutation({
    mutationFn: ({ id, text }: { id: number; text: string }) => api.post(`/clarifications/${id}/answer`, { response_text: text }),
    onSuccess: () => {
      setAnswering(null);
      qc.invalidateQueries({ queryKey: ["work-queue"] });
    },
  });
  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorAlert error={q.error} />;
  const d = q.data!;
  const clinic = me?.institution_kind === "clinic";

  return (
    <>
      <PageHeader title="Work queue" subtitle={`Open requests and tasks for ${me?.institution_name}`} />
      <ErrorAlert error={answer.error} />
      <Grid container spacing={2}>
        <Grid item xs={12} lg={clinic ? 6 : 12}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              Information requests assigned to {me?.institution_name} ({d.clarifications.length})
            </Typography>
            {!d.clarifications.length && <Empty>Nothing waiting.</Empty>}
            <Stack spacing={1.5}>
              {d.clarifications.map((c) => (
                <Paper key={c.id} sx={{ p: 1.5 }}>
                  <Stack direction="row" justifyContent="space-between">
                    <Typography variant="subtitle2">
                      {c.referral_reference} · {c.origin === "specialist" ? "from the specialist" : `from ${c.created_by}`}
                    </Typography>
                    <Stack direction="row" spacing={0.5}>
                      {c.overdue && <Tag tone="bad" label="overdue" />}
                      <Tag tone={c.status === "open" ? "warn" : "info"} label={c.status} />
                    </Stack>
                  </Stack>
                  <Typography variant="body2" sx={{ my: 0.5 }}>
                    {c.question}
                  </Typography>
                  <Typography variant="caption" color="text.secondary" display="block">
                    {c.patient_ref_at_assignee ? `Your patient record: ${c.patient_ref_at_assignee}` : c.patient_name ? `Patient: ${c.patient_name}` : ""}
                    {c.due_date ? ` · due ${c.due_date}` : ""} · asked {fmtDate(c.created_at)}
                  </Typography>
                  {c.response_text && <Typography variant="body2">Answered: {c.response_text}</Typography>}
                  <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
                    {c.status === "open" && (
                      <Button size="small" variant="contained" onClick={() => setAnswering(c)}>
                        Answer
                      </Button>
                    )}
                    {clinic && (
                      <Button size="small" component={RouterLink} to={`/referrals/${c.referral_id}?tab=review`}>
                        Open referral
                      </Button>
                    )}
                    {me?.institution_kind === "laboratory" && (
                      <Button size="small" component={RouterLink} to={`/lab?patient=${c.patient_ref_at_assignee ?? ""}`}>
                        Open laboratory record
                      </Button>
                    )}
                  </Stack>
                </Paper>
              ))}
            </Stack>
          </Paper>
        </Grid>
        {clinic && (
          <>
            <Grid item xs={12} lg={6}>
              <Paper sx={{ p: 2 }}>
                <Typography variant="h6" gutterBottom>
                  Follow-up tasks ({d.tasks?.length ?? 0})
                </Typography>
                {!d.tasks?.length && <Empty>No open tasks.</Empty>}
                <List dense>
                  {d.tasks?.map((t) => (
                    <ListItem key={t.id} secondaryAction={t.overdue ? <Tag tone="bad" label="overdue" /> : t.due_date ? <Tag tone="wait" label={`due ${t.due_date}`} /> : undefined}>
                      <ListItemText
                        primary={
                          <Link component={RouterLink} to={`/referrals/${t.referral_id}?tab=followthrough`}>
                            {t.referral_reference}: {t.description}
                          </Link>
                        }
                        secondary={`owner ${t.assignee_name ?? "unassigned"} · specified by ${t.specified_by}`}
                      />
                    </ListItem>
                  ))}
                </List>
              </Paper>
            </Grid>
            <Grid item xs={12} md={6} lg={4}>
              <RefList title="Awaiting clinician approval / amendments" rows={d.awaiting_approval} empty="Nothing to approve." />
            </Grid>
            <Grid item xs={12} md={6} lg={4}>
              <RefList title="Awaiting information" rows={d.awaiting_information} empty="None." />
            </Grid>
            <Grid item xs={12} md={6} lg={4}>
              <Paper sx={{ p: 2, height: "100%" }}>
                <Typography variant="h6" gutterBottom>
                  Responses to review ({d.responses_to_review?.length ?? 0})
                </Typography>
                {!d.responses_to_review?.length && <Empty>None.</Empty>}
                <List dense>
                  {d.responses_to_review?.map((x) => (
                    <ListItem key={x.referral_id}>
                      <ListItemText
                        primary={
                          <Link component={RouterLink} to={`/referrals/${x.referral_id}?tab=followthrough`}>
                            {x.referral_reference}
                          </Link>
                        }
                        secondary={`${x.specialist_name}, received ${fmtDate(x.received_at)}`}
                      />
                    </ListItem>
                  ))}
                </List>
              </Paper>
            </Grid>
            <Grid item xs={12} md={6}>
              <RefList title="Delivery problems" rows={d.delivery_problems} empty="No delivery problems." />
            </Grid>
            <Grid item xs={12} md={6}>
              <RefList title="Drafts in progress" rows={d.drafts} empty="No drafts." />
            </Grid>
          </>
        )}
      </Grid>
      {answering && (
        <ReasonDialog open title={`Answer request on ${answering.referral_reference}`} label="Answer" confirm="Send answer" minLength={2} onClose={() => setAnswering(null)} onConfirm={(text) => answer.mutate({ id: answering.id, text })} busy={answer.isPending}>
          <Typography variant="body2" sx={{ mb: 1 }}>
            {answering.question}
          </Typography>
        </ReasonDialog>
      )}
    </>
  );
}
