from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.city.activation_confirmation import (
    CityActivationConfirmationError,
    confirm_activation_intent,
)
from tools.city.audit_office import (
    CityAuditError,
    build_audit_entry,
)
from tools.city.command_boundary import (
    CityCommandError,
    LocalCommandDispatcher,
)
from tools.city.command_lease import (
    CityCommandLeaseError,
    prepare_command_lease,
)
from tools.city.dispatch_packet import (
    PACKET_PROTOCOL,
    CityDispatchPacketError,
    prepare_dispatch_packet,
)
from tools.city.dispatch_preflight import (
    PREFLIGHT_PROTOCOL,
    CityDispatchPreflightError,
    validate_dispatch_preflight,
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
    GRANT_PROTOCOL,
    CityRuntimeGrantError,
    issue_runtime_grant,
)
from tools.city.seal_office import (
    CitySealError,
    issue_inactive_certificate,
)
from tools.city.service_directory import (
    CityDirectoryError,
    build_directory,
)
from tools.city.storage_adapter import (
    CityStorageError,
    MemoryStorageAdapter,
    StorageConflictError,
)

DISPATCH_CONTRACT_PROTOCOL = (
    "bondik-city-authorized-dispatch/1"
)
RECEIPT_PROTOCOL = (
    "bondik-city-read-only-dispatch-receipt/1"
)
VERSION = 1

DEFAULT_CONTRACT_PATH = (
    ROOT
    / "config"
    / "city-authorized-dispatch-contract.json"
)


class CityAuthorizedDispatchError(ValueError):
    pass


