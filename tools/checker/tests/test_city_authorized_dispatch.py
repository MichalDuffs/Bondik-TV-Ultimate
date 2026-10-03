import copy
import subprocess
import sys
from pathlib import Path

import pytest

from tools.city.authorized_dispatch import (
    RECEIPT_PROTOCOL,
    CityAuthorizedDispatchError,
    _build_demo_sources,
    execute_authorized_read_only,
    load_contract,
)
from tools.city.command_boundary import (
    LocalCommandDispatcher,
)
from tools.city.service_directory import (
    build_directory,
)
from tools.city.storage_adapter import (
    MemoryStorageAdapter,
)


ROOT = Path(__file__).resolve().parents[3]


def sources():
    return _build_demo_sources()


def execute(
    grant=None,
    packet=None,
    preflight=None,
    dispatcher=None,
    storage=None,
    **kwargs,
):
    (
        default_grant,
        default_packet,
        default_preflight,
        default_dispatcher,
    ) = sources()

    return execute_authorized_read_only(
        (
            grant
            if grant is not None
            else default_grant
        ),
        (
            packet
            if packet is not None
            else default_packet
        ),
        (
            preflight
            if preflight is not None
            else default_preflight
        ),
        dispatcher=(
            dispatcher
            if dispatcher is not None
            else default_dispatcher
        ),
        storage=(
            storage
            if storage is not None
            else MemoryStorageAdapter()
        ),
        executed_at=kwargs.pop(
            "executed_at",
            "2026-10-03T22:30:00+02:00",
        ),
        **kwargs,
    )


def test_receipt_is_dispatched_and_consumed():
    value = execute()

    assert value["protocol"] == (
        RECEIPT_PROTOCOL
    )
    assert value["state"] == (
        "dispatched-consumed"
    )
    assert value["grantConsumed"] is True
    assert value["dispatchesCommand"] is True
    assert value["executesAction"] is True


def test_dispatch_is_exact_read_only_local():
    value = execute()

    assert value["command"][
        "commandType"
    ] == "city.status.read"
    assert value["command"][
        "targetBuildingId"
    ] == "control-tower"
    assert value["command"][
        "targetCapabilityId"
    ] == "city.control-tower.status-board"
    assert value["command"][
        "mutation"
    ] == "read-only"
    assert value["command"][
        "transport"
    ] == "local-in-process"


def test_dispatch_returns_registered_handler_result():
    value = execute()

    assert value["command"]["result"] == {
        "status": "available",
    }
    assert value["command"][
        "resultDigest"
    ].startswith("sha256:")


def test_dispatch_has_no_network_policy_event_or_handoff():
    value = execute()

    assert value["usesNetwork"] is False
    assert value["mutatesPolicy"] is False
    assert value["publishesEvent"] is False
    assert value["performsHandoff"] is False


def test_source_grant_artifact_is_not_mutated():
    grant, packet, preflight, dispatcher = (
        sources()
    )
    snapshot = copy.deepcopy(grant)

    value = execute_authorized_read_only(
        grant,
        packet,
        preflight,
        dispatcher=dispatcher,
        storage=MemoryStorageAdapter(),
        executed_at=(
            "2026-10-03T22:30:00+02:00"
        ),
    )

    assert grant == snapshot
    assert value["grant"][
        "sourceArtifactConsumed"
    ] is False
    assert value["grant"][
        "consumptionRecorded"
    ] is True


def test_consumption_claim_is_finalized_before_return():
    grant, packet, preflight, dispatcher = (
        sources()
    )
    storage = MemoryStorageAdapter()

    value = execute_authorized_read_only(
        grant,
        packet,
        preflight,
        dispatcher=dispatcher,
        storage=storage,
        executed_at=(
            "2026-10-03T22:30:00+02:00"
        ),
    )
    record = storage.read(
        "city.dispatch.spent",
        grant["grantId"],
    )

    assert record is not None
    assert record["revision"] == 2
    assert record["value"]["state"] == (
        "dispatched-consumed"
    )
    assert value["grant"][
        "consumptionRevision"
    ] == 2


