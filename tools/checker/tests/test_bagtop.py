from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "bagtop.py"
)

SPEC = importlib.util.spec_from_file_location(
    "bagtop_under_test",
    MODULE_PATH,
)

bagtop = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(bagtop)


def test_pop_variants_share_identity():
    a = {
        "candidate_name": "Pop",
        "tvg_id": "Pop.uk@SD",
    }
    b = {
        "candidate_name": "Pop",
        "tvg_id": "Pop.uk@HD",
    }

    assert bagtop.identity_key(a) == bagtop.identity_key(b)
    assert bagtop.identity_key(a) == "tvg:pop.uk"


def test_totalmusic_channels_stay_separate():
    dance = {
        "candidate_name": "Totalmusic Dance",
        "tvg_id": "TotalmusicDance.uk@HD",
    }
    concerts = {
        "candidate_name": "Totalmusic Concerts",
        "tvg_id": "TotalmusicConcerts.uk@HD",
    }

    assert (
        bagtop.identity_key(dance)
        != bagtop.identity_key(concerts)
    )


def test_tiny_pop_is_kids():
    row = {
        "candidate_name": "Tiny Pop",
        "tvg_id": "TinyPop.uk@SD",
        "category_inferred": "pop",
    }

    assert bagtop.detect_category(row) == "kids"


def test_pop_is_kids():
    row = {
        "candidate_name": "Pop",
        "tvg_id": "Pop.uk@SD",
        "category_inferred": "pop",
    }

    assert bagtop.detect_category(row) == "kids"


def test_hobby_maker_is_shopping_and_parked():
    row = {
        "candidate_name": "Hobby Maker",
        "tvg_id": "HobbyMaker.uk@SD",
        "category_inferred": "hobby",
        "review_flags": "",
    }

    category = bagtop.detect_category(row)

    assert category == "shopping"
    assert bagtop.classify(row, category) == "parking"
