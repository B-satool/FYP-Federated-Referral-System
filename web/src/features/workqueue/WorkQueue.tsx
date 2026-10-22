import { ReactNode, useState } from "react";
import { Link as RouterLink } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Box, Button, Link, Stack, Typography } from "@mui/material";
import { api } from "../../api/client";
import type { Clarification, Referral } from "../../api/types";
import { ErrorAlert, fmtDate, Loading, PageHeader, ReasonDialog, ReferralStatus, Section, Tag } from "../../components/common";
import { useMe } from "../../hooks";
import { actionableCount, Queue } from "./queue";

/** One row of a queue: what it is, a short detail, and what to do about it. */
function Row({ first, main, detail, aside }: { first: boolean; main: ReactNode; detail?: ReactNode; aside?: ReactNode }) {
  return (
    <Box component="li" sx={{ py: 1.5, borderTop: first ? "none" : "1px solid", borderColor: "divider", display: "flex", flexDirection: { xs: "column", md: "row" }, gap: 1, justifyContent: "space-between", alignItems: { md: "center" } }}>
      <Box sx={{ minWidth: 0 }}>
        <Typography sx={{ fontWeight: 600 }} component="div">
          {main}
        </Typography>
        {detail && (
          <Typography variant="body2" color="text.secondary" component="div">
            {detail}
          </Typography>
        )}
      </Box>
      {aside && (
        <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap sx={{ flexShrink: 0 }}>
          {aside}
        </Stack>
      )}
    </Box>
  );
}

function ReferralRows({ rows }: { rows: Referral[] }) {
  return (
    <Box component="ul" sx={{ listStyle: "none", m: 0, p: 0 }}>
      {rows.map((r, i) => (
        <Row
          key={r.id}
          first={i === 0}
          main={
            <Link component={RouterLink} to={`/referrals/${r.id}`}>
              {r.reference} · {r.patient.name}
            </Link>
          }
          detail={`Updated ${fmtDate(r.updated_at)}${r.amendment_open ? " · amendment open" : ""}`}
          aside={<ReferralStatus status={r.status} label={r.status_label} />}
        />
      ))}
    </Box>
  );
}

