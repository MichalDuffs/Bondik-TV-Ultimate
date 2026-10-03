import copy
import subprocess
import sys
from pathlib import Path

import pytest

from tools.city.activation_confirmation import (
    CONFIRMATION_PROTOCOL,
    CityActivationConfirmationError,
    confirm_activation_intent,
    load_contract,
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
from tools.city.seal_office import (
    issue_inactive_certificate,
)


ROOT = Path(__file__).resolve().parents[3]


def source_intent():
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
            "2026-10-03T21:30:00+02:00"
        ),
    )
    review = record_human_review(
        permit,
        reviewer_id="michal",
        decision="approve",
        reviewed_at=(
            "2026-10-03T21:31:00+02:00"
        ),
        note="Review complete.",
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
    return prepare_activation_intent(
        vault_entry,
        actor_id="michal",
        prepared_at=(
            "2026-10-03T21:32:00+02:00"
        ),
        reason="Prepare exact scope.",
    )


def confirmation(
    source=None,
    **overrides,
):
    source = (
        source
        if source is not None
        else source_intent()
    )
    kwargs = {
        "confirmer_id": "michal",
        "confirmed_at": (
            "2026-10-03T21:33:00+02:00"
        ),
        "confirm_intent_id": (
            source["intentId"]
        ),
        "reason": (
            "Confirm prepared activation intent."
        ),
    }
    kwargs.update(overrides)
    return confirm_activation_intent(
        source,
        **kwargs,
    )


def test_confirmation_is_confirmed_not_active():
    value = confirmation()

    assert value["protocol"] == (
        CONFIRMATION_PROTOCOL
    )
    assert value["state"] == (
        "confirmed-not-active"
    )
    assert value["authority"] == (
        "confirmation-only"
    )


def test_confirmation_grants_no_runtime_authority():
    value = confirmation()

    assert value["runtimeAuthority"] is False
    assert value["grantsPermission"] is False
    assert value["activatesPolicy"] is False
    assert value["executesAction"] is False


def test_exact_intent_id_echo_is_required():
    with pytest.raises(
        CityActivationConfirmationError,
        match="confirmIntentId mismatch",
    ):
        confirmation(
            confirm_intent_id="wrong-intent"
        )


def test_confirmation_preserves_exact_scope():
    value = confirmation()

    assert value["subject"] == {
        "id": "demo-agent",
        "role": "observer",
    }
    assert value["scope"] == {
        "operation": "command",
        "capabilityId": (
            "city.command-boundary.local"
        ),
    }


def test_confirmation_binds_intent_digest():
    source = source_intent()
    value = confirmation(source)

    assert value["evidence"][
        "intentId"
    ] == source["intentId"]
    assert value["evidence"][
        "intentDigest"
    ].startswith("sha256:")
    assert value["evidence"][
        "sourceActor"
    ] == source["actor"]


def test_confirmation_id_is_deterministic():
    source = source_intent()

    first = confirmation(source)
    second = confirmation(source)

    assert first["confirmationId"] == (
        second["confirmationId"]
    )


@pytest.mark.parametrize(
    "field",
    [
        "runtimeAuthority",
        "grantsPermission",
        "activatesPolicy",
        "executesAction",
    ],
)
def test_unsafe_intent_is_rejected(field):
    source = source_intent()
    source[field] = True

    with pytest.raises(
        CityActivationConfirmationError,
        match="unsafe field",
    ):
        confirmation(source)


def test_wrong_intent_state_is_rejected():
    source = source_intent()
    source["state"] = "active"

    with pytest.raises(
        CityActivationConfirmationError,
        match="prepared-not-active",
    ):
        confirmation(source)


def test_confirmer_id_is_validated():
    with pytest.raises(
        CityActivationConfirmationError,
        match="confirmerId is invalid",
    ):
        confirmation(
            confirmer_id="bad confirmer"
        )


def test_confirmation_time_requires_timezone():
    with pytest.raises(
        CityActivationConfirmationError,
        match="include timezone",
    ):
        confirmation(
            confirmed_at=(
                "2026-10-03T21:33:00"
            )
        )


def test_reason_is_required():
    with pytest.raises(
        CityActivationConfirmationError,
        match="non-empty string",
    ):
        confirmation(reason=" ")


def test_input_intent_is_not_mutated():
    source = source_intent()
    snapshot = copy.deepcopy(source)

    confirmation(source)

    assert source == snapshot


def test_contract_is_confirmation_only():
    contract = load_contract()

    assert contract[
        "authority"
    ] == "confirmation-only"
    assert contract[
        "confirmationState"
    ] == "confirmed-not-active"
    assert contract[
        "actorKind"
    ] == "human"
    assert contract["exposure"] == {
        "execution": "not-exposed",
        "mutation": "not-allowed",
        "network": "not-exposed",
        "permissionGrant": "not-allowed",
        "policyActivation": "not-allowed",
    }


def test_direct_cli_records_non_active_confirmation():
    result = subprocess.run(
        [
            sys.executable,
            str(
                ROOT
                / "tools"
                / "city"
                / "activation_confirmation.py"
            ),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout
    assert (
        "Bondik City Key Turn Office OK: "
        "confirmed-not-active / "
        "permission=false / "
        "bondik-city-activation-confirmation/1"
        in result.stdout
    )
