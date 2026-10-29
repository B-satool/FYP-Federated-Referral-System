// Copies the on-device OCR engine (Tesseract.js worker and WebAssembly core) and the English model into public/ocr,
// so they are served by this application instead of a third-party CDN: the page that reads a scanned paper never
// loads code from elsewhere (spec v4 10). Run before dev and build (package.json).
import { copyFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const web = join(dirname(fileURLToPath(import.meta.url)), "..");
const out = join(web, "public", "ocr");
mkdirSync(out, { recursive: true });
const files = [
  ["node_modules/tesseract.js/dist/worker.min.js", "worker.min.js"],
  ["node_modules/tesseract.js-core/tesseract-core-simd-lstm.wasm.js", "tesseract-core-simd-lstm.wasm.js"],
  ["node_modules/tesseract.js-core/tesseract-core-lstm.wasm.js", "tesseract-core-lstm.wasm.js"],
  ["node_modules/@tesseract.js-data/eng/4.0.0_best_int/eng.traineddata.gz", "eng.traineddata.gz"],
];
for (const [from, to] of files) copyFileSync(join(web, from), join(out, to));
console.log(`OCR assets copied to ${out}`);
