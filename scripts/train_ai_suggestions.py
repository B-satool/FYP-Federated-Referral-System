"""Offline AI suggestion layer (spec v2, section 8): possible drug-drug clashes with no DDInter entry.

Run by a person; the application only loads the output files and never runs a model.
  python scripts/train_ai_suggestions.py codes <DDInter folder>   # ATC classes for every DDInter drug (RxNav)
  python scripts/train_ai_suggestions.py train <DDInter folder>   # train, evaluate, write suggestions

Method (kept small enough to explain):
* Each drug is described by its WHO ATC classes.
* A pair (A, B) gets symmetric features: shared ATC level 1/3/4 class, how often A's class-mates
  interact with B (and B's with A) in the known interaction graph, how many interactions each drug
  has, and which ATC main groups are involved.
* Logistic regression. Positives are known DDInter interactions. Pairs absent from DDInter are
  unlabelled, not negatives: a random sample of them is used as the background class (PU learning).
* Evaluation holds out 20% of known interactions (and the same share of unlabelled pairs) and
  computes the class-mate features from the training interactions only. Recall is reported on the
  held-out interactions, by severity, and "suggestions per 100 not in DDInter" on held-out unlabelled
  pairs. The latter are not proven false: DDInter itself is incomplete.
* The final model is trained on all known interactions, then scores every pair among this project's
  ingredients that has NO DDInter entry. Pairs above the threshold become suggestions, each with the
  two ingredient names, a score and a one-line reason built from the features.

Output (rules/ai/): ddinter-atc.json, model.json, evaluation.json, suggestions.json.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import random
import sys
import time
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "rules" / "ai"
INGREDIENTS = ROOT / "rules" / "terminology" / "ingredients.json"
RXNAV = "https://rxnav.nlm.nih.gov/REST"
MODEL_VERSION = "ddi-suggest-logreg/1.0"
SEED = 20261027
ATC1 = "ABCDGHJLMNPRSV"


# ---------------------------------------------------------------- data
def load_pairs(folder: Path) -> tuple[dict[tuple[str, str], str], str]:
    pairs: dict[tuple[str, str], str] = {}
    files = sorted(folder.glob("ddinter_downloads_code_*.csv"))
    for f in files:
        with f.open(encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                a, b = r["Drug_A"].lower(), r["Drug_B"].lower()
                if a != b:
                    pairs.setdefault(tuple(sorted((a, b))), r["Level"])
    digest = hashlib.sha256(b"".join(f.read_bytes() for f in files)).hexdigest()
    return pairs, digest


# Classes left out of "class-mates": combination products, and topical, eye, ear, mouth and skin
# preparations (they would make unrelated drugs look alike, e.g. a vaginal ibuprofen class).
TOPICAL = ("D", "S", "A01", "G01", "G02", "R01", "R02", "C05", "M02")


def systemic(atc: dict[str, list[str]]) -> dict[str, list[str]]:
    names = json.loads((OUT / "atc-class-names.json").read_text(encoding="utf-8"))
    keep = lambda c: not c.startswith(TOPICAL) and "combination" not in names.get(c, "").lower()  # noqa: E731
    return {d: [c for c in cs if keep(c)] for d, cs in atc.items()}


def class_names() -> None:
    import httpx

    r = httpx.get(f"{RXNAV}/rxclass/allClasses.json", params={"classTypes": "ATC1-4"}, timeout=60)
    items = r.json()["rxclassMinConceptList"]["rxclassMinConcept"]
    names = {i["classId"]: i["className"] for i in items}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "atc-class-names.json").write_text(json.dumps(names, indent=0, sort_keys=True), encoding="utf-8")
    print(f"{len(names)} ATC class names")


def codes(folder: Path) -> None:
    import httpx

    from concurrent.futures import ThreadPoolExecutor

    class_names()
    pairs, _ = load_pairs(folder)
    drugs = sorted({d for p in pairs for d in p})
    path = OUT / "ddinter-atc.json"

    def lookup(client, d):
        time.sleep(0.4)  # 8 workers stay under RxNav's 20 requests per second
        try:
            return d, single_ingredient_atc(client, d)
        except Exception as exc:  # noqa: BLE001 - keep going; a missing code is recorded as none
            print(f"{d}: {exc}")
            return d, []

    with httpx.Client(timeout=30) as client, ThreadPoolExecutor(max_workers=8) as pool:
        known = dict(pool.map(lambda d: lookup(client, d), drugs))
    OUT.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(known, indent=0, sort_keys=True), encoding="utf-8")
    print(f"ATC codes for {sum(1 for v in known.values() if v)} of {len(drugs)} DDInter drugs")


def single_ingredient_atc(client, name: str) -> list[str]:
    """ATC classes the drug has on its own (RxClass term type IN), not via a combination product (MIN)."""
    r = client.get(f"{RXNAV}/rxclass/class/byDrugName.json", params={"drugName": name, "relaSource": "ATC"})
    items = ((r.json().get("rxclassDrugInfoList") or {}).get("rxclassDrugInfo")) or []
    return sorted({x["rxclassMinConceptItem"]["classId"] for x in items if x.get("minConcept", {}).get("tty") == "IN"})


# ---------------------------------------------------------------- features
class Graph:
    def __init__(self, positives: set[tuple[str, str]], atc: dict[str, list[str]]):
        self.nbr: dict[str, set[str]] = defaultdict(set)
        for a, b in positives:
            self.nbr[a].add(b)
            self.nbr[b].add(a)
        self.atc = atc
        self.members: dict[str, set[str]] = defaultdict(set)  # ATC prefix -> drugs
        for d, cs in atc.items():
            for c in cs:
                for n in (1, 3, 4, 5):
                    self.members[c[:n]].add(d)

    def classes(self, d: str, n: int) -> set[str]:
        return {c[:n] for c in self.atc.get(d, []) if len(c) >= n}

    def classmate_rate(self, a: str, b: str, n: int) -> tuple[float, str | None]:
        """Share of b's class-mates (ATC level n, excluding b) that interact with a; and one example."""
        mates = set().union(*(self.members[c] for c in self.classes(b, n))) - {a, b} if self.classes(b, n) else set()
        if not mates:
            return 0.0, None
        hits = sorted(mates & self.nbr[a])
        return len(hits) / len(mates), (hits[0] if hits else None)


