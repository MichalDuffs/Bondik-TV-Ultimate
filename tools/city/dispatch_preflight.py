from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.city.command_boundary import (
    CityCommandError,
    LocalCommandDispatcher,
)
from tools.city.dispatch_packet import (
    PACKET_PROTOCOL,
    CityDispatchPacketError,
    _dispatcher as packet_dispatcher,
    prepare_dispatch_packet,
)
from tools.city.service_directory import (
    DIRECTORY_PROTOCOL,
    CityDirectoryError,
    build_directory,
)
from tools.city.activation_confirmation import (
    CityActivationConfirmationError,
    confirm_activation_intent,
)
from tools.city.audit_office import (
    CityAuditError,
    build_audit_entry,
)
from tools.city.command_lease import (
    CityCommandLeaseError,
    prepare_command_lease,
)
from tools.city.grant_admission import (
    CityGrantAdmissionError,
    admit_runtime_grant,
)
from tools.city.ignition_office import (
    CityIgnitionError,
    prepare_activation_intent,
)
from tools.city.key_vault import (
    CityKeyVaultError,
    build_registry_entry,
)
from tools.city.permit_office import (
    CityPermitError,
    prepare_permit_request,
)
from tools.city.review_board import (
    CityReviewError,
    record_human_review,
)
from tools.city.runtime_grant import (
    CityRuntimeGrantError,
    issue_runtime_grant,
)
from tools.city.seal_office import (
    CitySealError,
    issue_inactive_certificate,
)

PREFLIGHT_CONTRACT_PROTOCOL = (
    "bondik-city-dispatch-preflight/1"
)
PREFLIGHT_PROTOCOL = (
    "bondik-city-dispatch-preflight-record/1"
)
VERSION = 1

DEFAULT_CONTRACT_PATH = (
    ROOT
    / "config"
    / "city-dispatch-preflight-contract.json"
)


class CityDispatchPreflightError(ValueError):
    pass


def _load_json(path: Path, *, label: str) -> Any:
    try:
        return json.loads(
            path.read_text(encoding="utf-8-sig")
        )
    except OSError as error:
        raise CityDispatchPreflightError(
            f"cannot read {label}: {error}"
        ) from error
    except json.JSONDecodeError as error:
        raise CityDispatchPreflightError(
            f"{label} must be valid JSON"
        ) from error


def _canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise CityDispatchPreflightError(
            "preflight value must be JSON serializable"
        ) from error


def _sha256(value: Any) -> str:
    return hashlib.sha256(
        _canonical_bytes(value)
    ).hexdigest()


def load_contract(
    path: Path = DEFAULT_CONTRACT_PATH,
) -> dict[str, Any]:
    payload = _load_json(
        path,
        label="dispatch preflight contract",
    )

    expected = {
        "protocol": PREFLIGHT_CONTRACT_PROTOCOL,
        "version": VERSION,
        "cityId": "bondik-city",
        "packetProtocol": PACKET_PROTOCOL,
        "directoryProtocol": DIRECTORY_PROTOCOL,
        "preflightProtocol": PREFLIGHT_PROTOCOL,
        "authority": "final-preflight-only",
        "preflightState": "validated-not-dispatched",
        "exposure": {
            "execution": "not-exposed",
            "mutation": "not-allowed",
            "network": "not-exposed",
            "permissionGrant": "not-allowed",
            "grantConsumption": "not-allowed",
        },
    }

    if not isinstance(payload, dict):
        raise CityDispatchPreflightError(
            "dispatch preflight contract root "
            "must be an object"
        )

    for key, value in expected.items():
        if payload.get(key) != value:
            raise CityDispatchPreflightError(
                f"dispatch preflight contract "
                f"field invalid: {key}"
            )

    return payload


def _require_active_target(
    directory: dict[str, Any],
    *,
    building_id: str,
    capability_id: str,
) -> None:
    if directory.get("protocol") != DIRECTORY_PROTOCOL:
        raise CityDispatchPreflightError(
            "directory protocol mismatch"
        )

    matches = []

    for location in directory.get(
        "locations",
        [],
    ):
        if location.get("id") != building_id:
            continue

        for capability in location.get(
            "capabilities",
            [],
        ):
            if capability.get("id") == capability_id:
                matches.append(capability)

    if len(matches) != 1:
        raise CityDispatchPreflightError(
            "preflight target capability "
            "must resolve exactly once"
        )

    if matches[0].get("status") != "active":
        raise CityDispatchPreflightError(
            "preflight target capability "
            "must be active"
        )


