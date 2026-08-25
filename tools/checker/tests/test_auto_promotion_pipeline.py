from pathlib import Path
import subprocess
import sys

SCRIPT = Path("tools/checker/auto_promotion_pipeline.py")

def test_help_works():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0
    assert "Bondik AUTO-PROMOTION PIPELINE v2.0.0" in result.stdout

def test_missing_candidates_fails_without_skip():
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--skip-stable-promotion",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert "--candidates is required" in combined

from pathlib import Path
import importlib.util
import json

SCRIPT = Path("tools/checker/auto_promotion_pipeline.py")

spec = importlib.util.spec_from_file_location("pipeline", SCRIPT)
pipeline = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(pipeline)

def test_dashboard_groups_channels(tmp_path, capsys):
    report = tmp_path / "promotion_status.json"

    report.write_text(
        json.dumps(
            {
                "channels": [
                    {
                        "name": "Ready",
                        "eligible": True,
                        "counted_passes": 3,
                        "required_passes": 3,
                        "last_result": "pass",
                    },
                    {
                        "name": "Almost",
                        "eligible": False,
                        "counted_passes": 2,
                        "required_passes": 3,
                        "last_result": "pass",
                    },
                    {
                        "name": "Early",
                        "eligible": False,
                        "counted_passes": 1,
                        "required_passes": 3,
                        "last_result": "pass",
                    },
                    {
                        "name": "Failed",
                        "eligible": False,
                        "counted_passes": 0,
                        "required_passes": 3,
                        "last_result": "fail",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    pipeline.print_promotion_dashboard(report)

    out = capsys.readouterr().out

    assert "READY NOW     : 1" in out
    assert "ALMOST READY  : 1" in out
    assert "EARLY TESTING : 1" in out
    assert "FAILED        : 1" in out
    assert "Ready: 3/3" in out
    assert "Almost: 2/3" in out
    assert "Early: 1/3" in out
    assert "Failed: 0/3" in out
def test_generate_playlists_flag_is_in_help():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.returncode == 0
    assert "--generate-playlists" in result.stdout
def test_candidate_review_dashboard_groups_new_and_alternatives(
    tmp_path,
    capsys,
):
    import csv

    review = tmp_path / "review.csv"

    rows = [
        {
            "candidate_name": "New TV",
            "country_inferred": "CZ",
            "category_inferred": "news",
            "bondik_score": "70",
            "stream_host": "new.example",
            "existing_channel_id": "",
            "review_flags": "manual-provenance-review",
        },
        {
            "candidate_name": "Existing TV",
            "country_inferred": "SK",
            "category_inferred": "",
            "bondik_score": "40",
            "stream_host": "alt.example",
            "existing_channel_id": "existing-tv-sk",
            "review_flags": "possible-existing-channel-alternative",
        },
    ]

    with review.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=rows[0].keys(),
        )
        writer.writeheader()
        writer.writerows(rows)

    pipeline.print_candidate_review_dashboard(review)

    out = capsys.readouterr().out

    assert "NEW CANDIDATES : 1" in out
    assert "ALTERNATIVES   : 1" in out
    assert "New TV" in out
    assert "Existing TV" in out
    assert "existing-tv-sk" in out
def test_candidate_approval_queue_contains_only_new_candidates(
    tmp_path,
):
    import csv
    import json

    review = tmp_path / "review.csv"
    output = tmp_path / "approval-queue.json"

    rows = [
        {
            "candidate_name": "New TV",
            "url": "https://new.example/stream.m3u8",
            "existing_channel_id": "",
        },
        {
            "candidate_name": "Existing TV",
            "url": "https://alt.example/stream.m3u8",
            "existing_channel_id": "existing-tv-cz",
        },
    ]

    with review.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=rows[0].keys(),
        )
        writer.writeheader()
        writer.writerows(rows)

    pipeline.write_candidate_approval_queue(
        review,
        output,
    )

    payload = json.loads(
        output.read_text(encoding="utf-8")
    )

    assert payload == {
        "candidates": [
            {
                "url": "https://new.example/stream.m3u8",
                "decision": "pending",
            }
        ]
    }
