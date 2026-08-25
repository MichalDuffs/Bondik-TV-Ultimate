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

    assert "REVIEW CASES : 1" in out
    assert "NEW STREAMS  : 1" in out
    assert "ALTERNATIVES : 1" in out
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

    assert len(payload["candidates"]) == 1

    item = payload["candidates"][0]

    assert item["url"] == "https://new.example/stream.m3u8"
    assert item["decision"] == "pending"
    assert item["name"] == "New TV"
def test_show_approval_queue(tmp_path, capsys):
    import json

    queue = tmp_path / "approval-queue.json"

    queue.write_text(
        json.dumps(
            {
                "candidates": [
                    {
                        "url": "https://example.com/test.m3u8",
                        "decision": "pending",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = pipeline.show_approval_queue(queue)

    out = capsys.readouterr().out

    assert result == 0
    assert "Bondik Approval Queue" in out
    assert "PENDING" in out
    assert "https://example.com/test.m3u8" in out

def test_set_approval_decision(tmp_path):
    import json

    queue = tmp_path / "approval-queue.json"

    queue.write_text(
        json.dumps(
            {
                "candidates": [
                    {
                        "name": "Test TV",
                        "url": "https://example.com/test.m3u8",
                        "decision": "pending",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = pipeline.set_approval_decision(
        queue,
        1,
        "approve",
    )

    assert result == 0

    payload = json.loads(
        queue.read_text(encoding="utf-8")
    )

    assert payload["candidates"][0]["decision"] == "approve"


def test_set_approval_decision_reject(tmp_path):
    import json

    queue = tmp_path / "approval-queue.json"

    queue.write_text(
        json.dumps(
            {
                "candidates": [
                    {
                        "name": "Test TV",
                        "url": "https://example.com/test.m3u8",
                        "decision": "pending",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = pipeline.set_approval_decision(
        queue,
        1,
        "reject",
    )

    assert result == 0

    payload = json.loads(
        queue.read_text(encoding="utf-8")
    )

    assert payload["candidates"][0]["decision"] == "reject"


def test_set_approval_decision_rejects_invalid_index(tmp_path):
    import json

    queue = tmp_path / "approval-queue.json"

    queue.write_text(
        json.dumps({"candidates": []}),
        encoding="utf-8",
    )

    assert pipeline.set_approval_decision(
        queue,
        0,
        "approve",
    ) == 1

    assert pipeline.set_approval_decision(
        queue,
        1,
        "approve",
    ) == 1
def test_corrob_provenance_never_marks_verified(tmp_path):
    import json

    queue = tmp_path / "approval-queue.json"

    queue.write_text(
        json.dumps(
            {
                "candidates": [
                    {
                        "name": "TV Central",
                        "url": "https://example.com/tv.m3u8",
                        "decision": "approve",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = pipeline.set_candidate_provenance(
        queue,
        1,
        "corroborated",
        "https://www.cetv.sk/",
        ["https://www.cetv.sk/o-tv-central/"],
        "Station corroborated; stream URL not directly confirmed.",
    )

    assert result == 0

    payload = json.loads(
        queue.read_text(encoding="utf-8")
    )

    provenance = payload["candidates"][0]["provenance"]

    assert provenance["level"] == "corroborated"
    assert provenance["verified"] is False


def test_official_provenance_marks_verified(tmp_path):
    import json

    queue = tmp_path / "approval-queue.json"

    queue.write_text(
        json.dumps(
            {
                "candidates": [
                    {
                        "name": "Official TV",
                        "url": "https://example.com/tv.m3u8",
                        "decision": "approve",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = pipeline.set_candidate_provenance(
        queue,
        1,
        "official",
        "https://example.com/",
        ["https://example.com/live"],
        "Official operator directly confirms this stream.",
    )

    assert result == 0

    payload = json.loads(
        queue.read_text(encoding="utf-8")
    )

    provenance = payload["candidates"][0]["provenance"]

    assert provenance["level"] == "official"
    assert provenance["verified"] is True
def test_show_approval_queue_displays_provenance(
    tmp_path,
    capsys,
):
    import json

    queue = tmp_path / "approval-queue.json"

    queue.write_text(
        json.dumps(
            {
                "candidates": [
                    {
                        "name": "TV Central",
                        "country": "SK",
                        "category": "unknown",
                        "score": "54",
                        "url": "https://example.com/tv.m3u8",
                        "decision": "approve",
                        "provenance": {
                            "level": "corroborated",
                            "verified": False,
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = pipeline.show_approval_queue(queue)

    out = capsys.readouterr().out

    assert result == 0
    assert "CORROBORATED / NOT VERIFIED" in out
    assert "APPROVE" in out
def test_show_approval_queue_displays_provenance(
    tmp_path,
    capsys,
):
    import json

    queue = tmp_path / "approval-queue.json"

    queue.write_text(
        json.dumps(
            {
                "candidates": [
                    {
                        "name": "TV Central",
                        "country": "SK",
                        "category": "unknown",
                        "score": "54",
                        "url": "https://example.com/tv.m3u8",
                        "decision": "approve",
                        "provenance": {
                            "level": "corroborated",
                            "verified": False,
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = pipeline.show_approval_queue(queue)

    out = capsys.readouterr().out

    assert result == 0
    assert "CORROBORATED / NOT VERIFIED" in out
    assert "APPROVE" in out
def test_approval_queue_preserves_review_state_by_exact_url(
    tmp_path,
):
    import csv
    import json

    review = tmp_path / "review.csv"
    queue = tmp_path / "approval-queue.json"

    queue.write_text(
        json.dumps(
            {
                "candidates": [
                    {
                        "name": "TV Central",
                        "url": "https://example.com/tv.m3u8",
                        "decision": "approve",
                        "provenance": {
                            "level": "corroborated",
                            "verified": False,
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with review.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "candidate_name",
                "country_inferred",
                "category_inferred",
                "bondik_score",
                "stream_host",
                "review_flags",
                "existing_channel_id",
                "url",
            ],
        )

        writer.writeheader()
        writer.writerow(
            {
                "candidate_name": "TV Central",
                "country_inferred": "SK",
                "category_inferred": "general",
                "bondik_score": "77",
                "stream_host": "fresh.example",
                "review_flags": "manual-provenance-review",
                "existing_channel_id": "",
                "url": "https://example.com/tv.m3u8",
            }
        )

    pipeline.write_candidate_approval_queue(
        review,
        queue,
    )

    payload = json.loads(
        queue.read_text(encoding="utf-8")
    )

    item = payload["candidates"][0]

    assert item["decision"] == "approve"
    assert item["provenance"]["level"] == "corroborated"
    assert item["provenance"]["verified"] is False
    assert item["score"] == "77"
    assert item["host"] == "fresh.example"
def test_approval_queue_preserves_review_state_by_exact_url(
    tmp_path,
):
    import csv
    import json

    review = tmp_path / "review.csv"
    queue = tmp_path / "approval-queue.json"

    queue.write_text(
        json.dumps(
            {
                "candidates": [
                    {
                        "name": "TV Central",
                        "url": "https://example.com/tv.m3u8",
                        "decision": "approve",
                        "provenance": {
                            "level": "corroborated",
                            "verified": False,
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with review.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "candidate_name",
                "country_inferred",
                "category_inferred",
                "bondik_score",
                "stream_host",
                "review_flags",
                "existing_channel_id",
                "url",
            ],
        )

        writer.writeheader()
        writer.writerow(
            {
                "candidate_name": "TV Central",
                "country_inferred": "SK",
                "category_inferred": "general",
                "bondik_score": "77",
                "stream_host": "fresh.example",
                "review_flags": "manual-provenance-review",
                "existing_channel_id": "",
                "url": "https://example.com/tv.m3u8",
            }
        )

    pipeline.write_candidate_approval_queue(
        review,
        queue,
    )

    payload = json.loads(
        queue.read_text(encoding="utf-8")
    )

    item = payload["candidates"][0]

    assert item["decision"] == "approve"
    assert item["provenance"]["level"] == "corroborated"
    assert item["provenance"]["verified"] is False
    assert item["score"] == "77"
    assert item["host"] == "fresh.example"

