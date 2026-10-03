import json

import pytest

from tools.city.build_github_service_snapshot import (
    GITHUB_SERVICE_PROTOCOL,
    CityGitHubServiceError,
    build_github_snapshot,
    validate_repository_name,
)


REPOSITORY = (
    "MichalDuffs/Bondik-TV-Ultimate"
)


def fake_payloads():
    base = (
        "/repos/"
        "MichalDuffs/"
        "Bondik-TV-Ultimate"
    )

    return {
        base: {
            "default_branch": "main",
            "visibility": "public",
            "pushed_at": (
                "2026-10-03T14:00:00Z"
            ),
            "html_url": (
                "https://github.com/"
                "MichalDuffs/"
                "Bondik-TV-Ultimate"
            ),
        },
        (
            f"{base}/branches/main"
        ): {
            "commit": {
                "sha": (
                    "abcdef0123456789"
                )
            }
        },
        (
            f"{base}/pulls"
            "?state=open&per_page=100"
        ): [
            {"number": 61},
            {"number": 62},
        ],
        (
            f"{base}/issues"
            "?state=open&per_page=100"
        ): [
            {"number": 34},
            {
                "number": 61,
                "pull_request": {},
            },
            {"number": 55},
        ],
        (
            f"{base}/actions/runs"
            "?per_page=100"
        ): {
            "workflow_runs": [
                {
                    "name": (
                        "Bondik TV "
                        "Stream Check"
                    ),
                    "path": (
                        ".github/workflows/"
                        "stream-check.yml"
                    ),
                    "head_branch": "main",
                    "head_sha": "aaa",
                    "status": "completed",
                    "conclusion": "failure",
                    "run_number": 128,
                    "event": "schedule",
                    "created_at": (
                        "2026-10-03T09:35:14Z"
                    ),
                    "html_url": (
                        "https://example/"
                        "stream-128"
                    ),
                },
                {
                    "name": (
                        "Bondik TV "
                        "Stream Check"
                    ),
                    "path": (
                        ".github/workflows/"
                        "stream-check.yml"
                    ),
                    "head_branch": "main",
                    "head_sha": "old",
                    "status": "completed",
                    "conclusion": "success",
                    "run_number": 127,
                    "event": "schedule",
                    "created_at": (
                        "2026-10-02T09:35:14Z"
                    ),
                    "html_url": (
                        "https://example/"
                        "stream-127"
                    ),
                },
                {
                    "name": (
                        "Feature CI"
                    ),
                    "path": (
                        ".github/workflows/"
                        "feature.yml"
                    ),
                    "head_branch": (
                        "feat/example"
                    ),
                    "head_sha": "feature",
                    "status": "completed",
                    "conclusion": "success",
                    "run_number": 5,
                    "event": "pull_request",
                    "created_at": (
                        "2026-10-03T10:00:00Z"
                    ),
                    "html_url": (
                        "https://example/"
                        "feature"
                    ),
                },
            ]
        },
    }


def fake_get_json(path):
    return fake_payloads()[path]


def test_builds_read_only_repository_snapshot():
    snapshot = build_github_snapshot(
        REPOSITORY,
        get_json=fake_get_json,
    )

    assert snapshot["protocol"] == (
        GITHUB_SERVICE_PROTOCOL
    )
    assert snapshot["repository"][
        "defaultBranch"
    ] == "main"
    assert snapshot["repository"][
        "defaultBranchHead"
    ] == "abcdef0123456789"
    assert snapshot["pullRequests"][
        "openCount"
    ] == 2
    assert snapshot["issues"][
        "openCount"
    ] == 2
    assert snapshot["exposure"] == {
        "mutation": "not-allowed",
        "token": "not-exported",
        "execution": "not-exposed",
    }


def test_workflows_use_latest_default_branch_run():
    snapshot = build_github_snapshot(
        REPOSITORY,
        get_json=fake_get_json,
    )
    workflows = snapshot[
        "workflows"
    ]["defaultBranchLatest"]

    assert len(workflows) == 1
    assert workflows[0]["runNumber"] == 128
    assert workflows[0]["conclusion"] == "failure"
    assert workflows[0]["headSha"] == "aaa"


@pytest.mark.parametrize(
    "repository",
    [
        "",
        "owner",
        "owner/repo/extra",
        "owner repo/name",
        "owner/name?x=1",
    ],
)
def test_invalid_repository_is_rejected(
    repository,
):
    with pytest.raises(
        CityGitHubServiceError,
        match="owner/name",
    ):
        validate_repository_name(
            repository
        )


def test_missing_default_branch_is_rejected():
    payloads = fake_payloads()
    base = (
        "/repos/"
        "MichalDuffs/"
        "Bondik-TV-Ultimate"
    )
    payloads[base] = {}

    with pytest.raises(
        CityGitHubServiceError,
        match="default branch missing",
    ):
        build_github_snapshot(
            REPOSITORY,
            get_json=payloads.__getitem__,
        )


def test_issue_count_excludes_pull_requests():
    snapshot = build_github_snapshot(
        REPOSITORY,
        get_json=fake_get_json,
    )

    assert snapshot["issues"][
        "openCount"
    ] == 2
