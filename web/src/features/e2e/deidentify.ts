/**
 * De-identification on the doctor's device before anything goes to the AI (spec v4 8.3).
 *
 * The same rules as the platform's earlier server-side scrubber (services/central/app/generation/privacy.py):
 * the patient's name parts, CNIC, record numbers and the referral reference become placeholders; institution names
 * become "a hospital", "a clinic" or "a laboratory"; doctors' names become "a doctor"; calendar dates become
 * "N days before the referral"; long numbers (phones, IDs) become "[number]". The doctor sees the result and can
 * edit it before sending. Automatic de-identification can miss things: the preview says so.
 */
const DATE = /\b(\d{4}-\d{2}-\d{2}|\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}|\d{4}-\d{2}|\d{1,2}\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?,?\s+\d{4}|(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4})\b/gi;
const LONG_NUMBER = /\b\d[\d -]{6,}\d\b/g;
const DOCTOR = /\b(Dr|Doctor|Prof)\.?\s+[A-Z][a-zA-Z'-]+(\s+[A-Z][a-zA-Z'-]+){0,2}/g;
const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

export type Places = { name: string; kind: string }[];

export class Scrubber {
  private name: RegExp | null;
  private ids: string[];
  private places: [RegExp, string][];
  constructor(patientName: string | null | undefined, ids: (string | null | undefined)[], places: Places, private reference: Date) {
    const parts = (patientName ?? "").split(/\W+/).filter((p) => p.length >= 3);
    this.name = parts.length ? new RegExp(`\\b(${parts.map(escape).join("|")})\\b`, "gi") : null;
    this.ids = ids.filter((i): i is string => !!i && i.length >= 3);
    this.places = [...places].sort((a, b) => b.name.length - a.name.length)
      .map((p) => [new RegExp(escape(p.name), "gi"), `a ${p.kind}`] as [RegExp, string]);
  }

  text(value: string | null | undefined): string {
    let out = value ?? "";
    for (const i of this.ids) out = out.split(i).join("[id]");
    const cnicDigits = this.ids.map((i) => i.replace(/\D/g, "")).filter((d) => d.length >= 13);
    for (const [re, generic] of this.places) out = out.replace(re, generic);
    out = out.replace(DOCTOR, "a doctor");
    if (this.name) out = out.replace(this.name, "[patient]");
    out = out.replace(DATE, "[date]");
    out = out.replace(LONG_NUMBER, (m) => (cnicDigits.includes(m.replace(/\D/g, "")) ? "[id]" : "[number]"));
    return out;
  }

  /** A date as days before (or after) the referral, never the calendar date. */
  when(value: string | null | undefined): string | null {
    if (!value) return null;
    const t = Date.parse(value.length === 7 ? `${value}-01` : value.length === 4 ? `${value}-01-01` : value);
    if (Number.isNaN(t)) return null;
    const days = Math.round((this.reference.getTime() - t) / 86_400_000);
    return days >= 0 ? `${days} days before the referral` : `${-days} days after the referral`;
  }
}

export function ageYears(birth: string | null | undefined, on: Date): number | null {
  if (!birth) return null;
  const b = new Date(birth.slice(0, 10));
  if (Number.isNaN(b.getTime())) return null;
  let age = on.getUTCFullYear() - b.getUTCFullYear();
  if (on.getUTCMonth() < b.getUTCMonth() || (on.getUTCMonth() === b.getUTCMonth() && on.getUTCDate() < b.getUTCDate())) age -= 1;
  return age;
}
