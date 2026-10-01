"""Generate the synthetic sample and evaluation documents.

Run inside the central image (has reportlab + Pillow):
  docker compose run --rm --no-deps -v ${PWD}:/repo -w /repo central python scripts/generate_samples.py

Every document is MACHINE-GENERATED and labelled synthetic. These samples show
the pipeline works on clean renders; they do NOT establish reliability on real
handwriting (see docs/evaluation.md).
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "samples" / "documents"
EVAL = ROOT / "evaluation" / "ocr"
LABEL = "SYNTHETIC SAMPLE - machine-generated for the FYP prototype - not a real patient"


def pdf_document(path: Path, title: str, lines: list[str]) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    w, h = A4
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(40, h - 30, LABEL)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, h - 60, title)
    c.setFont("Helvetica", 11)
    y = h - 95
    for line in lines:
        c.drawString(40, y, line)
        y -= 20
    c.save()


def scan_image(path: Path, lines: list[str], seed: int, noise: float = 0.04, rotate: float = 0.8, blur: float = 0.6) -> None:
    rnd = random.Random(seed)
    font = ImageFont.load_default(size=30)
    small = ImageFont.load_default(size=16)
    img = Image.new("L", (1400, 120 + 52 * len(lines)), 248)
    d = ImageDraw.Draw(img)
    d.text((40, 20), LABEL, fill=90, font=small)
    y = 70
    for line in lines:
        d.text((40 + rnd.randint(-4, 4), y), line, fill=rnd.randint(10, 50), font=font)
        y += 52
    img = img.rotate(rotate, fillcolor=248, expand=False)
    px = img.load()
    for _ in range(int(img.width * img.height * noise)):
        x, yy = rnd.randrange(img.width), rnd.randrange(img.height)
        px[x, yy] = rnd.randint(120, 200)
    img = img.filter(ImageFilter.GaussianBlur(blur))
    img.convert("RGB").save(path, quality=88)


def unreadable(path: Path, seed: int) -> None:
    rnd = random.Random(seed)
    img = Image.new("L", (1200, 800), 200)
    px = img.load()
    for x in range(img.width):
        for y in range(img.height):
            px[x, y] = rnd.randint(60, 230)
    img.filter(ImageFilter.GaussianBlur(6)).convert("RGB").save(path)


SAMPLE_DOCS = {
    "prescription_cardiology_digital.pdf": ("pdf", "Lahore Heart Centre - Prescription (synthetic)", [
        "Patient: Ayesha Khan    DOB: 14/03/1987    MRN (Clinic A): MR-102",
        "Date: 01/09/2026",
        "Prescriber: Dr Hassan Rafiq, Cardiology",
        "",
        "Rx",
        "1. Warfarin 7.5 mg tablet - 7.5 mg orally once daily",
        "2. Atorvastatin 20 mg tablet - 20 mg at night",
        "",
        "Target INR 2.0-3.0. Recheck INR in 4 weeks.",
    ]),
    "referral_note_scan.jpg": ("scan", None, [
        "Clinic note - Date: 10/09/2026",
        "Patient: Ayesha Khan, DOB 14/03/1987",
        "Reports taking Ecosprin 75 mg daily (unsure)",
        "Last INR 2.6 on 05/09/2026",
        "Hb 12.9 g/dL on 05/09/2026",
        "Requests orthodontic opinion for crowding",
    ]),
}

EVAL_DOCS = {
    "dev": [
        ("dev01_prescription.jpg", ["Prescription - Date: 12/08/2026", "Clopidogrel 75 mg tablet once daily",
                                    "Metformin 500 mg tablet twice daily", "Platelets 210 on 10/08/2026"],
         {"medications": ["clopidogrel", "metformin"], "labs": {"Platelets": 210.0}}),
        ("dev02_labslip.jpg", ["Lab slip - Date: 03/07/2026", "INR 3.1", "Hemoglobin 11.8 g/dL", "HbA1c 6.9 %"],
         {"medications": [], "labs": {"INR": 3.1, "Hemoglobin": 11.8, "HbA1c": 6.9}}),
        ("dev03_note.jpg", ["Clinic note - Date: 21/06/2026", "Takes Xarelto 20 mg once daily",
                            "Prednisolone 5 mg tablet stopped in May"],
         {"medications": ["xarelto", "prednisolone"], "labs": {}}),
    ],
    "heldout": [
        ("ho01_prescription.jpg", ["Prescription - Date: 02/09/2026", "Apixaban 5 mg tablet twice daily",
                                   "Atorvastatin 40 mg tablet at night"],
         {"medications": ["apixaban", "atorvastatin"], "labs": {}}),
        ("ho02_labslip.jpg", ["Lab report - Date: 15/09/2026", "INR 2.4", "Platelets 188", "Hb 13.4 g/dL"],
         {"medications": [], "labs": {"INR": 2.4, "Platelets": 188.0, "Hemoglobin": 13.4}}),
        ("ho03_note.jpg", ["Referral note - Date: 18/09/2026", "On Alendronate 70 mg once weekly",
                           "Aspirin 75 mg daily"],
         {"medications": ["alendronate", "aspirin"], "labs": {}}),
    ],
}


def main() -> None:
    SAMPLES.mkdir(parents=True, exist_ok=True)
    for name, (kind, title, lines) in SAMPLE_DOCS.items():
        if kind == "pdf":
            pdf_document(SAMPLES / name, title, lines)
        else:
            scan_image(SAMPLES / name, lines, seed=7)
    unreadable(SAMPLES / "unreadable_scan.png", seed=3)
    (SAMPLES / "rejected_not_a_pdf.pdf").write_bytes(b"This is a plain text file renamed to .pdf; it must be rejected.\n")
    (SAMPLES / "README.md").write_text(
        "# Sample documents (synthetic)\n\n" + LABEL + "\n\n"
        "| File | Purpose |\n|---|---|\n"
        "| prescription_cardiology_digital.pdf | Digital PDF with embedded text (dose differs from Clinic A record -> discrepancy) |\n"
        "| referral_note_scan.jpg | Scanned-style image (OCR path); patient-reported Ecosprin, INR, Hb |\n"
        "| unreadable_scan.png | Unreadable sample -> no text; manual path must remain |\n"
        "| rejected_not_a_pdf.pdf | Declared PDF that is really text -> rejected at upload |\n",
        encoding="utf-8")
    for split, docs in EVAL_DOCS.items():
        out = EVAL / split
        out.mkdir(parents=True, exist_ok=True)
        for i, (name, lines, expected) in enumerate(docs):
            scan_image(out / name, lines, seed=100 + i + (50 if split == "heldout" else 0),
                       noise=0.05 if split == "heldout" else 0.03, rotate=1.2 if split == "heldout" else 0.6)
            (out / (Path(name).stem + ".txt")).write_text("\n".join(lines) + "\n", encoding="utf-8")
            (out / (Path(name).stem + ".expected.json")).write_text(json.dumps(expected, indent=2), encoding="utf-8")
    print("samples written to", SAMPLES, "and", EVAL)


if __name__ == "__main__":
    main()
