#!/usr/bin/env python3
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path


SEPARATOR = "=" * 60


class SafeRedirectHandler(
    urllib.request.HTTPRedirectHandler
):
    def redirect_request(
        self,
        req,
        fp,
        code,
        msg,
        headers,
        newurl,
    ):
        redirected = super().redirect_request(
            req,
            fp,
            code,
            msg,
            headers,
            newurl,
        )

        if redirected is None:
            return None

        old_host = urllib.parse.urlparse(
            req.full_url
        ).netloc

        new_host = urllib.parse.urlparse(
            newurl
        ).netloc

        if old_host != new_host:
            redirected.remove_header(
                "Authorization"
            )

        return redirected


OPENER = urllib.request.build_opener(
    SafeRedirectHandler()
)


def parse_arguments():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--report",
        type=Path,
        default=Path("epg-check-report.txt"),
    )

    parser.add_argument(
        "--history",
        type=Path,
        default=Path("epg-history.txt"),
    )

    parser.add_argument(
        "--state",
        type=Path,
        default=Path("epg-health-state.json"),
    )

    return parser.parse_args()


def require_env(name: str) -> str:
    value = os.environ.get(name)

    if not value:
        raise RuntimeError(
            "missing required environment "
            f"variable: {name}"
        )

    return value


def github_request(
    url: str,
    token: str,
) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": (
                f"Bearer {token}"
            ),
            "Accept": (
                "application/vnd.github+json"
            ),
            "X-GitHub-Api-Version": (
                "2022-11-28"
            ),
        },
    )

    try:
        with OPENER.open(
            request,
            timeout=30,
        ) as response:
            return response.read()

    except urllib.error.HTTPError as exc:
        details = exc.read().decode(
            "utf-8",
            errors="replace",
        )

        raise RuntimeError(
            "GitHub API returned "
            f"HTTP {exc.code}: {details}"
        ) from exc

    except urllib.error.URLError as exc:
        raise RuntimeError(
            "GitHub API request failed: "
            f"{exc.reason}"
        ) from exc


def github_json(
    url: str,
    token: str,
):
    raw = github_request(
        url,
        token,
    )

    if not raw:
        return {}

    return json.loads(
        raw.decode("utf-8")
    )


def extract_failures(
    report: str,
) -> set[str]:
    failures: set[str] = set()
    current_source: str | None = None

    for raw_line in report.splitlines():
        line = raw_line.strip()

        if line.startswith("📡 "):
            current_source = (
                line.removeprefix("📡 ").strip()
            )
            continue

        if line.startswith("="):
            current_source = None
            continue

        if (
            current_source
            and raw_line[:1].isspace()
            and "❌" in line
        ):
            failures.add(
                current_source
            )

    return failures


def parse_streak_state(
    raw: str,
) -> dict[str, int]:
    payload = json.loads(raw)

    if not isinstance(payload, dict):
        raise ValueError(
            "EPG health state must be "
            "a JSON object"
        )

    streaks: dict[str, int] = {}

    for source, streak in payload.items():
        if (
            not isinstance(source, str)
            or not source.strip()
        ):
            raise ValueError(
                "invalid EPG source ID "
                "in health state"
            )

        if (
            not isinstance(streak, int)
            or isinstance(streak, bool)
            or streak < 1
        ):
            raise ValueError(
                "invalid EPG streak for "
                f"{source}"
            )

        streaks[source] = streak

    return streaks


def advance_streaks(
    current_failed: set[str],
    previous_streaks: dict[str, int],
) -> dict[str, int]:
    return {
        source: previous_streaks.get(
            source,
            0,
        ) + 1
        for source in sorted(
            current_failed
        )
    }


