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

