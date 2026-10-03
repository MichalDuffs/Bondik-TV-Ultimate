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
    prepare_command_lease,
)
from tools.city.dispatch_packet import (
    PACKET_PROTOCOL,
    CityDispatchPacketError,
    load_contract,
    prepare_dispatch_packet,
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
from tools.city.service_directory import (
    build_directory,
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
            "2026-10-03T22:10:00+02:00"
        ),
    )
    review = record_human_review(
        permit,
        reviewer_id="michal",
        decision="approve",
        reviewed_at=(
            "2026-10-03T22:11:00+02:00"
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
            "2026-10-03T22:12:00+02:00"
        ),
        reason="Prepare activation.",
    )
    confirmation = confirm_activation_intent(
        intent,
        confirmer_id="michal",
        confirmed_at=(
            "2026-10-03T22:13:00+02:00"
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

    dispatcher = LocalCommandDispatcher()
    dispatcher.register(
        command_type="city.status.read",
        building_id="control-tower",
        capability_id=(
            "city.control-tower.status-board"
        ),
        handler=lambda _arguments: {
            "status": "available",
        },
    )

    lease = prepare_command_lease(
        grant,
        admission,
        dispatcher=dispatcher,
        command_type="city.status.read",
        target_building_id="control-tower",
        target_capability_id=(
            "city.control-tower.status-board"
        ),
        arguments={
            "format": "summary",
        },
    )

    return grant, admission, lease


def packet(
    grant=None,
    admission=None,
    lease=None,
    **kwargs,
):
    default_grant, default_admission, default_lease = (
        sources()
    )
    return prepare_dispatch_packet(
        grant if grant is not None else default_grant,
        admission if admission is not None else default_admission,
        lease if lease is not None else default_lease,
        prepared_at=kwargs.pop(
            "prepared_at",
            "2026-10-03T22:14:00+02:00",
        ),
        **kwargs,
    )


def _digest(value):
    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
    )


def test_packet_is_ready_not_dispatched():
    value = packet()

    assert value["protocol"] == (
        PACKET_PROTOCOL
    )
    assert value["state"] == (
        "ready-not-dispatched"
    )
    assert value["dispatchesCommand"] is False
    assert value["executesAction"] is False


def test_packet_does_not_consume_or_connect():
    value = packet()

    assert value["grantConsumed"] is False
    assert value["consumerConnected"] is False
    assert value["grantsPermission"] is False
    assert value["runtimeAuthority"] is False


def test_packet_preserves_exact_command():
    value = packet()

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


def test_packet_preserves_human_confirmed_provenance():
    value = packet()

    assert value["requester"]["kind"] == (
        "human-confirmed-runtime-grant"
    )
    assert value["requester"][
        "confirmerId"
    ] == "michal"
    assert value["requester"][
        "subject"
    ] == {
        "id": "demo-agent",
        "role": "observer",
    }


def test_packet_binds_full_source_digests():
    grant, admission, lease = sources()
    value = packet(
        grant,
        admission,
        lease,
    )

    assert value["evidence"][
        "grantDigest"
    ] == _digest(grant)
    assert value["evidence"][
        "admissionDigest"
    ] == _digest(admission)
    assert value["evidence"][
        "leaseDigest"
    ] == _digest(lease)


def test_packet_id_is_deterministic():
    grant, admission, lease = sources()

    first = packet(
        grant,
        admission,
        lease,
    )
    second = packet(
        grant,
        admission,
        lease,
    )

    assert first["packetId"] == (
        second["packetId"]
    )


def test_tampered_admission_grant_digest_is_rejected():
    grant, admission, lease = sources()
    admission["evidence"]["grantDigest"] = (
        "sha256:" + "0" * 64
    )

    with pytest.raises(
        CityDispatchPacketError,
        match="admission grant digest mismatch",
    ):
        packet(
            grant,
            admission,
            lease,
        )


def test_tampered_lease_grant_digest_is_rejected():
    grant, admission, lease = sources()
    lease["source"]["grantDigest"] = (
        "sha256:" + "0" * 64
    )

    with pytest.raises(
        CityDispatchPacketError,
        match="lease grant digest mismatch",
    ):
        packet(
            grant,
            admission,
            lease,
        )


def test_tampered_lease_admission_digest_is_rejected():
    grant, admission, lease = sources()
    lease["source"][
        "admissionDigest"
    ] = "sha256:" + "0" * 64

    with pytest.raises(
        CityDispatchPacketError,
        match="lease admission digest mismatch",
    ):
        packet(
            grant,
            admission,
            lease,
        )


def test_tampered_arguments_digest_is_rejected():
    grant, admission, lease = sources()
    lease["command"][
        "argumentsDigest"
    ] = "sha256:" + "0" * 64

    with pytest.raises(
        CityDispatchPacketError,
        match="arguments digest mismatch",
    ):
        packet(
            grant,
            admission,
            lease,
        )


def test_consumed_grant_is_rejected():
    grant, admission, lease = sources()
    grant["consumed"] = True
    admission["evidence"][
        "grantDigest"
    ] = _digest(grant)
    lease["source"][
        "grantDigest"
    ] = _digest(grant)

    with pytest.raises(
        CityDispatchPacketError,
        match="must be unconsumed",
    ):
        packet(
            grant,
            admission,
            lease,
        )


def test_connected_admission_is_rejected():
    grant, admission, lease = sources()
    admission["consumerConnected"] = True

    with pytest.raises(
        CityDispatchPacketError,
        match="admission unsafe field",
    ):
        packet(
            grant,
            admission,
            lease,
        )


def test_dispatching_lease_is_rejected():
    grant, admission, lease = sources()
    lease["dispatchesCommand"] = True

    with pytest.raises(
        CityDispatchPacketError,
        match="lease unsafe field",
    ):
        packet(
            grant,
            admission,
            lease,
        )


def test_non_read_only_lease_is_rejected():
    grant, admission, lease = sources()
    lease["command"][
        "registrationMutation"
    ] = "write"

    with pytest.raises(
        CityDispatchPacketError,
        match="must be read-only",
    ):
        packet(
            grant,
            admission,
            lease,
        )


def test_subject_mismatch_is_rejected():
    grant, admission, lease = sources()
    lease["subject"]["id"] = "other"

    with pytest.raises(
        CityDispatchPacketError,
        match="lease subject mismatch",
    ):
        packet(
            grant,
            admission,
            lease,
        )


def test_current_directory_target_drift_fails_closed():
    grant, admission, lease = sources()
    directory = build_directory()

    for location in directory["locations"]:
        location["capabilities"] = [
            item
            for item in location["capabilities"]
            if item["id"]
            != "city.control-tower.status-board"
        ]

    with pytest.raises(
        CityDispatchPacketError,
        match="resolve exactly once",
    ):
        packet(
            grant,
            admission,
            lease,
            directory=directory,
        )


def test_tampered_admission_id_is_rejected():
    grant, admission, lease = sources()
    admission["admissionId"] = "admit-tampered"

    with pytest.raises(
        CityDispatchPacketError,
        match="admissionId integrity mismatch",
    ):
        packet(
            grant,
            admission,
            lease,
        )


def test_tampered_lease_id_is_rejected():
    grant, admission, lease = sources()
    lease["leaseId"] = "lease-tampered"

    with pytest.raises(
        CityDispatchPacketError,
        match="leaseId integrity mismatch",
    ):
        packet(
            grant,
            admission,
            lease,
        )


def test_prepared_time_requires_timezone():
    with pytest.raises(
        CityDispatchPacketError,
        match="include timezone",
    ):
        packet(
            prepared_at=(
                "2026-10-03T22:14:00"
            )
        )


def test_inputs_are_not_mutated():
    grant, admission, lease = sources()
    g_snapshot = copy.deepcopy(grant)
    a_snapshot = copy.deepcopy(
        admission
    )
    l_snapshot = copy.deepcopy(lease)

    packet(
        grant,
        admission,
        lease,
    )

    assert grant == g_snapshot
    assert admission == a_snapshot
    assert lease == l_snapshot


def test_contract_is_dispatch_preparation_only():
    contract = load_contract()

    assert contract["authority"] == (
        "dispatch-preparation-only"
    )
    assert contract["packetState"] == (
        "ready-not-dispatched"
    )
    assert contract["exposure"] == {
        "execution": "not-exposed",
        "mutation": "not-allowed",
        "network": "not-exposed",
        "permissionGrant": "not-allowed",
        "grantConsumption": "not-allowed",
    }


def test_direct_cli_prepares_packet_without_dispatch():
    result = subprocess.run(
        [
            sys.executable,
            str(
                ROOT
                / "tools"
                / "city"
                / "dispatch_packet.py"
            ),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout
    assert (
        "Bondik City Switchboard OK: "
        "ready-not-dispatched / "
        "command=city.status.read / "
        "consumed=false / dispatched=false / "
        "bondik-city-authorized-command-packet/1"
        in result.stdout
    )
