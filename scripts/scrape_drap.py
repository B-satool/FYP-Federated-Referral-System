"""Build a local snapshot of the DRAP product register from its public search pages.

Run by a person; the app never calls DRAP. The team agreed this on 2026-10-28
(docs/decisions/2026-10-28-drap-register-snapshot.md) because the DRAP search page is
sometimes down and the formal data request has not been answered yet.

  python scripts/scrape_drap.py list                   # every product: brand, generic names, company, reg. no.
  python scripts/scrape_drap.py details [--all] [--limit N]
                                                     # composition, strength, dosage form, route, status;
                                                     # only products made entirely of our ingredients unless
                                                     # --all; resumes where it stopped
  python scripts/scrape_drap.py details --common --total 2000
                                                     # instead: one product per brand, most common
                                                     # medicines first, until 2000 records in total
  python scripts/scrape_drap.py export                 # rows for scripts/import_brands.py

Writes rules/terminology/drap/:
  products.csv       one row per registered product (from the generic-name search)
  details.jsonl      one JSON object per product page fetched
  drugs.csv          every fetched product for human use: brand, generic names, strength, form, route
  brand-import.csv   products whose every ingredient is one of ours, in the import_brands.py format,
                     with checked_by left empty: a clinical reviewer checks each row before --write

Requests are spaced by --delay seconds (default 2) and retried with backoff, because the site drops
connections. Nothing here is a verified mapping until a reviewer has checked it (AGENTS.md 3 and 5).
"""
from __future__ import annotations

import csv
import html
import json
import re
import string
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INGREDIENTS = ROOT / "rules" / "terminology" / "ingredients.json"
NAMES = ROOT / "rules" / "terminology" / "medicine-names.pk.json"
OUT = ROOT / "rules" / "terminology" / "drap"
PRODUCTS = OUT / "products.csv"
DETAILS = OUT / "details.jsonl"
EXPORT = OUT / "brand-import.csv"
DRUGS = OUT / "drugs.csv"
DRUG_FIELDS = ["brand_name", "product_name", "generic_names", "strength", "dosage_form", "route", "company",
               "drap_reg_no", "retrieved_on"]

BASE = "https://eapp.dra.gov.pk/"
USER_AGENT = "FYP referral project register snapshot (academic, rate-limited)"
PRODUCT_FIELDS = ["product_id", "registration_no", "brand_name", "generic_names", "company", "retrieved_on"]
IMPORT_FIELDS = ["brand_name", "ingredients", "strength", "dosage_form", "drug_class", "company", "drap_reg_no",
                 "source", "retrieved_on", "checked_by"]
DETAIL_LABELS = {
    "Registration Date": "registration_date", "Used For": "used_for", "Product Category": "category",
    "Dosage Form": "dosage_form", "Route of Admin": "route", "Manufacturing Type": "manufacturing_type",
    "Variation Status": "variation_status",
}


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text))).strip()


def _request(path: str, data: dict | None, delay: float, tries: int = 6) -> str:
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    req = urllib.request.Request(BASE + path, data=body, headers={"User-Agent": USER_AGENT})
    for attempt in range(tries):
        time.sleep(delay if attempt == 0 else delay * 2 ** attempt)
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return resp.read().decode("utf-8-sig", errors="replace")
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            print(f"  retry {attempt + 1}/{tries - 1} for {path}: {exc}", file=sys.stderr)
    raise SystemExit(f"DRAP did not answer {path} after {tries} tries; run the same command again later")


def _generic_list(raw: str) -> list[str]:
    # DRAP separates combination parts with ", <br>"
    return [p for p in (_clean(x).lower().rstrip(",").strip() for x in re.split(r"<br\s*/?>", raw)) if p]


def cmd_list(delay: float) -> None:
    # The generic-name lookup matches substrings, so one letter or digit per request covers every product.
    products: dict[str, dict] = {}
    today = date.today().isoformat()
    for term in string.ascii_lowercase + string.digits:
        rows = json.loads(_request("productView.php", {"masterID": term}, delay) or "[]")
        new = 0
        for r in rows:
            if r["id"] not in products:
                new += 1
                products[r["id"]] = {
                    "product_id": r["id"], "registration_no": (r.get("registrationNo") or "").strip(),
                    "brand_name": _clean(r.get("approvedName") or ""),
                    "generic_names": "; ".join(_generic_list(r.get("genericName") or "")),
                    "company": _clean(r.get("companyName") or ""), "retrieved_on": today,
                }
        print(f"  '{term}': {len(rows)} rows, {new} new, {len(products)} total")
    OUT.mkdir(parents=True, exist_ok=True)
    with PRODUCTS.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=PRODUCT_FIELDS)
        w.writeheader()
        w.writerows(sorted(products.values(), key=lambda p: (p["brand_name"].lower(), p["registration_no"])))
    print(f"{len(products)} products written to {PRODUCTS.relative_to(ROOT)}")