def test_same_grant_cannot_be_replayed():
    grant, packet, preflight, dispatcher = (
        sources()
    )
    storage = MemoryStorageAdapter()

    execute_authorized_read_only(
        grant,
        packet,
        preflight,
        dispatcher=dispatcher,
        storage=storage,
        executed_at=(
            "2026-10-03T22:30:00+02:00"
        ),
    )

    with pytest.raises(
        CityAuthorizedDispatchError,
        match="already consumed or claimed",
    ):
        execute_authorized_read_only(
            grant,
            packet,
            preflight,
            dispatcher=dispatcher,
            storage=storage,
            executed_at=(
                "2026-10-03T22:31:00+02:00"
            ),
        )


def test_replay_does_not_call_handler_twice():
    grant, packet, preflight, _dispatcher = (
        sources()
    )
    calls = []
    dispatcher = LocalCommandDispatcher()
    dispatcher.register(
        command_type="city.status.read",
        building_id="control-tower",
        capability_id=(
            "city.control-tower.status-board"
        ),
        handler=lambda _arguments: (
            calls.append("called")
            or {"status": "available"}
        ),
    )
    storage = MemoryStorageAdapter()

    execute_authorized_read_only(
        grant,
        packet,
        preflight,
        dispatcher=dispatcher,
        storage=storage,
        executed_at=(
            "2026-10-03T22:30:00+02:00"
        ),
    )

    with pytest.raises(
        CityAuthorizedDispatchError,
        match="already consumed or claimed",
    ):
        execute_authorized_read_only(
            grant,
            packet,
            preflight,
            dispatcher=dispatcher,
            storage=storage,
            executed_at=(
                "2026-10-03T22:31:00+02:00"
            ),
        )

    assert calls == ["called"]


def test_handler_failure_still_consumes_claim():
    grant, packet, preflight, _dispatcher = (
        sources()
    )
    dispatcher = LocalCommandDispatcher()

    def broken(_arguments):
        raise RuntimeError("boom")

    dispatcher.register(
        command_type="city.status.read",
        building_id="control-tower",
        capability_id=(
            "city.control-tower.status-board"
        ),
        handler=broken,
    )
    storage = MemoryStorageAdapter()

    with pytest.raises(
        RuntimeError,
        match="boom",
    ):
        execute_authorized_read_only(
            grant,
            packet,
            preflight,
            dispatcher=dispatcher,
            storage=storage,
            executed_at=(
                "2026-10-03T22:30:00+02:00"
            ),
        )

    record = storage.read(
        "city.dispatch.spent",
        grant["grantId"],
    )

    assert record is not None
    assert record["revision"] == 2
    assert record["value"]["state"] == (
        "failed-consumed"
    )


def test_tampered_grant_digest_is_rejected_before_claim():
    grant, packet, preflight, dispatcher = (
        sources()
    )
    packet["evidence"]["grantDigest"] = (
        "sha256:" + "0" * 64
    )
    storage = MemoryStorageAdapter()

    with pytest.raises(
        CityAuthorizedDispatchError,
        match="packet grant digest mismatch",
    ):
        execute_authorized_read_only(
            grant,
            packet,
            preflight,
            dispatcher=dispatcher,
            storage=storage,
            executed_at=(
                "2026-10-03T22:30:00+02:00"
            ),
        )

    assert storage.list_keys(
        "city.dispatch.spent"
    ) == []


def test_tampered_preflight_is_rejected():
    grant, packet, preflight, dispatcher = (
        sources()
    )
    preflight["command"][
        "arguments"
    ]["tampered"] = True

    with pytest.raises(
        CityAuthorizedDispatchError,
        match="stale or tampered",
    ):
        execute(
            grant,
            packet,
            preflight,
            dispatcher,
        )


def test_registration_drift_is_rejected_before_claim():
    grant, packet, preflight, _dispatcher = (
        sources()
    )
    dispatcher = LocalCommandDispatcher()
    dispatcher.register(
        command_type="city.status.read",
        building_id="github-service",
        capability_id=(
            "city.github.repository-snapshot"
        ),
        handler=lambda _arguments: {},
    )
    storage = MemoryStorageAdapter()

    with pytest.raises(
        CityAuthorizedDispatchError,
        match="fresh preflight failed",
    ):
        execute_authorized_read_only(
            grant,
            packet,
            preflight,
            dispatcher=dispatcher,
            storage=storage,
            executed_at=(
                "2026-10-03T22:30:00+02:00"
            ),
        )

    assert storage.list_keys(
        "city.dispatch.spent"
    ) == []


