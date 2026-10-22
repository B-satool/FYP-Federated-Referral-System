import { ReactNode, useState } from "react";
import { Link as RouterLink } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Box, Button, Link, Paper, Stack, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Typography, useMediaQuery } from "@mui/material";
import { useTheme } from "@mui/material/styles";
import { api } from "../../api/client";
import type { Clarification, Me, Referral } from "../../api/types";
import { ErrorAlert, fmtDate, Loading, PageHeader, ReasonDialog, ReferralStatus, Section, Tag } from "../../components/common";
import { useMe } from "../../hooks";
import { actionableCount, Queue } from "./queue";

/** One row of the queue: which referral, what to do about it, and where to go. */
type Item = {
  key: string;
  reference: string;
  patient: string;
  todo: ReactNode;
  status: ReactNode;
  when: string | null;
  to: string;
  overdue?: boolean;
  actions?: ReactNode;
};

const ts = (d: string | null) => (d ? new Date(d).getTime() : Number.MAX_SAFE_INTEGER);

/** Overdue first, then oldest first. The order only reflects due dates and age; it never assigns clinical urgency. */
function byOverdueThenOldest(a: Item, b: Item) {
  if (!!a.overdue !== !!b.overdue) return a.overdue ? -1 : 1;
  return ts(a.when) - ts(b.when);
}

function referralItem(r: Referral, todo: ReactNode, tab?: string): Item {
  return {
    key: `ref-${r.id}`,
    reference: r.reference,
    patient: r.patient.name,
    todo,
    status: <ReferralStatus status={r.status} label={r.status_label} />,
    when: r.updated_at,
    to: `/referrals/${r.id}${tab ? `?tab=${tab}` : ""}`,
  };
}

function buildItems(d: Queue, me: Me | undefined, answer: (c: Clarification) => void) {
  const clinic = me?.institution_kind === "clinic";
  const lab = me?.institution_kind === "laboratory";
  const now: Item[] = [];
  const waiting: Item[] = [];

  for (const c of d.clarifications) {
    const open = c.status === "open";
    const item: Item = {
      key: `clar-${c.id}`,
      reference: c.referral_reference ?? `Referral ${c.referral_id}`,
      patient: c.patient_ref_at_assignee ? `Your record ${c.patient_ref_at_assignee}` : (c.patient_name ?? "Not recorded"),
      todo: (
        <>
          {open ? "Answer request" : "Answered, waiting for the requester"} {c.origin === "specialist" ? "from the specialist" : `from ${c.created_by}`}
          <Box component="span" sx={{ display: "block", color: "text.secondary" }}>
            {c.question}
            {c.due_date ? ` · due ${c.due_date}` : ""}
          </Box>
        </>
      ),
      status: <Tag tone={c.overdue ? "bad" : open ? "warn" : "info"} label={c.overdue ? "overdue" : c.status} />,
      when: c.created_at,
      to: clinic ? `/referrals/${c.referral_id}?tab=review` : lab ? `/lab?patient=${c.patient_ref_at_assignee ?? ""}` : "/work-queue",
      overdue: c.overdue,
      actions: open ? (
        <Button size="small" variant="contained" onClick={() => answer(c)}>
          Answer
        </Button>
      ) : undefined,
    };
    (open ? now : waiting).push(item);
  }

  for (const r of d.delivery_problems ?? []) now.push(referralItem(r, "Delivery failed: retry sending", "brief"));
  for (const r of d.awaiting_approval ?? []) now.push(referralItem(r, r.amendment_open ? "Approve the new version after a change" : "Review and approve the brief", "brief"));
  for (const x of d.responses_to_review ?? [])
    now.push({
      key: `resp-${x.referral_id}`,
      reference: x.referral_reference,
      patient: "",
      todo: `Read the response from ${x.specialist_name}`,
      status: <Tag tone="ok" label="response returned" />,
      when: x.received_at,
      to: `/referrals/${x.referral_id}?tab=followthrough`,
    });
  for (const t of d.tasks ?? [])
    now.push({
      key: `task-${t.id}`,
      reference: t.referral_reference ?? `Referral ${t.referral_id}`,
      patient: "",
      todo: (
        <>
          Follow-up task: {t.description}
          <Box component="span" sx={{ display: "block", color: "text.secondary" }}>
            Owner {t.assignee_name ?? "unassigned"} · specified by {t.specified_by}
          </Box>
        </>
      ),
      status: t.overdue ? <Tag tone="bad" label="overdue" /> : t.due_date ? <Tag tone="wait" label={`due ${t.due_date}`} /> : <Tag tone="info" label="open" />,
      when: t.due_date ?? t.created_at,
      to: `/referrals/${t.referral_id}?tab=followthrough`,
      overdue: t.overdue,
    });
  for (const r of d.awaiting_information ?? []) waiting.push(referralItem(r, "Records or answers before approval", "review"));

  now.sort(byOverdueThenOldest);
  waiting.sort(byOverdueThenOldest);
  const drafts = (d.drafts ?? []).map((r) => referralItem(r, r.amendment_open ? "Amendment open: finish and send for approval" : "Finish the draft and send for approval"));
  return { now, waiting, drafts };
}

