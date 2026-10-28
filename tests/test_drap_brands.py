"""DRAP register brands (docs/decisions/2026-10-28-drap-brands-loaded.md): a register brand maps to its
ingredient and is checked against DDInter; a name DRAP uses for different products is never guessed:
doctor or staff pick the one on the pack, by company."""
from __future__ import annotations

from conftest import new_referral
from helpers import central, ok

DOCTOR, STAFF = central("dr.ali"), central("staff.ali")


def _meds(rid: int) -> dict:
    return ok(STAFF.get(f"/referrals/{rid}/medications"))


def _entry(rid: int, name: str) -> dict:
    return next(m for m in _meds(rid)["entries"] if m["original_name"].startswith(name))


def test_register_brand_and_choosing_an_ambiguous_one_by_company():
    r = new_referral("Rubina", "akuh", "dentistry", "Surgical extraction of lower left molar", ["oral_surgery", "bleeding_risk"])
    rid = r["id"]
    ok(STAFF.post(f"/referrals/{rid}/retrieve"))
    for name in ("Coagurin 5 mg", "Glare 400 mg", "Lofen 50 mg"):
        ok(STAFF.post(f"/referrals/{rid}/medications/manual", {"name": name, "frequency": "once daily"}), 201)

    coagurin = _entry(rid, "Coagurin")
    assert coagurin["ingredient"] == "warfarin" and "DRAP" in coagurin["mapping_note"]

    glare = _entry(rid, "Glare")
    assert glare["mapping_status"] == "ambiguous" and "gliclazide or ibuprofen" in glare["mapping_note"]
    options = {c["ingredient"]: c for c in glare["mapping_choices"]}
    assert set(options) == {"gliclazide", "ibuprofen"} and all(c["company"] and c["known"] for c in options.values())
    flag = next(f for f in _meds(rid)["flags"] if f["kind"] == "unrecognised_medicine" and "Glare" in f["title"])
    assert "gliclazide or ibuprofen" in flag["message"]

    # a product that is not one of the options is refused
    bad = {**options["ibuprofen"], "company": "Some Other Pharma"}
    assert STAFF.post(f"/referrals/{rid}/medications/{glare['id']}/mapping",
                      {"ingredient": "ibuprofen", "company": bad["company"], "drap_reg_no": bad["drap_reg_no"]}).status_code == 422

    # staff pick by the company on the pack; the flags are checked again
    c = options["ibuprofen"]
    ok(STAFF.post(f"/referrals/{rid}/medications/{glare['id']}/mapping",
                  {"ingredient": "ibuprofen", "company": c["company"], "drap_reg_no": c["drap_reg_no"]}))
    glare = _entry(rid, "Glare")
    assert glare["mapping_status"] == "staff_mapped" and glare["ingredient"] == "ibuprofen"
    assert c["company"] in glare["mapping_note"] and "Hina Raza" in glare["mapping_note"]
    flags = _meds(rid)["flags"]
    assert any(f["kind"] == "interaction" and set(f["ingredients"]) == {"ibuprofen", "warfarin"} for f in flags)
    assert not any(f["kind"] == "unrecognised_medicine" and "Glare" in f["title"] for f in flags)

    # the doctor can choose too
    lofen = _entry(rid, "Lofen")
    d = next(x for x in lofen["mapping_choices"] if x["ingredient"] == "diclofenac")
    ok(DOCTOR.post(f"/referrals/{rid}/medications/{lofen['id']}/mapping",
                   {"ingredient": "diclofenac", "company": d["company"], "drap_reg_no": d["drap_reg_no"]}))
    lofen = _entry(rid, "Lofen")
    assert lofen["ingredient"] == "diclofenac" and "Dr Ali Raza" in lofen["mapping_note"]
