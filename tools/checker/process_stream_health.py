#!/usr/bin/env python3
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

FAILURE_RE = re.compile(r"^❌ (.+) \[stable\]$")
SEPARATOR = "=" * 60

class SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected is None:
            return None
        old_host = urllib.parse.urlparse(req.full_url).netloc
        new_host = urllib.parse.urlparse(newurl).netloc
        if old_host != new_host:
            redirected.remove_header("Authorization")
        return redirected

OPENER = urllib.request.build_opener(SafeRedirectHandler())

def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, default=Path("stream-check-report.txt"))
    parser.add_argument("--history", type=Path, default=Path("stream-history.txt"))
    parser.add_argument(
        "--state",
        type=Path,
        default=Path("stream-health-state.json"),
    )
    return parser.parse_args()

def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"missing required environment variable: {name}")
    return value

def github_request(url: str, token: str, *, method: str = "GET", payload=None) -> bytes:
    data = None
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with OPENER.open(request, timeout=30) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"GitHub API returned HTTP {exc.code}: {details}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"GitHub API request failed: {exc.reason}") from exc

def github_json(url: str, token: str, *, method: str = "GET", payload=None):
    raw = github_request(url, token, method=method, payload=payload)
    return {} if not raw else json.loads(raw.decode("utf-8"))

def extract_failures(report: str) -> set[str]:
    failures = set()
    for line in report.splitlines():
        match = FAILURE_RE.fullmatch(line.strip())
        if match:
            failures.add(match.group(1))
    return failures

def parse_streak_state(raw: str) -> dict[str, int]:
    payload = json.loads(raw)

    if not isinstance(payload, dict):
        raise ValueError("stream health state must be a JSON object")

    streaks: dict[str, int] = {}

    for channel, streak in payload.items():
        if not isinstance(channel, str) or not channel.strip():
            raise ValueError("stream health state contains an invalid channel name")

        if not isinstance(streak, int) or isinstance(streak, bool) or streak < 1:
            raise ValueError(
                f"stream health state contains an invalid streak for {channel}"
            )

        streaks[channel] = streak

    return streaks


def advance_streaks(
    current_failed: set[str],
    previous_streaks: dict[str, int],
    ) -> dict[str, int]:
    return {
        channel: previous_streaks.get(channel, 0) + 1
        for channel in sorted(current_failed)
    }


def write_streak_state(path: Path, streaks: dict[str, int]) -> None:
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


def find_previous_health_data(
    *,
    api_url: str,
    repository: str,
    run_id: int,
    token: str,
):
    artifacts = github_json(
        f"{api_url}/repos/{repository}/actions/artifacts?per_page=100",
        token,
    ).get("artifacts", [])

    candidates = []

    for artifact in artifacts:
        workflow_run = artifact.get("workflow_run") or {}

        if artifact.get("expired", False):
            continue

        if workflow_run.get("id") == run_id:
            continue

        if not artifact.get("name", "").startswith("stream-check-"):
            continue

        candidates.append(artifact)

    if not candidates:
        return None, {}

    previous = max(
        candidates,
        key=lambda artifact: artifact.get("created_at", ""),
    )

    archive_bytes = github_request(
        f"{api_url}/repos/{repository}/actions/artifacts/{previous['id']}/zip",
        token,
    )

    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        try:
            report_bytes = archive.read("stream-check-report.txt")
            previous_report = report_bytes.decode(
                "utf-8-sig",
                errors="replace",
            )
        except KeyError:
            previous_report = ""

        try:
            state_bytes = archive.read("stream-health-state.json")
        except KeyError:
            previous_streaks = {
                channel: 1
                for channel in extract_failures(previous_report)
            }
        else:
            try:
                previous_streaks = parse_streak_state(
                    state_bytes.decode(
                        "utf-8-sig",
                        errors="replace",
                    )
                )
            except (json.JSONDecodeError, ValueError) as exc:
                print(
                    "⚠️ Previous streak state invalid - "
                    f"falling back to report: {exc}"
                )
                previous_streaks = {
                    channel: 1
                    for channel in extract_failures(previous_report)
                }

    return previous_report, previous_streaks

