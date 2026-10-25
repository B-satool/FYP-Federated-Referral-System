"""Build the seed files from data.py.

    python3 seed-data/generate.py

Writes (all SYNTHETIC):
  seed-data/patients/<key>_<name>.json   one file per patient, split by source system
  seed-data/index.json                   one-line summary of every patient
  seed-data/documents/*.jpg|*.pdf        prescriptions for the OCR path, discharge summary,
                                         lab reports and radiology reports

Needs Pillow and reportlab (already in the central image).
"""
from __future__ import annotations

import json
import random
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from data import INSTITUTIONS, PATIENTS, SIX_MONTHS_AGO, TODAY  # noqa: E402

DOCS = HERE / "documents"
PATS = HERE / "patients"
DOCS.mkdir(exist_ok=True)
PATS.mkdir(exist_ok=True)

LABEL = "SYNTHETIC - machine-generated for the FYP prototype - not a real patient or prescription"
FONT_DIR = "/usr/share/fonts/truetype"


def font(name: str, size: int):
    for cand in (f"{FONT_DIR}/{name}", name):
        try:
            return ImageFont.truetype(cand, size)
        except OSError:
            continue
    return ImageFont.load_default()


# --------------------------------------------------------------------- prescriptions
PRESCRIPTIONS = {
    "P1_prescription_dentist_2026-10-05.jpg": dict(
        style="handwritten", clinic="Smile Dental Clinic, Tariq Road, Karachi", doctor="Dr Imran Butt, BDS",
        reg="PMDC 41233-D", date="05-10-2026", patient="Rubina Akhtar", age_sex="52 / F", cnic=None,
        dx="Pericoronitis, lower left wisdom tooth (38)",
        rx=["Tab. Brufen 400 mg    1+0+1    x 3 days  (after meals)",
            "Tab. Panadol 500 mg   SOS  (max 3 per day)",
            "Chlorhexidine mouthwash 0.2%    1 min, twice daily x 7 days"],
        advice=["Impacted wisdom tooth - needs extraction by oral surgeon", "Warm saline rinse", "Review after 1 week"]),
    "P2_prescription_clinic_2026-10-08.jpg": dict(
        style="printed", clinic="Dr Ali's Clinic, Clifton, Karachi", doctor="Dr Ali, MBBS, FCPS (Medicine)",
        reg="PMDC 28817-S", date="08-10-2026", patient="Muhammad Tariq Mahmood", age_sex="58 / M", cnic="37405-0000022-7",
        dx="Exertional chest tightness. Type 2 DM. HTN.",
        rx=["1. Tab. Cardiprin 75 mg      0+1+0   (after lunch)",
            "2. Tab. Lipitor 40 mg        0+0+1",
            "3. Tab. Renitec 10 mg        1+0+0",
            "4. Tab. Glucophage 850 mg    1+0+1   (with meals)",
            "5. Tab. Amaryl 2 mg          1+0+0   (before breakfast)"],
        advice=["Chest X-ray PA view, Troponin I, ECG", "Avoid heavy exertion", "Review in 1 week or earlier if pain at rest"]),
    "P3_prescription_orthopaedic_2026-07-22.jpg": dict(
        style="handwritten", clinic="Bone and Joint Clinic, Saddar, Karachi", doctor="Dr Naveed Qureshi, MBBS, FCPS (Orthopaedics)",
        reg="PMDC 33910-P", date="22-07-2026", patient="Abdul Rehman", age_sex="66 / M", cnic=None,
        dx="Osteoarthritis right knee (advanced)",
        rx=["Tab. Voltral 50 mg    1+0+1    x 14 days  (after food)",
            "Tab. Calcium-D        1+0+0    x 1 month",
            "Knee brace, walking stick"],
        advice=["Physiotherapy: quadriceps strengthening", "Weight reduction", "Review in 4 weeks with standing X-ray"]),
    "P4_prescription_hospital_2019-03-11.jpg": dict(
        style="printed", clinic="Aga Khan University Hospital - Hepatology OPD", doctor="Dr Tahir Mehmood, MBBS, FCPS (Gastroenterology)",
        reg="PMDC 19456-S", date="11-03-2019", patient="Shazia Parveen", age_sex="36 / F", cnic="42101-0000044-2",
        dx="Chronic hepatitis C, genotype 3",
        rx=["1. Tab. Sofosbuvir 400 mg     1+0+0   x 12 weeks",
            "2. Tab. Daclatasvir 60 mg     1+0+0   x 12 weeks"],
        advice=["HCV RNA (PCR) 12 weeks after completing treatment", "Avoid alcohol and herbal medicines", "Review monthly"]),
    "P4_prescription_clinic_2026-10-20.jpg": dict(
        style="printed", clinic="Dr Ali's Clinic, Clifton, Karachi", doctor="Dr Ali, MBBS, FCPS (Medicine)",
        reg="PMDC 28817-S", date="20-10-2026", patient="Shazia Parveen", age_sex="44 / F", cnic="42101-0000044-2",
        dx="Chronic liver disease with splenomegaly (ultrasound 16-10-2026)",
        rx=["1. Tab. Inderal 20 mg        1+0+1",
            "2. Cap. Risek 20 mg          1+0+0   (before breakfast)",
            "3. Tab. Ferrous fumarate 200 mg   0+1+0",
            "4. Tab. Panadol 500 mg       SOS  (max 3 per day)"],
        advice=["Do NOT take Brufen or other painkillers", "Salt restriction", "Referred to hepatology for endoscopy"]),
    "P5_prescription_cardiology_2025-06-18.jpg": dict(
        style="handwritten", clinic="Ziauddin Hospital - Cardiology OPD", doctor="Dr Aamir Hussain, MBBS, FCPS (Cardiology)",
        reg="PMDC 24318-S", date="18-06-2025", patient="Imtiaz Ali Soomro", age_sex="44 / M", cnic=None,
        dx="CAD - PCI with drug-eluting stent to LAD (16-06-2025)",
        rx=["Tab. Disprin Cardio 75 mg   1+0+0",
            "Tab. Plavix 75 mg           0+1+0   x 12 months",
            "Tab. Lipitor 40 mg          0+0+1",
            "Tab. Concor 2.5 mg          1+0+0"],
        advice=["Do not stop Plavix or Disprin without asking the cardiologist", "Review in 1 month with ECG", "Control sugar"]),
}


