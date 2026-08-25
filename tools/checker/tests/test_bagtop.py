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
        '[{"id":"Cached.test"}]',
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
        '[{"id":"Explicit.test"}]',
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


def test_diversity_floor_blocks_large_quality_drop():
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
            "candidate_name": "Kids Weak",
            "bagtop_category": "kids",
            "bagtop_score": "70",
        },
    ]

    result = bagtop.select_diverse_top(
        rows,
        2,
        max_score_gap=10,
    )

    assert [
        row["candidate_name"]
        for row in result
    ] == [
        "Music A",
        "Music B",
    ]


def test_diversity_floor_allows_small_quality_drop():
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
            "candidate_name": "Kids Good",
            "bagtop_category": "kids",
            "bagtop_score": "90",
        },
    ]

    result = bagtop.select_diverse_top(
        rows,
        2,
        max_score_gap=10,
    )

    assert [
        row["candidate_name"]
        for row in result
    ] == [
        "Music A",
        "Kids Good",
    ]


def test_zero_diversity_gap_requires_cutoff_quality():
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
            "candidate_name": "Kids Almost",
            "bagtop_category": "kids",
            "bagtop_score": "94",
        },
    ]

    result = bagtop.select_diverse_top(
        rows,
        2,
        max_score_gap=0,
    )

    assert [
        row["candidate_name"]
        for row in result
    ] == [
        "Music A",
        "Music B",
    ]


def test_select_top_passes_diversity_score_gap():
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
            "candidate_name": "Kids Weak",
            "bagtop_category": "kids",
            "bagtop_score": "80",
        },
    ]

    result = bagtop.select_top(
        rows,
        2,
        "diverse",
        diversity_score_gap=5,
    )

    assert [
        row["candidate_name"]
        for row in result
    ] == [
        "Music A",
        "Music B",
    ]


def test_category_cap_blocks_third_same_category():
    rows = [
        {
            "candidate_name": "Music A",
            "bagtop_category": "music",
            "bagtop_score": "100",
        },
        {
            "candidate_name": "Music B",
            "bagtop_category": "music",
            "bagtop_score": "99",
        },
        {
            "candidate_name": "Music C",
            "bagtop_category": "music",
            "bagtop_score": "98",
        },
        {
            "candidate_name": "Movie A",
            "bagtop_category": "movies",
            "bagtop_score": "97",
        },
        {
            "candidate_name": "Kids A",
            "bagtop_category": "kids",
            "bagtop_score": "96",
        },
    ]

    result = bagtop.select_diverse_top(
        rows,
        5,
        max_score_gap=10,
        max_per_category=2,
    )

    names = [
        row["candidate_name"]
        for row in result
    ]

    assert "Music A" in names
    assert "Music B" in names
    assert "Music C" not in names
    assert len(result) == 4


def test_category_cap_allows_two_per_category():
    rows = [
        {
            "candidate_name": "Music A",
            "bagtop_category": "music",
            "bagtop_score": "100",
        },
        {
            "candidate_name": "Movie A",
            "bagtop_category": "movies",
            "bagtop_score": "99",
        },
        {
            "candidate_name": "Music B",
            "bagtop_category": "music",
            "bagtop_score": "98",
        },
        {
            "candidate_name": "Movie B",
            "bagtop_category": "movies",
            "bagtop_score": "97",
        },
    ]

    result = bagtop.select_diverse_top(
        rows,
        4,
        max_score_gap=10,
        max_per_category=2,
    )

    assert len(result) == 4


def test_category_cap_one_keeps_only_unique_categories():
    rows = [
        {
            "candidate_name": "Music A",
            "bagtop_category": "music",
            "bagtop_score": "100",
        },
        {
            "candidate_name": "Music B",
            "bagtop_category": "music",
            "bagtop_score": "99",
        },
        {
            "candidate_name": "Kids A",
            "bagtop_category": "kids",
            "bagtop_score": "98",
        },
    ]

    result = bagtop.select_diverse_top(
        rows,
        3,
        max_score_gap=10,
        max_per_category=1,
    )

    assert [
        row["candidate_name"]
        for row in result
    ] == [
        "Music A",
        "Kids A",
    ]


def test_zero_category_cap_is_unlimited():
    rows = [
        {
            "candidate_name": "Music A",
            "bagtop_category": "music",
            "bagtop_score": "100",
        },
        {
            "candidate_name": "Music B",
            "bagtop_category": "music",
            "bagtop_score": "99",
        },
        {
            "candidate_name": "Music C",
            "bagtop_category": "music",
            "bagtop_score": "98",
        },
    ]

    result = bagtop.select_diverse_top(
        rows,
        3,
        max_score_gap=10,
        max_per_category=0,
    )

    assert len(result) == 3


