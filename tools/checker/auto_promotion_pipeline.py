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
import json
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

    parser.add_argument(
        "--show-approval-queue",
        action="store_true",
        help="Show the current NEW-candidate approval queue and exit",
    )

    decision_group = parser.add_mutually_exclusive_group()

    decision_group.add_argument(
        "--approve",
        type=int,
        metavar="N",
        help="Approve candidate number N in the current approval queue",
    )

    decision_group.add_argument(
        "--reject",
        type=int,
        metavar="N",
        help="Reject candidate number N in the current approval queue",
    )

    return parser.parse_args()


def write_candidate_approval_queue(
    csv_path: Path,
    output_path: Path,
) -> None:
    if not csv_path.exists():
        return

    import csv

    with csv_path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        rows = list(csv.DictReader(handle))

    candidates = []

    for row in rows:
        existing = str(
            row.get("existing_channel_id", "")
        ).strip()

        if existing:
            continue

        url = str(row.get("url", "")).strip()

        if not url:
            continue

        candidates.append(
            {
                "name": str(
                    row.get("candidate_name", "")
                ).strip(),
                "country": str(
                    row.get("country_inferred", "")
                ).strip(),
                "category": (
                    str(
                        row.get("category_inferred", "")
                    ).strip()
                    or "unknown"
                ),
                "score": str(
                    row.get("bondik_score", "")
                ).strip(),
                "host": str(
                    row.get("stream_host", "")
                ).strip(),
                "flags": str(
                    row.get("review_flags", "")
                ).strip(),
                "url": url,
                "decision": "pending",
            }
        )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        json.dumps(
            {"candidates": candidates},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print()
    print(
        f"?? Approval queue written: "
        f"{output_path}"
    )
    print(
        f"?? Pending NEW candidates: "
        f"{len(candidates)}"
    )


def print_candidate_review_dashboard(csv_path: Path) -> None:
    if not csv_path.exists():
        print()
        print("? Candidate review dashboard unavailable: review.csv not found.")
        return

    import csv

    with csv_path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        rows = list(csv.DictReader(handle))

    new_items = []
    alternatives = []

    for row in rows:
        name = str(row.get("candidate_name", "")).strip()
        country = str(row.get("country_inferred", "")).strip()
        category = str(row.get("category_inferred", "")).strip() or "unknown"
        score = str(row.get("bondik_score", "")).strip()
        host = str(row.get("stream_host", "")).strip()
        existing = str(row.get("existing_channel_id", "")).strip()
        flags = str(row.get("review_flags", "")).strip()

        item = {
            "name": name,
            "country": country,
            "category": category,
            "score": score,
            "host": host,
            "existing": existing,
            "flags": flags,
        }

        if existing:
            alternatives.append(item)
        else:
            new_items.append(item)

    print()
    print("=" * 72)
    print("?? Bondik Candidate Review Dashboard")
    print("=" * 72)
    print(f"NEW CANDIDATES : {len(new_items)}")
    print(f"ALTERNATIVES   : {len(alternatives)}")

    if new_items:
        print()
        print("New candidates:")

        for item in new_items:
            print(
                f"?? {item['name']} "
                f"({item['country']} / {item['category']}) "
                f"score={item['score']}"
            )
            print(f"   host : {item['host']}")
            print(f"   flags: {item['flags']}")

    if alternatives:
        print()
        print("Existing-channel alternatives:")

        for item in alternatives:
            print(
                f"?? {item['name']} "
                f"-> existing={item['existing']} "
                f"score={item['score']}"
            )
            print(f"   flags: {item['flags']}")


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


def set_candidate_provenance(
    path: Path,
    index: int,
    level: str,
    website: str,
    evidence: list[str],
    note: str,
) -> int:
    """Attach provenance evidence without weakening the v1.1 gate."""

    allowed_levels = {
        "official",
        "corroborated",
        "unverified",
    }

    if level not in allowed_levels:
        print(f"ERROR: invalid provenance level: {level}")
        return 1

    if not path.exists():
        print(f"ERROR: approval queue not found: {path}")
        return 1

    payload = json.loads(
        path.read_text(encoding="utf-8-sig")
    )

    candidates = payload.get("candidates", [])

    if (
        not isinstance(candidates, list)
        or index < 1
        or index > len(candidates)
    ):
        print(f"ERROR: candidate number {index} does not exist")
        return 1

    item = candidates[index - 1]

    if not isinstance(item, dict):
        print("ERROR: invalid candidate entry")
        return 1

    # Critical safety rule:
    # only direct official provenance satisfies v1.1 verified=True.
    verified = level == "official"

    item["provenance"] = {
        "level": level,
        "verified": verified,
        "website": website.strip(),
        "evidence": [
            str(value).strip()
            for value in evidence
            if str(value).strip()
        ],
        "note": note.strip(),
    }

    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    name = (
        str(item.get("name", "")).strip()
        or str(item.get("url", "")).strip()
        or f"candidate {index}"
    )

    print()
    print("=" * 72)
    print("Bondik Provenance Update")
    print("=" * 72)
    print(f"Candidate : {index}. {name}")
    print(f"Level     : {level.upper()}")
    print(f"Verified  : {verified}")
    print(f"Website   : {website}")
    print()
    print("Evidence stored. Existing promotion safety gates remain unchanged.")

    return 0


def set_approval_decision(
    path: Path,
    index: int,
    decision: str,
) -> int:
    if not path.exists():
        print(f"ERROR: approval queue not found: {path}")
        return 1

    if index < 1:
        print("ERROR: candidate number must be 1 or greater")
        return 1

    payload = json.loads(
        path.read_text(encoding="utf-8-sig")
    )

    candidates = payload.get("candidates", [])

    if not isinstance(candidates, list):
        print("ERROR: invalid approval queue")
        return 1

    if index > len(candidates):
        print(
            f"ERROR: candidate number {index} does not exist "
            f"(queue contains {len(candidates)})"
        )
        return 1

    if decision not in {"approve", "reject"}:
        print(f"ERROR: invalid decision: {decision}")
        return 1

    item = candidates[index - 1]

    if not isinstance(item, dict):
        print("ERROR: invalid candidate entry")
        return 1

    previous = (
        str(item.get("decision", "")).strip()
        or "pending"
    )

    item["decision"] = decision

    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    name = (
        str(item.get("name", "")).strip()
        or str(item.get("url", "")).strip()
        or f"candidate {index}"
    )

    print()
    print("=" * 72)
    print("Bondik Approval Decision")
    print("=" * 72)
    print(f"Candidate : {index}. {name}")
    print(f"Previous  : {previous.upper()}")
    print(f"Decision  : {decision.upper()}")
    print()
    print("Queue updated only. No channel promotion was performed.")

    return 0


def show_approval_queue(path: Path) -> int:
    if not path.exists():
        print(f"ERROR: approval queue not found: {path}")
        return 1

    payload = json.loads(
        path.read_text(encoding="utf-8-sig")
    )

    candidates = payload.get("candidates", [])

    print()
    print("=" * 72)
    print("?? Bondik Approval Queue")
    print("=" * 72)

    if not candidates:
        print("No pending candidates.")
        return 0

    for index, item in enumerate(candidates, start=1):
        name = str(item.get("name", "")).strip() or "Unknown"
        country = str(item.get("country", "")).strip() or "?"
        category = str(item.get("category", "")).strip() or "unknown"
        score = str(item.get("score", "")).strip() or "?"
        host = str(item.get("host", "")).strip()
        flags = str(item.get("flags", "")).strip()
        url = str(item.get("url", "")).strip()
        decision = (
            str(item.get("decision", "")).strip()
            or "pending"
        )

        provenance = item.get("provenance")

        if isinstance(provenance, dict):
            provenance_level = (
                str(provenance.get("level", "")).strip()
                or "unverified"
            )
            provenance_verified = (
                provenance.get("verified") is True
            )
        else:
            provenance_level = "missing"
            provenance_verified = False

        verification_label = (
            "VERIFIED"
            if provenance_verified
            else "NOT VERIFIED"
        )

        print(
            f"{index}. {name} | {country} | "
            f"{category} | score={score} | "
            f"{decision.upper()}"
        )

        print(
            f"   provenance: "
            f"{provenance_level.upper()} / "
            f"{verification_label}"
        )

        if host:
            print(f"   host      : {host}")

        if flags:
            print(f"   flags     : {flags}")

        print(f"   url       : {url}")

    return 0


def main() -> int:
    args = parse_args()

    print()
    print(f"🐾 Bondik AUTO-PROMOTION PIPELINE v{VERSION}")
    print("=" * 72)
    print(f"Testing apply : {args.apply_testing}")
    print(f"Stable apply  : {args.apply_stable}")
    print("=" * 72)

    approval_queue = (
        args.candidate_out_dir / "approval-queue.json"
    )

    if args.show_approval_queue:
        return show_approval_queue(
            approval_queue
        )

    if args.approve is not None:
        return set_approval_decision(
            approval_queue,
            args.approve,
            "approve",
        )

    if args.reject is not None:
        return set_approval_decision(
            approval_queue,
            args.reject,
            "reject",
        )

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

        review_csv = (
            args.candidate_out_dir / "review.csv"
        )

        print_candidate_review_dashboard(
            review_csv
        )

        write_candidate_approval_queue(
            review_csv,
            args.candidate_out_dir
            / "approval-queue.json",
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





