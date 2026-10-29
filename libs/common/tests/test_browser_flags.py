"""The browser's Layer 1 medication-flag library (web/src/features/e2e/flags.ts), run under Node on a synthetic
bundle (spec v4 9.1, T-FLAG-1), and the repository holds no drug-procedure table (T-FLAG-2)."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is not installed")
def test_layer1_library():
    run = subprocess.run(["node", str(ROOT / "web" / "scripts" / "flags-check.ts")], capture_output=True, text=True,
                         timeout=120, cwd=ROOT)
    assert run.returncode == 0, run.stderr[-800:]
    checks = json.loads(run.stdout.strip().splitlines()[-1])
    failed = [k for k, v in checks.items() if not v]
    assert not failed and len(checks) >= 12, failed


def test_no_drug_procedure_table_in_rules_or_code():
    """No rule file pairs a medicine or drug class with a procedure, and no code or test carries such a list. The
    evaluation benchmark (evaluation/, clearly a synthetic test set, never loaded at runtime) is excluded."""
    assert not (ROOT / "rules" / "medication" / "seed-rules.json").exists()
    labels = json.loads((ROOT / "rules" / "labels" / "label-rules.json").read_text(encoding="utf-8"))
    assert not [r for r in labels["rules"] if r.get("kind") == "drug_procedure"]

    def pairs_drug_with_procedure(node) -> bool:
        """An object naming a medicine (ingredient or drug class) together with procedures."""
        if isinstance(node, dict):
            drug = {"drug_class", "ingredient", "ingredients", "drug"} & set(node)
            proc = {"procedure_tags", "procedure", "procedures"} & set(node) or node.get("kind") == "drug_procedure"
            return bool(drug and proc) or any(pairs_drug_with_procedure(v) for v in node.values())
        return isinstance(node, list) and any(pairs_drug_with_procedure(v) for v in node)

    offenders = [str(p.relative_to(ROOT)) for p in ROOT.glob("rules/**/*.json")
                 if pairs_drug_with_procedure(json.loads(p.read_text(encoding="utf-8")))]
    code = re.compile(r'kind\s*=\s*"drug_procedure"|"kind":\s*"drug_procedure"|seed-rules\.json|"RULE-0\d\d"')
    for path in [*ROOT.glob("services/**/*.py"), *ROOT.glob("web/src/**/*.ts*"), *ROOT.glob("tests/**/*.py"),
                 *ROOT.glob("scripts/**/*.py")]:
        if "migrations" in path.parts:
            continue
        if code.search(path.read_text(encoding="utf-8", errors="ignore")):
            offenders.append(str(path.relative_to(ROOT)))
    assert not offenders, offenders
