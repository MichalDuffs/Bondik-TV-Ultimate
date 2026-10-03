import copy
import subprocess
import sys
from pathlib import Path

import pytest

from tools.city.audit_office import (
    build_audit_entry,
)
from tools.city.ignition_office import (
    INTENT_PROTOCOL,
    CityIgnitionError,
    load_contract,
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


def vault_entry():
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
            "2026-10-03T21:20:00+02:00"
        ),
    )
    review = record_human_review(
        permit,
        reviewer_id="michal",
        decision="approve",
        reviewed_at=(
            "2026-10-03T21:21:00+02:00"
        ),
        note="Review complete.",
    )
    certificate = issue_inactive_certificate(
        build_audit_entry(
            permit,
            review,
        )
    )
    return build_registry_entry(
        certificate
    )


def intent(**overrides):
    kwargs = {
        "actor_id": "michal",
        "prepared_at": (
            "2026-10-03T21:22:00+02:00"
        ),
        "reason": (
            "Prepare for later explicit "
            "human activation."
        ),
    }
    kwargs.update(overrides)
    return prepare_activation_intent(
        vault_entry(),
        **kwargs,
    )


def test_intent_is_prepared_but_not_active():
    value = intent()

    assert value["protocol"] == (
        INTENT_PROTOCOL
    )
    assert value["state"] == (
        "prepared-not-active"
    )
    assert value["authority"] == (
        "intent-only"
    )


def test_intent_grants_no_runtime_authority():
    value = intent()

    assert value[
        "runtimeAuthority"
    ] is False
    assert value[
        "grantsPermission"
    ] is False
    assert value[
        "activatesPolicy"
    ] is False
    assert value[
        "executesAction"
    ] is False


def test_intent_preserves_exact_scope():
    value = intent()

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


def test_intent_requires_human_actor():
    value = intent()

    assert value["actor"] == {
        "kind": "human",
        "id": "michal",
    }


def test_intent_links_vault_and_certificate_evidence():
    source = vault_entry()
    value = prepare_activation_intent(
        source,
        actor_id="michal",
        prepared_at=(
            "2026-10-03T21:22:00+02:00"
        ),
        reason="Prepare.",
    )

    assert value["evidence"][
        "vaultEntryDigest"
    ].startswith("sha256:")
    assert value["evidence"][
        "certificateId"
    ] == source["certificateId"]
    assert value["evidence"][
        "certificateDigest"
    ] == source["certificateDigest"]


def test_intent_id_is_deterministic():
    source = vault_entry()
    kwargs = {
        "actor_id": "michal",
        "prepared_at": (
            "2026-10-03T21:22:00+02:00"
        ),
        "reason": "Prepare.",
    }

    first = prepare_activation_intent(
        source,
        **kwargs,
    )
    second = prepare_activation_intent(
        source,
        **kwargs,
    )

    assert first["intentId"] == (
        second["intentId"]
    )


def test_tampered_certificate_digest_is_rejected():
    source = vault_entry()
    source["certificateDigest"] = (
        "sha256:" + "0" * 64
    )

    with pytest.raises(
        CityIgnitionError,
        match="digest mismatch",
    ):
        prepare_activation_intent(
            source,
            actor_id="michal",
            prepared_at=(
                "2026-10-03T21:22:00+02:00"
            ),
            reason="Prepare.",
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
def test_unsafe_vault_entry_is_rejected(
    field,
):
    source = vault_entry()
    source[field] = True

    with pytest.raises(
        CityIgnitionError,
        match="unsafe field",
    ):
        prepare_activation_intent(
            source,
            actor_id="michal",
            prepared_at=(
                "2026-10-03T21:22:00+02:00"
            ),
            reason="Prepare.",
        )


def test_actor_id_is_validated():
    with pytest.raises(
        CityIgnitionError,
        match="actorId is invalid",
    ):
        intent(
            actor_id="bad actor"
        )


def test_prepared_time_requires_timezone():
    with pytest.raises(
        CityIgnitionError,
        match="include timezone",
    ):
        intent(
            prepared_at=(
                "2026-10-03T21:22:00"
            )
        )


def test_reason_is_required():
    with pytest.raises(
        CityIgnitionError,
        match="non-empty string",
    ):
        intent(reason=" ")


def test_input_vault_entry_is_not_mutated():
    source = vault_entry()
    snapshot = copy.deepcopy(source)

    prepare_activation_intent(
        source,
        actor_id="michal",
        prepared_at=(
            "2026-10-03T21:22:00+02:00"
        ),
        reason="Prepare.",
    )

    assert source == snapshot


def test_contract_is_intent_only():
    contract = load_contract()

    assert contract[
        "authority"
    ] == "intent-only"
    assert contract[
        "intentState"
    ] == "prepared-not-active"
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


def test_direct_cli_prepares_non_active_intent():
    result = subprocess.run(
        [
            sys.executable,
            str(
                ROOT
                / "tools"
                / "city"
                / "ignition_office.py"
            ),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout
    assert (
        "Bondik City Ignition Office OK: "
        "prepared-not-active / "
        "permission=false / "
        "bondik-city-activation-intent/1"
        in result.stdout
    )
