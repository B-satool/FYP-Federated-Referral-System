"""Fill RxNorm ingredient codes (RxCUI) and WHO ATC codes into rules/terminology/ingredients.json.

Run by a person (needs internet); the application never calls RxNav.
  python scripts/build_ingredient_codes.py

Source: US NLM RxNav REST API (RxNorm, and RxClass for ATC). Free; see https://lhncbc.nlm.nih.gov/RxNav/
Ingredients not marketed in the US may have no RxNorm code; that is recorded, not guessed.
"""
from __future__ import annotations

import json
import time
from datetime import date
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "rules" / "terminology" / "ingredients.json"
SOURCES = ROOT / "rules" / "sources.json"
RXNAV = "https://rxnav.nlm.nih.gov/REST"


def rxcui(client: httpx.Client, name: str) -> str | None:
    r = client.get(f"{RXNAV}/rxcui.json", params={"name": name, "search": 2})
    ids = (r.json().get("idGroup") or {}).get("rxnormId") or []
    return ids[0] if ids else None


def atc(client: httpx.Client, name: str) -> list[str]:
    r = client.get(f"{RXNAV}/rxclass/class/byDrugName.json", params={"drugName": name, "relaSource": "ATC"})
    items = ((r.json().get("rxclassDrugInfoList") or {}).get("rxclassDrugInfo")) or []
    return sorted({i["rxclassMinConceptItem"]["classId"] for i in items})


def main() -> None:
    data = json.loads(FILE.read_text(encoding="utf-8"))
    missing = []
    with httpx.Client(timeout=30) as client:
        for ing in data["ingredients"]:
            if ing.get("components"):
                continue
            query = ing.get("label_name") or ing["standard"]
            ing["rxnorm_id"] = rxcui(client, query) or rxcui(client, ing["standard"])
            ing["atc_codes"] = atc(client, query) or atc(client, ing["standard"])
            if not ing["rxnorm_id"]:
                missing.append(ing["name"])
            time.sleep(0.1)  # RxNav asks for at most 20 requests per second
    data["codes_retrieved"] = date.today().isoformat()
    FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    src = json.loads(SOURCES.read_text(encoding="utf-8"))
    src["rxnav"]["retrieved"] = data["codes_retrieved"]
    SOURCES.write_text(json.dumps(src, indent=2) + "\n", encoding="utf-8")
    print(f"{len(data['ingredients'])} ingredients; no RxNorm code for: {', '.join(missing) or 'none'}")


if __name__ == "__main__":
    main()