def _load_json(path: Path, *, label: str) -> Any:
    try:
        return json.loads(
            path.read_text(encoding="utf-8-sig")
        )
    except OSError as error:
        raise CityAuthorizedDispatchError(
            f"cannot read {label}: {error}"
        ) from error
    except json.JSONDecodeError as error:
        raise CityAuthorizedDispatchError(
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
        raise CityAuthorizedDispatchError(
            "dispatch value must be JSON serializable"
        ) from error


def _sha256(value: Any) -> str:
    return hashlib.sha256(
        _canonical_bytes(value)
    ).hexdigest()


def _validate_time(value: Any) -> str:
    if not isinstance(value, str):
        raise CityAuthorizedDispatchError(
            "executedAt must be a string"
        )

    normalized = (
        value[:-1] + "+00:00"
        if value.endswith("Z")
        else value
    )

    try:
        parsed = datetime.fromisoformat(
            normalized
        )
    except ValueError as error:
        raise CityAuthorizedDispatchError(
            "executedAt must be ISO-8601"
        ) from error

    if parsed.tzinfo is None:
        raise CityAuthorizedDispatchError(
            "executedAt must include timezone"
        )

    return value


def load_contract(
    path: Path = DEFAULT_CONTRACT_PATH,
) -> dict[str, Any]:
    payload = _load_json(
        path,
        label="authorized dispatch contract",
    )

    expected = {
        "protocol": DISPATCH_CONTRACT_PROTOCOL,
        "version": VERSION,
        "cityId": "bondik-city",
        "grantProtocol": GRANT_PROTOCOL,
        "packetProtocol": PACKET_PROTOCOL,
        "preflightProtocol": PREFLIGHT_PROTOCOL,
        "receiptProtocol": RECEIPT_PROTOCOL,
        "authority": "exact-read-only-executor",
        "receiptState": "dispatched-consumed",
        "consumptionNamespace": (
            "city.dispatch.spent"
        ),
        "constraints": {
            "readOnly": True,
            "singleUse": True,
            "localOnly": True,
            "claimBeforeDispatch": True,
        },
        "exposure": {
            "network": "not-exposed",
            "policyMutation": "not-allowed",
            "eventPublishing": "not-allowed",
            "handoff": "not-allowed",
        },
    }

    if not isinstance(payload, dict):
        raise CityAuthorizedDispatchError(
            "authorized dispatch contract root "
            "must be an object"
        )

    for key, value in expected.items():
        if payload.get(key) != value:
            raise CityAuthorizedDispatchError(
                f"authorized dispatch contract "
                f"field invalid: {key}"
            )

    return payload


def _validate_storage(storage: Any) -> None:
    if (
        storage is None
        or not callable(
            getattr(storage, "read", None)
        )
        or not callable(
            getattr(storage, "write", None)
        )
    ):
        raise CityAuthorizedDispatchError(
            "storage adapter is invalid"
        )


def execute_authorized_read_only(
    grant: Any,
    packet: Any,
    preflight: Any,
    *,
    dispatcher: LocalCommandDispatcher,
    storage: Any,
    executed_at: Any,
    directory: dict[str, Any] | None = None,
    contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    contract = (
        contract
        if contract is not None
        else load_contract()
    )

    if not isinstance(grant, dict):
        raise CityAuthorizedDispatchError(
            "grant must be an object"
        )
    if not isinstance(packet, dict):
        raise CityAuthorizedDispatchError(
            "packet must be an object"
        )
    if not isinstance(preflight, dict):
        raise CityAuthorizedDispatchError(
            "preflight must be an object"
        )
    if not isinstance(
        dispatcher,
        LocalCommandDispatcher,
    ):
        raise CityAuthorizedDispatchError(
            "dispatcher must be LocalCommandDispatcher"
        )

    _validate_storage(storage)
    executed_at = _validate_time(
        executed_at
    )

    if grant.get("protocol") != (
        contract["grantProtocol"]
    ):
        raise CityAuthorizedDispatchError(
            "grant protocol mismatch"
        )
    if packet.get("protocol") != (
        contract["packetProtocol"]
    ):
        raise CityAuthorizedDispatchError(
            "packet protocol mismatch"
        )
    if preflight.get("protocol") != (
        contract["preflightProtocol"]
    ):
        raise CityAuthorizedDispatchError(
            "preflight protocol mismatch"
        )

    if grant.get("state") != "issued-unconsumed":
        raise CityAuthorizedDispatchError(
            "grant must be issued-unconsumed"
        )
    if grant.get("grantsPermission") is not True:
        raise CityAuthorizedDispatchError(
            "grant must carry permission"
        )
    if grant.get("runtimeAuthority") is not True:
        raise CityAuthorizedDispatchError(
            "grant must carry runtime authority"
        )
    if grant.get("consumed") is not False:
        raise CityAuthorizedDispatchError(
            "grant artifact must be unconsumed"
        )
    if grant.get("constraints") != {
        "singleUse": True,
        "localOnly": True,
        "consumerConnected": False,
    }:
        raise CityAuthorizedDispatchError(
            "grant constraints invalid"
        )

    if packet.get("state") != (
        "ready-not-dispatched"
    ):
        raise CityAuthorizedDispatchError(
            "packet must be ready-not-dispatched"
        )
    if preflight.get("state") != (
        "validated-not-dispatched"
    ):
        raise CityAuthorizedDispatchError(
            "preflight must be validated-not-dispatched"
        )
    if preflight.get("preflightPassed") is not True:
        raise CityAuthorizedDispatchError(
            "preflight must pass"
        )
    if preflight.get(
        "singleUseRequired"
    ) is not True:
        raise CityAuthorizedDispatchError(
            "preflight must require single use"
        )
    if preflight.get(
        "grantConsumptionRequired"
    ) is not True:
        raise CityAuthorizedDispatchError(
            "preflight must require grant consumption"
        )

    for source_name, source in (
        ("packet", packet),
        ("preflight", preflight),
    ):
        for field in (
            "grantConsumed",
            "consumerConnected",
            "dispatchesCommand",
            "executesAction",
            "mutatesPolicy",
        ):
            if source.get(field) is not False:
                raise CityAuthorizedDispatchError(
                    f"{source_name} unsafe field: {field}"
                )

    grant_id = grant.get("grantId")
    packet_id = packet.get("packetId")
    preflight_id = preflight.get(
        "preflightId"
    )

    if (
        not isinstance(grant_id, str)
        or not grant_id
        or not isinstance(packet_id, str)
        or not packet_id
        or not isinstance(preflight_id, str)
        or not preflight_id
    ):
        raise CityAuthorizedDispatchError(
            "dispatch source identities invalid"
        )

    evidence = packet.get("evidence")
    requester = packet.get("requester")

    if not isinstance(evidence, dict):
        raise CityAuthorizedDispatchError(
            "packet evidence invalid"
        )
    if not isinstance(requester, dict):
        raise CityAuthorizedDispatchError(
            "packet requester invalid"
        )

    expected_grant_digest = (
        "sha256:" + _sha256(grant)
    )

    if evidence.get("grantId") != grant_id:
        raise CityAuthorizedDispatchError(
            "packet grantId mismatch"
        )
    if evidence.get(
        "grantDigest"
    ) != expected_grant_digest:
        raise CityAuthorizedDispatchError(
            "packet grant digest mismatch"
        )
    if requester.get("grantId") != grant_id:
        raise CityAuthorizedDispatchError(
            "requester grantId mismatch"
        )

    human_authorization = grant.get(
        "humanAuthorization"
    )

    if not isinstance(
        human_authorization,
        dict,
    ):
        raise CityAuthorizedDispatchError(
            "grant human authorization invalid"
        )

    if requester.get("confirmerId") != (
        human_authorization.get(
            "confirmerId"
        )
    ):
        raise CityAuthorizedDispatchError(
            "human confirmer mismatch"
        )

    directory = (
        directory
        if directory is not None
        else build_directory()
    )

    try:
        fresh_preflight = (
            validate_dispatch_preflight(
                packet,
                dispatcher=dispatcher,
                directory=directory,
            )
        )
    except CityDispatchPreflightError as error:
        raise CityAuthorizedDispatchError(
            f"fresh preflight failed: {error}"
        ) from error

    if fresh_preflight != preflight:
        raise CityAuthorizedDispatchError(
            "preflight is stale or tampered"
        )

    command = packet.get("command")

    if not isinstance(command, dict):
        raise CityAuthorizedDispatchError(
            "packet command invalid"
        )

    if command.get("mutation") != "read-only":
        raise CityAuthorizedDispatchError(
            "only read-only dispatch is allowed"
        )
    if command.get("transport") != (
        "local-in-process"
    ):
        raise CityAuthorizedDispatchError(
            "only local-in-process dispatch is allowed"
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
        raise CityAuthorizedDispatchError(
            "packet command shape invalid"
        )

    building_id = target.get("buildingId")
    capability_id = target.get(
        "capabilityId"
    )

    if (
        not isinstance(building_id, str)
        or not building_id
        or not isinstance(capability_id, str)
        or not capability_id
    ):
        raise CityAuthorizedDispatchError(
            "packet target invalid"
        )

    claim_id = (
        "consume-"
        + hashlib.sha256(
            (
                grant_id
                + "|"
                + preflight_id
            ).encode("utf-8")
        ).hexdigest()[:24]
    )

    command_id = (
        "authorized-"
        + hashlib.sha256(
            (
                packet_id
                + "|"
                + preflight_id
            ).encode("utf-8")
        ).hexdigest()[:24]
    )

    namespace = contract[
        "consumptionNamespace"
    ]

    claim_value = {
        "protocol": RECEIPT_PROTOCOL,
        "version": VERSION,
        "kind": "dispatch-consumption-claim",
        "claimId": claim_id,
        "state": "claimed-before-dispatch",
        "grantId": grant_id,
        "grantDigest": expected_grant_digest,
        "packetId": packet_id,
        "packetDigest": (
            "sha256:" + _sha256(packet)
        ),
        "preflightId": preflight_id,
        "preflightDigest": (
            "sha256:" + _sha256(preflight)
        ),
        "commandId": command_id,
        "executedAt": executed_at,
    }

    try:
        claim_record = storage.write(
            namespace,
            grant_id,
            claim_value,
            expected_revision=0,
        )
    except StorageConflictError as error:
        raise CityAuthorizedDispatchError(
            "grant already consumed or claimed"
        ) from error
    except CityStorageError as error:
        raise CityAuthorizedDispatchError(
            f"cannot claim grant: {error}"
        ) from error

    try:
        report = (
            dispatcher
            ._dispatch_registered_read_only(
                command_id=command_id,
                command_type=command_type,
                building_id=building_id,
                capability_id=capability_id,
                arguments=copy.deepcopy(
                    arguments
                ),
            )
        )
    except Exception as error:
        failed_value = copy.deepcopy(
            claim_value
        )
        failed_value["state"] = (
            "failed-consumed"
        )
        failed_value["errorType"] = (
            type(error).__name__
        )

        try:
            storage.write(
                namespace,
                grant_id,
                failed_value,
                expected_revision=(
                    claim_record["revision"]
                ),
            )
        except CityStorageError as storage_error:
            raise CityAuthorizedDispatchError(
                "dispatch failed and failure "
                "consumption record could not "
                "be finalized"
            ) from storage_error

        raise

    result_digest = (
        "sha256:" + _sha256(report.result)
    )

    consumed_value = copy.deepcopy(
        claim_value
    )
    consumed_value.update(
        {
            "state": "dispatched-consumed",
            "resultDigest": result_digest,
        }
    )

    try:
        consumed_record = storage.write(
            namespace,
            grant_id,
            consumed_value,
            expected_revision=(
                claim_record["revision"]
            ),
        )
    except CityStorageError as error:
        raise CityAuthorizedDispatchError(
            "dispatch completed but consumption "
            "record could not be finalized"
        ) from error

    receipt_id = (
        "dispatch-"
        + hashlib.sha256(
            (
                claim_id
                + "|"
                + executed_at
            ).encode("utf-8")
        ).hexdigest()[:24]
    )

    return {
        "protocol": RECEIPT_PROTOCOL,
        "version": VERSION,
        "cityId": contract["cityId"],
        "kind": "read-only-dispatch-receipt",
        "receiptId": receipt_id,
        "state": contract["receiptState"],
        "authority": contract["authority"],
        "executedAt": executed_at,
        "grant": {
            "grantId": grant_id,
            "sourceArtifactConsumed": False,
            "consumptionRecorded": True,
            "consumptionNamespace": namespace,
            "consumptionRevision": (
                consumed_record["revision"]
            ),
        },
        "packet": {
            "packetId": packet_id,
            "packetDigest": (
                "sha256:" + _sha256(packet)
            ),
        },
        "preflight": {
            "preflightId": preflight_id,
            "preflightDigest": (
                "sha256:" + _sha256(preflight)
            ),
        },
        "command": {
            "commandId": command_id,
            "commandType": (
                report.command_type
            ),
            "targetBuildingId": (
                report.target_building_id
            ),
            "targetCapabilityId": (
                capability_id
            ),
            "mutation": "read-only",
            "transport": "local-in-process",
            "result": copy.deepcopy(
                report.result
            ),
            "resultDigest": result_digest,
        },
        "singleUse": True,
        "grantConsumed": True,
        "consumerConnected": True,
        "dispatchesCommand": True,
        "executesAction": True,
        "mutatesPolicy": False,
        "publishesEvent": False,
        "performsHandoff": False,
        "usesNetwork": False,
        "exposure": copy.deepcopy(
            contract["exposure"]
        ),
    }


def _build_demo_sources() -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    LocalCommandDispatcher,
]:
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
    preflight = validate_dispatch_preflight(
        packet,
        dispatcher=dispatcher,
    )

    return (
        grant,
        packet,
        preflight,
        dispatcher,
    )


def main() -> int:
    argparse.ArgumentParser(
        description=(
            "Consume one human-confirmed grant "
            "and execute one exact local read-only "
            "Bondik City command."
        )
    ).parse_args()

    storage = MemoryStorageAdapter()

    try:
        (
            grant,
            packet,
            preflight,
            dispatcher,
        ) = _build_demo_sources()
        receipt = execute_authorized_read_only(
            grant,
            packet,
            preflight,
            dispatcher=dispatcher,
            storage=storage,
            executed_at=(
                "2026-01-01T00:05:00Z"
            ),
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
        CityDispatchPreflightError,
        CityDirectoryError,
        CityCommandError,
        CityStorageError,
        CityAuthorizedDispatchError,
    ) as error:
        print(
            "Bondik City Contactor Office ERROR: "
            f"{error}"
        )
        return 1

    print(
        "Bondik City Contactor Office OK: "
        f"{receipt['state']} / "
        "command=city.status.read / "
        "consumed=true / dispatched=true / "
        "result=available / "
        f"{RECEIPT_PROTOCOL}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