def test_directory_drift_is_rejected_before_claim():
    grant, packet, preflight, dispatcher = (
        sources()
    )
    directory = build_directory()

    for location in directory["locations"]:
        location["capabilities"] = [
            item
            for item in location["capabilities"]
            if item["id"]
            != "city.control-tower.status-board"
        ]

    storage = MemoryStorageAdapter()

    with pytest.raises(
        CityAuthorizedDispatchError,
        match="fresh preflight failed",
    ):
        execute_authorized_read_only(
            grant,
            packet,
            preflight,
            dispatcher=dispatcher,
            storage=storage,
            executed_at=(
                "2026-10-03T22:30:00+02:00"
            ),
            directory=directory,
        )

    assert storage.list_keys(
        "city.dispatch.spent"
    ) == []


@pytest.mark.parametrize(
    "field,value,match",
    [
        (
            "state",
            "other",
            "issued-unconsumed",
        ),
        (
            "grantsPermission",
            False,
            "carry permission",
        ),
        (
            "runtimeAuthority",
            False,
            "carry runtime authority",
        ),
        (
            "consumed",
            True,
            "artifact must be unconsumed",
        ),
    ],
)
def test_unsafe_grant_is_rejected(
    field,
    value,
    match,
):
    grant, packet, preflight, dispatcher = (
        sources()
    )
    grant[field] = value

    with pytest.raises(
        CityAuthorizedDispatchError,
        match=match,
    ):
        execute(
            grant,
            packet,
            preflight,
            dispatcher,
        )


def test_invalid_grant_constraints_are_rejected():
    grant, packet, preflight, dispatcher = (
        sources()
    )
    grant["constraints"]["singleUse"] = False

    with pytest.raises(
        CityAuthorizedDispatchError,
        match="constraints invalid",
    ):
        execute(
            grant,
            packet,
            preflight,
            dispatcher,
        )


def test_human_confirmer_mismatch_is_rejected():
    grant, packet, preflight, dispatcher = (
        sources()
    )
    packet["requester"]["confirmerId"] = (
        "other-human"
    )

    with pytest.raises(
        CityAuthorizedDispatchError,
        match="human confirmer mismatch",
    ):
        execute(
            grant,
            packet,
            preflight,
            dispatcher,
        )


def test_executed_time_requires_timezone():
    with pytest.raises(
        CityAuthorizedDispatchError,
        match="include timezone",
    ):
        execute(
            executed_at=(
                "2026-10-03T22:30:00"
            )
        )


def test_invalid_storage_is_rejected():
    with pytest.raises(
        CityAuthorizedDispatchError,
        match="storage adapter is invalid",
    ):
        execute(
            storage=object()
        )


def test_receipt_id_is_deterministic_for_same_evidence_and_time():
    grant, packet, preflight, dispatcher = (
        sources()
    )

    first = execute_authorized_read_only(
        grant,
        packet,
        preflight,
        dispatcher=dispatcher,
        storage=MemoryStorageAdapter(),
        executed_at=(
            "2026-10-03T22:30:00+02:00"
        ),
    )
    second = execute_authorized_read_only(
        grant,
        packet,
        preflight,
        dispatcher=dispatcher,
        storage=MemoryStorageAdapter(),
        executed_at=(
            "2026-10-03T22:30:00+02:00"
        ),
    )

    assert first["receiptId"] == (
        second["receiptId"]
    )


def test_contract_is_exact_read_only_executor():
    contract = load_contract()

    assert contract["authority"] == (
        "exact-read-only-executor"
    )
    assert contract["receiptState"] == (
        "dispatched-consumed"
    )
    assert contract["constraints"] == {
        "readOnly": True,
        "singleUse": True,
        "localOnly": True,
        "claimBeforeDispatch": True,
    }


def test_direct_cli_dispatches_one_read_only_command():
    result = subprocess.run(
        [
            sys.executable,
            str(
                ROOT
                / "tools"
                / "city"
                / "authorized_dispatch.py"
            ),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout
    assert (
        "Bondik City Contactor Office OK: "
        "dispatched-consumed / "
        "command=city.status.read / "
        "consumed=true / dispatched=true / "
        "result=available / "
        "bondik-city-read-only-dispatch-receipt/1"
        in result.stdout
    )
