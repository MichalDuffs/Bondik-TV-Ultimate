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


def test_metadata_music_resolves_unknown_candidate():
    metadata = {
        "radioram.pl": {
            "id": "RadioRAM.pl",
            "categories": ["music"],
            "is_nsfw": False,
        }
    }

    row = {
        "candidate_name": "Radio RAM",
        "tvg_id": "RadioRAM.pl@HD",
        "category_inferred": "unknown",
    }

    assert (
        bagtop.detect_category(row, metadata)
        == "music"
    )


def test_metadata_movies_resolves_filmbox():
    metadata = {
        "filmboxplusfestival.pl": {
            "id": "FILMBOXPlusFestival.pl",
            "categories": ["movies"],
            "is_nsfw": False,
        }
    }

    row = {
        "candidate_name": "FILMBOX+ Festival HD",
        "tvg_id": "FILMBOXPlusFestival.pl@HD",
        "category_inferred": "unknown",
    }

    assert (
        bagtop.detect_category(row, metadata)
        == "movies"
    )


def test_metadata_shop_goes_to_parking():
    metadata = {
        "mango.pl": {
            "id": "Mango.pl",
            "categories": ["shop"],
            "is_nsfw": False,
        }
    }

    row = {
        "candidate_name": "Mango",
        "tvg_id": "Mango.pl@SD",
        "category_inferred": "unknown",
        "review_flags": "",
    }

    entry = bagtop.metadata_for_row(
        row,
        metadata,
    )

    category = bagtop.detect_category(
        row,
        metadata,
    )

    assert category == "shopping"
    assert (
        bagtop.classify(
            row,
            category,
            entry,
        )
        == "parking"
    )


def test_metadata_general_stays_review():
    metadata = {
        "avers.ua": {
            "id": "Avers.ua",
            "categories": ["general"],
            "is_nsfw": False,
        }
    }

    row = {
        "candidate_name": "Avers",
        "tvg_id": "Avers.ua@SD",
        "category_inferred": "unknown",
        "review_flags": "",
    }

    entry = bagtop.metadata_for_row(
        row,
        metadata,
    )

    category = bagtop.detect_category(
        row,
        metadata,
    )

    assert category == "unknown"
    assert (
        bagtop.classify(
            row,
            category,
            entry,
        )
        == "review"
    )


def test_exact_override_beats_metadata():
    metadata = {
        "hobbymaker.uk": {
            "id": "HobbyMaker.uk",
            "categories": ["general"],
            "is_nsfw": False,
        }
    }

    row = {
        "candidate_name": "Hobby Maker",
        "tvg_id": "HobbyMaker.uk@SD",
        "category_inferred": "hobby",
    }

    assert (
        bagtop.detect_category(row, metadata)
        == "shopping"
    )


def test_nsfw_metadata_is_parked():
    metadata = {
        "example.test": {
            "id": "Example.test",
            "categories": ["movies"],
            "is_nsfw": True,
        }
    }

    row = {
        "candidate_name": "Example",
        "tvg_id": "Example.test@HD",
        "category_inferred": "unknown",
        "review_flags": "",
    }

    entry = bagtop.metadata_for_row(
        row,
        metadata,
    )

    category = bagtop.detect_category(
        row,
        metadata,
    )

    assert category == "movies"
    assert (
        bagtop.classify(
            row,
            category,
            entry,
        )
        == "parking"
    )
