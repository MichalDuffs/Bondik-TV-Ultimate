from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(ROOT),
    )

from tools.github_api import SafeRedirectHandler

GITHUB_SERVICE_PROTOCOL = (
    "bondik-city-github-service/1"
)
GITHUB_SERVICE_VERSION = 1
CITY_ID = "bondik-city"
BUILDING_ID = "github-service"
API_ROOT = "https://api.github.com"
DEFAULT_REPOSITORY = (
    "MichalDuffs/Bondik-TV-Ultimate"
)
DEFAULT_OUTPUT = Path(
    "city-github-snapshot.json"
)

REPOSITORY_RE = re.compile(
    r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$"
)


class CityGitHubServiceError(
    ValueError
):
    pass


def validate_repository_name(
    repository: str,
) -> str:
    if not REPOSITORY_RE.fullmatch(
        repository
    ):
        raise CityGitHubServiceError(
            "repository must use owner/name"
        )

    return repository


def _decode_json_response(
    raw: bytes,
    *,
    label: str,
) -> Any:
    try:
        return json.loads(
            raw.decode("utf-8")
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as error:
        raise CityGitHubServiceError(
            f"{label} returned invalid JSON"
        ) from error


def github_get_json(
    path: str,
    *,
    token: str | None = None,
    opener=None,
) -> Any:
    if not path.startswith("/repos/"):
        raise CityGitHubServiceError(
            "GitHub service path must stay "
            "inside /repos/"
        )

    url = f"{API_ROOT}{path}"

    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": (
            "Bondik-City-GitHub-Service/1"
        ),
    }

    if token:
        headers["Authorization"] = (
            f"Bearer {token}"
        )

    request = urllib.request.Request(
        url,
        headers=headers,
        method="GET",
    )

    if opener is None:
        opener = urllib.request.build_opener(
            SafeRedirectHandler()
        )

    try:
        with opener.open(
            request,
            timeout=20,
        ) as response:
            raw = response.read()
    except urllib.error.HTTPError as error:
        try:
            details = error.read().decode(
                "utf-8",
                errors="replace",
            )
        except OSError:
            details = (
                "<response body unavailable>"
            )

        raise CityGitHubServiceError(
            "GitHub API returned "
            f"HTTP {error.code}: {details}"
        ) from error
    except urllib.error.URLError as error:
        raise CityGitHubServiceError(
            "GitHub API request failed: "
            f"{error.reason}"
        ) from error

    return _decode_json_response(
        raw,
        label=path,
    )


