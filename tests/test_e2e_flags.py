"""Spec v4 WP7: medication flags (T-FLAG-1, T-FLAG-2, T-FLAG-3).

* The data bundle is versioned and hash-checked, holds the Pakistani brand names (DRAP register, an ambiguous name
  with its products by company) and the DDInter pairs, and no drug-procedure table.
* The browser's library, run on the real bundle, flags a known pair from brand names and reports an unmapped brand
  as "could not be assessed", not "no flag".
* Ignore / Research are audited with a hash of the flag, never medicine names.
* Layer 2 (the AI) gets generic names and the procedure only; without a model it says so.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess

import pytest

from conftest import new_referral
from e2e_client import ROOT
from flows import central_python
from helpers import central, ok
from refcommon import e2e


@pytest.fixture(scope="module")
def bundle():
    return ok(central("dr.ali").get("/med-bundle"))


def test_bundle_is_hash_checked_and_has_the_brand_and_interaction_data(bundle):
    assert hashlib.sha256(e2e.canonical(bundle["content"])).hexdigest() == bundle["sha256"]
    c = bundle["content"]
    kinds = {row[4] for row in c["names"]}
    assert {"generic", "brand", "register_brand", "register_ambiguous"} <= kinds and len(c["names"]) > 4000
    glare = c["options"].get("glare")
    assert glare and len({o["ingredient"] for o in glare}) > 1 and all(o["company"] for o in glare)
    assert any({p[0], p[1]} == {"aspirin", "clopidogrel"} for p in c["interactions"])
    assert "procedure" not in json.dumps(c).lower()  # no drug-procedure table (T-FLAG-2)
    assert central("staff.ali").get("/med-bundle").status_code == 200  # reference data, not patient data


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is not installed")
def test_browser_library_on_the_real_bundle(bundle, tmp_path):
    meds = [{"id": "1", "name": "Disprin 75mg", "source": "list"}, {"id": "2", "name": "Plavix 75 mg", "source": "record"},
            {"id": "3", "name": "Zzqx Herbal Tonic", "source": "list"}, {"id": "4", "name": "Glare 80mg", "source": "list"}]
    (tmp_path / "b.json").write_text(json.dumps(bundle), encoding="utf-8")
    (tmp_path / "m.json").write_text(json.dumps(meds), encoding="utf-8")
    run = subprocess.run(["node", str(ROOT / "web" / "scripts" / "flags-check.ts"), str(tmp_path / "b.json"),
                          str(tmp_path / "m.json")], capture_output=True, text=True, timeout=120, cwd=ROOT)
    assert run.returncode == 0, run.stderr[-800:]
    ev = json.loads(run.stdout)
    pairs = [sorted(f["ingredients"]) for f in ev["flags"]]
    assert ["aspirin", "clopidogrel"] in pairs
    flag = next(f for f in ev["flags"] if sorted(f["ingredients"]) == ["aspirin", "clopidogrel"])
    assert flag["source"] == "DDInter 2.0" and flag["sourceRef"] and flag["datasetVersion"]
    not_assessed = {x["med"]["id"]: x["reason"] for x in ev["notAssessed"]}
    assert not_assessed["3"].startswith("Not in") and not_assessed["4"].startswith("Choose")


def test_ignore_and_research_are_audited_without_names():
    r = new_referral("Rubina Akhtar", "akuh", "dentistry", None)
    key = hashlib.sha256(b"rec:x|list:0|aspirin|clopidogrel").hexdigest()
    for action in ("flag.ignore", "flag.research"):
        ok(central("dr.ali").post("/e2e/client-events", {"action": action, "target_type": "flag", "target_id": key[:16],
                                                        "referral_id": r["id"], "detail": {"flag_key": key, "layer": 1,
                                                                                           "name": "aspirin"}}), 202)
    trail = [a for a in ok(central("dr.ali").get(f"/referrals/{r['id']}/audit")) if a["action"].startswith("flag.")]
    assert {a["action"] for a in trail} == {"flag.ignore", "flag.research"}
    assert all(a["detail"]["flag_key"] == key and "name" not in a["detail"] for a in trail)  # unknown keys are dropped


def test_layer2_gets_generic_names_only():
    r = new_referral("Rubina Akhtar", "akuh", "dentistry", "Surgical extraction of lower left molar", ["oral_surgery"])
    body = {"referral_id": r["id"], "payload": {"medicines": ["aspirin", "clopidogrel", "alendronic acid"],
                                                "procedure": "Surgical extraction of lower left molar",
                                                "age_band": "40-49", "already_flagged": [["aspirin", "clopidogrel"]],
                                                "not_in_dataset": []}}
    assert central("staff.ali").post("/ai/relay/flags", body).status_code == 403
    configured = central_python("from app.config import settings; print(settings.llm_configured)").splitlines()[-1] == "True"
    resp = central("dr.ali").post("/ai/relay/flags", body)
    if not configured:
        assert resp.status_code == 503 and "not available" in resp.text
        return
    if resp.status_code in (502, 503):
        pytest.skip(f"model did not answer usably: {resp.text[:200]}")
    out = ok(resp)
    names = {"aspirin", "clopidogrel", "alendronic acid", body["payload"]["procedure"].lower()}
    for s in out["suggestions"]:
        assert s["label"] == "AI suggestion, not verified"
        assert s["drug"].lower() in names and s["other_drug_or_procedure"].lower() in names
        assert {s["drug"].lower(), s["other_drug_or_procedure"].lower()} != {"aspirin", "clopidogrel"}  # never repeats Layer 1
