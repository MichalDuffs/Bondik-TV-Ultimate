import copy
import subprocess
import sys
from pathlib import Path

import pytest

from tools.city.activation_confirmation import (
    confirm_activation_intent,
)
from tools.city.audit_office import (
    build_audit_entry,
)
from tools.city.ignition_office import (
    prepare_activation_intent,
)
from tools.city.key_vault import (
    build_registry_entry,
)
from tools.city.permit_office import (
    prepare_permit_request,
)
from tools.city.review_board import (
    record_human_review,
)
from tools.city.runtime_grant import (
    GRANT_PROTOCOL,
    CityRuntimeGrantError,
    issue_runtime_grant,
    load_contract,
)
from tools.city.seal_office import (
    issue_inactive_certificate,
)


ROOT = Path(__file__).resolve().parents[3]


def sources():
    permit = prepare_permit_request(
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
            "2026-10-03T21:40:00+02:00"
        ),
    )
    review = record_human_review(
        permit,
        reviewer_id="michal",
        decision="approve",
        reviewed_at=(
            "2026-10-03T21:41:00+02:00"
        ),
        note="Approved.",
    )
    certificate = issue_inactive_certificate(
        build_audit_entry(
            permit,
            review,
        )
    )
    vault_entry = build_registry_entry(
        certificate
    )
    intent = prepare_activation_intent(
        vault_entry,
        actor_id="michal",
        prepared_at=(
            "2026-10-03T21:42:00+02:00"
        ),
        reason="Prepare activation.",
    )
    confirmation = confirm_activation_intent(
        intent,
        confirmer_id="michal",
        confirmed_at=(
            "2026-10-03T21:43:00+02:00"
        ),
        confirm_intent_id=intent["intentId"],
        reason="Confirm intent.",
    )
    return intent, confirmation


def test_grant_is_issued_unconsumed():
    intent, confirmation = sources()
    grant = issue_runtime_grant(
        intent,
        confirmation,
    )

    assert grant["protocol"] == (
        GRANT_PROTOCOL
    )
    assert grant["state"] == (
        "issued-unconsumed"
    )
    assert grant["consumed"] is False


def test_grant_carries_runtime_permission_but_does_not_execute():
    intent, confirmation = sources()
    grant = issue_runtime_grant(
        intent,
        confirmation,
    )

    assert grant["grantsPermission"] is True
    assert grant["runtimeAuthority"] is True
    assert grant["executesAction"] is False
    assert grant["activatesPolicy"] is False
    assert grant["mutatesPolicy"] is False
    assert grant["consumerConnected"] is False


def test_grant_scope_is_exact():
    intent, confirmation = sources()
    grant = issue_runtime_grant(
        intent,
        confirmation,
    )

    assert grant["subject"] == {
        "id": "demo-agent",
        "role": "observer",
    }
    assert grant["scope"] == {
        "operation": "command",
        "capabilityId": (
            "city.command-boundary.local"
        ),
    }


def test_grant_is_human_confirmed():
    intent, confirmation = sources()
    grant = issue_runtime_grant(
        intent,
        confirmation,
    )

    assert grant[
        "humanAuthorization"
    ] == {
        "confirmerId": "michal",
        "confirmationId": (
            confirmation["confirmationId"]
        ),
    }


def test_confirmation_digest_is_bound():
    intent, confirmation = sources()
    grant = issue_runtime_grant(
        intent,
        confirmation,
    )

    assert grant["evidence"][
        "intentId"
    ] == intent["intentId"]
    assert grant["evidence"][
        "intentDigest"
    ].startswith("sha256:")
    assert grant["evidence"][
        "confirmationDigest"
    ].startswith("sha256:")


def test_grant_id_is_deterministic():
    intent, confirmation = sources()

    first = issue_runtime_grant(
        intent,
        confirmation,
    )
    second = issue_runtime_grant(
        intent,
        confirmation,
    )

    assert first["grantId"] == (
        second["grantId"]
    )


def test_confirmation_for_other_intent_is_rejected():
    intent, confirmation = sources()
    broken = copy.deepcopy(confirmation)
    broken["evidence"]["intentId"] = (
        "intent-other"
    )

    with pytest.raises(
        CityRuntimeGrantError,
        match="intentId mismatch",
    ):
        issue_runtime_grant(
            intent,
            broken,
        )


def test_tampered_confirmation_digest_is_rejected():
    intent, confirmation = sources()
    broken = copy.deepcopy(confirmation)
    broken["evidence"]["intentDigest"] = (
        "sha256:" + "0" * 64
    )

    with pytest.raises(
        CityRuntimeGrantError,
        match="intent digest mismatch",
    ):
        issue_runtime_grant(
            intent,
            broken,
        )


def test_scope_mismatch_is_rejected():
    intent, confirmation = sources()
    broken = copy.deepcopy(confirmation)
    broken["scope"]["capabilityId"] = (
        "city.other"
    )

    with pytest.raises(
        CityRuntimeGrantError,
        match="scope mismatch",
    ):
        issue_runtime_grant(
            intent,
            broken,
        )


@pytest.mark.parametrize(
    "source_name,field",
    [
        ("intent", "runtimeAuthority"),
        ("intent", "grantsPermission"),
        ("intent", "activatesPolicy"),
        ("intent", "executesAction"),
        ("confirmation", "runtimeAuthority"),
        ("confirmation", "grantsPermission"),
        ("confirmation", "activatesPolicy"),
        ("confirmation", "executesAction"),
    ],
)
def test_unsafe_sources_are_rejected(
    source_name,
    field,
):
    intent, confirmation = sources()
    source = (
        intent
        if source_name == "intent"
        else confirmation
    )
    source[field] = True

    with pytest.raises(
        CityRuntimeGrantError,
        match="unsafe field",
    ):
        issue_runtime_grant(
            intent,
            confirmation,
        )


def test_inputs_are_not_mutated():
    intent, confirmation = sources()
    i_snapshot = copy.deepcopy(intent)
    c_snapshot = copy.deepcopy(
        confirmation
    )

    issue_runtime_grant(
        intent,
        confirmation,
    )

    assert intent == i_snapshot
    assert confirmation == c_snapshot


def test_contract_requires_single_use_local_unconnected():
    contract = load_contract()

    assert contract["authority"] == (
        "grant-issuer"
    )
    assert contract["grantState"] == (
        "issued-unconsumed"
    )
    assert contract["constraints"] == {
        "singleUse": True,
        "localOnly": True,
        "consumerConnected": False,
    }


def test_direct_cli_issues_unconsumed_grant():
    result = subprocess.run(
        [
            sys.executable,
            str(
                ROOT
                / "tools"
                / "city"
                / "runtime_grant.py"
            ),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout
    assert (
        "Bondik City Grant Office OK: "
        "issued-unconsumed / "
        "permission=true / consumed=false / "
        "bondik-city-runtime-grant-token/1"
        in result.stdout
    )
