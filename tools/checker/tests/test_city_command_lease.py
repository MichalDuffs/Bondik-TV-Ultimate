import copy
import hashlib
import json
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
from tools.city.command_boundary import (
    LocalCommandDispatcher,
)
from tools.city.command_lease import (
    LEASE_PROTOCOL,
    CityCommandLeaseError,
    load_contract,
    prepare_command_lease,
)
from tools.city.grant_admission import (
    admit_runtime_grant,
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
    issue_runtime_grant,
)
from tools.city.seal_office import (
    issue_inactive_certificate,
)


ROOT = Path(__file__).resolve().parents[3]


def grant_and_admission():
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
            "2026-10-03T22:00:00+02:00"
        ),
    )
    review = record_human_review(
        permit,
        reviewer_id="michal",
        decision="approve",
        reviewed_at=(
            "2026-10-03T22:01:00+02:00"
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
            "2026-10-03T22:02:00+02:00"
        ),
        reason="Prepare activation.",
    )
    confirmation = confirm_activation_intent(
        intent,
        confirmer_id="michal",
        confirmed_at=(
            "2026-10-03T22:03:00+02:00"
        ),
        confirm_intent_id=intent["intentId"],
        reason="Confirm intent.",
    )
    grant = issue_runtime_grant(
        intent,
        confirmation,
    )
    admission = admit_runtime_grant(
        grant,
        consumer_id="dispatch-office",
    )
    return grant, admission


def dispatcher():
    value = LocalCommandDispatcher()
    value.register(
        command_type="city.status.read",
        building_id="control-tower",
        capability_id=(
            "city.control-tower.status-board"
        ),
        handler=lambda _arguments: {
            "status": "available",
        },
    )
    return value


def lease(**overrides):
    grant, admission = grant_and_admission()
    kwargs = {
        "grant": grant,
        "admission": admission,
        "dispatcher": dispatcher(),
        "command_type": "city.status.read",
        "target_building_id": "control-tower",
        "target_capability_id": (
            "city.control-tower.status-board"
        ),
        "arguments": {
            "format": "summary",
        },
    }
    kwargs.update(overrides)
    return prepare_command_lease(
        **kwargs
    )


def test_lease_is_prepared_and_unconsumed():
    value = lease()

    assert value["protocol"] == (
        LEASE_PROTOCOL
    )
    assert value["state"] == (
        "prepared-unconsumed"
    )
    assert value["grantConsumed"] is False


def test_lease_does_not_dispatch_or_execute():
    value = lease()

    assert value["dispatchesCommand"] is False
    assert value["executesAction"] is False
    assert value["consumerConnected"] is False


def test_lease_narrows_without_granting_again():
    value = lease()

    assert value[
        "sourceGrantPermission"
    ] is True
    assert value[
        "sourceGrantRuntimeAuthority"
    ] is True
    assert value["grantsPermission"] is False
    assert value["runtimeAuthority"] is False


def test_exact_command_scope_is_preserved():
    value = lease()

    assert value["command"][
        "commandType"
    ] == "city.status.read"
    assert value["command"]["target"] == {
        "buildingId": "control-tower",
        "capabilityId": (
            "city.control-tower.status-board"
        ),
    }
    assert value["command"][
        "arguments"
    ] == {
        "format": "summary",
    }


def test_arguments_digest_is_bound():
    value = lease()

    assert value["command"][
        "argumentsDigest"
    ].startswith("sha256:")
    assert value["source"][
        "grantDigest"
    ].startswith("sha256:")
    assert value["source"][
        "admissionDigest"
    ].startswith("sha256:")


def test_lease_id_is_deterministic():
    grant, admission = grant_and_admission()
    kwargs = {
        "grant": grant,
        "admission": admission,
        "dispatcher": dispatcher(),
        "command_type": "city.status.read",
        "target_building_id": "control-tower",
        "target_capability_id": (
            "city.control-tower.status-board"
        ),
        "arguments": {},
    }

    first = prepare_command_lease(
        **kwargs
    )
    second = prepare_command_lease(
        **kwargs
    )

    assert first["leaseId"] == (
        second["leaseId"]
    )


def test_unregistered_command_is_rejected():
    with pytest.raises(
        CityCommandLeaseError,
        match="not registered",
    ):
        lease(
            command_type="city.other.read"
        )


