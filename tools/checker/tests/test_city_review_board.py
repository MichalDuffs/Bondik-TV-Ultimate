import copy
import subprocess
import sys
from pathlib import Path

import pytest

from tools.city.permit_office import (
    prepare_permit_request,
)
ROOT = Path(__file__).resolve().parents[3]


from tools.city.review_board import (
    REVIEW_PROTOCOL,
    CityReviewError,
    load_contract,
    record_human_review,
)


def permit():
    return prepare_permit_request(
        ticket_id="permit-001",
        principal={
            "id": "demo-agent",
            "role": "observer",
        },
        operation="command",
        capability_id=(
            "city.command-boundary.local"
        ),
        reason="Need human review.",
        requested_at=(
            "2026-10-03T20:35:00+02:00"
        ),
    )


def test_approve_is_recorded_but_grants_nothing():
    review = record_human_review(
        permit(),
        reviewer_id="michal",
        decision="approve",
        reviewed_at=(
            "2026-10-03T20:36:00+02:00"
        ),
        note="Approved as human review record.",
    )

    assert review["protocol"] == (
        REVIEW_PROTOCOL
    )
    assert review["effect"] == (
        "recorded-only"
    )
    assert review["review"][
        "decision"
    ] == "approve"
    assert review["grantsPermission"] is False
    assert review["changesPolicy"] is False
    assert review["executesAction"] is False


@pytest.mark.parametrize(
    "decision",
    [
        "approve",
        "deny",
        "needs-info",
    ],
)
def test_supported_decisions_are_records_only(
    decision,
):
    review = record_human_review(
        permit(),
        reviewer_id="michal",
        decision=decision,
        reviewed_at=(
            "2026-10-03T20:36:00+02:00"
        ),
    )

    assert review["review"][
        "decision"
    ] == decision
    assert review["effect"] == (
        "recorded-only"
    )
    assert review["grantsPermission"] is False


def test_current_gatehouse_decision_is_preserved():
    review = record_human_review(
        permit(),
        reviewer_id="michal",
        decision="approve",
        reviewed_at=(
            "2026-10-03T20:36:00+02:00"
        ),
    )

    assert review["permit"][
        "currentPolicy"
    ] == {
        "decision": "deny",
        "reason": (
            "operation-denied-by-policy"
        ),
    }


def test_route_is_preserved():
    review = record_human_review(
        permit(),
        reviewer_id="michal",
        decision="approve",
        reviewed_at=(
            "2026-10-03T20:36:00+02:00"
        ),
    )

    assert review["permit"]["route"][
        "locationId"
    ] == "dispatch-office"


def test_non_pending_permit_is_rejected():
    value = permit()
    value["status"] = "reviewed"

    with pytest.raises(
        CityReviewError,
        match="pending human review",
    ):
        record_human_review(
            value,
            reviewer_id="michal",
            decision="approve",
            reviewed_at=(
                "2026-10-03T20:36:00+02:00"
            ),
        )


def test_permission_granting_permit_is_rejected():
    value = permit()
    value["grantsPermission"] = True

    with pytest.raises(
        CityReviewError,
        match="must not grant permission",
    ):
        record_human_review(
            value,
            reviewer_id="michal",
            decision="approve",
            reviewed_at=(
                "2026-10-03T20:36:00+02:00"
            ),
        )


def test_invalid_decision_is_rejected():
    with pytest.raises(
        CityReviewError,
        match="decision is invalid",
    ):
        record_human_review(
            permit(),
            reviewer_id="michal",
            decision="execute-now",
            reviewed_at=(
                "2026-10-03T20:36:00+02:00"
            ),
        )


def test_reviewer_id_is_validated():
    with pytest.raises(
        CityReviewError,
        match="reviewerId is invalid",
    ):
        record_human_review(
            permit(),
            reviewer_id="bad reviewer",
            decision="deny",
            reviewed_at=(
                "2026-10-03T20:36:00+02:00"
            ),
        )


def test_review_time_requires_timezone():
    with pytest.raises(
        CityReviewError,
        match="include timezone",
    ):
        record_human_review(
            permit(),
            reviewer_id="michal",
            decision="deny",
            reviewed_at=(
                "2026-10-03T20:36:00"
            ),
        )


def test_note_limit_is_enforced():
    with pytest.raises(
        CityReviewError,
        match="size limit",
    ):
        record_human_review(
            permit(),
            reviewer_id="michal",
            decision="deny",
            reviewed_at=(
                "2026-10-03T20:36:00+02:00"
            ),
            note="x" * 2049,
        )


def test_input_permit_is_not_mutated():
    original = permit()
    snapshot = copy.deepcopy(original)

    record_human_review(
        original,
        reviewer_id="michal",
        decision="approve",
        reviewed_at=(
            "2026-10-03T20:36:00+02:00"
        ),
    )

    assert original == snapshot


def test_contract_is_record_only():
    contract = load_contract()

    assert contract["authority"] == (
        "record-only"
    )
    assert contract["reviewEffect"] == (
        "recorded-only"
    )
    assert contract["exposure"] == {
        "execution": "not-exposed",
        "mutation": "not-allowed",
        "network": "not-exposed",
        "permissionGrant": "not-allowed",
        "policyChange": "not-allowed",
    }


def test_direct_cli_records_without_granting():
    result = subprocess.run(
        [
            sys.executable,
            str(
                ROOT
                / "tools"
                / "city"
                / "review_board.py"
            ),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout
    assert (
        "Bondik City Review Board OK: "
        "approve / recorded-only / "
        "permission=false / "
        "bondik-city-human-review/1"
        in result.stdout
    )
