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

PROMOTE_APPROVED = ROOT / "tools" / "checker" / "promote_approved_candidates.py"
TESTING_GATE = ROOT / "tools" / "checker" / "testing_promotion_gate.py"
PROMOTE_STABLE = ROOT / "tools" / "checker" / "promote_testing_to_stable.py"

DEFAULT_CHANNELS = ROOT / "channels" / "channels.yaml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=f"Bondik AUTO-PROMOTION PIPELINE v{VERSION}"
    )

    parser.add_argument("--candidates", type=Path)
    parser.add_argument("--testing-decisions", type=Path)
    parser.add_argument("--stable-decisions", type=Path)

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

    return parser.parse_args()


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

    if not args.skip_testing_import:
        if not args.candidates:
            raise SystemExit(
                "ERROR: --candidates is required unless "
                "--skip-testing-import is used"
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
            str(args.candidates),
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

