import type { Clarification, FollowupTask, Referral } from "../../api/types";

export type Queue = {
  clarifications: Clarification[];
  tasks?: FollowupTask[];
  awaiting_approval?: Referral[];
  awaiting_information?: Referral[];
  responses_to_review?: { referral_id: number; referral_reference: string; specialist_name: string; received_at: string }[];
  delivery_problems?: Referral[];
  drafts?: Referral[];
};

/** Items that need someone to act. Drafts and waiting items are excluded on purpose. */
export function actionableCount(q: Queue | undefined): number {
  if (!q) return 0;
  return (
    q.clarifications.filter((c) => c.status === "open").length +
    (q.tasks?.length ?? 0) +
    (q.awaiting_approval?.length ?? 0) +
    (q.responses_to_review?.length ?? 0) +
    (q.delivery_problems?.length ?? 0)
  );
}