def find_previous_health_state(
    *,
    api_url: str,
    repository: str,
    run_id: int,
    token: str,
) -> dict[str, int]:
    payload = github_json(
        (
            f"{api_url}/repos/{repository}"
            "/actions/artifacts?per_page=100"
        ),
        token,
    )

    artifacts = payload.get(
        "artifacts",
        [],
    )

    candidates = []

    for artifact in artifacts:
        workflow_run = (
            artifact.get("workflow_run")
            or {}
        )

        if artifact.get(
            "expired",
            False,
        ):
            continue

        if workflow_run.get("id") == run_id:
            continue

        if not artifact.get(
            "name",
            "",
        ).startswith("epg-check-"):
            continue

        candidates.append(
            artifact
        )

    if not candidates:
        return {}

    previous = max(
        candidates,
        key=lambda artifact: artifact.get(
            "created_at",
            "",
        ),
    )

    archive = github_request(
        (
            f"{api_url}/repos/{repository}"
            "/actions/artifacts/"
            f"{previous['id']}/zip"
        ),
        token,
    )

    with zipfile.ZipFile(
        io.BytesIO(archive)
    ) as zip_file:
        try:
            state_bytes = zip_file.read(
                "epg-health-state.json"
            )
        except KeyError:
            return {}

    try:
        return parse_streak_state(
            state_bytes.decode(
                "utf-8-sig",
                errors="replace",
            )
        )

    except (
        json.JSONDecodeError,
        ValueError,
    ) as exc:
        print(
            "⚠️ Previous EPG state invalid - "
            f"baseline used: {exc}"
        )

        return {}


def build_history(
    current_failed: set[str],
    previous_streaks: dict[str, int],
):
    current_streaks = advance_streaks(
        current_failed,
        previous_streaks,
    )

    new_failures = sorted(
        source
        for source in current_failed
        if source not in previous_streaks
    )

    repeated = sorted(
        source
        for source in current_failed
        if source in previous_streaks
    )

    recovered = sorted(
        set(previous_streaks)
        - current_failed
    )

    lines = [
        "",
        SEPARATOR,
        "🐾 Bondík EPG History",
    ]

    for source in new_failures:
        lines.append(
            "⚠️ New EPG failure: "
            f"{source} "
            f"(streak ×{current_streaks[source]})"
        )

    for source in repeated:
        lines.append(
            "🚨 Repeated EPG failure: "
            f"{source} "
            f"(streak ×{current_streaks[source]})"
        )

    for source in recovered:
        lines.append(
            "✅ EPG recovered: "
            f"{source} "
            "(previous streak "
            f"×{previous_streaks[source]})"
        )

    if (
        not new_failures
        and not repeated
        and not recovered
    ):
        lines.append(
            "🟢 No EPG health changes - "
            "all sources healthy."
        )

    return (
        "\n".join(lines) + "\n",
        repeated,
        recovered,
    )


def write_streak_state(
    path: Path,
    streaks: dict[str, int],
) -> None:
    path.write_text(
        json.dumps(
            streaks,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def load_previous_streaks(
    state_path: Path,
) -> dict[str, int]:
    if (
        os.environ.get("GITHUB_ACTIONS")
        == "true"
    ):
        return find_previous_health_state(
            api_url=require_env(
                "GITHUB_API_URL"
            ),
            repository=require_env(
                "GITHUB_REPOSITORY"
            ),
            run_id=int(
                require_env(
                    "GITHUB_RUN_ID"
                )
            ),
            token=require_env(
                "GITHUB_TOKEN"
            ),
        )

    if not state_path.is_file():
        return {}

    try:
        return parse_streak_state(
            state_path.read_text(
                encoding="utf-8-sig",
            )
        )

    except (
        json.JSONDecodeError,
        ValueError,
    ) as exc:
        print(
            "⚠️ Previous EPG state invalid - "
            f"baseline used: {exc}"
        )

        return {}


def main() -> int:
    args = parse_arguments()

    if not args.report.is_file():
        print(
            "❌ EPG report not found: "
            f"{args.report}",
            file=sys.stderr,
        )
        return 1

    report = args.report.read_text(
        encoding="utf-8-sig",
        errors="replace",
    )

    current_failed = extract_failures(
        report
    )

    try:
        previous_streaks = (
            load_previous_streaks(
                args.state
            )
        )
    except (
        RuntimeError,
        ValueError,
        zipfile.BadZipFile,
    ) as exc:
        print(
            "❌ Unable to load previous "
            f"EPG state: {exc}",
            file=sys.stderr,
        )
        return 1

    history, _, _ = build_history(
        current_failed,
        previous_streaks,
    )

    current_streaks = advance_streaks(
        current_failed,
        previous_streaks,
    )

    write_streak_state(
        args.state,
        current_streaks,
    )

    args.history.write_text(
        history,
        encoding="utf-8",
        newline="\n",
    )

    print(
        history,
        end="",
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
