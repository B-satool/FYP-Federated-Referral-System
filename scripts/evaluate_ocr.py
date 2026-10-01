"""OCR + field-extraction evaluation on the dev and held-out samples (Stage 4 evaluation resources).

Run inside the central image (uses the same extract_document() as production):
  docker compose run --rm --no-deps -v ${PWD}:/repo -w /srv central python /repo/scripts/evaluate_ocr.py [--split dev|heldout|all]

Metrics: character error rate (CER), word error rate (WER), supported-field
precision/recall, and processing time. Samples are machine-generated renders;
results do NOT establish reliability on real handwriting.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/srv")

REPO = Path("/repo")
EVAL = REPO / "evaluation" / "ocr"


def levenshtein(a: list, b: list) -> int:
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def norm(text: str) -> str:
    return " ".join(text.replace("\n", " ").split()).lower()


def evaluate(split: str) -> dict:
    from app.documents import extract_rules, processing
    from app.documents.storage import LocalStorage

    tmp = Path(tempfile.mkdtemp())
    processing.storage = LocalStorage(tmp)  # isolate from the application's document store
    rows = []
    for img in sorted((EVAL / split).glob("*.jpg")):
        truth = (img.with_suffix(".txt")).read_text(encoding="utf-8")
        expected = json.loads(img.with_name(img.stem + ".expected.json").read_text())
        shutil.copy(img, tmp / img.name)

        class Doc:  # minimal stand-in for the Document row
            storage_key = img.name
            detected_type = "image/jpeg"

        start = time.monotonic()
        pages, _meta = processing.extract_document(Doc())
        ocr_ms = int((time.monotonic() - start) * 1000)
        lines = [{"i": i, "page": p.page, **ln} for p in pages for i, ln in enumerate(p.lines)]
        # The first rendered line is the synthetic-data label, not part of the document text.
        text = "\n".join(ln["text"] for ln in lines if "synthetic" not in ln["text"].lower())
        fields = extract_rules.extract(lines)
        t, h = norm(truth), norm(text)
        cer = levenshtein(list(t), list(h)) / max(1, len(t))
        wer = levenshtein(t.split(), h.split()) / max(1, len(t.split()))
        got_meds = {f["name"].split()[0].lower() for f in fields["medications"]}
        exp_meds = set(expected["medications"])
        got_labs = {f["test"]: f["value"] for f in fields["labs"]}
        lab_hits = sum(1 for k, v in expected["labs"].items() if got_labs.get(k) == v)
        rows.append({
            "file": img.name, "cer": round(cer, 4), "wer": round(wer, 4), "ocr_ms": ocr_ms,
            "mean_ocr_confidence": pages[0].mean_confidence,
            "medications_expected": sorted(exp_meds), "medications_found": sorted(got_meds),
            "medication_tp": len(exp_meds & got_meds), "medication_fp": len(got_meds - exp_meds),
            "labs_expected": expected["labs"], "labs_found": got_labs, "lab_tp": lab_hits,
            "lab_fp": sum(1 for k in got_labs if k not in expected["labs"] or got_labs[k] != expected["labs"].get(k)),
        })
    shutil.rmtree(tmp, ignore_errors=True)
    exp_fields = sum(len(r["medications_expected"]) + len(r["labs_expected"]) for r in rows)
    tp = sum(r["medication_tp"] + r["lab_tp"] for r in rows)
    fp = sum(r["medication_fp"] + r["lab_fp"] for r in rows)
    return {
        "split": split, "documents": len(rows),
        "mean_cer": round(sum(r["cer"] for r in rows) / max(1, len(rows)), 4),
        "mean_wer": round(sum(r["wer"] for r in rows) / max(1, len(rows)), 4),
        "field_recall": round(tp / max(1, exp_fields), 3),
        "field_precision": round(tp / max(1, tp + fp), 3),
        "mean_ocr_ms": int(sum(r["ocr_ms"] for r in rows) / max(1, len(rows))),
        "rows": rows,
    }


def main() -> None:
    import pytesseract

    parser = argparse.ArgumentParser()
    parser.add_argument("--split", default="all", choices=["dev", "heldout", "all"])
    args = parser.parse_args()
    splits = ["dev", "heldout"] if args.split == "all" else [args.split]
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ocr_engine": f"tesseract {pytesseract.get_tesseract_version()}",
        "extractor": "rules-extractor/1",
        "caveat": "Machine-generated renders only; no claim about real handwriting reliability.",
        "results": [evaluate(s) for s in splits],
    }
    out = REPO / "evaluation" / "results" / "ocr-latest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    for r in report["results"]:
        print(f"{r['split']:8} docs={r['documents']} CER={r['mean_cer']:.3f} WER={r['mean_wer']:.3f} "
              f"field recall={r['field_recall']:.2f} precision={r['field_precision']:.2f} mean OCR {r['mean_ocr_ms']} ms")
    print("written", out)


if __name__ == "__main__":
    main()