def test_registration_target_mismatch_is_rejected():
    with pytest.raises(
        CityCommandLeaseError,
        match="target does not match registration",
    ):
        lease(
            target_building_id="github-service"
        )


def test_inactive_or_unknown_target_fails_closed():
    grant, admission = grant_and_admission()
    value = LocalCommandDispatcher()
    value.register(
        command_type="city.missing.read",
        building_id="control-tower",
        capability_id="city.missing",
        handler=lambda _arguments: {},
    )

    with pytest.raises(
        CityCommandLeaseError,
        match="resolve exactly once",
    ):
        prepare_command_lease(
            grant,
            admission,
            dispatcher=value,
            command_type="city.missing.read",
            target_building_id="control-tower",
            target_capability_id="city.missing",
            arguments={},
        )


def test_tampered_admission_grant_digest_is_rejected():
    grant, admission = grant_and_admission()
    broken = copy.deepcopy(admission)
    broken["evidence"]["grantDigest"] = (
        "sha256:" + "0" * 64
    )

    with pytest.raises(
        CityCommandLeaseError,
        match="grant digest mismatch",
    ):
        prepare_command_lease(
            grant,
            broken,
            dispatcher=dispatcher(),
            command_type="city.status.read",
            target_building_id="control-tower",
            target_capability_id=(
                "city.control-tower.status-board"
            ),
            arguments={},
        )


def test_consumed_grant_is_rejected():
    grant, admission = grant_and_admission()
    grant["consumed"] = True

    with pytest.raises(
        CityCommandLeaseError,
        match="must be unconsumed",
    ):
        prepare_command_lease(
            grant,
            admission,
            dispatcher=dispatcher(),
            command_type="city.status.read",
            target_building_id="control-tower",
            target_capability_id=(
                "city.control-tower.status-board"
            ),
            arguments={},
        )


def test_connected_consumer_is_rejected():
    grant, admission = grant_and_admission()
    admission["consumerConnected"] = True

    with pytest.raises(
        CityCommandLeaseError,
        match="remain disconnected",
    ):
        prepare_command_lease(
            grant,
            admission,
            dispatcher=dispatcher(),
            command_type="city.status.read",
            target_building_id="control-tower",
            target_capability_id=(
                "city.control-tower.status-board"
            ),
            arguments={},
        )


def test_grant_scope_must_be_command_boundary():
    grant, admission = grant_and_admission()
    grant["scope"]["capabilityId"] = (
        "city.other"
    )
    admission["evidence"]["grantDigest"] = (
        "sha256:"
        + hashlib.sha256(
            json.dumps(
                grant,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
    )

    with pytest.raises(
        CityCommandLeaseError,
        match="not scoped to command boundary",
    ):
        prepare_command_lease(
            grant,
            admission,
            dispatcher=dispatcher(),
            command_type="city.status.read",
            target_building_id="control-tower",
            target_capability_id=(
                "city.control-tower.status-board"
            ),
            arguments={},
        )


def test_arguments_must_be_object():
    with pytest.raises(
        CityCommandLeaseError,
        match="arguments must be an object",
    ):
        lease(arguments=[])


def test_input_grant_and_admission_are_not_mutated():
    grant, admission = grant_and_admission()
    grant_snapshot = copy.deepcopy(grant)
    admission_snapshot = copy.deepcopy(
        admission
    )

    prepare_command_lease(
        grant,
        admission,
        dispatcher=dispatcher(),
        command_type="city.status.read",
        target_building_id="control-tower",
        target_capability_id=(
            "city.control-tower.status-board"
        ),
        arguments={},
    )

    assert grant == grant_snapshot
    assert admission == admission_snapshot


def test_contract_is_scope_narrowing_only():
    contract = load_contract()

    assert contract["authority"] == (
        "scope-narrowing-only"
    )
    assert contract["leaseState"] == (
        "prepared-unconsumed"
    )
    assert contract["constraints"] == {
        "readOnly": True,
        "singleUse": True,
        "localOnly": True,
        "consumerConnected": False,
    }


def test_direct_cli_prepares_non_dispatching_lease():
    result = subprocess.run(
        [
            sys.executable,
            str(
                ROOT
                / "tools"
                / "city"
                / "command_lease.py"
            ),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout
    assert (
        "Bondik City Relay Office OK: "
        "prepared-unconsumed / "
        "command=city.status.read / "
        "consumed=false / dispatched=false / "
        "bondik-city-command-lease-token/1"
        in result.stdout
    )
