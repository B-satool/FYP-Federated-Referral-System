/**
 * Which records go in the package (spec v4 8.2). The doctor decides; this is only where the ticks start.
 *
 * Tier 1, the deterministic floor, runs here in the browser and always works: current diagnoses, operations,
 * current medicines, and visits, results and imaging from the last 6 months. Tier 2, the AI ranking, runs only when
 * the doctor asks for it (ai.ts). The doctor's ticks are kept on this device (localStorage) until approval, when they
 * become the signed manifest.
 */
import type { OpenedItem } from "./records";

export const FLOOR_VERSION = "floor/1";
export const RECENT_DAYS = 183;

export type FloorReason = { include: boolean; reason: string };

function daysAgo(date: string | null | undefined, today = new Date()): number | null {
  if (!date) return null;
  const t = Date.parse(date.length === 7 ? `${date}-01` : date.length === 4 ? `${date}-01-01` : date);
  return Number.isNaN(t) ? null : (today.getTime() - t) / 86_400_000;
}

/** The floor's choice for one item, with the reason shown to the doctor. */
export function floor(item: OpenedItem, today = new Date()): FloorReason {
  if (item.state !== "ok" || !item.content) {
    return { include: false, reason: "Not opened on this device" };
  }
  const c = item.content;
  const age = daysAgo(c.date ?? item.title.date, today);
  if (c.sensitive_category) return { include: false, reason: "Sensitive record: include only if it matters for this referral" };
  switch (c.category) {
    case "condition": {
      const status = String(c.record?.status ?? "active");
      return status === "active" ? { include: true, reason: "Current diagnosis" } : { include: false, reason: `Diagnosis ${status}` };
    }
    case "surgery": return { include: true, reason: "Previous operation" };
    case "medication": return { include: true, reason: "Current medicine" };
    case "visit":
    case "lab":
    case "imaging":
      return age !== null && age <= RECENT_DAYS ? { include: true, reason: "From the last 6 months" }
        : { include: false, reason: "Older than 6 months" };
    case "note":
    case "medication_list":
    case "scan":
      return { include: true, reason: "Added by you for this referral" };
    default:
      return { include: false, reason: "Not part of the default selection" };
  }
}

const key = (referralId: number) => `refx:selection:${referralId}`;

export function loadChoices(referralId: number): Record<string, boolean> {
  try {
    return JSON.parse(localStorage.getItem(key(referralId)) ?? "{}");
  } catch {
    return {};
  }
}

export function saveChoices(referralId: number, choices: Record<string, boolean>) {
  try {
    localStorage.setItem(key(referralId), JSON.stringify(choices));
  } catch {
    /* storage may be unavailable: the choices then last for this page only */
  }
}

export function isSelected(item: OpenedItem, choices: Record<string, boolean>): boolean {
  const id = item.title.item_id;
  return id in choices ? choices[id] : floor(item).include;
}
