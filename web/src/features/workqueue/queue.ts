import type { WorkQueue } from "../../api/types";

export type Queue = WorkQueue;

/** Items that need the signed-in person to act (shown as the work-queue badge). */
export function actionableCount(q: Queue | undefined): number {
  if (!q) return 0;
  const n = (xs?: unknown[]) => xs?.length ?? 0;
  return (
    n(q.flags_to_acknowledge) +
    n(q.responses_to_review) +
    n(q.results_to_see) +
    n(q.to_prepare) +
    n(q.link_requests) +
    n(q.tests_to_send) +
    n(q.delivery_problems) +
    n(q.info_requests) +
    (q.follow_up ?? []).filter((f) => !f.patient_informed || f.open_tasks > 0).length
  );
}
