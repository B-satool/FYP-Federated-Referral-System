import { Alert } from "@mui/material";
import type { Referral } from "../../api/types";
import { fmtDate } from "../../components/common";

/** How long the referral's shared records are kept (docs/decisions/2026-10-28-referral-expiry.md). */
export function HoldNotice({ r }: { r: Referral }) {
  if (r.working_set_purged_at) return null; // the tabs show "no longer held" themselves
  const until = r.working_set_expires_at;
  let text: string;
  if (r.receiver_completed_at) {
    text = `Marked complete by ${r.receiver_completed_by ?? "the receiving doctor"} on ${fmtDate(r.receiver_completed_at)}. The shared records are removed on ${fmtDate(until)}.`;
  } else if (r.status === "declined") {
    text = "Declined: the shared records are being removed now.";
  } else if (r.kind === "test") {
    text = until
      ? `Held until ${fmtDate(until)}, then removed.`
      : "Held until the results are back, then removed 72 hours later.";
  } else if (r.status === "cancelled") {
    text = `Cancelled: the shared records are removed on ${fmtDate(until)}.`;
  } else if (until) {
    text = `Accepted. The shared records are kept until ${fmtDate(until)} (the receiving doctor can extend this), or until 72 hours after they mark the referral complete.`;
  } else {
    text = "Kept until the receiving doctor has finished with the referral: removed 72 hours after they mark it complete, or straight away if they decline it.";
  }
  return (
    <Alert severity="info" variant="outlined">
      {text} The reference and the fingerprint of what was sent are always kept.
    </Alert>
  );
}
