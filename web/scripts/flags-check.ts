// Checks of the browser's Layer 1 flag library (src/features/e2e/flags.ts) on a small synthetic bundle.
// Run by libs/common/tests/test_browser_flags.py:  node web/scripts/flags-check.ts
// Prints a JSON object of named checks; every one must be true.
// With arguments it evaluates instead: node web/scripts/flags-check.ts <bundle.json> <meds.json>  (tests/test_e2e_flags.py)
import { readFileSync } from "node:fs";
import { distance, evaluate, mapName, nameIndex, normalize } from "../src/features/e2e/flags.ts";
import type { Bundle } from "../src/features/e2e/flags.ts";

if (process.argv[3]) {
  const real = JSON.parse(readFileSync(process.argv[2], "utf8")) as Bundle;
  const meds = JSON.parse(readFileSync(process.argv[3], "utf8"));
  console.log(JSON.stringify(evaluate(meds, real)));
  process.exit(0);
}

const bundle: Bundle = {
  version: "test", sha256: "0".repeat(64),
  content: {
    type: "refx.med-bundle/v1",
    names: [
      ["aspirin", "aspirin", "aspirin", "antiplatelet", "generic"],
      ["disprin", "Disprin", "aspirin", "antiplatelet", "brand"],
      ["clopidogrel", "clopidogrel", "clopidogrel", "antiplatelet", "generic"],
      ["plavix", "Plavix", "clopidogrel", "antiplatelet", "brand"],
      ["warfarin", "warfarin", "warfarin", "anticoagulant", "generic"],
      ["vitamin", "Vitamin", "colecalciferol", "vitamin", "register_brand"],
      ["glare", "Glare", "gliclazide | ibuprofen", "", "register_ambiguous"],
      ["augmentin", "Augmentin", "co-amoxiclav", "antibiotic", "brand"],
      ["omeprazole", "omeprazole", "omeprazole", "ppi", "generic"],
    ],
    options: { glare: [
      { ingredient: "gliclazide", company: "Mass Pharma", drap_reg_no: "1", strength: "80 mg", dosage_form: "tablet" },
      { ingredient: "ibuprofen", company: "Shrooq", drap_reg_no: "2", strength: "400 mg", dosage_form: "tablet" }] },
    components: { "co-amoxiclav": ["amoxicillin", "clavulanic acid"] },
    in_source: ["aspirin", "clopidogrel", "warfarin", "ibuprofen", "amoxicillin", "omeprazole"],
    interactions: [
      ["aspirin", "clopidogrel", "Major", "DDInter1-DDInter2", "Increased risk of bleeding.", "DailyMed: clopidogrel"],
      ["ibuprofen", "warfarin", "Major", "DDInter3-DDInter4", null, null],
      ["amoxicillin", "warfarin", "Moderate", "DDInter5-DDInter4", null, null],
    ],
    interaction_source: { name: "DDInter 2.0", url: "https://ddinter.scbdd.com", licence: "CC BY-NC-SA 4.0", version: "test-1" },
  },
};

const idx = nameIndex(bundle.content);
const ev = evaluate([
  { id: "1", name: "Tab Disprin 75mg", source: "list" },
  { id: "2", name: "Plavix 75 mg", source: "record" },
  { id: "3", name: "Panadol Extra", source: "list" },
  { id: "4", name: "Glare 80mg", source: "list" },
], bundle);
const chosen = evaluate([{ id: "4", name: "Glare", source: "list", choice: "ibuprofen" }, { id: "5", name: "Warfarin 5mg", source: "list" }], bundle);
const combo = evaluate([{ id: "a", name: "Augmentin 625", source: "list" }, { id: "b", name: "warfarin", source: "list" }], bundle);
const typo = mapName(idx, "Clopidogrl 75mg");
const none = evaluate([{ id: "x", name: "omeprazole", source: "list" }], bundle);

const checks = {
  normalize_drops_forms_and_strengths: normalize("Tab. Disprin 75mg (EC)") === "disprin",
  brand_maps_to_ingredient: mapName(idx, "Disprin").ingredient === "aspirin",
  register_name_only_at_the_start: mapName(idx, "Multi Vitamin").status === "unmapped" && mapName(idx, "Vitamin D3").status === "mapped",
  known_pair_flags_from_brand_names: ev.flags.length === 1 && ev.flags[0].ingredients.join("+") === "aspirin+clopidogrel"
    && ev.flags[0].source === "DDInter 2.0" && ev.flags[0].quote === "Increased risk of bleeding." && ev.flags[0].datasetVersion === "test-1",
  unmapped_is_not_assessed_never_safe: ev.notAssessed.some((x) => x.med.id === "3" && x.reason.startsWith("Not in")),
  ambiguous_waits_for_the_doctor: ev.results.find((r) => r.id === "4")!.mapping.status === "ambiguous"
    && ev.notAssessed.some((x) => x.med.id === "4" && x.reason.startsWith("Choose")),
  chosen_product_is_checked: chosen.flags.length === 1 && chosen.flags[0].ingredients.join("+") === "ibuprofen+warfarin",
  combination_checks_each_ingredient: combo.flags.some((f) => f.ingredients.includes("amoxicillin")),
  approximate_spelling_is_probable_and_marked: typo.status === "probable" && typo.ingredient === "clopidogrel" && typo.matchedTo === "clopidogrel",
  distance_is_bounded: distance("clopidogrel", "clopidogrl") === 1 && distance("aspirin", "omeprazole") > 2,
  single_medicine_has_no_flags_but_is_assessed: none.flags.length === 0 && none.notAssessed.length === 0,
  deterministic: JSON.stringify(evaluate([{ id: "1", name: "Disprin", source: "l" }, { id: "2", name: "Plavix", source: "l" }], bundle))
    === JSON.stringify(evaluate([{ id: "1", name: "Disprin", source: "l" }, { id: "2", name: "Plavix", source: "l" }], bundle)),
};
console.log(JSON.stringify(checks));