def build_history(
    current_failed: set[str],
    previous_report,
    previous_streaks: dict[str, int] | None = None,
):
    lines = ["", SEPARATOR, "\U0001f43e Bond\u00edk Stream History"]

    if previous_streaks is None:
        previous_failed = (
            set()
            if previous_report is None
            else extract_failures(previous_report)
        )
        previous_streaks = {
            channel: 1
            for channel in previous_failed
        }

    current_streaks = advance_streaks(
        current_failed,
        previous_streaks,
    )

    repeated = []
    recovered = []

    if previous_report is None and not previous_streaks:
        lines.append(
            "\u2139\ufe0f No previous report available - baseline created."
        )

        for channel in sorted(current_failed):
            lines.append(
                f"\u26a0\ufe0f New failure: {channel} "
                f"(streak \u00d7{current_streaks[channel]})"
            )

        return "\n".join(lines) + "\n", repeated, recovered

    new_failures = sorted(
        channel
        for channel in current_failed
        if channel not in previous_streaks
    )

    repeated = sorted(
        channel
        for channel in current_failed
        if channel in previous_streaks
    )

    recovered = sorted(
        set(previous_streaks) - current_failed
    )

    for channel in new_failures:
        lines.append(
            f"\u26a0\ufe0f New failure: {channel} "
            f"(streak \u00d7{current_streaks[channel]})"
        )

    for channel in repeated:
        lines.append(
            f"\U0001f6a8 Repeated failure: {channel} "
            f"(streak \u00d7{current_streaks[channel]})"
        )

    for channel in recovered:
        lines.append(
            f"\u2705 Recovered since previous run: {channel} "
            f"(previous streak \u00d7{previous_streaks[channel]})"
        )

    if not new_failures and not repeated and not recovered:
        if current_failed:
            lines.append("\u2139\ufe0f Stream health unchanged.")
        else:
            lines.append(
                "\U0001f7e2 No stream health changes - all streams healthy."
            )

    return "\n".join(lines) + "\n", repeated, recovered


def append_text(path: Path, text: str) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(text)

def list_open_issues(*, api_url: str, repository: str, token: str):
    payload = github_json(
        f"{api_url}/repos/{repository}/issues?state=open&per_page=100", token
    )
    return [issue for issue in payload if "pull_request" not in issue]

def find_issue_number(issues, title: str):
    for issue in issues:
        if issue.get("title") == title and isinstance(issue.get("number"), int):
            return issue["number"]
    return None

def create_outage_issue(*, api_url, repository, token, server_url, run_id, sha, channel):
    title = f"🚨 Stream outage: {channel}"
    body = f"""## 🐾 Bondík Stream Health Alert

The stream **{channel}** failed in consecutive health checks.

This issue was created automatically after Bondík confirmed that the failure was not just a temporary outage.

- Run: {server_url}/{repository}/actions/runs/{run_id}
- Commit: `{sha}`
- Status: 🚨 repeated failure

The issue will be closed automatically when the stream recovers.

---
🐾 Bondik TV Ultimate
"""
    return github_json(
        f"{api_url}/repos/{repository}/issues",
        token,
        method="POST",
        payload={"title": title, "body": body},
    )

def should_comment_on_streak(streak: int) -> bool:
    if streak == 3:
        return True

    return streak >= 5 and streak % 5 == 0


def comment_outage_issue(
    *,
    api_url,
    repository,
    token,
    server_url,
    run_id,
    sha,
    channel,
    streak,
    issue_number,
):
    body = f"""## \U0001f43e Bondik Stream Health Update

The stream **{channel}** is still unavailable.

- Run: {server_url}/{repository}/actions/runs/{run_id}
- Commit: `{sha}`
- Status: \U0001f6a8 outage continues
- Failure streak: \u00d7{streak}

Bondik will keep monitoring the stream automatically.

---
\U0001f43e Bondik TV Ultimate
"""

    github_json(
        f"{api_url}/repos/{repository}/issues/{issue_number}/comments",
        token,
        method="POST",
        payload={"body": body},
    )


