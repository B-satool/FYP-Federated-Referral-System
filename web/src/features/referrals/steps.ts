import type { ReferralDetail } from "../../api/types";

/**
 * The referral as a journey. Doctors and staff see different steps: the doctor requests the
 * referral and acknowledges flags; staff link the patient, gather records and send it.
 * Step keys are also the ?tab= values, so links from notifications open the right step.
 */
export type StepKey = "request" | "links" | "records" | "papers" | "medicines" | "tests" | "send" | "summary" | "response" | "audit";
export type StepState = "done" | "attention" | "todo" | "waiting" | "optional" | "later" | "ended";
export type Role = "doctor" | "staff";

export const STEP_LABEL: Record<StepKey, string> = {
  request: "Request",
  links: "Patient links",
  records: "Records",
  papers: "Papers",
  medicines: "Medicines & flags",
  tests: "Tests & scans",
  send: "Check & send",
  summary: "Summary",
  response: "Response & follow-up",
  audit: "History",
};

export const STATE_LABEL: Record<StepState, string> = {
  done: "Done",
  attention: "Needs attention",
  todo: "To do",
  waiting: "Waiting",
  optional: "Optional",
  later: "Later",
  ended: "Ended",
};

export type Phase = { title: string; steps: StepKey[] };

export function layout(role: Role): Phase[] {
  return role === "doctor"
    ? [
        { title: "Request", steps: ["request"] },
        { title: "Check", steps: ["medicines", "tests", "summary"] },
        { title: "Follow through", steps: ["response"] },
      ]
    : [
        { title: "Request", steps: ["request"] },
        { title: "Prepare", steps: ["links", "records", "papers", "medicines", "tests"] },
        { title: "Send", steps: ["send"] },
        { title: "Follow through", steps: ["response"] },
      ];
}

export function stepOrder(role: Role): StepKey[] {
  return [...layout(role).flatMap((p) => p.steps), "audit"];
}

export type StepStatus = { state: StepState; note: string };

const SENT = ["submitted", "acknowledged", "accepted", "response_returned", "followup_pending", "closed"];
const ENDED = ["declined", "cancelled"];
const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

function item(r: ReferralDetail, key: string) {
  return r.readiness?.find((i) => i.key === key);
}

