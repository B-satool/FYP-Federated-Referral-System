/**
 * Reading a scanned paper on this device (spec v4 10, D15). Tesseract.js runs in a Web Worker in this browser; its
 * engine and the English model are served by this application (public/ocr), not a CDN. The image and the text never
 * reach our servers: the text is encrypted with the scan before upload. Tesseract reads printed text well and
 * handwriting poorly; the doctor checks and corrects every field against the image.
 */
import { createWorker } from "tesseract.js";
import { mapName, NameIndex } from "./flags";

export const OCR_ENGINE = "Tesseract.js 5.1.1 (on this device, English best_int model)";

export type OcrLine = { text: string; confidence: number };
export type OcrResult = { text: string; lines: OcrLine[]; confidence: number };

export async function readImage(image: Blob, onProgress?: (p: number) => void): Promise<OcrResult> {
  const worker = await createWorker("eng", 1, {
    workerPath: "/ocr/worker.min.js", corePath: "/ocr", langPath: "/ocr", gzip: true, workerBlobURL: false,
    logger: (m: { status: string; progress: number }) => { if (m.status === "recognizing text") onProgress?.(m.progress); },
  });
  try {
    const { data } = await worker.recognize(image);
    const lines = (data.lines ?? []).map((l) => ({ text: l.text.trim(), confidence: Math.round(l.confidence) })).filter((l) => l.text);
    return { text: data.text, lines, confidence: Math.round(data.confidence) };
  } finally {
    await worker.terminate();
  }
}

export type ReadMedicine = { name: string; strength: string; dose: string; frequency: string; line: string; confidence: number; ingredient: string | null };

const STRENGTH = /(\d+(?:\.\d+)?)\s?(mg|mcg|g|ml|units?|iu)\b/i;
const FREQUENCY = /\b(od|bd|bid|tds|tid|qds|qid|hs|prn|stat|once daily|twice daily|three times daily|at night|daily|weekly|1\+0\+1|1\+1\+1|0\+0\+1|1\+0\+0)\b/i;
const DOSE = /\b(\d+(?:\/\d+)?)\s*(tab|tabs|tablet|tablets|cap|caps|capsule|capsules|puff|puffs|drop|drops|ml|unit|units)\b/i;

/** Lines that name a known medicine, split into name, strength, dose and frequency for the doctor to check. A line
 * that names nothing known is left out of the suggestions (the full text is still kept with the scan). */
export function medicinesInText(lines: OcrLine[], idx: NameIndex): ReadMedicine[] {
  const out: ReadMedicine[] = [];
  for (const l of lines) {
    const cleaned = l.text.replace(/^(rx|tab\.?|cap\.?|inj\.?|syp\.?|[-•*\d.)]+)\s+/i, "").trim();
    const words = cleaned.split(/\s+/);
    for (let n = Math.min(3, words.length); n >= 1; n--) {
      const candidate = words.slice(0, n).join(" ");
      const m = mapName(idx, candidate);
      if (m.status === "mapped" || m.status === "probable" || m.status === "ambiguous") {
        out.push({ name: candidate, strength: l.text.match(STRENGTH)?.[0] ?? "", dose: l.text.match(DOSE)?.[0] ?? "",
          frequency: l.text.match(FREQUENCY)?.[0] ?? "", line: l.text, confidence: l.confidence, ingredient: m.ingredient });
        break;
      }
    }
  }
  return out;
}