FEATURES = ["same_atc1", "same_atc3", "same_atc4", "mate4_max", "mate4_mean", "mate3_max", "mate3_mean",
            "deg_min", "deg_max", "no_atc"] + [f"group_{g}" for g in ATC1]


def features(g: Graph, a: str, b: str) -> list[float]:
    m4a, _ = g.classmate_rate(a, b, 4)
    m4b, _ = g.classmate_rate(b, a, 4)
    m3a, _ = g.classmate_rate(a, b, 3)
    m3b, _ = g.classmate_rate(b, a, 3)
    da, db = math.log1p(len(g.nbr[a])) / 7, math.log1p(len(g.nbr[b])) / 7
    groups = g.classes(a, 1) | g.classes(b, 1)
    return [float(bool(g.classes(a, 1) & g.classes(b, 1))), float(bool(g.classes(a, 3) & g.classes(b, 3))),
            float(bool(g.classes(a, 4) & g.classes(b, 4))), max(m4a, m4b), (m4a + m4b) / 2, max(m3a, m3b),
            (m3a + m3b) / 2, min(da, db), max(da, db), float(not g.atc.get(a) or not g.atc.get(b))] + \
        [float(x in groups) for x in ATC1]


def reason(g: Graph, a: str, b: str, class_names: dict[str, str]) -> str:
    """One line from the strongest class-mate evidence, naming the ATC class and up to two examples."""
    best = None
    for x, y in ((a, b), (b, a)):  # y's class-mates that interact with x
        for c in sorted(g.classes(y, 4)):
            mates = sorted((g.members[c] - {x, y}) & g.nbr[x])
            if mates and (best is None or len(mates) > best[0]):
                best = (len(mates), x, y, c, mates)
    if best:
        n, x, y, c, mates = best
        ex = " and ".join(mates[:2])
        return (f"{y} is in the ATC class {c} ({class_names.get(c, c).lower()}); {n} other drug(s) in that class, "
                f"for example {ex}, have recorded DDInter interactions with {x}.")
    if g.classes(a, 4) & g.classes(b, 4):
        return f"{a} and {b} are in the same drug class."
    return "Scored as similar to known interacting pairs by drug class and how many interactions each drug has."


# ---------------------------------------------------------------- model
def fit(X: list[list[float]], y: list[int]):
    from sklearn.linear_model import LogisticRegression

    model = LogisticRegression(max_iter=2000, class_weight="balanced", C=1.0)
    model.fit(X, y)
    return model


def score(model, X):
    return [float(p) for p in model.predict_proba(X)[:, 1]]