/** Each step's state from the data already loaded for the referral (no extra requests). */
export function computeSteps(r: ReferralDetail, role: Role): Record<StepKey, StepStatus> {
  const sent = SENT.includes(r.status);
  const ended = ENDED.includes(r.status);
  const out = {} as Record<StepKey, StepStatus>;
  const dest = r.destination_name;

  out.request = r.status === "draft"
    ? { state: "attention", note: "Not submitted yet" }
    : { state: "done", note: `By ${r.requesting_doctor_name}` };

  const link = item(r, "destination_link");
  const destLinked = r.sources.some((s) => s.destination && s.linked);
  out.links = destLinked || sent ? { state: "done", note: `Confirmed by ${dest}` }
    : link?.detail.startsWith("Waiting") ? { state: "waiting", note: `Waiting for ${dest}` }
    : { state: "todo", note: "Request a link" };

  const retrieved = r.sources.filter((s) => s.latest);
  const problems = retrieved.filter((s) => ["unavailable", "denied", "invalid", "partial"].includes(s.latest!.status));
  out.records = retrieved.length === 0 ? { state: "todo", note: "Retrieve records" }
    : problems.length ? { state: "attention", note: `${plural(problems.length, "source", "sources")} incomplete` }
    : { state: "done", note: `${retrieved.filter((s) => s.latest!.status === "successful").length} used` };

  const docs = item(r, "documents");
  out.papers = docs && !docs.ok ? { state: "attention", note: docs.detail } : { state: "optional", note: "From the patient" };

  const checked = item(r, "meds_checked");
  const doses = item(r, "dose_differences");
  const flags = item(r, "flags");
  if (role === "doctor") {
    out.medicines = flags && !flags.ok ? { state: "attention", note: flags.detail.replace(/ waiting for .*/, " to acknowledge") }
      : { state: "done", note: "Flags acknowledged" };
  } else if (doses && !doses.ok) {
    out.medicines = { state: "attention", note: "Different doses" };
  } else if (checked && !checked.ok) {
    out.medicines = { state: "todo", note: "Ask the patient" };
  } else if (flags && !flags.ok) {
    out.medicines = { state: "waiting", note: "Doctor to acknowledge" };
  } else {
    out.medicines = { state: "done", note: "Checked" };
  }

  const dx = r.diagnostics.filter((d) => d.status !== "cancelled");
  const unsent = dx.filter((d) => d.status === "draft");
  const results = dx.filter((d) => d.status === "reported");
  const unseen = results.filter((d) => !d.seen_at);
  const rejected = dx.filter((d) => d.status === "rejected");
  out.tests = dx.length === 0 ? { state: "optional", note: "None requested" }
    : rejected.length ? { state: "attention", note: `${plural(rejected.length, "rejected", "rejected")}` }
    : role === "staff" && unsent.length ? { state: "todo", note: `${plural(unsent.length, "to send", "to send")}` }
    : role === "doctor" && unseen.length ? { state: "attention", note: `${plural(unseen.length, "result", "results")} ready` }
    : results.length === dx.length ? { state: "done", note: "Results back" }
    : { state: "waiting", note: `${results.length} of ${dx.length} back` };

  const todo = (r.readiness ?? []).filter((i) => i.blocking && !i.ok);
  out.send = r.amendment_open ? { state: "attention", note: "Send the new version" }
    : sent ? { state: "done", note: `Sent v${r.submitted_package_version ?? r.current_package_version}` }
    : r.status === "draft" ? { state: "later", note: "After the request" }
    : todo.length ? { state: "todo", note: `${plural(todo.length, "check", "checks")} left` }
    : { state: "attention", note: "Ready to send" };
  out.summary = sent ? { state: "done", note: `Sent v${r.submitted_package_version ?? r.current_package_version}` }
    : { state: "optional", note: "What will be sent" };

  const openInfo = r.clarifications.filter((c) => c.status === "open").length;
  const respMap: Record<string, StepStatus> = {
    submitted: { state: "waiting", note: "Not acknowledged yet" },
    acknowledged: { state: "waiting", note: "Awaiting decision" },
    accepted: { state: "waiting", note: "Awaiting response" },
    response_returned: { state: "attention", note: role === "doctor" ? "Review the response" : "Response received" },
    followup_pending: { state: "attention", note: "Follow-up" },
    closed: { state: "done", note: "Closed" },
  };
  out.response = openInfo ? { state: "attention", note: `${plural(openInfo, "question", "questions")} to answer` }
    : respMap[r.status] ?? { state: "later", note: "After sending" };
  out.audit = { state: "optional", note: "" };

  if (ended) {
    const note = r.status === "declined" ? "Declined" : "Cancelled";
    for (const k of Object.keys(out) as StepKey[]) if (k !== "audit") out[k] = { state: "ended", note };
  }
  return out;
}

export type NextStep = { heading: string; body: string; tab?: StepKey; action?: string; tone: "info" | "warn" | "ok" };

