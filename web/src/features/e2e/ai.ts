/**
 * AI record suggestions (spec v4 8.2, tier 2): only when the doctor clicks "Suggest", only de-identified text, and only
 * after the doctor has seen (and may edit) exactly what is sent. The platform relays it to the model without storing
 * or logging it. The answer is a suggestion: the doctor's ticks decide.
 */
import { api } from "../../api/client";
import type { ReferralDetail } from "../../api/types";
import { ageYears, Places, Scrubber } from "./deidentify";
import { OpenedItem, summary } from "./records";
import { floor } from "./selection";

export type SelectionPayload = {
  patient: { age_years: number | null; sex: string | null };
  referral: Record<string, unknown>;
  records: { id: number; category: string; when: string | null; default: boolean; text: string }[];
};
export type Suggestion = { id: number; recommendation: "include" | "exclude" | "optional"; relevance: "high" | "medium" | "low"; reason: string };
export type SuggestionAnswer = { recommendations: Suggestion[]; missing: string[]; dropped_ids: number; withheld: number; model: string; label: string };

/** The de-identified payload and the map from its small ids back to item ids (item ids never leave the device). */
export function buildSelectionPayload(r: ReferralDetail, items: OpenedItem[], places: Places): { payload: SelectionPayload; ids: Map<number, string> } {
  const on = new Date(r.requested_at ?? r.created_at);
  const s = new Scrubber(r.patient.name, [r.patient.cnic, r.patient.local_patient_id, r.reference], places, on);
  const ids = new Map<number, string>();
  const records = items.filter((i) => i.state === "ok" && i.content).map((i, n) => {
    ids.set(n + 1, i.title.item_id);
    const c = i.content!;
    const extra = typeof c.record?.text === "string" ? ` ${c.record.text}` : "";
    return { id: n + 1, category: c.category, when: s.when(c.date ?? i.title.date), default: floor(i).include,
      text: s.text(`${summary(c)}${extra}`).slice(0, 300) };
  });
  return {
    ids,
    payload: {
      patient: { age_years: ageYears(r.patient.birth_date, on), sex: r.patient.sex },
      referral: { kind: r.kind, reason: s.text(r.reason), consultation_notes: s.text((r.consultation_notes ?? "").slice(0, 2000)) || null,
        department: r.destination_department_name, planned_procedure: r.procedure_status === "planned" ? s.text(r.planned_procedure) : null,
        procedure_status: r.procedure_status, urgency: r.urgency },
      records,
    },
  };
}

export function askSelection(referralId: number, payload: SelectionPayload): Promise<SuggestionAnswer> {
  return api.post<SuggestionAnswer>("/ai/relay/selection", { referral_id: referralId, payload });
}