function QueueTable({ items, todoHeading }: { items: Item[]; todoHeading: string }) {
  return (
    <TableContainer>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Referral</TableCell>
            <TableCell>Patient</TableCell>
            <TableCell>{todoHeading}</TableCell>
            <TableCell>Status</TableCell>
            <TableCell>Updated</TableCell>
            <TableCell>
              <span className="sr-only">Actions</span>
            </TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {items.map((i) => (
            <TableRow key={i.key}>
              <TableCell sx={{ fontWeight: 600, whiteSpace: "nowrap" }}>{i.reference}</TableCell>
              <TableCell>{i.patient}</TableCell>
              <TableCell>{i.todo}</TableCell>
              <TableCell>{i.status}</TableCell>
              <TableCell sx={{ whiteSpace: "nowrap" }}>{fmtDate(i.when)}</TableCell>
              <TableCell align="right">
                <Stack direction="row" spacing={1} justifyContent="flex-end" alignItems="center">
                  {i.actions}
                  <Link component={RouterLink} to={i.to} aria-label={`Open ${i.reference}`}>
                    Open
                  </Link>
                </Stack>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}

function QueueCards({ items }: { items: Item[] }) {
  return (
    <Stack component="ul" spacing={1.5} sx={{ listStyle: "none", m: 0, p: 0 }}>
      {items.map((i) => (
        <Paper component="li" key={i.key} sx={{ p: 2 }}>
          <Stack direction="row" justifyContent="space-between" alignItems="flex-start" spacing={1}>
            <Typography sx={{ fontWeight: 700 }}>{i.reference}</Typography>
            {i.status}
          </Stack>
          {i.patient && <Typography>{i.patient}</Typography>}
          <Typography variant="body2" component="div" sx={{ mt: 0.5 }}>
            {i.todo}
          </Typography>
          <Stack direction="row" spacing={2} alignItems="center" sx={{ mt: 1.5 }}>
            <Link component={RouterLink} to={i.to} aria-label={`Open ${i.reference}`}>
              Open
            </Link>
            {i.actions}
          </Stack>
        </Paper>
      ))}
    </Stack>
  );
}

function Group({ title, items, todoHeading, wide }: { title: string; items: Item[]; todoHeading: string; wide: boolean }) {
  if (items.length === 0) return null;
  const heading = `${title} (${items.length})`;
  if (!wide)
    return (
      <Box component="section" aria-label={heading}>
        <Typography variant="h6" component="h2" sx={{ mb: 1 }}>
          {heading}
        </Typography>
        <QueueCards items={items} />
      </Box>
    );
  return (
    <Section title={heading}>
      <QueueTable items={items} todoHeading={todoHeading} />
    </Section>
  );
}

export function WorkQueue() {
  const { data: me } = useMe();
  const qc = useQueryClient();
  const theme = useTheme();
  const wide = useMediaQuery(theme.breakpoints.up("md"), { noSsr: true });
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
  const clinic = me?.institution_kind === "clinic";
  const total = actionableCount(q.data);
  const { now, waiting, drafts } = buildItems(q.data!, me, setAnswering);
  const listed = now.length + waiting.length + drafts.length;
  const where = me?.institution_name;
  const subtitle =
    total > 0
      ? `${total} ${total === 1 ? "item needs" : "items need"} you, overdue first.`
      : listed > 0
        ? `Nothing needs action at ${where}. The items below are in progress or waiting on others.`
        : `Nothing needs action at ${where}.`;

  return (
    <>
      <PageHeader
        title="Work queue"
        subtitle={subtitle}
        actions={
          clinic && (
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
              <Button variant="contained" component={RouterLink} to="/referrals/new">
                New referral
              </Button>
              <Button variant="outlined" component={RouterLink} to="/referrals">
                View all referrals
              </Button>
            </Stack>
          )
        }
      />
      <ErrorAlert error={answer.error} />
      <Stack spacing={2.5}>
        <Group title="Needs your action now" items={now} todoHeading="What to do" wide={wide} />
        <Group title="Waiting on others" items={waiting} todoHeading="Waiting for" wide={wide} />
        <Group title="Drafts in progress" items={drafts} todoHeading="Next" wide={wide} />
        {listed === 0 && (
          <Section title="All clear">
            <Typography color="text.secondary">There is nothing in your queue. New requests and tasks will appear here.</Typography>
          </Section>
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
