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


def test_metadata_source_uses_existing_cache(
    tmp_path,
    monkeypatch,
):
    cache = tmp_path / "channels.json"
    cache.write_text(
        "[]",
        encoding="utf-8",
    )

    downloads = []

    monkeypatch.setattr(
        bagtop,
        "download_channel_metadata",
        lambda path: downloads.append(path),
    )

    path, mode = bagtop.resolve_metadata_source(
        channel_metadata=None,
        metadata_cache=cache,
        refresh_metadata=False,
        no_metadata=False,
    )

    assert path == cache
    assert mode == "cache"
    assert downloads == []


def test_metadata_source_downloads_missing_cache(
    tmp_path,
    monkeypatch,
):
    cache = tmp_path / "channels.json"

    def fake_download(path):
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        path.write_text(
            '[{"id":"Example.test"}]',
            encoding="utf-8",
        )

    monkeypatch.setattr(
        bagtop,
        "download_channel_metadata",
        fake_download,
    )

    path, mode = bagtop.resolve_metadata_source(
        channel_metadata=None,
        metadata_cache=cache,
        refresh_metadata=False,
        no_metadata=False,
    )

    assert path == cache
    assert mode == "downloaded"
    assert cache.exists()


def test_metadata_refresh_failure_uses_cache(
    tmp_path,
    monkeypatch,
):
    cache = tmp_path / "channels.json"
    cache.write_text(
        '[{"id":"Cached.test"}]',
        encoding="utf-8",
    )

    def failing_download(path):
        raise OSError("network down")

    monkeypatch.setattr(
        bagtop,
        "download_channel_metadata",
        failing_download,
    )

    path, mode = bagtop.resolve_metadata_source(
        channel_metadata=None,
        metadata_cache=cache,
        refresh_metadata=True,
        no_metadata=False,
    )

    assert path == cache
    assert mode == "cache-fallback"


def test_explicit_metadata_beats_cache(
    tmp_path,
):
    explicit = tmp_path / "explicit.json"
    explicit.write_text(
        "[]",
        encoding="utf-8",
    )

    cache = tmp_path / "cache.json"

    path, mode = bagtop.resolve_metadata_source(
        channel_metadata=explicit,
        metadata_cache=cache,
        refresh_metadata=False,
        no_metadata=False,
    )

    assert path == explicit
    assert mode == "explicit"


def test_no_metadata_disables_metadata(
    tmp_path,
):
    path, mode = bagtop.resolve_metadata_source(
        channel_metadata=None,
        metadata_cache=tmp_path / "channels.json",
        refresh_metadata=False,
        no_metadata=True,
    )

    assert path is None
    assert mode == "disabled"


def test_diverse_top_prefers_different_categories():
    rows = [
        {
            "candidate_name": "Music A",
            "bagtop_category": "music",
            "bagtop_score": "100",
        },
        {
            "candidate_name": "Music B",
            "bagtop_category": "music",
            "bagtop_score": "95",
        },
        {
            "candidate_name": "Movie A",
            "bagtop_category": "movies",
            "bagtop_score": "90",
        },
    ]

    result = bagtop.select_diverse_top(
        rows,
        2,
    )

    assert [
        row["candidate_name"]
        for row in result
    ] == [
        "Music A",
        "Movie A",
    ]


def test_diverse_top_second_pass_fills_remaining_slots():
    rows = [
        {
            "candidate_name": "Music A",
            "bagtop_category": "music",
        },
        {
            "candidate_name": "Movie A",
            "bagtop_category": "movies",
        },
        {
            "candidate_name": "Music B",
            "bagtop_category": "music",
        },
    ]

    result = bagtop.select_diverse_top(
        rows,
        3,
    )

    assert len(result) == 3
    assert result[2]["candidate_name"] == "Music B"


def test_score_strategy_preserves_ranking():
    rows = [
        {
            "candidate_name": "Music A",
            "bagtop_category": "music",
        },
        {
            "candidate_name": "Music B",
            "bagtop_category": "music",
        },
        {
            "candidate_name": "Movie A",
            "bagtop_category": "movies",
        },
    ]

    result = bagtop.select_top(
        rows,
        2,
        "score",
    )

    assert [
        row["candidate_name"]
        for row in result
    ] == [
        "Music A",
        "Music B",
    ]


def test_diverse_strategy_uses_diversity_gate():
    rows = [
        {
            "candidate_name": "Music A",
            "bagtop_category": "music",
        },
        {
            "candidate_name": "Music B",
            "bagtop_category": "music",
        },
        {
            "candidate_name": "Kids A",
            "bagtop_category": "kids",
        },
    ]

    result = bagtop.select_top(
        rows,
        2,
        "diverse",
    )

    assert [
        row["candidate_name"]
        for row in result
    ] == [
        "Music A",
        "Kids A",
    ]