def _our_names() -> dict[str, str]:
    """Every spelling we know for a single ingredient (lower case) -> our ingredient name.

    Combinations are left out: a DRAP component is one substance and must never map to a combination.
    """
    names: dict[str, str] = {}
    combos = set()
    for i in json.loads(INGREDIENTS.read_text(encoding="utf-8"))["ingredients"]:
        if i.get("components"):
            combos.add(i["name"])
            continue
        for n in (i["name"], i.get("standard"), i.get("label_name")):
            if n:
                names[n.lower()] = i["name"]
    for e in json.loads(NAMES.read_text(encoding="utf-8"))["entries"]:
        if e["ingredient"] in combos:
            continue
        for g in e.get("generic", []):
            names.setdefault(g.lower(), e["ingredient"])
    return names


# Words DRAP adds after the substance name that do not change which substance it is.
SALT_WORDS = set("""
sodium potassium calcium magnesium hcl hydrochloride hydrobromide besylate besilate maleate mesylate mesilate
sulphate sulfate phosphate citrate tartrate succinate fumarate acetate bromide chloride trihydrate dihydrate
monohydrate hemihydrate sesquihydrate anhydrous micronized micronised as eq equivalent to of bp usp ph eur base
""".split())


def _match(generic: str, ours: dict[str, str]) -> str | None:
    """Our ingredient for one DRAP component, or None.

    DRAP adds salts and forms ("warfarin sodium", "amlodipine besylate"), so the longest known leading
    name is used, but only when every remaining word is a salt or form word or a repeat of the name.
    A short spelling that is the start of a longer ingredient name ("hyoscine" for hyoscine
    butylbromide) must match exactly, so "hyoscine hydrobromide" is not taken for it.
    """
    words = re.sub(r"[^a-z0-9 ]", " ", generic.lower()).split()
    for n in range(len(words), 0, -1):
        key = " ".join(words[:n])
        hit = ours.get(key)
        if not hit:
            continue
        rest = words[n:]
        if not rest:
            return hit
        if hit.lower() != key and hit.lower().startswith(key + " "):
            return None
        if all(w in SALT_WORDS or w in words[:n] or any(ch.isdigit() for ch in w) for w in rest):
            return hit
        return None
    return None


FORM_WORDS = set("""
tablet tablets tab tabs capsule capsules cap caps injection inj infusion syrup suspension susp solution
cream ointment gel drops drop sachet sachets powder inhaler suppository suppositories lotion spray
granules vial ampoule elixir emulsion chewable dispersible effervescent film coated
oral liquid dry eye ear nasal topical water soluble iv im
""".split())


def _base_brand(name: str) -> str:
    """'Coagurin 5mg Tablets' -> 'Coagurin'; 'Panadol Extra 500mg' -> 'Panadol Extra'."""
    kept = []
    tokens = re.sub(r"\(.*?\)|\[.*?\]", " ", name).strip(" '\".:;,-*").split()
    for n, tok in enumerate(tokens):
        # the first word is always the brand, even when it has digits ("20-OSB", "3D")
        if n and (any(ch.isdigit() for ch in tok) or tok.lower().strip(".,-") in FORM_WORDS):
            break
        kept.append(tok)
    base = " ".join(kept).strip(" -,.")
    return base.title() if base.isupper() and len(base) > 4 and not any(ch.isdigit() for ch in base) else base


