import type { ReferralDetail } from "../../api/types";

/**
 * The referral workflow as an ordered journey (SRS section 4).
 * Step keys are also the values of the ?tab= query parameter, so existing deep links keep working.
 */
export type StepKey = "overview" | "sources" | "documents" | "medications" | "review" | "brief" | "followthrough" | "audit";
export type StepState = "done" | "attention" | "todo" | "waiting" | "optional" | "later" | "ended";

export const PHASES: { title: string; steps: [StepKey, string][] }[] = [
  {
    title: "Prepare",
    steps: [
      ["overview", "Overview"],
      ["sources", "Sources & evidence"],
      ["documents", "Documents"],
    ],
  },
  {
    title: "Verify",
    steps: [
      ["medications", "Medications & flags"],
      ["review", "Checklist & clarifications"],
    ],
  },
  { title: "Approve and send", steps: [["brief", "Brief & approval"]] },
  { title: "Follow through", steps: [["followthrough", "Specialist & follow-up"]] },
];

export const AUDIT_STEP: [StepKey, string] = ["audit", "Audit trail"];
export const STEP_ORDER: StepKey[] = [...PHASES.flatMap((p) => p.steps.map((s) => s[0])), "audit"];
export const STEP_LABEL: Record<StepKey, string> = Object.fromEntries([...PHASES.flatMap((p) => p.steps), AUDIT_STEP]) as Record<StepKey, string>;

export const STATE_LABEL: Record<StepState, string> = {
  done: "Complete",
  attention: "Needs attention",
  todo: "To do",
  waiting: "Waiting",
  optional: "Optional",
  later: "Not yet",
  ended: "Ended",
};

export type StepStatus = { state: StepState; note: string };

const AFTER_SEND = ["submitted", "acknowledged", "accepted", "response_returned", "followup_pending", "closed"];
const ENDED = ["declined", "cancelled"];
const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

/** Works out each step's state from the data already loaded for the referral. No extra requests. */
export function computeSteps(r: ReferralDetail): Record<StepKey, StepStatus> {
  const blockers = r.approval_blockers;
  const medBlockers = blockers.filter((b) => ["medication_evaluation", "medication_evaluation_failed", "flag_review"].includes(b.type));
  const reviewBlockers = blockers.filter((b) => b.type === "review_item");
  const noBrief = blockers.some((b) => b.type === "brief");

  if (ENDED.includes(r.status)) {
    const ended: StepStatus = { state: "ended", note: r.status === "declined" ? "Declined" : "Cancelled" };
    return { overview: ended, sources: ended, documents: ended, medications: ended, review: ended, brief: ended, followthrough: ended, audit: { state: "optional", note: "" } };
  }

  // Overview
  const missing: string[] = [];
  if (!r.reason.trim()) missing.push("Add a reason");
  if (!r.referring_clinician_id) missing.push("Assign a clinician");
  if (r.procedure_status === "not_stated") missing.push("Procedure not stated");
  const overview: StepStatus = missing.length ? { state: "attention", note: missing[0] } : { state: "done", note: "Details saved" };

  // Sources
  const linked = r.sources.filter((s) => s.linked);
  const retrieved = linked.filter((s) => s.latest);
  const problems = retrieved.filter((s) => !["successful", "empty"].includes(s.latest!.status));
  let sources: StepStatus;
  if (linked.length === 0) sources = { state: "todo", note: "No linked sources" };
  else if (retrieved.length === 0) sources = { state: "todo", note: "Retrieve records" };
  else if (problems.length) sources = { state: "attention", note: `${plural(problems.length, "source", "sources")} incomplete` };
  else if (retrieved.length < linked.length) sources = { state: "todo", note: "Some not retrieved" };
  else sources = { state: "done", note: `${retrieved.length} of ${r.sources.length} sources` };

  // Medications
  let medications: StepStatus;
  if (medBlockers.length === 0) medications = { state: "done", note: "Flags reviewed" };
  else if (medBlockers.some((b) => b.type === "medication_evaluation_failed")) medications = { state: "attention", note: "Evaluation failed" };
  else if (medBlockers.some((b) => b.type === "medication_evaluation")) medications = { state: "attention", note: "Run evaluation" };
  else medications = { state: "attention", note: `${plural(medBlockers.length, "flag", "flags")} to review` };

  // Checklist
  const review: StepStatus = reviewBlockers.length ? { state: "attention", note: `${plural(reviewBlockers.length, "open item", "open items")}` } : { state: "done", note: "Nothing blocking" };

  // Brief and approval
  let brief: StepStatus;
  if (r.amendment_open) brief = { state: "attention", note: "New version to approve" };
  else if (r.status === "awaiting_approval") brief = { state: "attention", note: "Ready for approval" };
  else if (r.status === "approved") brief = { state: "attention", note: r.delivery_status === "failed" ? "Sending failed" : "Ready to send" };
  else if (AFTER_SEND.includes(r.status)) brief = { state: "done", note: `Version ${r.submitted_package_version ?? r.current_package_version ?? ""}`.trim() };
  else if (noBrief) brief = { state: "todo", note: "No brief yet" };
  else brief = { state: "todo", note: "Review the brief" };

  // Specialist and follow-up
  let followthrough: StepStatus;
  switch (r.status) {
    case "submitted":
      followthrough = { state: "waiting", note: "Awaiting acknowledgment" };
      break;
    case "acknowledged":
      followthrough = { state: "waiting", note: "Awaiting decision" };
      break;
    case "accepted":
      followthrough = { state: "waiting", note: "Awaiting response" };
      break;
    case "response_returned":
      followthrough = { state: "attention", note: "Review response" };
      break;
    case "followup_pending":
      followthrough = { state: "attention", note: "Tasks open" };
      break;
    case "closed":
      followthrough = { state: "done", note: "Closed" };
      break;
    default:
      followthrough = { state: "later", note: "After sending" };
  }

  return { overview, sources, documents: { state: "optional", note: "Paper records" }, medications, review, brief, followthrough, audit: { state: "optional", note: "" } };
}

