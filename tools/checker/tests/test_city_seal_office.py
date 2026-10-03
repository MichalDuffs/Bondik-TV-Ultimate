import copy
import subprocess
import sys
from pathlib import Path

import pytest

from tools.city.audit_office import (
    build_audit_entry,
)
from tools.city.permit_office import (
    prepare_permit_request,
)
from tools.city.review_board import (
    record_human_review,
)
from tools.city.seal_office import (
    CERTIFICATE_PROTOCOL,
    CitySealError,
    issue_inactive_certificate,
    load_contract,
)


ROOT = Path(__file__).resolve().parents[3]


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
            "2026-10-03T21:00:00+02:00"
        ),
    )


def audit(
    *,
    decision="approve",
):
    p = permit()
    r = record_human_review(
        p,
        reviewer_id="michal",
        decision=decision,
        reviewed_at=(
            "2026-10-03T21:01:00+02:00"
        ),
        note="Review complete.",
    )
    return build_audit_entry(
        p,
        r,
    )


def test_approved_audit_issues_inactive_certificate():
    certificate = (
        issue_inactive_certificate(
            audit()
        )
    )

    assert certificate[
        "protocol"
    ] == CERTIFICATE_PROTOCOL
    assert certificate[
        "state"
    ] == "issued-inactive"
    assert certificate[
        "authority"
    ] == "certificate-only"


def test_certificate_grants_no_runtime_authority():
    certificate = (
        issue_inactive_certificate(
            audit()
        )
    )

    assert certificate[
        "runtimeAuthority"
    ] is False
    assert certificate[
        "grantsPermission"
    ] is False
    assert certificate[
        "activatesPolicy"
    ] is False
    assert certificate[
        "executesAction"
    ] is False


def test_certificate_scope_is_exact():
    certificate = (
        issue_inactive_certificate(
            audit()
        )
    )

    assert certificate[
        "subject"
    ] == {
        "id": "demo-agent",
        "role": "observer",
    }
    assert certificate[
        "scope"
    ] == {
        "operation": "command",
        "capabilityId": (
            "city.command-boundary.local"
        ),
    }


def test_certificate_preserves_review_identity():
    certificate = (
        issue_inactive_certificate(
            audit()
        )
    )

    assert certificate[
        "review"
    ]["reviewerId"] == "michal"
    assert certificate[
        "review"
    ]["decision"] == "approve"


def test_certificate_links_to_audit_evidence():
    source = audit()
    certificate = (
        issue_inactive_certificate(
            source
        )
    )

    assert certificate[
        "evidence"
    ]["auditEntryId"] == (
        source["entryId"]
    )
    assert certificate[
        "evidence"
    ][
        "auditEntryDigest"
    ].startswith("sha256:")
    assert certificate[
        "evidence"
    ]["permitDigest"] == (
        source["permitDigest"]
    )
    assert certificate[
        "evidence"
    ]["reviewDigest"] == (
        source["reviewDigest"]
    )


def test_certificate_id_is_deterministic():
    source = audit()

    first = (
        issue_inactive_certificate(
            source
        )
    )
    second = (
        issue_inactive_certificate(
            source
        )
    )

    assert first[
        "certificateId"
    ] == second[
        "certificateId"
    ]


@pytest.mark.parametrize(
    "decision",
    [
        "deny",
        "needs-info",
    ],
)
def test_non_approved_review_cannot_be_sealed(
    decision,
):
    with pytest.raises(
        CitySealError,
        match="not approvable",
    ):
        issue_inactive_certificate(
            audit(
                decision=decision
            )
        )


def test_tampered_permit_review_link_is_rejected():
    source = audit()
    broken = copy.deepcopy(source)
    broken["review"]["permit"][
        "route"
    ]["locationId"] = "wrong-place"

    with pytest.raises(
        CitySealError,
        match="linkage invalid",
    ):
        issue_inactive_certificate(
            broken
        )


def test_permission_granting_audit_is_rejected():
    source = audit()
    source["grantsPermission"] = True

    with pytest.raises(
        CitySealError,
        match="must not grant permission",
    ):
        issue_inactive_certificate(
            source
        )


def test_policy_changing_audit_is_rejected():
    source = audit()
    source["changesPolicy"] = True

    with pytest.raises(
        CitySealError,
        match="must not change policy",
    ):
        issue_inactive_certificate(
            source
        )


def test_executing_audit_is_rejected():
    source = audit()
    source["executesAction"] = True

    with pytest.raises(
        CitySealError,
        match="must not execute action",
    ):
        issue_inactive_certificate(
            source
        )


def test_input_audit_is_not_mutated():
    source = audit()
    snapshot = copy.deepcopy(source)

    issue_inactive_certificate(
        source
    )

    assert source == snapshot


def test_contract_is_inactive_and_non_granting():
    contract = load_contract()

    assert contract[
        "authority"
    ] == "certificate-only"
    assert contract[
        "certificateState"
    ] == "issued-inactive"
    assert contract[
        "exposure"
    ] == {
        "execution": "not-exposed",
        "mutation": "not-allowed",
        "network": "not-exposed",
        "permissionGrant": "not-allowed",
        "policyActivation": "not-allowed",
    }


def test_direct_cli_issues_inactive_certificate():
    result = subprocess.run(
        [
            sys.executable,
            str(
                ROOT
                / "tools"
                / "city"
                / "seal_office.py"
            ),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout
    assert (
        "Bondik City Seal Office OK: "
        "issued-inactive / "
        "permission=false / "
        "bondik-city-approval-certificate/1"
        in result.stdout
    )