def test_score_strategy_ignores_category_cap():
    rows = [
        {
            "candidate_name": "Music A",
            "bagtop_category": "music",
            "bagtop_score": "100",
        },
        {
            "candidate_name": "Music B",
            "bagtop_category": "music",
            "bagtop_score": "99",
        },
        {
            "candidate_name": "Music C",
            "bagtop_category": "music",
            "bagtop_score": "98",
        },
    ]

    result = bagtop.select_top(
        rows,
        3,
        "score",
        diversity_score_gap=10,
        max_per_category=1,
    )

    assert len(result) == 3


def test_movie_categories_share_family():
    assert bagtop.category_family("movies") == "movies"
    assert bagtop.category_family("cinema") == "movies"
    assert bagtop.category_family("film") == "movies"
    assert bagtop.category_family("action") == "movies"
    assert bagtop.category_family("comedy") == "movies"


def test_music_categories_share_family():
    assert bagtop.category_family("music") == "music"
    assert bagtop.category_family("concerts") == "music"
    assert bagtop.category_family("live music") == "music"
    assert bagtop.category_family("rock") == "music"
    assert bagtop.category_family("pop") == "music"


def test_specialist_aliases_share_family():
    assert bagtop.category_family("cartoon") == "animation"
    assert bagtop.category_family("animation") == "animation"
    assert bagtop.category_family("astronomy") == "space"
    assert bagtop.category_family("space") == "space"
    assert bagtop.category_family("animals") == "wildlife"
    assert bagtop.category_family("wildlife") == "wildlife"


def test_category_family_cap_blocks_disguised_duplicates():
    rows = [
        {
            "candidate_name": "Movie A",
            "bagtop_category": "movies",
            "bagtop_score": "100",
        },
        {
            "candidate_name": "Cinema B",
            "bagtop_category": "cinema",
            "bagtop_score": "99",
        },
        {
            "candidate_name": "Film C",
            "bagtop_category": "film",
            "bagtop_score": "98",
        },
        {
            "candidate_name": "Kids A",
            "bagtop_category": "kids",
            "bagtop_score": "97",
        },
    ]

    result = bagtop.select_diverse_top(
        rows,
        4,
        max_score_gap=10,
        max_per_category=2,
    )

    names = [
        row["candidate_name"]
        for row in result
    ]

    assert "Movie A" in names
    assert "Cinema B" in names
    assert "Film C" not in names
    assert "Kids A" in names
    assert len(result) == 3


def test_score_strategy_still_ignores_category_family_cap():
    rows = [
        {
            "candidate_name": "Movie A",
            "bagtop_category": "movies",
            "bagtop_score": "100",
        },
        {
            "candidate_name": "Cinema B",
            "bagtop_category": "cinema",
            "bagtop_score": "99",
        },
        {
            "candidate_name": "Film C",
            "bagtop_category": "film",
            "bagtop_score": "98",
        },
    ]

    result = bagtop.select_top(
        rows,
        3,
        "score",
        diversity_score_gap=10,
        max_per_category=1,
    )

    assert len(result) == 3


def test_score_selection_ledger_marks_score():
    rows = [
        {
            "candidate_name": "Music A",
            "bagtop_category": "music",
            "bagtop_score": "100",
        },
        {
            "candidate_name": "Movie A",
            "bagtop_category": "movies",
            "bagtop_score": "99",
        },
    ]

    result = bagtop.select_top_with_reasons(
        rows,
        2,
        "score",
    )

    assert [
        row["bagtop_top_reason"]
        for row in result
    ] == [
        "score",
        "score",
    ]


def test_selection_ledger_adds_rank():
    rows = [
        {
            "candidate_name": "Music A",
            "bagtop_category": "music",
            "bagtop_score": "100",
        },
        {
            "candidate_name": "Kids A",
            "bagtop_category": "kids",
            "bagtop_score": "99",
        },
    ]

    result = bagtop.select_top_with_reasons(
        rows,
        2,
        "score",
    )

    assert [
        row["bagtop_top_rank"]
        for row in result
    ] == [1, 2]


def test_diverse_selection_ledger_marks_first_pass():
    rows = [
        {
            "candidate_name": "Music A",
            "bagtop_category": "music",
            "bagtop_score": "100",
        },
        {
            "candidate_name": "Kids A",
            "bagtop_category": "kids",
            "bagtop_score": "99",
        },
    ]

    result = bagtop.select_top_with_reasons(
        rows,
        2,
        "diverse",
    )

    assert [
        row["bagtop_top_reason"]
        for row in result
    ] == [
        "diversity",
        "diversity",
    ]