def close_issue(*, api_url, repository, token, issue_number):
    github_json(
        f"{api_url}/repos/{repository}/issues/{issue_number}",
        token,
        method="PATCH",
        payload={"state": "closed", "state_reason": "completed"},
    )

def manage_issues(
    *,
    api_url,
    repository,
    token,
    server_url,
    run_id,
    sha,
    repeated,
    recovered,
    streaks=None,
):
    streaks = streaks or {}
    if not repeated and not recovered:
        print("No issue action required.")
        return
    open_issues = list_open_issues(
        api_url=api_url, repository=repository, token=token
    )
    for channel in repeated:
        title = f"🚨 Stream outage: {channel}"
        existing = find_issue_number(open_issues, title)
        if existing is not None:
            streak = streaks.get(channel)

            if streak is not None and should_comment_on_streak(streak):
                comment_outage_issue(
                    api_url=api_url,
                    repository=repository,
                    token=token,
                    server_url=server_url,
                    run_id=run_id,
                    sha=sha,
                    channel=channel,
                    streak=streak,
                    issue_number=existing,
                )

                print(
                    f"Updated issue #{existing} for {channel} "
                    f"(streak \u00d7{streak})."
                )
            else:
                print(
                    f"Issue already open for {channel} "
                    f"(#{existing})."
                )

            continue
        issue = create_outage_issue(
            api_url=api_url,
            repository=repository,
            token=token,
            server_url=server_url,
            run_id=run_id,
            sha=sha,
            channel=channel,
        )
        number = issue.get("number")
        print(f"Created issue #{number} for {channel}.")
        if isinstance(number, int):
            open_issues.append(issue)
    for channel in recovered:
        title = f"🚨 Stream outage: {channel}"
        issue_number = find_issue_number(open_issues, title)
        if issue_number is None:
            print(f"No open issue found for recovered stream {channel}.")
            continue
        close_issue(
            api_url=api_url,
            repository=repository,
            token=token,
            issue_number=issue_number,
        )
        print(f"Closed issue #{issue_number} - {channel} recovered.")
        open_issues = [
            issue for issue in open_issues if issue.get("number") != issue_number
        ]

def main() -> int:
    args = parse_arguments()

    if not args.report.is_file():
        print(
            f"\u274c Stream report not found: {args.report}",
            file=sys.stderr,
        )
        return 1

    try:
        token = require_env("GITHUB_TOKEN")
        api_url = require_env("GITHUB_API_URL")
        repository = require_env("GITHUB_REPOSITORY")
        run_id = int(require_env("GITHUB_RUN_ID"))
        server_url = os.environ.get(
            "GITHUB_SERVER_URL",
            "https://github.com",
        )
        sha = require_env("GITHUB_SHA")

        current_report = args.report.read_text(encoding="utf-8")
        current_failed = extract_failures(current_report)

        previous_report, previous_streaks = find_previous_health_data(
            api_url=api_url,
            repository=repository,
            run_id=run_id,
            token=token,
        )

        current_streaks = advance_streaks(
            current_failed,
            previous_streaks,
        )

        history_text, repeated, recovered = build_history(
            current_failed,
            previous_report,
            previous_streaks,
        )

        write_streak_state(
            args.state,
            current_streaks,
        )

        args.history.write_text(
            history_text,
            encoding="utf-8",
            newline="\n",
        )

        append_text(args.report, history_text)

        step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if step_summary:
            append_text(Path(step_summary), history_text)

        print(history_text.rstrip())

        manage_issues(
            api_url=api_url,
            repository=repository,
            token=token,
            server_url=server_url,
            run_id=run_id,
            sha=sha,
            repeated=repeated,
            recovered=recovered,
            streaks=current_streaks,
        )

    except Exception as exc:
        print(
            f"\u274c Stream health processing failed: {exc}",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
