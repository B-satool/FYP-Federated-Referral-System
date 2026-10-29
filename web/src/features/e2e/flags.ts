/**
 * Medication flags, Layer 1 (spec v4 9.1): deterministic, data-backed, run on the doctor's device.
 *
 * Pure functions over the downloaded bundle (GET /med-bundle): no I/O, so it is tested under Node
 * (web/scripts/flags-check.ts) and nothing about the patient's medicines leaves the device for this layer.
 *
 * 1. Map each written name to ingredients: the hand-checked names, then the DRAP register (only where the written name
 *    starts with the brand), the same rules as services/central/app/medications/mapping.py. A name registered for two
 *    medicines is ambiguous: the doctor picks by company, it is never guessed. A spelling one or two letters away from
 *    a single known name is a "probable" match, shown with the name it was matched to.
 * 2. Check every pair of ingredients across different medicines against the DDInter pairs in the bundle.
 * 3. Anything not mapped, or with no interaction data, is "could not be assessed": never "no issues" (AGENTS.md 7).
 *    Those names (generic or as written) are what Layer 2, the AI, may be asked about.
 *
 * No drug-procedure table exists here or in the bundle (T-FLAG-2).
 */

export type NameRow = [name: string, display: string, ingredient: string, drugClass: string, kind: string];
export type Option = { ingredient: string; company: string | null; drap_reg_no: string | null; strength: string | null; dosage_form: string | null };
export type BundleContent = {
  type: string;
  names: NameRow[];
  options: Record<string, Option[]>;
  components: Record<string, string[]>;
  in_source: string[];
  interactions: [a: string, b: string, severity: string, sourceRef: string, quote: string | null, labelSource: string | null][];
  interaction_source: { name: string; url: string; licence: string; version: string | null };
};
export type Bundle = { version: string; sha256: string; content: BundleContent };

export type Med = { id: string; name: string; strength?: string | null; dose?: string | null; frequency?: string | null; source: string; choice?: string | null };
export type Mapping = {
  status: "mapped" | "probable" | "ambiguous" | "unmapped";
  ingredient: string | null;
  drugClass: string | null;
  matchedTo: string | null; // the known name it was matched to
  note: string;
  options: Option[];
};
export type MedResult = Med & { mapping: Mapping; ingredients: string[] };
export type Flag = {
  key: string; meds: [string, string]; medIds: [string, string]; ingredients: [string, string]; severity: string;
  source: string; sourceRef: string; sourceUrl: string; datasetVersion: string | null; quote: string | null; labelSource: string | null;
  approximate: boolean; // a name in the pair was matched approximately
};
export type Evaluation = { results: MedResult[]; flags: Flag[]; notAssessed: { med: MedResult; reason: string }[]; datasetVersion: string | null };

const FORM_WORDS = new Set([
  "tablet", "tablets", "tab", "tabs", "capsule", "capsules", "cap", "caps", "sachet", "sachets", "syrup", "susp",
  "suspension", "injection", "inj", "mg", "mcg", "g", "ml", "units", "unit", "iu", "oral", "po", "od", "bd", "tds",
  "daily", "once", "twice", "weekly", "film", "coated", "ec", "sr", "xr", "er", "sodium", "potassium", "with",
  "and", "per", "x", "months", "month", "days", "day", "at", "night",
]);
const REGISTER = new Set(["register_brand", "register_ambiguous"]);

export function normalize(name: string): string {
  const text = name.toLowerCase().replace(/\+/g, " ").replace(/[\d.,/%()\-:]+/g, " ");
  return text.split(/\s+/).filter((t) => t && !FORM_WORDS.has(t)).join(" ");
}

/** Damerau-Levenshtein distance (optimal string alignment), stopping early past `max`. */
export function distance(a: string, b: string, max = 2): number {
  if (Math.abs(a.length - b.length) > max) return max + 1;
  const d: number[][] = Array.from({ length: a.length + 1 }, (_, i) => [i, ...Array(b.length).fill(0)]);
  for (let j = 0; j <= b.length; j++) d[0][j] = j;
  for (let i = 1; i <= a.length; i++) {
    let rowMin = Infinity;
    for (let j = 1; j <= b.length; j++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost);
      if (i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) d[i][j] = Math.min(d[i][j], d[i - 2][j - 2] + 1);
      rowMin = Math.min(rowMin, d[i][j]);
    }
    if (rowMin > max) return max + 1;
  }
  return d[a.length][b.length];
}

export type NameIndex = { rows: NameRow[]; byFirst: Map<string, NameRow[]>; options: Record<string, Option[]> };

export function nameIndex(b: BundleContent): NameIndex {
  const byFirst = new Map<string, NameRow[]>();
  for (const r of b.names) {
    const k = r[0][0] ?? "";
    if (!byFirst.has(k)) byFirst.set(k, []);
    byFirst.get(k)!.push(r);
  }
  return { rows: b.names, byFirst, options: b.options };
}

const unmapped = (note = "Not in the medicine name list; kept as written"): Mapping =>
  ({ status: "unmapped", ingredient: null, drugClass: null, matchedTo: null, note, options: [] });

