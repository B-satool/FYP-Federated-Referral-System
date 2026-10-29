import type { ReferralDetail, RequestKind } from "../../api/types";

/**
 * A request as a journey. Doctors and staff see different steps.
 * Referral: the doctor requests it; staff retrieve the records and upload papers and mark it ready; the doctor
 * reviews the clinical content (records, papers, medicines, flags) and marks the packet reviewed; staff send it;
 * the receiving doctor accepts or declines. Staff never see clinical content (decision 2026-10-29).
 * Test request: the doctor lists the tests; staff send the orders; the results come back.
 * Step keys are also the ?tab= values, so links from notifications open the right step.
 */
export type StepKey = "request" | "records" | "papers" | "medicines" | "tests" | "send" | "summary" | "response" | "audit";
export type StepState = "done" | "attention" | "todo" | "waiting" | "optional" | "later" | "ended";
export type Role = "doctor" | "staff";

export const STEP_LABEL: Record<StepKey, string> = {
  request: "Request",
  records: "Consent & records",
  papers: "Papers",
  medicines: "Medicines & flags",
  tests: "Tests & results",
  send: "Check & send",
  summary: "Approve & sign",
  response: "Outcome & follow-up",
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

export function layout(role: Role, kind: RequestKind = "referral"): Phase[] {
  if (kind === "test") {
    return [
      { title: "Request", steps: ["request"] },
      { title: role === "doctor" ? "Results" : "Send and follow", steps: ["tests"] },
    ];
  }
  // Spec v4: the doctor reviews the decrypted records, enters the medicines, adds papers and signs the package;
  // staff handle consent, the records requests and sending, and see titles only (D14).
  return role === "doctor"
    ? [
        { title: "Request", steps: ["request"] },
        { title: "Review", steps: ["records", "medicines", "papers", "summary"] },
        { title: "Follow through", steps: ["response"] },
      ]
    : [
        { title: "Request", steps: ["request"] },
        { title: "Consent and records", steps: ["records"] },
        { title: "Send", steps: ["send"] },
        { title: "Follow through", steps: ["response"] },
      ];
}

export function stepOrder(role: Role, kind: RequestKind = "referral"): StepKey[] {
  return [...layout(role, kind).flatMap((p) => p.steps), "audit"];
}

export type StepStatus = { state: StepState; note: string };

const SENT = ["submitted", "acknowledged", "accepted", "response_returned", "followup_pending", "closed"];
const ENDED = ["declined", "cancelled"];
const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

function item(r: ReferralDetail, key: string) {
  return r.readiness?.find((i) => i.key === key);
}

function testSteps(r: ReferralDetail, role: Role, out: Record<StepKey, StepStatus>) {
  const dx = r.diagnostics.filter((d) => d.status !== "cancelled");
  const unsent = dx.filter((d) => d.status === "draft");
  const results = dx.filter((d) => d.status === "reported");
  const unseen = results.filter((d) => !d.seen_at);
  const rejected = dx.filter((d) => d.status === "rejected");
  out.tests = r.status === "closed" ? { state: "done", note: "Closed" }
    : rejected.length ? { state: "attention", note: `${rejected.length} not accepted` }
    : role === "staff" && unsent.length ? { state: "todo", note: `${plural(unsent.length, "order", "orders")} to send` }
    : role === "doctor" && unseen.length ? { state: "attention", note: `${plural(unseen.length, "result", "results")} ready` }
    : role === "staff" && r.status === "response_returned" && !r.patient_informed_at ? { state: "attention", note: "Tell the patient" }
    : dx.length && results.length === dx.length ? { state: "done", note: "Results back" }
    : { state: "waiting", note: `${results.length} of ${dx.length} back` };
}

/** Each step's state from the data already loaded for the request (no extra requests). */
export function computeSteps(r: ReferralDetail, role: Role): Record<StepKey, StepStatus> {
  const sent = SENT.includes(r.status);
  const ended = ENDED.includes(r.status);
  const out = {} as Record<StepKey, StepStatus>;

  out.request = r.status === "draft"
    ? { state: "attention", note: "Not submitted yet" }
    : { state: "done", note: `By ${r.requesting_doctor_name}` };

  if (r.kind === "test") {
    testSteps(r, role, out);
  } else {
    const consent = r.consent?.status;
    const reqs = r.record_requests;
    const problems = reqs.filter((x) => ["refused", "partial", "unavailable", "failed", "not_linked"].includes(x.status));
    const waiting = reqs.filter((x) => x.status === "pending_manual_review");
    out.records = sent ? { state: "done", note: `${r.encrypted_item_count} received` }
      : !consent || ["declined", "revoked", "expired"].includes(consent)
        ? { state: role === "staff" ? "todo" : "waiting", note: consent ? `Consent ${consent}` : "Ask the patient for consent" }
      : consent === "requested" ? { state: "waiting", note: "Waiting for the patient" }
      : !reqs.length ? { state: "todo", note: "Request the records" }
      : problems.length ? { state: "attention", note: `${plural(problems.length, "institution", "institutions")} did not send everything` }
      : waiting.length ? { state: "waiting", note: `${waiting.length} waiting for review there` }
      : { state: role === "doctor" ? "attention" : "done", note: `${r.encrypted_item_count} received${role === "doctor" ? ": review them" : ""}` };

    const docs = item(r, role === "doctor" ? "documents" : "documents_read");
    out.papers = docs && !docs.ok && (role !== "doctor" || r.prepared_at)
      ? { state: "attention", note: docs.detail } : { state: "optional", note: "From the patient" };

    const checked = item(r, "meds_checked");
    const doses = item(r, "dose_differences");
    const flags = item(r, "flags");
    const medsDone = [checked, doses, flags].every((i) => !i || i.ok);
    if (role === "doctor") {
      out.medicines = !r.prepared_at && !sent ? { state: "later", note: "After staff retrieve the records" }
        : checked && !checked.ok ? { state: "todo", note: "Confirm with the patient" }
        : doses && !doses.ok ? { state: "attention", note: "Different doses" }
        : flags && !flags.ok ? { state: "attention", note: flags.detail.replace(/ waiting for .*/, " to review") }
        : { state: "done", note: "Checked" };
    } else {
      out.medicines = sent || medsDone ? { state: "done", note: "Checked by the doctor" }
        : r.prepared_at ? { state: "waiting", note: "Doctor is checking" } : { state: "later", note: "The doctor checks them" };
    }

    const todo = (r.readiness ?? []).filter((i) => i.blocking && !i.ok);
    out.send = r.amendment_open ? { state: "attention", note: "Send the new version" }
      : sent ? { state: "done", note: `Sent v${r.submitted_package_version ?? r.current_package_version}` }
      : r.status === "draft" ? { state: "later", note: "After the request" }
      : !r.prepared_at ? { state: "todo", note: "Mark ready for the doctor" }
      : todo.length ? { state: "waiting", note: "Doctor reviewing the packet" }
      : { state: "attention", note: "Ready to send" };
    out.summary = sent ? { state: "done", note: `Sent v${r.submitted_package_version ?? r.current_package_version}` }
      : { state: "optional", note: "What will be sent" };

    const openInfo = r.clarifications.filter((c) => c.status === "open").length;
    const respMap: Record<string, StepStatus> = {
      submitted: { state: "waiting", note: "Not acknowledged yet" },
      acknowledged: { state: "waiting", note: "Awaiting decision" },
      accepted: { state: "attention", note: r.patient_informed_at ? "Close the referral" : "Accepted: tell the patient" },
      response_returned: { state: "attention", note: role === "doctor" ? "Review the response" : "Response received" },
      followup_pending: { state: "attention", note: "Follow-up" },
      closed: { state: "done", note: "Closed" },
    };
    out.response = openInfo ? { state: "attention", note: `${plural(openInfo, "question", "questions")} to answer` }
      : respMap[r.status] ?? { state: "later", note: "After sending" };
  }
  out.audit = { state: "optional", note: "" };

  if (ended) {
    const note = r.status === "declined" ? "Declined" : "Withdrawn";
    for (const k of Object.keys(out) as StepKey[]) if (k !== "audit") out[k] = { state: "ended", note };
  }
  return out;
}

export type NextStep = { heading: string; body: string; tab?: StepKey; action?: string; tone: "info" | "warn" | "ok" };

function nextForTest(r: ReferralDetail, role: Role): NextStep {
  const dx = r.diagnostics.filter((d) => d.status !== "cancelled");
  const unseen = dx.filter((d) => d.status === "reported" && !d.seen_at);
  const unsent = dx.filter((d) => d.status === "draft");
  const rejected = dx.filter((d) => d.status === "rejected");
  if (role === "doctor") {
    if (r.status === "draft") return { heading: "Submit the request", body: "Check the tests, then submit. Staff send the orders.", tab: "request", action: "Open the request", tone: "info" };
    if (rejected.length) return { heading: `${rejected[0].test} was not accepted`, body: rejected[0].reject_reason ?? "", tab: "tests", action: "See the tests", tone: "warn" };
    if (unseen.length) return { heading: "A result is ready", body: `${unseen[0].test} from ${unseen[0].destination_name}.`, tab: "tests", action: "See the result", tone: "warn" };
    if (unsent.length) return { heading: "Staff are sending the orders", body: "You will be told when results come back.", tab: "tests", action: "See the tests", tone: "info" };
    return { heading: dx.every((d) => d.status === "reported") ? "All results received" : "Waiting for results", body: "Each test shows its own progress.", tab: "tests", action: "See the tests", tone: "info" };
  }
  if (unsent.length) return { heading: "Check and send the orders", body: `${plural(unsent.length, "test", "tests")} to send. The department confirms the patient when the order arrives.`, tab: "tests", action: "Go to Tests & results", tone: "warn" };
  if (r.status === "response_returned" && !r.patient_informed_at) return { heading: "Tell the patient the results", body: "Once the doctor has seen them, tell the patient, record it and close the request.", tab: "tests", action: "Go to Tests & results", tone: "warn" };
  return { heading: "Waiting for results", body: "Each test shows its own progress.", tab: "tests", action: "See the tests", tone: "info" };
}

/** The single most useful thing to do next, written for the person looking at the request. */
export function nextStep(r: ReferralDetail, role: Role): NextStep {
  if (r.status === "closed") return { heading: "This request is closed", body: "Every step is finished. The full history stays available.", tab: "audit", action: "Open history", tone: "ok" };
  if (r.status === "declined") return { heading: `${r.destination_name} declined this referral`, body: r.decline_reason ? `Reason: ${r.decline_reason}` : "No reason was given.", tone: "warn" };
  if (r.status === "cancelled") return { heading: "This request was withdrawn", body: r.cancel_reason ? `Reason: ${r.cancel_reason}` : "", tone: "warn" };
  if (r.kind === "test") return nextForTest(r, role);
  const openInfo = r.clarifications.filter((c) => c.status === "open");
  if (openInfo.length) return role === "doctor"
    ? { heading: `${r.destination_name} asks for more information`, body: openInfo[0].question, tab: "response", action: "Answer", tone: "warn" }
    : { heading: `${r.destination_name} asks for more information`, body: "The doctor has been asked to answer.", tab: "response", action: "View progress", tone: "info" };

  if (role === "doctor") {
    if (r.status === "draft") return { heading: "Submit the request", body: "Check the form, then submit it. Staff then gather the records and medicines.", tab: "request", action: "Open the request", tone: "info" };
    if (r.status === "requested" && !r.prepared_at) return { heading: "In progress: staff are retrieving the records", body: "They retrieve the records and upload the patient's papers. You are then asked to review everything that goes in the packet.", tab: "records", action: "See the records so far", tone: "info" };
    if (r.status === "requested" || r.amendment_open) {
      const order = ["documents", "meds_checked", "dose_differences", "flags"];
      const todo = order.map((k) => item(r, k)).find((i) => i && !i.ok);
      if (todo) {
        const tab = (todo.tab ?? "medicines") as StepKey;
        return { heading: todo.label, body: todo.detail || "Only you see the clinical content; staff send once you have reviewed the packet.", tab, action: `Go to ${STEP_LABEL[tab]}`, tone: "warn" };
      }
      if (!r.packet_reviewed_at) return { heading: "Review the packet", body: "Check the records chosen for the packet and the letter, then mark the packet reviewed. Staff then send it.", tab: "summary", action: "Go to the letter", tone: "warn" };
    }
    if (r.status === "response_returned") return { heading: "Review the specialist's response", body: "Record that you have seen the outcome. Staff then inform the patient and follow up.", tab: "response", action: "Go to the response", tone: "warn" };
    if (["accepted", "followup_pending"].includes(r.status)) {
      if (!r.patient_informed_at) return { heading: `${r.destination_name} accepted the referral`, body: "Staff tell the patient and record it. Then you or staff can close the referral.", tab: "response", action: "Go to follow-up", tone: "info" };
      return { heading: "Close the referral", body: "The patient has been told. Close the referral once any follow-up tasks have an outcome.", tab: "response", action: "Go to follow-up", tone: "warn" };
    }
    if (r.status === "requested") return { heading: "Packet reviewed: staff will send it", body: "Staff send the referral with the patient's details; the receiving side confirms the patient when it arrives.", tab: "summary", action: "See the letter", tone: "ok" };
  } else {
    if (r.amendment_open) return { heading: "Send the new version", body: "Something changed after the referral was sent. Check it and send the new version; the earlier version stays unchanged.", tab: "send", action: "Go to Check & send", tone: "warn" };
    if (r.delivery_status === "failed") return { heading: "Sending failed", body: "Retry the delivery. A retry never creates a duplicate.", tab: "send", action: "Go to Check & send", tone: "warn" };
    if (r.status === "requested") {
      const todo = (r.readiness ?? []).find((i) => i.blocking && !i.ok);
      if (!todo) return { heading: "Ready to send", body: "The doctor has reviewed the packet. Send it.", tab: "send", action: "Go to Check & send", tone: "ok" };
      if (todo.key === "prepared") return { heading: "Mark it ready for the doctor", body: "The records are retrieved and the papers uploaded. Mark it ready so the doctor can review the packet.", tab: "send", action: "Go to Check & send", tone: "warn" };
      if (todo.who !== "staff") return { heading: "Waiting for the doctor", body: "The doctor checks the papers, medicines, flags and records, then marks the packet reviewed. You will be told when it is ready to send.", tab: "send", action: "See progress", tone: "info" };
      const tab = (todo.tab === "request" ? "request" : todo.tab ?? "send") as StepKey;
      return { heading: todo.label, body: todo.detail, tab, action: `Go to ${STEP_LABEL[tab]}`, tone: "warn" };
    }
    if (["accepted", "response_returned", "followup_pending"].includes(r.status)) {
      if (!r.patient_informed_at) return { heading: "Tell the patient the outcome", body: `${r.destination_name} accepted the referral. Tell the patient and the next steps, then record it.`, tab: "response", action: "Go to follow-up", tone: "warn" };
      return { heading: "Close the referral", body: "Record any task outcomes, then close the referral.", tab: "response", action: "Go to follow-up", tone: "info" };
    }
  }
  const waiting: Record<string, string> = {
    submitted: `Delivered to ${r.destination_name}. Their staff take it in, confirm the patient and assign a doctor.`,
    acknowledged: `${r.destination_name} received it. Their staff assign a doctor, who accepts, declines or asks for information.`,
  };
  return { heading: `Waiting for ${r.destination_name}`, body: waiting[r.status] ?? "", tab: "response", action: "View progress", tone: "info" };
}
