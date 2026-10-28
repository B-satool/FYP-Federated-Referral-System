"""DRAP register brand names: matched only at the start of the written name, filtered when loaded."""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.medications import mapping


@dataclass
class Name:
    name: str
    ingredient: str
    drug_class: str
    kind: str = "brand"
    status: str = "active"
    display: str = ""

    def __post_init__(self):
        self.display = self.display or self.name.title()


INDEX = mapping.NameIndex([
    Name("warfarin", "warfarin", "anticoagulant", "generic"),
    Name("calcium", "calcium carbonate/colecalciferol", "calcium_vitamin_d", "generic"),
    Name("loprin", "aspirin", "antiplatelet"),
    Name("coagurin", "warfarin", "anticoagulant", mapping.REGISTER_KIND),
    Name("vitamin", "colecalciferol", "calcium_vitamin_d", mapping.REGISTER_KIND),  # would be refused at load
    Name("a tin", "atorvastatin", "statin", mapping.REGISTER_KIND),
])


def test_register_brand_at_the_start_maps_and_says_where_it_came_from():
    m = INDEX.map("Coagurin 5mg Tablets")
    assert (m.status, m.ingredient, m.note) == ("mapped", "warfarin", mapping.REGISTER_NOTE)
    assert INDEX.map("A-Tin 10 mg").ingredient == "atorvastatin"


def test_register_brand_inside_other_words_does_not_match():
    m = INDEX.map("Calcium with vitamin D3 tablet")
    assert (m.status, m.ingredient) == ("mapped", "calcium carbonate/colecalciferol")  # "vitamin" is not used
    assert INDEX.map("Neo coagurin").status == "unmapped"  # ("Tablet" would be dropped as a form word)


def test_hand_checked_names_still_match_anywhere_and_carry_no_register_note():
    m = INDEX.map("Tab. Loprin 75 mg")
    assert (m.ingredient, m.note) == ("aspirin", None)
    m = INDEX.map("Coagurin (warfarin) 5 mg")
    assert (m.ingredient, m.note) == ("warfarin", None)  # the generic name confirms it


@pytest.mark.parametrize("key,usable", [("d", False), ("ds", False), ("a e", False), ("vitamin", False),
                                        ("calcium", False), ("asa", True), ("a tin", True), ("coagurin", True)])
def test_register_names_that_are_too_short_or_ordinary_words_are_not_loaded(key, usable):
    assert mapping.usable_register_name(key) is usable


def test_a_register_name_for_two_medicines_says_what_it_could_be():
    index = mapping.NameIndex([
        Name("ibuprofen", "ibuprofen", "nsaid", "generic"),
        Name("glare", "gliclazide | ibuprofen", "", mapping.AMBIGUOUS_KIND),
    ])
    m = index.map("Glare 400 mg")
    assert m.status == "ambiguous" and "gliclazide or ibuprofen" in m.note
    assert index.map("Glare (ibuprofen) 400 mg").ingredient == "ibuprofen"  # the generic name settles it