def _parse_detail(page: str) -> dict:
    out: dict = {}
    for label, value in re.findall(r'record-label">(.*?)</div>\s*<div class="record-value">(.*?)</div>', page, re.S):
        key = DETAIL_LABELS.get(_clean(label))
        if key:
            out[key] = _clean(value)
    m = re.search(r"<h6>Composition</h6>.*?<tbody>(.*?)</tbody>", page, re.S)
    out["composition"] = []
    for row in re.findall(r"<tr>(.*?)</tr>", m.group(1) if m else "", re.S):
        cells = [_clean(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        if len(cells) >= 4:
            out["composition"].append({"generic": cells[0].lower(), "operator": cells[1], "strength": cells[2],
                                       "unit": cells[3]})
    return out


def _products() -> list[dict]:
    if not PRODUCTS.exists():
        sys.exit("Run 'list' first")
    with PRODUCTS.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


VET_HINTS = re.compile(r"\b(vet|veterinary|poultry|broiler|cattle|livestock|calves|sheep|goats?|equine|canine|feline)\b", re.I)


def _common_first(products: list[dict], done: set[str]) -> list[dict]:
    """One product per brand, most common medicines first.

    A medicine is as common as the number of companies registering it; within a medicine, brands with
    more registrations (strengths, forms) come first. Medicines take turns, so the list covers many
    medicines before it goes deep into any one. Names that look veterinary are left out here; the
    detail page then says for certain (export drops non-human products).
    """
    def medicine(generic_names: str) -> str:
        # "ciprofloxacin (as hcl)" and "ciprofloxacin" are the same medicine
        parts = []
        for g in generic_names.split("; "):
            words = re.sub(r"\(.*?\)|[^a-z ]", " ", g.lower()).split()
            parts.append(" ".join(w for w in words if w not in SALT_WORDS) or g)
        return "; ".join(sorted(set(parts)))

    companies: dict[str, set] = {}
    brands: dict[tuple[str, str], list[dict]] = {}
    for p in products:
        generic = medicine(p["generic_names"])
        companies.setdefault(generic, set()).add(p["company"].lower())
        brand = _base_brand(p["brand_name"]).lower()
        if brand and p["registration_no"]:
            brands.setdefault((generic, brand), []).append(p)
    fetched = {k for k, ps in brands.items() if any(p["registration_no"] in done for p in ps)}
    per_generic: dict[str, list[list[dict]]] = {}
    for key, ps in brands.items():
        if key not in fetched and not any(VET_HINTS.search(p["brand_name"]) for p in ps):
            per_generic.setdefault(key[0], []).append(ps)
    for generic, lists in per_generic.items():
        # real brand names before products named after the medicine itself ("Paracetamol 500mg")
        names = set(generic.replace(";", " ").split())
        lists.sort(key=lambda ps: (bool(set(_base_brand(ps[0]["brand_name"]).lower().split()) & names), -len(ps)))
    order = sorted(per_generic, key=lambda g: -len(companies[g]))
    out, depth = [], 0
    while any(depth < len(per_generic[g]) for g in order):
        out.extend(per_generic[g][depth][0] for g in order if depth < len(per_generic[g]))
        depth += 1
    return out


def cmd_details(delay: float, everything: bool, limit: int | None, common: bool = False, total: int | None = None) -> None:
    ours = _our_names()
    done = set()
    if DETAILS.exists():
        done = {json.loads(line)["registration_no"] for line in DETAILS.read_text(encoding="utf-8").splitlines() if line}
    if common:
        todo = _common_first(_products(), done)
    else:
        todo = [p for p in _products() if p["registration_no"] and p["registration_no"] not in done
                and (everything or all(_match(g, ours) for g in p["generic_names"].split("; ")))]
    if total is not None:
        limit = max(0, total - len(done)) if limit is None else min(limit, max(0, total - len(done)))
    todo = todo[:limit] if limit is not None else todo
    print(f"{len(done)} already fetched, {len(todo)} to fetch (about {len(todo) * delay / 60:.0f} min)")
    with DETAILS.open("a", encoding="utf-8") as fh:
        for n, p in enumerate(todo, 1):
            page = _request("product_view_web.php?" + urllib.parse.urlencode({"reg_no": p["registration_no"]}), None, delay)
            record = {"registration_no": p["registration_no"], "product_id": p["product_id"],
                      "retrieved_on": date.today().isoformat(), **_parse_detail(page)}
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            fh.flush()
            if n % 50 == 0:
                print(f"  {n}/{len(todo)}")
    print(f"Details in {DETAILS.relative_to(ROOT)}")


def cmd_export() -> None:
    ours = _our_names()
    details = {}
    if DETAILS.exists():
        for line in DETAILS.read_text(encoding="utf-8").splitlines():
            if line:
                d = json.loads(line)
                details[d["registration_no"]] = d
    # One row per base brand and ingredient set; strengths, forms, companies and reg. nos are merged.
    groups: dict[tuple[str, str], dict] = {}
    partial = not_human = unchecked = 0
    for p in _products():
        d = details.get(p["registration_no"], {})
        if d.get("used_for") and d["used_for"].lower() != "human":
            not_human += 1
            continue
        comp = d.get("composition") or [{"generic": g, "strength": "", "unit": ""} for g in p["generic_names"].split("; ") if g]
        matched = [_match(c["generic"], ours) for c in comp]
        brand = _base_brand(p["brand_name"])
        if not brand or not matched or None in matched:
            partial += any(matched)
            continue
        unchecked += not d
        ingredients = ";".join(sorted(set(matched)))
        g = groups.setdefault((brand.lower(), ingredients), {
            "brand_name": brand, "ingredients": ingredients, "strength": [], "dosage_form": [], "company": [],
            "drap_reg_no": [], "retrieved_on": [],
        })
        strength = " + ".join(f"{c['strength']} {c['unit']}".strip() for c in comp if c.get("strength"))
        for key, value in (("strength", strength), ("dosage_form", (d.get("dosage_form") or "").lower()),
                           ("company", p["company"]), ("drap_reg_no", p["registration_no"]),
                           ("retrieved_on", d.get("retrieved_on") or p["retrieved_on"])):
            if value and value not in g[key]:
                g[key].append(value)
    rows = [{**g, "strength": "; ".join(g["strength"]), "dosage_form": "; ".join(g["dosage_form"]),
             "company": "; ".join(g["company"]), "drap_reg_no": "; ".join(g["drap_reg_no"]),
             "retrieved_on": min(g["retrieved_on"]), "drug_class": "",
             "source": "DRAP product register web search", "checked_by": ""}
            for g in sorted(groups.values(), key=lambda g: (g["brand_name"].lower(), g["ingredients"]))]
    # The drugs list: every product whose details were fetched and that is for human use.
    products = {p["registration_no"]: p for p in _products()}
    drugs = []
    for reg, d in details.items():
        p = products.get(reg)
        if not p or (d.get("used_for") or "").lower() != "human":
            continue
        comp = d.get("composition") or []
        drugs.append({
            "brand_name": _base_brand(p["brand_name"]) or p["brand_name"], "product_name": p["brand_name"],
            "generic_names": "; ".join(c["generic"] for c in comp) or p["generic_names"],
            "strength": " + ".join(f"{c['strength']} {c['unit']}".strip() for c in comp if c.get("strength")),
            "dosage_form": d.get("dosage_form", ""), "route": d.get("route", ""), "company": p["company"],
            "drap_reg_no": reg, "retrieved_on": d.get("retrieved_on", ""),
        })
    drugs.sort(key=lambda r: (r["brand_name"].lower(), r["strength"]))
    with DRUGS.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=DRUG_FIELDS)
        w.writeheader()
        w.writerows(drugs)
    print(f"{len(drugs)} human medicines with brand, generic and strength written to {DRUGS.relative_to(ROOT)}")
    clashes = {}
    for r in rows:
        clashes.setdefault(r["brand_name"].lower(), set()).add(r["ingredients"])
    clashes = {b: s for b, s in clashes.items() if len(s) > 1}
    with EXPORT.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=IMPORT_FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} brands with only our ingredients written to {EXPORT.relative_to(ROOT)}; "
          f"{partial} products skipped because a part is not one of our ingredients, {not_human} veterinary or "
          f"other non-human products skipped")
    if unchecked:
        print(f"{unchecked} products have no details yet, so they may be veterinary: run 'details' before importing")
    if clashes:
        print(f"{len(clashes)} brand names map to more than one ingredient set; import_brands.py will refuse the "
              f"second one, so a reviewer must choose:")
        for b, s in sorted(clashes.items())[:20]:
            print(f"  {b}: {' | '.join(sorted(s))}")
    print("A reviewer fills checked_by before: python scripts/import_brands.py rules/terminology/drap/brand-import.csv --write")


def _opt(args: list[str], name: str, default: str | None) -> str | None:
    return args[args.index(name) + 1] if name in args else default


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] not in ("list", "details", "export"):
        sys.exit(__doc__)
    wait = float(_opt(args, "--delay", "2"))
    if args[0] == "list":
        cmd_list(wait)
    elif args[0] == "details":
        lim, tot = _opt(args, "--limit", None), _opt(args, "--total", None)
        cmd_details(wait, "--all" in args, int(lim) if lim else None, "--common" in args, int(tot) if tot else None)
    else:
        cmd_export()
