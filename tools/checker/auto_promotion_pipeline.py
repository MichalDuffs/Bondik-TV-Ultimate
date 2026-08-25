#!/usr/bin/env python3
"""Bondik TV AUTO-PROMOTION PIPELINE v2.0.

Orchestrates the existing Bondik promotion tools without bypassing
their safety gates.

Pipeline:
1. Candidate approval -> testing
2. Testing Promotion Gate
3. Stable promotion review/apply
4. Playlist regeneration

DRY-RUN is the default.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


# Keep Bondik CLI output UTF-8 safe on Windows, including subprocess tests.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


VERSION = "2.0.0"

ROOT = Path(__file__).resolve().parents[2]

HUNTER = ROOT / "tools" / "checker" / "hunt_m3u.py"
PREPARE_CANDIDATES = ROOT / "tools" / "checker" / "prepare_hunt_candidates.py"
PROMOTE_APPROVED = ROOT / "tools" / "checker" / "promote_approved_candidates.py"
TESTING_GATE = ROOT / "tools" / "checker" / "testing_promotion_gate.py"
PROMOTE_STABLE = ROOT / "tools" / "checker" / "promote_testing_to_stable.py"
GENERATE_PLAYLISTS = ROOT / "tools" / "generator" / "generate_playlists.py"

DEFAULT_SOURCE_LIST = ROOT / "tools" / "discovery" / "sources-czsk.txt"
DEFAULT_HUNTER_OUT = ROOT / "hunt-results" / "auto-v2-hunter"
DEFAULT_CANDIDATE_OUT = ROOT / "hunt-results" / "auto-v2-candidates"
DEFAULT_KNOWN_SOURCE = ROOT / "playlists" / "ultimate.m3u"

DEFAULT_CHANNELS = ROOT / "channels" / "channels.yaml"

PROMOTION_REPORT = (
    ROOT
    / "hunt-results"
    / "testing-promotion"
    / "promotion_status.json"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=f"Bondik AUTO-PROMOTION PIPELINE v{VERSION}"
    )

    parser.add_argument("--candidates", type=Path)
    parser.add_argument("--testing-decisions", type=Path)
    parser.add_argument("--stable-decisions", type=Path)

    parser.add_argument(
        "--run-hunter",
        action="store_true",
        help="Run Hunter and Candidate Gate before promotion stages",
    )

    parser.add_argument(
        "--source-list",
        type=Path,
        default=DEFAULT_SOURCE_LIST,
        help="Hunter source-list file",
    )

    parser.add_argument(
        "--country",
        action="append",
        dest="countries",
        default=[],
        help="Hunter country filter; may be repeated",
    )

    parser.add_argument(
        "--hunter-out-dir",
        type=Path,
        default=DEFAULT_HUNTER_OUT,
    )

    parser.add_argument(
        "--candidate-out-dir",
        type=Path,
        default=DEFAULT_CANDIDATE_OUT,
    )

    parser.add_argument(
        "--hunter-workers",
        type=int,
        default=24,
    )

    parser.add_argument(
        "--hunter-timeout",
        type=float,
        default=8.0,
    )

    parser.add_argument(
        "--channels",
        type=Path,
        default=DEFAULT_CHANNELS,
    )

    parser.add_argument(
        "--required-passes",
        type=int,
        default=3,
    )

    parser.add_argument(
        "--min-gap-hours",
        type=float,
        default=24.0,
    )

    parser.add_argument(
        "--apply-testing",
        action="store_true",
        help="Allow approved candidates to be inserted as testing",
    )

    parser.add_argument(
        "--apply-stable",
        action="store_true",
        help="Allow eligible approved testing channels to become stable",
    )

    parser.add_argument(
        "--skip-testing-import",
        action="store_true",
        help="Skip candidate -> testing stage",
    )

    parser.add_argument(
        "--skip-stable-promotion",
        action="store_true",
        help="Skip testing -> stable stage",
    )

    parser.add_argument(
        "--generate-playlists",
        action="store_true",
        help="Regenerate generated M3U playlists after promotion stages",
    )

    return parser.parse_args()


def print_promotion_dashboard(report_path: Path = PROMOTION_REPORT) -> None:
    if not report_path.exists():
        print()
        print("ℹ️ Promotion dashboard unavailable: report not found.")
        return

    import json

    payload = json.loads(
        report_path.read_text(encoding="utf-8-sig")
    )

    channels = payload.get("channels", [])

    if not isinstance(channels, list):
        print()
        print("ℹ️ Promotion dashboard unavailable: invalid report.")
        return

    ready = []
    almost = []
    early = []
    failed = []

    for row in channels:
        if not isinstance(row, dict):
            continue

        name = str(row.get("name", row.get("id", "unknown")))
        counted = int(row.get("counted_passes", 0) or 0)
        required = int(row.get("required_passes", 0) or 0)
        last_result = str(row.get("last_result", "")).casefold()

        item = (name, counted, required)

        if last_result != "pass":
            failed.append(item)
        elif row.get("eligible") is True:
            ready.append(item)
        elif required > 0 and counted == required - 1:
            almost.append(item)
        else:
            early.append(item)

    print()
    print("=" * 72)
    print("🐾 Bondik Promotion Dashboard")
    print("=" * 72)
    print(f"READY NOW     : {len(ready)}")
    print(f"ALMOST READY  : {len(almost)}")
    print(f"EARLY TESTING : {len(early)}")
    print(f"FAILED        : {len(failed)}")

    if ready:
        print()
        print("Ready now:")
        for name, counted, required in ready:
            print(f"🏆 {name}: {counted}/{required}")

    if almost:
        print()
        print("Almost ready:")
        for name, counted, required in almost:
            print(f"🟡 {name}: {counted}/{required}")

    if early:
        print()
        print("Early testing:")
        for name, counted, required in early:
            print(f"🧪 {name}: {counted}/{required}")

    if failed:
        print()
        print("Failed:")
        for name, counted, required in failed:
            print(f"❌ {name}: {counted}/{required}")


def run_step(name: str, command: list[str]) -> None:
    print()
    print("=" * 72)
    print(f"🐾 {name}")
    print("=" * 72)
    print(" ".join(command))
    print()

    result = subprocess.run(
        command,
        cwd=ROOT,
        check=False,
    )

    if result.returncode != 0:
        raise SystemExit(
            f"❌ Pipeline stopped: {name} returned {result.returncode}"
        )


def main() -> int:
    args = parse_args()

    print()
    print(f"🐾 Bondik AUTO-PROMOTION PIPELINE v{VERSION}")
    print("=" * 72)
    print(f"Testing apply : {args.apply_testing}")
    print(f"Stable apply  : {args.apply_stable}")
    print("=" * 72)

    python = sys.executable

    generated_candidates = None

    if args.run_hunter:
        if not args.source_list.exists():
            raise SystemExit(
                f"ERROR: Hunter source list not found: {args.source_list}"
            )

        countries = args.countries or ["CZ", "SK"]

        hunter_command = [
            python,
            str(HUNTER),
            "--source-list",
            str(args.source_list),
            "--known-source",
            str(DEFAULT_KNOWN_SOURCE),
            "--new-only",
            "--workers",
            str(args.hunter_workers),
            "--timeout",
            str(args.hunter_timeout),
            "--out-dir",
            str(args.hunter_out_dir),
        ]

        for country in countries:
            hunter_command.extend(
                ["--country", str(country).strip().upper()]
            )

        run_step(
            "Hunter discovery",
            hunter_command,
        )

        hunter_results = args.hunter_out_dir / "results.json"

        if not hunter_results.exists():
            raise SystemExit(
                f"ERROR: Hunter results not found: {hunter_results}"
            )

        run_step(
            "Candidate Gate",
            [
                python,
                str(PREPARE_CANDIDATES),
                str(hunter_results),
                "--channels",
                str(args.channels),
                "--out-dir",
                str(args.candidate_out_dir),
            ],
        )

        generated_candidates = (
            args.candidate_out_dir / "candidates.json"
        )

        if not generated_candidates.exists():
            raise SystemExit(
                "ERROR: Candidate Gate output not found: "
                f"{generated_candidates}"
            )

    if not args.skip_testing_import:
        candidates_path = args.candidates or generated_candidates

        if not candidates_path:
            raise SystemExit(
                "ERROR: --candidates is required unless "
                "--run-hunter or --skip-testing-import is used"
            )

        if not args.testing_decisions:
            raise SystemExit(
                "ERROR: --testing-decisions is required unless "
                "--skip-testing-import is used"
            )

        command = [
            python,
            str(PROMOTE_APPROVED),
            "--candidates",
            str(candidates_path),
            "--decisions",
            str(args.testing_decisions),
            "--channels",
            str(args.channels),
        ]

        if args.apply_testing:
            command.append("--apply")

        run_step(
            "Candidate approval -> testing",
            command,
        )

    run_step(
        "Testing Promotion Gate",
        [
            python,
            str(TESTING_GATE),
            "--channels",
            str(args.channels),
            "--required-passes",
            str(args.required_passes),
            "--min-gap-hours",
            str(args.min_gap_hours),
        ],
    )

    print_promotion_dashboard()

    if not args.skip_stable_promotion:
        if not args.stable_decisions:
            print()
            print(
                "ℹ️ Stable promotion skipped: "
                "--stable-decisions not supplied."
            )
        else:
            command = [
                python,
                str(PROMOTE_STABLE),
                "--decisions",
                str(args.stable_decisions),
                "--channels",
                str(args.channels),
            ]

            if args.apply_stable:
                command.append("--apply")

            run_step(
                "Testing -> stable",
                command,
            )

    if args.generate_playlists:
        run_step(
            "Generate playlists",
            [
                python,
                str(GENERATE_PLAYLISTS),
            ],
        )

    print()
    print("=" * 72)
    print("✅ Bondik pipeline finished")
    print("=" * 72)
    print(
        "🐾 Safety gates remain active. "
        "No promotion occurs without the underlying checks."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())