export type NextStep = { heading: string; body: string; tab?: StepKey; action?: string; tone: "info" | "warn" | "ok" };

const PREPARE_COPY: Partial<Record<StepKey, { heading: string; body: string }>> = {
  overview: { heading: "Complete the referral details", body: "Add the reason for referral, assign a referring clinician and state the planned procedure, or record that it is unknown." },
  sources: { heading: "Retrieve records from the connected systems", body: "Pull permitted records from the clinic, laboratory and specialist systems so the brief rests on source data. Any source that denies access or is unavailable is shown explicitly." },
  medications: { heading: "Confirm current medications and review the flags", body: "A clinician confirms which medications are current. Each matching flag then needs a Reviewed or Request clarification decision before approval." },
  review: { heading: "Resolve missing or conflicting information", body: "Open items block approval until they are answered, or a clinician records an override with a reason." },
  brief: { heading: "Prepare the referral brief", body: "Start from the evidence template, generate a draft, or write it by hand. Every statement taken from a record needs a source reference." },
};

/** The single most useful thing to do next, written for the person looking at the referral. */
export function nextStep(r: ReferralDetail, isClinician: boolean): NextStep {
  const steps = computeSteps(r);

  if (r.status === "closed") return { heading: "This referral is closed", body: "Every step is finished. The full history stays available in the audit trail.", tab: "audit", action: "Open Audit trail", tone: "ok" };
  if (ENDED.includes(r.status)) {
    const reason = r.status === "declined" ? r.decline_reason : r.cancel_reason;
    return { heading: r.status === "declined" ? "The specialist declined this referral" : "This referral was cancelled", body: reason ? `Reason recorded: ${reason}` : "No reason was recorded.", tab: "audit", action: "Open Audit trail", tone: "warn" };
  }
  if (r.amendment_open) {
    return {
      heading: "A new version needs approval",
      body: "The clinical content has been edited since the last version was sent. That version stays unchanged until the new one is approved and delivered.",
      tab: "brief",
      action: isClinician ? "Go to Brief & approval" : undefined,
      tone: "warn",
    };
  }

  switch (r.status) {
    case "awaiting_approval":
      return isClinician
        ? { heading: "Review and approve the brief", body: "Approve the exact version that will be sent. Any later change to clinical content creates a new version that needs approval again.", tab: "brief", action: "Go to Brief & approval", tone: "info" }
        : { heading: "Waiting for a clinician to approve", body: "A referring clinician must approve the brief before it can be sent. You can still add records or answer clarification requests.", tone: "info" };
    case "approved":
      return r.delivery_status === "failed"
        ? { heading: "Sending failed", body: "The approved version is kept. Retry the delivery. A retry never creates a duplicate referral.", tab: "brief", action: "Go to Brief & approval", tone: "warn" }
        : { heading: "Send the approved version to the specialist", body: "The approved version is ready. Delivery and the specialist's acknowledgment are recorded separately.", tab: "brief", action: "Go to Brief & approval", tone: "info" };
    case "submitted":
      return { heading: "Waiting for the specialist to acknowledge", body: "The package has been delivered. This page refreshes on its own when the specialist acts.", tab: "followthrough", action: "View delivery status", tone: "info" };
    case "acknowledged":
      return { heading: "Waiting for the specialist's decision", body: "The specialist has acknowledged receipt and will accept, decline or ask for clarification.", tab: "followthrough", action: "View progress", tone: "info" };
    case "accepted":
      return { heading: "Waiting for the consultation response", body: "The specialist has accepted the referral. The approved response will appear here when it is returned.", tab: "followthrough", action: "View progress", tone: "info" };
    case "response_returned":
      return isClinician
        ? { heading: "Review the specialist's response", body: "Record that you have reviewed it, then add any follow-up tasks.", tab: "followthrough", action: "Go to Specialist & follow-up", tone: "warn" }
        : { heading: "A response is ready for clinician review", body: "A referring clinician must record that they have reviewed it. You can then record the follow-up tasks they specify.", tab: "followthrough", action: "View response", tone: "warn" };
    case "followup_pending":
      return { heading: "Finish the follow-up tasks", body: "Record each task's outcome or the reason it was not completed. The referral can be closed once every task has a disposition.", tab: "followthrough", action: "Go to Specialist & follow-up", tone: "warn" };
  }

  // Draft and awaiting information: guide the user to the first unfinished preparation step.
  for (const key of ["overview", "sources", "medications", "review", "brief"] as StepKey[]) {
    const s = steps[key];
    // A brief that already exists is not a prompt to write one; the next move is to request approval.
    if (key === "brief" && !r.approval_blockers.some((b) => b.type === "brief")) continue;
    if (s.state === "attention" || s.state === "todo") {
      const copy = PREPARE_COPY[key]!;
      return { heading: copy.heading, body: copy.body, tab: key, action: `Go to ${STEP_LABEL[key]}`, tone: "info" };
    }
  }
  return {
    heading: "Ready to request clinician approval",
    body: "Every check the system can make has passed. Send the referral for clinician approval from the Overview.",
    tab: "overview",
    action: "Go to Overview",
    tone: "ok",
  };
}