def validate_dispatch_preflight(
    packet: Any,
    *,
    dispatcher: LocalCommandDispatcher,
    directory: dict[str, Any] | None = None,
    contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    contract = (
        contract
        if contract is not None
        else load_contract()
    )

    if not isinstance(packet, dict):
        raise CityDispatchPreflightError(
            "packet must be an object"
        )

    if packet.get("protocol") != (
        contract["packetProtocol"]
    ):
        raise CityDispatchPreflightError(
            "packet protocol mismatch"
        )

    if packet.get("state") != (
        "ready-not-dispatched"
    ):
        raise CityDispatchPreflightError(
            "packet must be ready-not-dispatched"
        )

    for field in (
        "grantConsumed",
        "consumerConnected",
        "dispatchesCommand",
        "executesAction",
        "mutatesPolicy",
    ):
        if packet.get(field) is not False:
            raise CityDispatchPreflightError(
                f"packet unsafe field: {field}"
            )

    if packet.get("grantsPermission") is not False:
        raise CityDispatchPreflightError(
            "packet must not grant permission"
        )

    if packet.get("runtimeAuthority") is not False:
        raise CityDispatchPreflightError(
            "packet must not carry runtime authority"
        )

    requester = packet.get("requester")
    command = packet.get("command")
    evidence = packet.get("evidence")

    if requester is None or not isinstance(
        requester,
        dict,
    ):
        raise CityDispatchPreflightError(
            "packet requester invalid"
        )

    if requester.get("kind") != (
        "human-confirmed-runtime-grant"
    ):
        raise CityDispatchPreflightError(
            "packet requester provenance invalid"
        )

    if not isinstance(command, dict):
        raise CityDispatchPreflightError(
            "packet command invalid"
        )

    if not isinstance(evidence, dict):
        raise CityDispatchPreflightError(
            "packet evidence invalid"
        )

    packet_id = packet.get("packetId")
    prepared_at = packet.get("preparedAt")
    lease_id = requester.get("leaseId")

    if (
        not isinstance(packet_id, str)
        or not packet_id
        or not isinstance(prepared_at, str)
        or not prepared_at
        or not isinstance(lease_id, str)
        or not lease_id
    ):
        raise CityDispatchPreflightError(
            "packet identity invalid"
        )

    expected_packet_id = (
        "packet-"
        + hashlib.sha256(
            (
                lease_id
                + "|"
                + prepared_at
            ).encode("utf-8")
        ).hexdigest()[:24]
    )

    if packet_id != expected_packet_id:
        raise CityDispatchPreflightError(
            "packetId integrity mismatch"
        )

    if evidence.get("leaseId") != lease_id:
        raise CityDispatchPreflightError(
            "packet leaseId mismatch"
        )

    command_type = command.get("commandType")
    target = command.get("target")
    arguments = command.get("arguments")

    if (
        not isinstance(command_type, str)
        or not command_type
        or not isinstance(target, dict)
        or not isinstance(arguments, dict)
    ):
        raise CityDispatchPreflightError(
            "packet command shape invalid"
        )

    if command.get("mutation") != "read-only":
        raise CityDispatchPreflightError(
            "packet command must be read-only"
        )

    if command.get("transport") != (
        "local-in-process"
    ):
        raise CityDispatchPreflightError(
            "packet transport must be local-in-process"
        )

    expected_arguments_digest = (
        "sha256:" + _sha256(arguments)
    )

    if command.get(
        "argumentsDigest"
    ) != expected_arguments_digest:
        raise CityDispatchPreflightError(
            "packet arguments digest mismatch"
        )

    building_id = target.get("buildingId")
    capability_id = target.get("capabilityId")

    if (
        not isinstance(building_id, str)
        or not building_id
        or not isinstance(capability_id, str)
        or not capability_id
    ):
        raise CityDispatchPreflightError(
            "packet target invalid"
        )

    if not isinstance(
        dispatcher,
        LocalCommandDispatcher,
    ):
        raise CityDispatchPreflightError(
            "dispatcher must be LocalCommandDispatcher"
        )

    try:
        registration = (
            dispatcher.describe_registration(
                command_type
            )
        )
    except CityCommandError as error:
        raise CityDispatchPreflightError(
            str(error)
        ) from error

    if registration.mutation != "read-only":
        raise CityDispatchPreflightError(
            "dispatch registration must be read-only"
        )

    if (
        registration.building_id
        != building_id
        or registration.capability_id
        != capability_id
    ):
        raise CityDispatchPreflightError(
            "dispatch registration target mismatch"
        )

    directory = (
        directory
        if directory is not None
        else build_directory()
    )

    _require_active_target(
        directory,
        building_id=building_id,
        capability_id=capability_id,
    )

    preflight_id = (
        "preflight-"
        + hashlib.sha256(
            (
                packet_id
                + "|"
                + command_type
                + "|"
                + building_id
                + "|"
                + capability_id
                + "|"
                + _sha256(arguments)
            ).encode("utf-8")
        ).hexdigest()[:24]
    )

    return {
        "protocol": PREFLIGHT_PROTOCOL,
        "version": VERSION,
        "cityId": contract["cityId"],
        "kind": "dispatch-preflight",
        "preflightId": preflight_id,
        "state": contract["preflightState"],
        "authority": contract["authority"],
        "packet": {
            "packetId": packet_id,
            "packetDigest": (
                "sha256:" + _sha256(packet)
            ),
        },
        "registration": {
            "commandType": (
                registration.command_type
            ),
            "buildingId": (
                registration.building_id
            ),
            "capabilityId": (
                registration.capability_id
            ),
            "mutation": (
                registration.mutation
            ),
        },
        "command": copy.deepcopy(command),
        "requester": copy.deepcopy(
            requester
        ),
        "preflightPassed": True,
        "singleUseRequired": True,
        "grantConsumptionRequired": True,
        "grantConsumed": False,
        "consumerConnected": False,
        "dispatchesCommand": False,
        "executesAction": False,
        "grantsPermission": False,
        "runtimeAuthority": False,
        "mutatesPolicy": False,
        "exposure": copy.deepcopy(
            contract["exposure"]
        ),
    }


def _build_demo_packet() -> tuple[
    dict[str, Any],
    LocalCommandDispatcher,
]:
    dispatcher = packet_dispatcher()

    permit = prepare_permit_request(
        ticket_id="demo-ticket-1",
        principal={
            "id": "demo-agent",
            "role": "observer",
        },
        operation="command",
        capability_id=(
            "city.command-boundary.local"
        ),
        reason="Request human review.",
        requested_at=(
            "2026-01-01T00:00:00Z"
        ),
    )
    review = record_human_review(
        permit,
        reviewer_id="demo-human",
        decision="approve",
        reviewed_at=(
            "2026-01-01T00:01:00Z"
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
        actor_id="demo-human",
        prepared_at=(
            "2026-01-01T00:02:00Z"
        ),
        reason="Prepare activation.",
    )
    confirmation = confirm_activation_intent(
        intent,
        confirmer_id="demo-human",
        confirmed_at=(
            "2026-01-01T00:03:00Z"
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
    lease = prepare_command_lease(
        grant,
        admission,
        dispatcher=dispatcher,
        command_type="city.status.read",
        target_building_id="control-tower",
        target_capability_id=(
            "city.control-tower.status-board"
        ),
        arguments={},
    )
    packet = prepare_dispatch_packet(
        grant,
        admission,
        lease,
        prepared_at=(
            "2026-01-01T00:04:00Z"
        ),
    )

    return packet, dispatcher


def main() -> int:
    argparse.ArgumentParser(
        description=(
            "Run final Bondik City read-only "
            "dispatch preflight without dispatching."
        )
    ).parse_args()

    try:
        packet, dispatcher = (
            _build_demo_packet()
        )
        preflight = (
            validate_dispatch_preflight(
                packet,
                dispatcher=dispatcher,
            )
        )
    except (
        CityPermitError,
        CityReviewError,
        CityAuditError,
        CitySealError,
        CityKeyVaultError,
        CityIgnitionError,
        CityActivationConfirmationError,
        CityRuntimeGrantError,
        CityGrantAdmissionError,
        CityCommandLeaseError,
        CityDispatchPacketError,
        CityDirectoryError,
        CityDispatchPreflightError,
    ) as error:
        print(
            "Bondik City Dispatch Gate ERROR: "
            f"{error}"
        )
        return 1

    print(
        "Bondik City Dispatch Gate OK: "
        f"{preflight['state']} / "
        "command=city.status.read / "
        "preflight=true / dispatched=false / "
        f"{PREFLIGHT_PROTOCOL}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