def _require_dict(
    value: Any,
    *,
    label: str,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CityGitHubServiceError(
            f"{label} must be an object"
        )

    return value


def _require_list(
    value: Any,
    *,
    label: str,
) -> list[Any]:
    if not isinstance(value, list):
        raise CityGitHubServiceError(
            f"{label} must be a list"
        )

    return value


def _latest_default_branch_runs(
    workflow_runs: list[Any],
    *,
    default_branch: str,
) -> list[dict[str, Any]]:
    latest: dict[
        str,
        dict[str, Any],
    ] = {}

    for item in workflow_runs:
        if not isinstance(item, dict):
            continue

        if (
            item.get("head_branch")
            != default_branch
        ):
            continue

        key = (
            item.get("path")
            or item.get("name")
        )

        if (
            not isinstance(key, str)
            or not key
        ):
            continue

        previous = latest.get(key)

        created_at = item.get(
            "created_at",
            "",
        )
        previous_created_at = (
            previous.get(
                "created_at",
                "",
            )
            if previous
            else ""
        )

        if (
            previous is None
            or created_at
            > previous_created_at
        ):
            latest[key] = item

    result = []

    for key in sorted(latest):
        run = latest[key]
        result.append(
            {
                "name": run.get("name"),
                "path": run.get("path"),
                "status": run.get("status"),
                "conclusion": (
                    run.get("conclusion")
                ),
                "runNumber": (
                    run.get("run_number")
                ),
                "event": run.get("event"),
                "headSha": run.get(
                    "head_sha"
                ),
                "createdAt": run.get(
                    "created_at"
                ),
                "url": run.get(
                    "html_url"
                ),
            }
        )

    return result


def build_github_snapshot(
    repository: str,
    *,
    get_json: Callable[
        [str],
        Any,
    ],
) -> dict[str, Any]:
    repository = (
        validate_repository_name(
            repository
        )
    )
    encoded_repository = "/".join(
        urllib.parse.quote(
            part,
            safe="",
        )
        for part
        in repository.split("/")
    )
    base = f"/repos/{encoded_repository}"

    repo_payload = _require_dict(
        get_json(base),
        label="repository response",
    )

    default_branch = repo_payload.get(
        "default_branch"
    )

    if (
        not isinstance(
            default_branch,
            str,
        )
        or not default_branch
    ):
        raise CityGitHubServiceError(
            "repository default branch missing"
        )

    encoded_branch = urllib.parse.quote(
        default_branch,
        safe="",
    )

    branch_payload = _require_dict(
        get_json(
            f"{base}/branches/{encoded_branch}"
        ),
        label="branch response",
    )

    branch_commit = _require_dict(
        branch_payload.get("commit"),
        label="branch commit",
    )
    branch_sha = branch_commit.get(
        "sha"
    )

    if (
        not isinstance(branch_sha, str)
        or not branch_sha
    ):
        raise CityGitHubServiceError(
            "default branch SHA missing"
        )

    pulls = _require_list(
        get_json(
            f"{base}/pulls"
            "?state=open&per_page=100"
        ),
        label="pull request response",
    )

    issues_payload = _require_list(
        get_json(
            f"{base}/issues"
            "?state=open&per_page=100"
        ),
        label="issue response",
    )
    issues = [
        issue
        for issue in issues_payload
        if (
            isinstance(issue, dict)
            and "pull_request"
            not in issue
        )
    ]

    runs_payload = _require_dict(
        get_json(
            f"{base}/actions/runs"
            "?per_page=100"
        ),
        label="workflow runs response",
    )
    workflow_runs = _require_list(
        runs_payload.get(
            "workflow_runs"
        ),
        label="workflow_runs",
    )

    workflows = (
        _latest_default_branch_runs(
            workflow_runs,
            default_branch=default_branch,
        )
    )

    return {
        "protocol": (
            GITHUB_SERVICE_PROTOCOL
        ),
        "version": (
            GITHUB_SERVICE_VERSION
        ),
        "cityId": CITY_ID,
        "buildingId": BUILDING_ID,
        "mode": (
            "read-only-repository-evidence"
        ),
        "repository": {
            "fullName": repository,
            "visibility": (
                repo_payload.get(
                    "visibility"
                )
            ),
            "defaultBranch": (
                default_branch
            ),
            "defaultBranchHead": (
                branch_sha
            ),
            "pushedAt": (
                repo_payload.get(
                    "pushed_at"
                )
            ),
            "url": repo_payload.get(
                "html_url"
            ),
        },
        "pullRequests": {
            "openCount": len(pulls),
            "truncated": (
                len(pulls) == 100
            ),
        },
        "issues": {
            "openCount": len(issues),
            "truncated": (
                len(issues_payload) == 100
            ),
        },
        "workflows": {
            "defaultBranchLatest": (
                workflows
            ),
            "sourceRunWindow": len(
                workflow_runs
            ),
            "truncated": (
                len(workflow_runs)
                == 100
            ),
        },
        "exposure": {
            "mutation": "not-allowed",
            "token": "not-exported",
            "execution": "not-exposed",
        },
    }


def write_snapshot(
    path: Path,
    payload: dict[str, Any],
) -> None:
    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def parse_arguments():
    parser = argparse.ArgumentParser(
        description=(
            "Build a read-only Bondik City "
            "GitHub repository snapshot."
        )
    )
    parser.add_argument(
        "--repository",
        default=DEFAULT_REPOSITORY,
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
    )
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()
    token = os.environ.get(
        "GITHUB_TOKEN"
    )

    def get_json(path: str):
        return github_get_json(
            path,
            token=token,
        )

    try:
        snapshot = build_github_snapshot(
            args.repository,
            get_json=get_json,
        )
        write_snapshot(
            args.output,
            snapshot,
        )
    except CityGitHubServiceError as error:
        print(
            "❌ Bondik City GitHub Service: "
            f"{error}"
        )
        return 1

    repository = snapshot["repository"]

    print(
        "Bondik City GitHub Service OK: "
        f"{repository['defaultBranch']} @ "
        f"{repository['defaultBranchHead'][:12]} / "
        "open PRs "
        f"{snapshot['pullRequests']['openCount']} / "
        "workflows "
        f"{len(snapshot['workflows']['defaultBranchLatest'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