def test_diverse_selection_ledger_marks_score_fill():
    rows = [
        {
            "candidate_name": "Music A",
            "bagtop_category": "music",
            "bagtop_score": "100",
        },
        {
            "candidate_name": "Music B",
            "bagtop_category": "music",
            "bagtop_score": "99",
        },
        {
            "candidate_name": "Kids A",
            "bagtop_category": "kids",
            "bagtop_score": "98",
        },
    ]

    result = bagtop.select_top_with_reasons(
        rows,
        3,
        "diverse",
        max_per_category=2,
    )

    assert [
        row["candidate_name"]
        for row in result
    ] == [
        "Music A",
        "Kids A",
        "Music B",
    ]

    assert [
        row["bagtop_top_reason"]
        for row in result
    ] == [
        "diversity",
        "diversity",
        "score-fill",
    ]


def test_selection_ledger_uses_family_without_mutating_source():
    rows = [
        {
            "candidate_name": "Cinema A",
            "bagtop_category": "cinema",
            "bagtop_score": "100",
        },
    ]

    result = bagtop.select_top_with_reasons(
        rows,
        1,
        "score",
    )

    assert (
        result[0]["bagtop_top_family"]
        == "movies"
    )

    assert "bagtop_top_rank" not in rows[0]
    assert "bagtop_top_reason" not in rows[0]
    assert "bagtop_top_family" not in rows[0]


def test_score_audit_marks_selected_and_top_limit():
    rows = [
        {
            "candidate_name": "A",
            "bagtop_category": "music",
            "bagtop_score": "100",
        },
        {
            "candidate_name": "B",
            "bagtop_category": "kids",
            "bagtop_score": "99",
        },
        {
            "candidate_name": "C",
            "bagtop_category": "movies",
            "bagtop_score": "98",
        },
    ]

    audit = bagtop.build_selection_audit(
        rows,
        2,
        "score",
    )

    assert [
        row["bagtop_audit_decision"]
        for row in audit
    ] == [
        "selected-score",
        "selected-score",
        "skipped-top-limit",
    ]


def test_diverse_audit_marks_selection_reasons():
    rows = [
        {
            "candidate_name": "Music A",
            "bagtop_category": "music",
            "bagtop_score": "100",
        },
        {
            "candidate_name": "Music B",
            "bagtop_category": "music",
            "bagtop_score": "99",
        },
        {
            "candidate_name": "Kids A",
            "bagtop_category": "kids",
            "bagtop_score": "98",
        },
    ]

    audit = bagtop.build_selection_audit(
        rows,
        3,
        "diverse",
        max_per_category=2,
    )

    decisions = {
        row["candidate_name"]:
        row["bagtop_audit_decision"]
        for row in audit
    }

    assert decisions["Music A"] == "selected-diversity"
    assert decisions["Kids A"] == "selected-diversity"
    assert decisions["Music B"] == "selected-score-fill"


def test_diverse_audit_marks_category_cap():
    rows = [
        {
            "candidate_name": "Music A",
            "bagtop_category": "music",
            "bagtop_score": "100",
        },
        {
            "candidate_name": "Music B",
            "bagtop_category": "music",
            "bagtop_score": "99",
        },
        {
            "candidate_name": "Music C",
            "bagtop_category": "music",
            "bagtop_score": "98",
        },
        {
            "candidate_name": "Kids A",
            "bagtop_category": "kids",
            "bagtop_score": "97",
        },
    ]

    audit = bagtop.build_selection_audit(
        rows,
        4,
        "diverse",
        max_per_category=2,
    )

    decisions = {
        row["candidate_name"]:
        row["bagtop_audit_decision"]
        for row in audit
    }

    assert decisions["Music C"] == "skipped-category-cap"


def test_diversity_floor_is_diagnostic_not_final_rejection():
    rows = [
        {
            "candidate_name": "Music A",
            "bagtop_category": "music",
            "bagtop_score": "100",
        },
        {
            "candidate_name": "Music B",
            "bagtop_category": "music",
            "bagtop_score": "99",
        },
        {
            "candidate_name": "Music C",
            "bagtop_category": "music",
            "bagtop_score": "98",
        },
        {
            "candidate_name": "Kids Weak",
            "bagtop_category": "kids",
            "bagtop_score": "80",
        },
    ]

    audit = bagtop.build_selection_audit(
        rows,
        3,
        "diverse",
        diversity_score_gap=5,
        max_per_category=2,
    )

    weak = next(
        row
        for row in audit
        if row["candidate_name"] == "Kids Weak"
    )

    assert weak["bagtop_diversity_eligible"] == "false"
    assert weak["bagtop_audit_decision"] == "selected-score-fill"