export function mapName(idx: NameIndex, raw: string, choice?: string | null): Mapping {
  const norm = normalize(raw);
  if (!norm) return unmapped();
  const padded = ` ${norm} `;
  const candidates = idx.byFirst.get(norm[0]) ?? [];
  let matched = idx.rows.filter((r) => norm === r[0] || norm.startsWith(`${r[0]} `)
    || (!REGISTER.has(r[4]) && padded.includes(` ${r[0]} `)));
  const clash = matched.filter((r) => r[4] === "register_ambiguous");
  matched = matched.filter((r) => r[4] !== "register_ambiguous");
  if (clash.length && !matched.length) {
    const options = idx.options[clash[0][0]] ?? [];
    const picked = choice ? options.find((o) => o.ingredient === choice) : undefined;
    if (picked) {
      return { status: "mapped", ingredient: picked.ingredient, drugClass: null, matchedTo: clash[0][1], options,
        note: `${clash[0][1]} chosen by the doctor: ${picked.company ?? "company not recorded"}${picked.drap_reg_no ? `, DRAP ${picked.drap_reg_no}` : ""}` };
    }
    return { status: "ambiguous", ingredient: null, drugClass: null, matchedTo: clash[0][1], options,
      note: `${clash[0][1]} is registered in Pakistan for different medicines. Check the company on the pack and choose which one it is.` };
  }
  const hits = new Map(matched.map((r) => [`${r[2]}|${r[3]}`, r]));
  if (hits.size === 1) {
    const r = [...hits.values()][0];
    const registerOnly = matched.every((x) => x[4] === "register_brand");
    return { status: "mapped", ingredient: r[2], drugClass: r[3], matchedTo: r[1], options: [],
      note: registerOnly ? "Brand from the DRAP product register" : "" };
  }
  if (hits.size > 1) {
    return { ...unmapped(), status: "ambiguous", note: `Name matches several medicines: ${[...new Set(matched.map((r) => r[2]))].sort().join(", ")}` };
  }
  // approximate: the first word one or two letters away from exactly one known single-word name
  const first = norm.split(" ")[0];
  if (first.length >= 5) {
    const max = first.length >= 8 ? 2 : 1;
    const near = candidates.filter((r) => !r[0].includes(" ") && r[4] !== "register_ambiguous" && distance(first, r[0], max) <= max);
    const ingredients = new Set(near.map((r) => r[2]));
    if (near.length && ingredients.size === 1) {
      const r = near.find((x) => !REGISTER.has(x[4])) ?? near[0];
      return { status: "probable", ingredient: r[2], drugClass: r[3], matchedTo: r[1], options: [],
        note: `Spelling close to ${r[1]}: check it is the same medicine` };
    }
  }
  return unmapped();
}

export function ingredientsOf(b: BundleContent, ingredient: string): string[] {
  return b.components[ingredient] ?? (ingredient.includes("/") ? ingredient.split("/").map((s) => s.trim()) : [ingredient]);
}

export function evaluate(meds: Med[], bundle: Bundle): Evaluation {
  const b = bundle.content;
  const idx = nameIndex(b);
  const pairs = new Map(b.interactions.map((x) => [[x[0], x[1]].sort().join("|"), x]));
  const inSource = new Set(b.in_source);
  const results: MedResult[] = meds.map((m) => {
    const mapping = mapName(idx, m.name, m.choice);
    return { ...m, mapping, ingredients: mapping.ingredient ? ingredientsOf(b, mapping.ingredient) : [] };
  });
  const notAssessed: { med: MedResult; reason: string }[] = [];
  for (const r of results) {
    if (r.mapping.status === "unmapped") notAssessed.push({ med: r, reason: "Not in the medicine name list" });
    else if (r.mapping.status === "ambiguous") notAssessed.push({ med: r, reason: "Choose which product it is first" });
    else if (!r.ingredients.some((i) => inSource.has(i))) notAssessed.push({ med: r, reason: "No interaction data for this ingredient" });
  }
  const flags: Flag[] = [];
  const seen = new Set<string>();
  for (let i = 0; i < results.length; i++) {
    for (let j = i + 1; j < results.length; j++) {
      const A = results[i], B = results[j];
      for (const a of A.ingredients) {
        for (const c of B.ingredients) {
          if (a === c) continue;
          const hit = pairs.get([a, c].sort().join("|"));
          const key = `${[A.id, B.id].sort().join("|")}|${[a, c].sort().join("|")}`;
          if (!hit || seen.has(key)) continue;
          seen.add(key);
          flags.push({ key, meds: [A.name, B.name], medIds: [A.id, B.id], ingredients: [a, c], severity: hit[2],
            source: b.interaction_source.name, sourceRef: hit[3], sourceUrl: b.interaction_source.url,
            datasetVersion: b.interaction_source.version, quote: hit[4], labelSource: hit[5],
            approximate: A.mapping.status === "probable" || B.mapping.status === "probable" });
        }
      }
    }
  }
  const order: Record<string, number> = { Major: 0, Moderate: 1, Minor: 2, Unknown: 3 };
  flags.sort((x, y) => (order[x.severity] ?? 4) - (order[y.severity] ?? 4));
  return { results, flags, notAssessed, datasetVersion: b.interaction_source.version };
}