export function WorkQueue() {
  const { data: me } = useMe();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["work-queue"], queryFn: () => api.get<Queue>("/work-queue"), refetchInterval: 15000 });
  const [answering, setAnswering] = useState<Clarification | null>(null);
  const answer = useMutation({
    mutationFn: ({ id, text }: { id: number; text: string }) => api.post(`/clarifications/${id}/answer`, { response_text: text }),
    meta: { success: "Answer sent." },
    onSuccess: () => {
      setAnswering(null);
      qc.invalidateQueries({ queryKey: ["work-queue"] });
    },
  });
  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorAlert error={q.error} />;
  const d = q.data!;
  const clinic = me?.institution_kind === "clinic";
  const total = actionableCount(d);

  const empty: string[] = [];
  const noteEmpty = (label: string, n: number | undefined) => {
    if (!n) empty.push(label);
    return !!n;
  };

  return (
    <>
      <PageHeader
        title="Work queue"
        subtitle={total === 0 ? `Nothing needs action at ${me?.institution_name}.` : `${total} ${total === 1 ? "item needs" : "items need"} action at ${me?.institution_name}.`}
      />
      <ErrorAlert error={answer.error} />
      <Stack spacing={2}>
        {noteEmpty("Information requests", d.clarifications.length) && (
          <Section id="requests" title={`Information requests (${d.clarifications.length})`} description={`Questions assigned to ${me?.institution_name}. Answering moves the referral forward.`}>
            <Box component="ul" sx={{ listStyle: "none", m: 0, p: 0 }}>
              {d.clarifications.map((c, i) => (
                <Row
                  key={c.id}
                  first={i === 0}
                  main={
                    <>
                      {c.referral_reference} · {c.origin === "specialist" ? "from the specialist" : `from ${c.created_by}`}
                    </>
                  }
                  detail={
                    <>
                      <Box component="span" sx={{ display: "block", color: "text.primary" }}>
                        {c.question}
                      </Box>
                      {c.patient_ref_at_assignee ? `Your patient record: ${c.patient_ref_at_assignee}` : c.patient_name ? `Patient: ${c.patient_name}` : ""}
                      {c.due_date ? ` · due ${c.due_date}` : ""} · asked {fmtDate(c.created_at)}
                      {c.response_text && <Box component="span" sx={{ display: "block" }}>Answered: {c.response_text}</Box>}
                    </>
                  }
                  aside={
                    <>
                      {c.overdue && <Tag tone="bad" label="overdue" />}
                      <Tag tone={c.status === "open" ? "warn" : "info"} label={c.status} />
                      {c.status === "open" && (
                        <Button size="small" variant="contained" onClick={() => setAnswering(c)}>
                          Answer
                        </Button>
                      )}
                      {clinic && (
                        <Button size="small" variant="outlined" component={RouterLink} to={`/referrals/${c.referral_id}?tab=review`}>
                          Open referral
                        </Button>
                      )}
                      {me?.institution_kind === "laboratory" && (
                        <Button size="small" variant="outlined" component={RouterLink} to={`/lab?patient=${c.patient_ref_at_assignee ?? ""}`}>
                          Open laboratory record
                        </Button>
                      )}
                    </>
                  }
                />
              ))}
            </Box>
          </Section>
        )}

        {clinic && (
          <>
            {noteEmpty("Awaiting clinician approval", d.awaiting_approval?.length) && (
              <Section id="approval" title={`Awaiting clinician approval (${d.awaiting_approval!.length})`} description="Includes referrals with a new version to approve after a change.">
                <ReferralRows rows={d.awaiting_approval!} />
              </Section>
            )}
            {noteEmpty("Responses to review", d.responses_to_review?.length) && (
              <Section id="responses" title={`Responses to review (${d.responses_to_review!.length})`} description="Specialist responses that a referring clinician has not yet reviewed.">
                <Box component="ul" sx={{ listStyle: "none", m: 0, p: 0 }}>
                  {d.responses_to_review!.map((x, i) => (
                    <Row
                      key={x.referral_id}
                      first={i === 0}
                      main={
                        <Link component={RouterLink} to={`/referrals/${x.referral_id}?tab=followthrough`}>
                          {x.referral_reference}
                        </Link>
                      }
                      detail={`${x.specialist_name}, received ${fmtDate(x.received_at)}`}
                    />
                  ))}
                </Box>
              </Section>
            )}
            {noteEmpty("Follow-up tasks", d.tasks?.length) && (
              <Section id="tasks" title={`Follow-up tasks (${d.tasks!.length})`} description="Tasks specified by a clinician that are still open.">
                <Box component="ul" sx={{ listStyle: "none", m: 0, p: 0 }}>
                  {d.tasks!.map((t, i) => (
                    <Row
                      key={t.id}
                      first={i === 0}
                      main={
                        <Link component={RouterLink} to={`/referrals/${t.referral_id}?tab=followthrough`}>
                          {t.referral_reference}: {t.description}
                        </Link>
                      }
                      detail={`Owner ${t.assignee_name ?? "unassigned"} · specified by ${t.specified_by}`}
                      aside={t.overdue ? <Tag tone="bad" label="overdue" /> : t.due_date ? <Tag tone="wait" label={`due ${t.due_date}`} /> : undefined}
                    />
                  ))}
                </Box>
              </Section>
            )}
            {noteEmpty("Delivery problems", d.delivery_problems?.length) && (
              <Section id="delivery" title={`Delivery problems (${d.delivery_problems!.length})`} description="Approved referrals that could not be delivered. Retrying never creates a duplicate.">
                <ReferralRows rows={d.delivery_problems!} />
              </Section>
            )}
            {noteEmpty("Awaiting information", d.awaiting_information?.length) && (
              <Section id="info" title={`Awaiting information (${d.awaiting_information!.length})`} description="Waiting for records or answers before they can go for approval.">
                <ReferralRows rows={d.awaiting_information!} />
              </Section>
            )}
            {noteEmpty("Drafts in progress", d.drafts?.length) && (
              <Section id="drafts" title={`Drafts in progress (${d.drafts!.length})`}>
                <ReferralRows rows={d.drafts!} />
              </Section>
            )}
          </>
        )}
        {empty.length > 0 && (
          <Typography variant="body2" color="text.secondary">
            Nothing to show for: {empty.join(", ").toLowerCase()}.
          </Typography>
        )}
      </Stack>
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