/** The single most useful thing to do next, written for the person looking at the referral. */
export function nextStep(r: ReferralDetail, role: Role): NextStep {
  if (r.status === "closed") return { heading: "This referral is closed", body: "Every step is finished. The full history stays available.", tab: "audit", action: "Open history", tone: "ok" };
  if (r.status === "declined") return { heading: `${r.destination_name} declined this referral`, body: r.decline_reason ? `Reason: ${r.decline_reason}` : "No reason was given.", tone: "warn" };
  if (r.status === "cancelled") return { heading: "This referral was cancelled", body: r.cancel_reason ? `Reason: ${r.cancel_reason}` : "", tone: "warn" };
  const openInfo = r.clarifications.filter((c) => c.status === "open");
  if (openInfo.length) return { heading: `${r.destination_name} asks for more information`, body: openInfo[0].question, tab: "response", action: "Answer", tone: "warn" };

  if (role === "doctor") {
    if (r.status === "draft") return { heading: "Submit the request", body: "Check the form, then submit it. Staff then link the patient, gather the records and send the referral.", tab: "request", action: "Open the request", tone: "info" };
    const flags = item(r, "flags");
    if (flags && !flags.ok) return { heading: "Acknowledge the medication flags", body: "The medicines were checked against the planned procedure. Acknowledge each flag for this patient; staff cannot send until you do.", tab: "medicines", action: "Go to Medicines & flags", tone: "warn" };
    const unseen = r.diagnostics.filter((d) => d.status === "reported" && !d.seen_at);
    if (unseen.length) return { heading: "A test result is ready", body: `${unseen[0].test} from ${unseen[0].destination_name}.`, tab: "tests", action: "See the result", tone: "warn" };
    if (r.status === "response_returned") return { heading: "Review the specialist's response", body: "Record that you have seen the outcome. Staff then inform the patient and follow up.", tab: "response", action: "Go to the response", tone: "warn" };
    if (r.status === "requested") return { heading: "Staff are preparing this referral", body: "They are linking the patient, gathering records and checking medicines. You will be told if anything needs you.", tab: "summary", action: "See what will be sent", tone: "info" };
  } else {
    if (r.amendment_open) return { heading: "Send the new version", body: "Something changed after the referral was sent. Check it and send the new version; the earlier version stays unchanged.", tab: "send", action: "Go to Check & send", tone: "warn" };
    if (r.delivery_status === "failed") return { heading: "Sending failed", body: "Retry the delivery. A retry never creates a duplicate.", tab: "send", action: "Go to Check & send", tone: "warn" };
    if (r.status === "requested") {
      const todo = (r.readiness ?? []).find((i) => i.blocking && !i.ok);
      if (!todo) return { heading: "Ready to send", body: "Every check is done. Review the summary and send the referral.", tab: "send", action: "Go to Check & send", tone: "ok" };
      const tab = (todo.tab === "request" ? "request" : todo.tab ?? "send") as StepKey;
      return { heading: todo.label, body: todo.detail || (todo.who === "doctor" ? "This needs the doctor." : ""), tab, action: `Go to ${STEP_LABEL[tab]}`, tone: todo.who === "doctor" ? "info" : "warn" };
    }
    const unsent = r.diagnostics.filter((d) => d.status === "draft");
    if (unsent.length) return { heading: "Send the test and scan requests", body: `${unsent.length} request(s) not sent yet. They are separate orders and do not wait for the specialist.`, tab: "tests", action: "Go to Tests & scans", tone: "info" };
    if (["response_returned", "followup_pending"].includes(r.status)) {
      if (!r.patient_informed_at) return { heading: "Tell the patient the outcome", body: "Inform the patient of the specialist's response and the next steps, then record it.", tab: "response", action: "Go to follow-up", tone: "warn" };
      return { heading: "Finish the follow-up", body: "Record task outcomes, then close the referral once the doctor has reviewed the response.", tab: "response", action: "Go to follow-up", tone: "info" };
    }
  }
  const waiting: Record<string, string> = {
    submitted: `Delivered to ${r.destination_name}. Waiting for them to acknowledge.`,
    acknowledged: `${r.destination_name} acknowledged it and will accept, decline or ask for information.`,
    accepted: `${r.destination_name} accepted the referral. Their response will appear here.`,
  };
  return { heading: "Waiting for the receiving hospital", body: waiting[r.status] ?? "", tab: "response", action: "View progress", tone: "info" };
}