def sample_unlabelled(drugs: list[str], positives: set, n: int, rng: random.Random) -> list[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    while len(out) < n:
        a, b = rng.sample(drugs, 2)
        p = tuple(sorted((a, b)))
        if p not in positives:
            out.add(p)
    return sorted(out)


def train(folder: Path) -> None:
    pairs, digest = load_pairs(folder)
    if not (OUT / "atc-class-names.json").exists():
        class_names()
    atc = systemic(json.loads((OUT / "ddinter-atc.json").read_text(encoding="utf-8")))
    rng = random.Random(SEED)
    positives = sorted(pairs)
    drugs = sorted({d for p in positives for d in p})

    # --- evaluation split
    held = set(rng.sample(positives, len(positives) // 5))
    train_pos = [p for p in positives if p not in held]
    unl = sample_unlabelled(drugs, set(positives), len(positives), rng)
    held_unl = set(unl[: len(unl) // 5])
    train_unl = unl[len(unl) // 5:]
    g = Graph(set(train_pos), atc)  # class-mate features from training interactions only
    sub = rng.sample(train_pos, min(len(train_pos), 60000))
    X = [features(g, a, b) for a, b in sub] + [features(g, a, b) for a, b in train_unl[:60000]]
    y = [1] * len(sub) + [0] * min(len(train_unl), 60000)
    model = fit(X, y)
    hp = score(model, [features(g, a, b) for a, b in sorted(held)])
    hu = score(model, [features(g, a, b) for a, b in sorted(held_unl)])
    thresholds = {}
    for t in (0.5, 0.6, 0.7, 0.8, 0.9):
        by_sev = {}
        for sev in ("Major", "Moderate", "Minor", "Unknown"):
            idx = [i for i, p in enumerate(sorted(held)) if pairs[p] == sev]
            by_sev[sev] = round(sum(1 for i in idx if hp[i] >= t) / len(idx), 3) if idx else None
        flagged_unl = sum(1 for s in hu if s >= t)
        flagged_pos = sum(1 for s in hp if s >= t)
        thresholds[str(t)] = {
            "recall_held_out_interactions": round(flagged_pos / len(hp), 3), "recall_by_severity": by_sev,
            "suggestions_not_in_ddinter_per_100_unlabelled_pairs": round(100 * flagged_unl / len(hu), 1),
        }
    threshold = 0.8
    evaluation = {
        "model_version": MODEL_VERSION, "trained": date.today().isoformat(), "training_data": f"DDInter 2.0 files sha256 {digest}",
        "known_interactions": len(positives), "drugs": len(drugs), "drugs_with_atc": sum(1 for d in drugs if atc.get(d)),
        "held_out_interactions": len(hp), "held_out_unlabelled_pairs": len(hu), "threshold_used": threshold,
        "by_threshold": thresholds,
        "caveats": ["Unlabelled pairs are not proven non-interacting; DDInter is incomplete, so 'not in DDInter' is not 'false'.",
                    "Trained only on DDInter, so the model mostly generalises DDInter's class patterns; it cannot find mechanisms DDInter lacks.",
                    "Drugs in one ATC group can behave differently: cimetidine and esomeprazole share group A02B, but only cimetidine "
                    "strongly inhibits liver enzymes, so class-mate evidence can overstate a clash.",
                    "Held-out unlabelled pairs are random pairs, which are easier to tell apart than the pairs a doctor actually sees.",
                    "Not a clinical accuracy figure."],
    }

    # --- final model on everything, then score our ingredients' pairs with no DDInter entry
    g_all = Graph(set(positives), atc)
    sub = rng.sample(positives, min(len(positives), 80000))
    X = [features(g_all, a, b) for a, b in sub] + [features(g_all, a, b) for a, b in unl[:80000]]
    y = [1] * len(sub) + [0] * min(len(unl), 80000)
    final = fit(X, y)
    ours = json.loads(INGREDIENTS.read_text(encoding="utf-8"))["ingredients"]
    names = {i["name"]: (i.get("standard") or i["name"]).lower() for i in ours if not i.get("components")}
    extra = {i["standard"].lower(): i.get("atc_codes", []) for i in ours if i.get("standard") and i["standard"].lower() not in atc}
    atc.update(systemic(extra))  # ingredients DDInter lacks still have ATC codes from RxNav
    g_all.atc = atc
    for d, cs in atc.items():
        for c in cs:
            for n in (1, 3, 4, 5):
                g_all.members[c[:n]].add(d)
    names_atc = json.loads((OUT / "atc-class-names.json").read_text(encoding="utf-8"))
    suggestions = []
    for a, b in ((x, y2) for x in sorted(names) for y2 in sorted(names) if x < y2):
        sa, sb = names[a], names[b]
        if tuple(sorted((sa, sb))) in pairs:
            continue  # DDInter has an entry: the verified flag comes from the table, never from the model
        s = score(final, [features(g_all, sa, sb)])[0]
        if s >= threshold:
            suggestions.append({"pair_key": f"{a}|{b}", "ingredient_a": a, "ingredient_b": b, "score": round(s, 3),
                                "reason": reason(g_all, sa, sb, names_atc).replace(sa, a).replace(sb, b)})
    data_version = f"DDInter 2.0 ({digest[:12]}), ATC via RxNav {date.today().isoformat()}"
    model_doc = {"model_version": MODEL_VERSION, "data_version": data_version, "features": FEATURES,
                 "coefficients": [round(c, 6) for c in final.coef_[0]], "intercept": round(float(final.intercept_[0]), 6),
                 "threshold": threshold, "seed": SEED}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "model.json").write_text(json.dumps(model_doc, indent=2) + "\n", encoding="utf-8")
    (OUT / "evaluation.json").write_text(json.dumps(evaluation, indent=2) + "\n", encoding="utf-8")
    (OUT / "suggestions.json").write_text(json.dumps(
        {"model_version": MODEL_VERSION, "data_version": data_version, "threshold": threshold,
         "label": "AI suggestion, unverified", "suggestions": suggestions}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evaluation["by_threshold"], indent=2))
    print(f"{len(suggestions)} suggestions among our ingredients (threshold {threshold})")


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("codes", "train"):
        sys.exit(__doc__)
    (codes if sys.argv[1] == "codes" else train)(Path(sys.argv[2]))
