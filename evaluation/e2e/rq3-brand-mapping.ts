// RQ3 (spec v4 15), brand mapping: how the browser's Layer 1 matcher (web/src/features/e2e/flags.ts) handles the
// ways a Pakistani brand name is written. Synthetic benchmark: for each hand-checked brand with a known ingredient,
// variants a prescription or a patient might produce (case, strength and form words, spacing, one or two typing
// slips). Measured: exact matches, approximate ("probable") matches to the right ingredient, wrong ingredients
// (the costly error), and unmapped (left for the doctor and the AI: safe, not silent).
// Run: node evaluation/e2e/rq3-brand-mapping.ts <bundle.json>   (bundle from GET /med-bundle)
import { readFileSync } from "node:fs";
import { mapName, nameIndex } from "../../web/src/features/e2e/flags.ts";
import type { Bundle } from "../../web/src/features/e2e/flags.ts";

const bundle = JSON.parse(readFileSync(process.argv[2], "utf8")) as Bundle;
const idx = nameIndex(bundle.content);
const brands = bundle.content.names.filter((r) => r[4] === "brand" && r[0].length >= 5 && !r[0].includes(" "));

function variants(display: string): { kind: string; text: string }[] {
  const w = display;
  const mid = Math.floor(w.length / 2);
  return [
    { kind: "as_written", text: w },
    { kind: "upper_with_strength", text: `${w.toUpperCase()} 75mg` },
    { kind: "tab_prefix_and_form", text: `Tab. ${w} 500 mg tablets` },
    { kind: "dropped_letter", text: w.slice(0, mid) + w.slice(mid + 1) },
    { kind: "swapped_letters", text: w.slice(0, mid) + w[mid + 1] + w[mid] + w.slice(mid + 2) },
    { kind: "doubled_letter", text: w.slice(0, mid) + w[mid] + w.slice(mid) },
    { kind: "two_slips", text: (w.slice(0, mid) + w.slice(mid + 1)).replace(/[aeiou](?!.*[aeiou])/i, "") },
  ];
}

const rows: Record<string, { n: number; exact: number; probable: number; wrong: number; unmapped: number; ambiguous: number }> = {};
for (const [, display, ingredient] of brands) {
  for (const v of variants(display)) {
    const r = (rows[v.kind] ??= { n: 0, exact: 0, probable: 0, wrong: 0, unmapped: 0, ambiguous: 0 });
    r.n++;
    const m = mapName(idx, v.text);
    if (m.status === "unmapped") r.unmapped++;
    else if (m.status === "ambiguous") r.ambiguous++;
    else if (m.ingredient !== ingredient) r.wrong++;
    else if (m.status === "mapped") r.exact++;
    else r.probable++;
  }
}
console.log(JSON.stringify({ brands: brands.length, bundle_version: bundle.version, by_variant: rows }, null, 1));