def draw_prescription(spec: dict, out: Path, seed: int) -> None:
    rnd = random.Random(seed)
    W, H = 1240, 1650
    paper = (250, 247, 238) if spec["style"] == "handwritten" else (252, 252, 250)
    im = Image.new("RGB", (W, H), paper)
    d = ImageDraw.Draw(im)
    hand = spec["style"] == "handwritten"
    ink = (28, 40, 120) if hand else (25, 25, 25)
    body = font("freefont/FreeSerifItalic.ttf", 40) if hand else font("dejavu/DejaVuSans.ttf", 33)
    mono = font("dejavu/DejaVuSansMono.ttf", 33)
    head = font("dejavu/DejaVuSans-Bold.ttf", 44)
    small = font("dejavu/DejaVuSans.ttf", 26)

    def text(xy, s, f, fill=ink, jitter=False):
        if not jitter:
            d.text(xy, s, font=f, fill=fill)
            return
        x, y = xy
        for ch in s:  # slightly uneven baseline and spacing to look hand-written
            d.text((x, y + rnd.randint(-3, 3)), ch, font=f, fill=fill)
            x += d.textlength(ch, font=f) + rnd.uniform(-0.5, 1.2)

    # letterhead
    d.rectangle([0, 0, W, 190], fill=(226, 236, 234) if not hand else paper)
    hsize = 44
    while d.textlength(spec["clinic"], font=font("dejavu/DejaVuSans-Bold.ttf", hsize)) > W - 120:
        hsize -= 2
    head = font("dejavu/DejaVuSans-Bold.ttf", hsize)
    text((60, 40), spec["clinic"], head, fill=(10, 80, 96) if not hand else ink)
    text((60, 105), spec["doctor"], small)
    text((60, 140), spec["reg"], small)
    d.line([60, 205, W - 60, 205], fill=(90, 90, 90), width=3)

    text((60, 235), f"Date: {spec['date']}", body, jitter=hand)
    text((620, 235), f"Age/Sex: {spec['age_sex']}", body, jitter=hand)
    text((60, 300), f"Patient: {spec['patient']}", body, jitter=hand)
    if spec["cnic"]:
        text((60, 365), f"CNIC: {spec['cnic']}", body, jitter=hand)
    text((60, 430), f"Dx: {spec['dx']}", body, jitter=hand)
    d.line([60, 495, W - 60, 495], fill=(150, 150, 150), width=2)

    text((60, 515), "Rx", font("dejavu/DejaVuSerif-Bold.ttf", 80), fill=ink)
    y = 630
    for line in spec["rx"]:
        text((120, y), line, body if hand else mono, jitter=hand)
        y += 84
    y += 40
    text((60, y), "Advice:", body, jitter=hand)
    y += 66
    for line in spec["advice"]:
        text((120, y), "- " + line, body, jitter=hand)
        y += 62
    d.line([W - 480, H - 260, W - 80, H - 260], fill=ink, width=3)
    text((W - 470, H - 245), spec["doctor"].split(",")[0], small)
    text((60, H - 70), LABEL, font("dejavu/DejaVuSans.ttf", 20), fill=(110, 110, 110))

    # phone-photo look: tilt, uneven light, grain, slight blur
    im = im.rotate(rnd.uniform(-1.6, 1.6), resample=Image.BICUBIC, expand=False, fillcolor=(205, 200, 190))
    grad = Image.linear_gradient("L").resize((W, H)).rotate(rnd.choice([0, 90, 180, 270]))
    shade = Image.new("RGB", (W, H), (60, 55, 45))
    im = Image.composite(shade, im, grad.point(lambda v: int(v * 0.16)))
    px = im.load()
    for _ in range(W * H // 30):
        x, yy = rnd.randrange(W), rnd.randrange(H)
        r, g, b = px[x, yy]
        n = rnd.randint(-14, 14)
        px[x, yy] = (max(0, min(255, r + n)), max(0, min(255, g + n)), max(0, min(255, b + n)))
    im = im.filter(ImageFilter.GaussianBlur(0.7))
    im.save(out, "JPEG", quality=82)


# ----------------------------------------------------------------------- PDFs
def pdf(path: Path, title: str, header_lines: list[str], blocks: list[tuple[str, list[str]]]) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    w, h = A4
    y = h - 40

    def line(s, f="Helvetica", size=10, gap=15, x=40):
        nonlocal y
        if y < 60:
            c.showPage()
            y = h - 40
        c.setFont(f, size)
        c.drawString(x, y, s[:110])
        y -= gap

    c.setFont("Helvetica-Oblique", 8)
    c.drawString(40, y, LABEL)
    y -= 26
    line(title, "Helvetica-Bold", 15, 24)
    for s in header_lines:
        line(s)
    y -= 8
    for head, rows in blocks:
        y -= 6
        line(head, "Helvetica-Bold", 11, 18)
        for r in rows:
            line(r, size=10)
    c.save()


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def patient_header(p: dict, inst: str) -> list[str]:
    dm = p["demographics"]
    return [f"Patient: {dm['name']}    Sex: {dm['sex']}    DOB: {dm['dob']} ({dm['age']} y)",
            f"Local ID at this institution: {p['local_ids'].get(inst) or 'n/a'}    CNIC: {dm['cnic']}",
            f"Institution: {INSTITUTIONS[inst]}"]


def lab_pdfs(p: dict) -> None:
    labs = p["sources"].get("lab-b", {}).get("labs", [])
    by_date: dict[str, list[dict]] = {}
    for item in labs:
        by_date.setdefault(item["date"], []).append(item)
    for date, panels in by_date.items():
        blocks = []
        for panel in panels:
            rows = [f"{'Test':<30}{'Result':<16}{'Unit':<16}{'Reference':<16}Flag"]
            for r in panel["results"]:
                rows.append(f"{r['test']:<30}{str(r['value']):<16}{r['unit']:<16}{r['reference']:<16}{r['flag'].upper()}")
            if panel.get("note"):
                rows.append(f"Note: {panel['note']}")
            blocks.append((panel["panel"], rows))
        hdr = patient_header(p, "lab-b") + [f"Collected / reported: {date}", "Report status: final"]
        pdf(DOCS / f"{p['key']}_lab_report_{date}.pdf", "Laboratory Report", hdr, blocks)


def imaging_pdfs(p: dict) -> None:
    for rad in [k for k in p["sources"] if k.startswith("rad-")]:
        for item in p["sources"][rad].get("imaging", []):
            wrap, cur = [], ""
            for wd in item["findings"].split():
                if len(cur) + len(wd) > 95:
                    wrap.append(cur)
                    cur = ""
                cur += wd + " "
            wrap.append(cur)
            hdr = patient_header(p, rad) + [f"Study date: {item['date']}", f"Study: {item['study']}", f"Body part: {item['body_part']}"]
            pdf(DOCS / f"{p['key']}_radiology_report_{item['date']}_{slug(item['study'])[:24]}.pdf",
                "Radiology Report", hdr,
                [("Findings", wrap), ("Impression", [item["impression"]]), ("Reported by", [item["radiologist"]]),
                 ("Note", ["Report only. The image file itself is not included in this synthetic dataset."])])


def discharge_summary() -> None:
    p = next(x for x in PATIENTS if x["key"] == "P2")
    hdr = patient_header(p, "aku") + ["Admission / discharge: 30-08-2026 (emergency department, same day)"]
    pdf(DOCS / "P2_discharge_summary_AKUH_2026-08-31.pdf", "Emergency Department Discharge Summary", hdr, [
        ("Presenting complaint", ["Central chest pain at rest for about 40 minutes, no radiation, no sweating."]),
        ("Investigations", ["ECG: normal sinus rhythm, no ST change.", "Troponin I: negative at 0 and 3 hours.", "Chest examination normal. BP 146/90, pulse 78."]),
        ("Impression", ["Chest pain, likely musculoskeletal. Cardiac cause not fully excluded."]),
        ("Medicines on discharge (as recorded by the ED)", [
            "Metformin 500 mg twice daily",
            "Aspirin 75 mg once daily",
            "Atorvastatin 20 mg once daily",
            "Omeprazole 20 mg once daily for 2 weeks"]),
        ("Advice", ["Review with your physician within one week.", "Return immediately if pain returns at rest or lasts more than 15 minutes."]),
        ("Doctor", ["Dr Nida Iqbal, Medical Officer, Aga Khan University Hospital"]),
    ])


# ------------------------------------------------------------------------ JSON
def patient_json(p: dict) -> dict:
    out = {k: p[k] for k in ("key", "department", "demographics", "local_ids", "referral", "brought_by_patient", "sources", "scenario")}
    out["_meta"] = {"synthetic": True, "reference_date": TODAY, "recent_window_start": SIX_MONTHS_AGO,
                    "institutions": {k: INSTITUTIONS[k] for k in INSTITUTIONS if k in p["sources"] or k in p["local_ids"] or k == p["referral"]["from_institution"]}}
    # What the platform should show by default, so the seed doubles as an expected-result file
    rec = {"conditions": [], "surgeries": [], "visits_last_6_months": [], "current_medications": []}
    for inst, s in p["sources"].items():
        for c in s.get("conditions", []):
            rec["conditions"].append({**c, "source": inst})
        for sx in s.get("surgeries", []):
            rec["surgeries"].append({**sx, "source": inst})
        for v in s.get("visits", []):
            if v["date"] >= SIX_MONTHS_AGO:
                rec["visits_last_6_months"].append({**v, "source": inst})
        for m in s.get("medications", []):
            if m["status"] == "active":
                rec["current_medications"].append({**m, "source": inst})
    rec["visits_last_6_months"].sort(key=lambda v: v["date"], reverse=True)
    out["expected_retrieval_view"] = rec
    return out


def main() -> None:
    index = []
    for p in PATIENTS:
        name = slug(p["demographics"]["name"])
        (PATS / f"{p['key']}_{name}.json").write_text(json.dumps(patient_json(p), indent=2, ensure_ascii=False) + "\n")
        lab_pdfs(p)
        imaging_pdfs(p)
        dm, r = p["demographics"], p["referral"]
        index.append({"key": p["key"], "name": dm["name"], "age": dm["age"], "sex": dm["sex"], "city": dm["city"],
                      "referral_from": INSTITUTIONS[r["from_institution"]], "referral_to": f"{INSTITUTIONS[r['to_institution']]} / {r['to_department']}",
                      "planned_procedure": r["planned_procedure"], "should_flag": p["scenario"]["should_flag"]})
    (HERE / "index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n")
    discharge_summary()
    for i, (fn, spec) in enumerate(PRESCRIPTIONS.items()):
        draw_prescription(spec, DOCS / fn, seed=100 + i)
    print("patients:", len(PATIENTS), "documents:", len(list(DOCS.iterdir())))


if __name__ == "__main__":
    main()