def test_selection_audit_does_not_mutate_source():
    rows = [
        {
            "candidate_name": "Cinema A",
            "bagtop_category": "cinema",
            "bagtop_score": "100",
        },
    ]

    audit = bagtop.build_selection_audit(
        rows,
        1,
        "score",
    )

    assert audit[0]["bagtop_audit_family"] == "movies"
    assert "bagtop_audit_decision" not in rows[0]
    assert "bagtop_audit_rank" not in rows[0]


def test_run_manifest_records_production_inputs():
    manifest = bagtop.build_run_manifest(
        metadata_mode="cache",
        metadata_source="channels.json",
        metadata_records=100,
        top_strategy="diverse",
        diversity_score_gap=10,
        max_per_category=2,
        input_candidates=50,
        raw_goodies=12,
        unique_goodies=10,
        review_count=20,
        parking_count=18,
        top_requested=4,
        top_selected=3,
    )

    assert manifest["bagtop_version"] == "1.0.0"
    assert manifest["metadata"]["mode"] == "cache"
    assert manifest["metadata"]["records"] == 100
    assert manifest["selection"]["top_requested"] == 4
    assert manifest["selection"]["top_selected"] == 3
    assert (
        manifest["selection"]["max_per_category_family"]
        == 2
    )
    assert manifest["counts"]["collapsed_alternatives"] == 2


def test_invalid_metadata_cache_is_repaired(
    tmp_path,
    monkeypatch,
):
    cache = tmp_path / "channels.json"
    cache.write_text(
        "{broken",
        encoding="utf-8",
    )

    def fake_download(path):
        path.write_text(
            '[{"id":"Repaired.test"}]',
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
    assert mode == "cache-repaired"

    metadata = bagtop.load_channel_metadata(
        cache
    )

    assert "repaired.test" in metadata


def test_invalid_metadata_cache_repair_failure_raises(
    tmp_path,
    monkeypatch,
):
    cache = tmp_path / "channels.json"
    cache.write_text(
        "{broken",
        encoding="utf-8",
    )

    def failing_download(path):
        raise OSError("network down")

    monkeypatch.setattr(
        bagtop,
        "download_channel_metadata",
        failing_download,
    )

    try:
        bagtop.resolve_metadata_source(
            channel_metadata=None,
            metadata_cache=cache,
            refresh_metadata=False,
            no_metadata=False,
        )
    except RuntimeError as exc:
        assert (
            "automatic repair failed"
            in str(exc)
        )
    else:
        raise AssertionError(
            "invalid cache must not be accepted"
        )


def test_refresh_failure_never_uses_invalid_cache(
    tmp_path,
    monkeypatch,
):
    cache = tmp_path / "channels.json"
    cache.write_text(
        "[]",
        encoding="utf-8",
    )

    def failing_download(path):
        raise OSError("network down")

    monkeypatch.setattr(
        bagtop,
        "download_channel_metadata",
        failing_download,
    )

    try:
        bagtop.resolve_metadata_source(
            channel_metadata=None,
            metadata_cache=cache,
            refresh_metadata=True,
            no_metadata=False,
        )
    except RuntimeError as exc:
        assert (
            "existing cache is invalid"
            in str(exc)
        )
    else:
        raise AssertionError(
            "invalid fallback cache must be rejected"
        )


def test_invalid_explicit_metadata_is_rejected(
    tmp_path,
):
    explicit = tmp_path / "explicit.json"
    explicit.write_text(
        "[]",
        encoding="utf-8",
    )

    try:
        bagtop.resolve_metadata_source(
            channel_metadata=explicit,
            metadata_cache=(
                tmp_path / "cache.json"
            ),
            refresh_metadata=False,
            no_metadata=False,
        )
    except ValueError as exc:
        assert "empty" in str(exc)
    else:
        raise AssertionError(
            "invalid explicit metadata must fail"
        )


def test_downloaded_metadata_is_revalidated(
    tmp_path,
    monkeypatch,
):
    cache = tmp_path / "channels.json"

    def bad_download(path):
        path.write_text(
            "[]",
            encoding="utf-8",
        )

    monkeypatch.setattr(
        bagtop,
        "download_channel_metadata",
        bad_download,
    )

    try:
        bagtop.resolve_metadata_source(
            channel_metadata=None,
            metadata_cache=cache,
            refresh_metadata=False,
            no_metadata=False,
        )
    except RuntimeError as exc:
        assert (
            "no valid cache exists"
            in str(exc)
        )
    else:
        raise AssertionError(
            "bad downloaded metadata must fail"
        )
