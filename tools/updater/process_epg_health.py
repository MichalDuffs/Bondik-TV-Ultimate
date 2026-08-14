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
    *,
    method: str = "GET",
    payload=None,
) -> bytes:
    data = None

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    if payload is not None:
        data = json.dumps(
            payload,
            ensure_ascii=False,
        ).encode("utf-8")

        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(
        url,
        data=data,
        headers=headers,
        method=method,
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
    *,
    method: str = "GET",
    payload=None,
):
    raw = github_request(
        url,
        token,
        method=method,
        payload=payload,
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


EPG_OUTAGE_LABELS = (
    {
        "name": "epg-health",
        "color": "1d76db",
        "description": "Automated EPG health monitoring",
    },
    {
        "name": "automated",
        "color": "bfdadc",
        "description": "Created or managed automatically",
    },
    {
        "name": "outage",
        "color": "d73a4a",
        "description": "Confirmed service outage",
    },
)


def list_open_issues(
    *,
    api_url: str,
    repository: str,
    token: str,
):
    payload = github_json(
        (
            f"{api_url}/repos/{repository}"
            "/issues?state=open&per_page=100"
        ),
        token,
    )

    return [
        issue
        for issue in payload
        if "pull_request" not in issue
    ]


def find_issue_number(
    issues,
    title: str,
):
    for issue in issues:
        if (
            issue.get("title") == title
            and isinstance(
                issue.get("number"),
                int,
            )
        ):
            return issue["number"]

    return None


def ensure_epg_labels(
    *,
    api_url: str,
    repository: str,
    token: str,
) -> None:
    labels = github_json(
        (
            f"{api_url}/repos/{repository}"
            "/labels?per_page=100"
        ),
        token,
    )

    if not isinstance(labels, list):
        raise RuntimeError(
            "GitHub labels response "
            "must be a list"
        )

    existing = {
        label.get("name")
        for label in labels
        if isinstance(label, dict)
    }

    for label in EPG_OUTAGE_LABELS:
        if label["name"] in existing:
            continue

        github_json(
            (
                f"{api_url}/repos/{repository}"
                "/labels"
            ),
            token,
            method="POST",
            payload=label,
        )


def create_epg_issue(
    *,
    api_url: str,
    repository: str,
    token: str,
    server_url: str,
    run_id: int,
    sha: str,
    source: str,
):
    ensure_epg_labels(
        api_url=api_url,
        repository=repository,
        token=token,
    )

    title = f"🚨 EPG outage: {source}"

    body = f"""## 🐾 Bondík EPG Health Alert

The EPG source **{source}** failed in consecutive health checks.

This issue was created automatically after Bondík confirmed that the failure was not just a temporary incident.

- Run: {server_url}/{repository}/actions/runs/{run_id}
- Commit: `{sha}`
- Status: 🚨 repeated EPG failure

The issue will be closed automatically when the EPG source recovers.

---
🐾 Bondik TV Ultimate
"""

    return github_json(
        (
            f"{api_url}/repos/{repository}"
            "/issues"
        ),
        token,
        method="POST",
        payload={
            "title": title,
            "body": body,
            "labels": [
                label["name"]
                for label in EPG_OUTAGE_LABELS
            ],
        },
    )


def close_issue(
    *,
    api_url: str,
    repository: str,
    token: str,
    issue_number: int,
) -> None:
    github_json(
        (
            f"{api_url}/repos/{repository}"
            f"/issues/{issue_number}"
        ),
        token,
        method="PATCH",
        payload={
            "state": "closed",
            "state_reason": "completed",
        },
    )


def should_comment_on_streak(
    streak: int,
) -> bool:
    if streak == 3:
        return True

    return (
        streak >= 5
        and streak % 5 == 0
    )


def comment_epg_issue(
    *,
    api_url: str,
    repository: str,
    token: str,
    server_url: str,
    run_id: int,
    sha: str,
    source: str,
    streak: int,
    issue_number: int,
) -> None:
    body = f"""## 🐾 Bondík EPG Health Update

The EPG source **{source}** is still failing.

- Run: {server_url}/{repository}/actions/runs/{run_id}
- Commit: `{sha}`
- Status: 🚨 EPG outage continues
- Failure streak: ×{streak}

Bondík will keep monitoring the EPG source automatically.

---
🐾 Bondik TV Ultimate
"""

    github_json(
        (
            f"{api_url}/repos/{repository}"
            f"/issues/{issue_number}/comments"
        ),
        token,
        method="POST",
        payload={
            "body": body,
        },
    )


def manage_issues(
    *,
    api_url: str,
    repository: str,
    token: str,
    server_url: str,
    run_id: int,
    sha: str,
    repeated,
    recovered,
    streaks=None,
) -> None:
    streaks = streaks or {}

    if not repeated and not recovered:
        print(
            "No EPG issue action required."
        )
        return

    open_issues = list_open_issues(
        api_url=api_url,
        repository=repository,
        token=token,
    )

    for source in repeated:
        title = (
            f"🚨 EPG outage: {source}"
        )

        existing = find_issue_number(
            open_issues,
            title,
        )

        if existing is not None:
            streak = streaks.get(
                source
            )

            if (
                streak is not None
                and should_comment_on_streak(
                    streak
                )
            ):
                comment_epg_issue(
                    api_url=api_url,
                    repository=repository,
                    token=token,
                    server_url=server_url,
                    run_id=run_id,
                    sha=sha,
                    source=source,
                    streak=streak,
                    issue_number=existing,
                )

                print(
                    "Updated EPG issue "
                    f"#{existing} for {source} "
                    f"(streak ×{streak})."
                )

            else:
                print(
                    "EPG issue already open for "
                    f"{source} (#{existing})."
                )

            continue

        issue = create_epg_issue(
            api_url=api_url,
            repository=repository,
            token=token,
            server_url=server_url,
            run_id=run_id,
            sha=sha,
            source=source,
        )

        number = issue.get("number")

        print(
            f"Created EPG issue #{number} "
            f"for {source}."
        )

        if isinstance(number, int):
            open_issues.append(issue)

    for source in recovered:
        title = (
            f"🚨 EPG outage: {source}"
        )

        issue_number = find_issue_number(
            open_issues,
            title,
        )

        if issue_number is None:
            print(
                "No open EPG issue found "
                f"for recovered source {source}."
            )
            continue

        close_issue(
            api_url=api_url,
            repository=repository,
            token=token,
            issue_number=issue_number,
        )

        print(
            f"Closed EPG issue #{issue_number} "
            f"- {source} recovered."
        )

        open_issues = [
            issue
            for issue in open_issues
            if issue.get("number")
            != issue_number
        ]


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

    history, repeated, recovered = build_history(
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

    if (
        os.environ.get("GITHUB_ACTIONS")
        == "true"
    ):
        try:
            manage_issues(
                api_url=require_env(
                    "GITHUB_API_URL"
                ),
                repository=require_env(
                    "GITHUB_REPOSITORY"
                ),
                token=require_env(
                    "GITHUB_TOKEN"
                ),
                server_url=os.environ.get(
                    "GITHUB_SERVER_URL",
                    "https://github.com",
                ),
                run_id=int(
                    require_env(
                        "GITHUB_RUN_ID"
                    )
                ),
                sha=require_env(
                    "GITHUB_SHA"
                ),
                repeated=repeated,
                recovered=recovered,
                streaks=current_streaks,
            )

        except (
            RuntimeError,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            print(
                "❌ Unable to manage "
                f"EPG issues: {exc}",
                file=sys.stderr,
            )
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
