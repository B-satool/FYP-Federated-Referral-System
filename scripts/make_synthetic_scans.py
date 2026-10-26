"""Draws synthetic 'scan' images for testing report uploads (not real images of anyone).

Run inside the central image, which has Pillow:
  docker compose run --rm --no-deps -v ${PWD}/seed-data:/out -v ${PWD}/scripts:/scripts central python /scripts/make_synthetic_scans.py /out/documents/imaging
"""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

LABEL = "SYNTHETIC TEST IMAGE - NOT A REAL SCAN"


def _base(seed: int) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    random.seed(seed)
    img = Image.new("L", (512, 512), 0)
    return img, ImageDraw.Draw(img)


def knee_mri(path: Path) -> None:
    img, d = _base(1)
    d.ellipse((140, 40, 372, 250), fill=150)    # femur
    d.ellipse((150, 270, 362, 480), fill=140)   # tibia
    d.rectangle((150, 240, 362, 280), fill=60)  # joint space
    d.arc((170, 225, 340, 300), 200, 340, fill=220, width=6)  # meniscus
    for _ in range(4000):
        x, y = random.randrange(512), random.randrange(512)
        d.point((x, y), fill=random.randrange(0, 60))
    img = img.filter(ImageFilter.GaussianBlur(2))
    ImageDraw.Draw(img).text((10, 490), LABEL, fill=255)
    img.save(path)


def mrcp(path: Path) -> None:
    img, d = _base(2)
    d.ellipse((60, 80, 300, 360), fill=70)  # liver
    pts = [(260 + 40 * math.sin(t / 10), 120 + t * 3) for t in range(90)]
    d.line(pts, fill=230, width=7)          # bile duct
    d.ellipse((300, 220, 380, 330), fill=200)  # gallbladder
    for cx, cy in ((330, 280), (345, 300), (320, 300)):
        d.ellipse((cx - 8, cy - 8, cx + 8, cy + 8), fill=40)  # stones
    img = img.filter(ImageFilter.GaussianBlur(1.5))
    ImageDraw.Draw(img).text((10, 490), LABEL, fill=255)
    img.save(path)


def chest_xray(path: Path) -> None:
    img, d = _base(3)
    d.rectangle((0, 0, 512, 512), fill=200)
    d.ellipse((90, 90, 240, 430), fill=60)
    d.ellipse((270, 90, 420, 430), fill=60)
    d.ellipse((220, 230, 330, 400), fill=190)  # heart
    for i in range(8):
        d.arc((70, 80 + i * 40, 440, 200 + i * 40), 190, 350, fill=230, width=4)  # ribs
    img = img.filter(ImageFilter.GaussianBlur(2))
    ImageDraw.Draw(img).text((10, 490), LABEL, fill=0)
    img.save(path)


if __name__ == "__main__":
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    knee_mri(out / "synthetic_mri-knee-coronal.png")
    mrcp(out / "synthetic_mrcp-coronal.png")
    chest_xray(out / "synthetic_chest-x-ray-pa.png")
    print("written to", out)
