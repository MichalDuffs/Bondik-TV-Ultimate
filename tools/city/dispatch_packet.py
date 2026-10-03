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
    MAX_ARGUMENT_BYTES,
    CityCommandError,
    LocalCommandDispatcher,
)
from tools.city.command_lease import (
    LEASE_PROTOCOL,
    CityCommandLeaseError,
    prepare_command_lease,
)
from tools.city.grant_admission import (
    ADMISSION_PROTOCOL,
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
    DIRECTORY_PROTOCOL,
    CityDirectoryError,
    build_directory,
)

PACKET_CONTRACT_PROTOCOL = (
    "bondik-city-dispatch-packet/1"
)
PACKET_PROTOCOL = (
    "bondik-city-authorized-command-packet/1"
)
VERSION = 1

DEFAULT_CONTRACT_PATH = (
    ROOT
    / "config"
    / "city-dispatch-packet-contract.json"
)


class CityDispatchPacketError(ValueError):
    pass


def _load_json(path: Path, *, label: str) -> Any:
    try:
        return json.loads(
            path.read_text(encoding="utf-8-sig")
        )
    except OSError as error:
        raise CityDispatchPacketError(
            f"cannot read {label}: {error}"
        ) from error
    except json.JSONDecodeError as error:
        raise CityDispatchPacketError(
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
        raise CityDispatchPacketError(
            "packet value must be JSON serializable"
        ) from error


def _sha256(value: Any) -> str:
    return hashlib.sha256(
        _canonical_bytes(value)
    ).hexdigest()


def _validate_time(value: Any) -> str:
    if not isinstance(value, str):
        raise CityDispatchPacketError(
            "preparedAt must be a string"
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
        raise CityDispatchPacketError(
            "preparedAt must be ISO-8601"
        ) from error

    if parsed.tzinfo is None:
        raise CityDispatchPacketError(
            "preparedAt must include timezone"
        )

    return value


def load_contract(
    path: Path = DEFAULT_CONTRACT_PATH,
) -> dict[str, Any]:
    payload = _load_json(
        path,
        label="dispatch packet contract",
    )

    expected = {
        "protocol": PACKET_CONTRACT_PROTOCOL,
        "version": VERSION,
        "cityId": "bondik-city",
        "grantProtocol": GRANT_PROTOCOL,
        "admissionProtocol": ADMISSION_PROTOCOL,
        "leaseProtocol": LEASE_PROTOCOL,
        "directoryProtocol": DIRECTORY_PROTOCOL,
        "packetProtocol": PACKET_PROTOCOL,
        "authority": "dispatch-preparation-only",
        "packetState": "ready-not-dispatched",
        "exposure": {
            "execution": "not-exposed",
            "mutation": "not-allowed",
            "network": "not-exposed",
            "permissionGrant": "not-allowed",
            "grantConsumption": "not-allowed",
        },
    }

    if not isinstance(payload, dict):
        raise CityDispatchPacketError(
            "dispatch packet contract root "
            "must be an object"
        )

    for key, value in expected.items():
        if payload.get(key) != value:
            raise CityDispatchPacketError(
                f"dispatch packet contract "
                f"field invalid: {key}"
            )

    return payload


def _resolve_active_target(
    directory: dict[str, Any],
    *,
    building_id: str,
    capability_id: str,
) -> None:
    if directory.get("protocol") != DIRECTORY_PROTOCOL:
        raise CityDispatchPacketError(
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
        raise CityDispatchPacketError(
            "packet target capability "
            "must resolve exactly once"
        )

    if matches[0].get("status") != "active":
        raise CityDispatchPacketError(
            "packet target capability "
            "must be active"
        )


def prepare_dispatch_packet(
    grant: Any,
    admission: Any,
    lease: Any,
    *,
    prepared_at: Any,
    directory: dict[str, Any] | None = None,
    contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    contract = (
        contract
        if contract is not None
        else load_contract()
    )

    if not isinstance(grant, dict):
        raise CityDispatchPacketError(
            "grant must be an object"
        )
    if not isinstance(admission, dict):
        raise CityDispatchPacketError(
            "admission must be an object"
        )
    if not isinstance(lease, dict):
        raise CityDispatchPacketError(
            "lease must be an object"
        )

    if grant.get("protocol") != (
        contract["grantProtocol"]
    ):
        raise CityDispatchPacketError(
            "grant protocol mismatch"
        )
    if admission.get("protocol") != (
        contract["admissionProtocol"]
    ):
        raise CityDispatchPacketError(
            "admission protocol mismatch"
        )
    if lease.get("protocol") != (
        contract["leaseProtocol"]
    ):
        raise CityDispatchPacketError(
            "lease protocol mismatch"
        )

    if grant.get("state") != "issued-unconsumed":
        raise CityDispatchPacketError(
            "grant must be issued-unconsumed"
        )
    if admission.get("state") != (
        "admitted-not-consumed"
    ):
        raise CityDispatchPacketError(
            "admission must be admitted-not-consumed"
        )
    if lease.get("state") != "prepared-unconsumed":
        raise CityDispatchPacketError(
            "lease must be prepared-unconsumed"
        )

    if grant.get("grantsPermission") is not True:
        raise CityDispatchPacketError(
            "grant must carry permission"
        )
    if grant.get("runtimeAuthority") is not True:
        raise CityDispatchPacketError(
            "grant must carry runtime authority"
        )
    if grant.get("consumed") is not False:
        raise CityDispatchPacketError(
            "grant must be unconsumed"
        )

    for source_name, source in (
        ("admission", admission),
        ("lease", lease),
    ):
        for field in (
            "grantConsumed",
            "consumerConnected",
            "dispatchesCommand",
            "executesAction",
        ):
            if source.get(field) is not False:
                raise CityDispatchPacketError(
                    f"{source_name} unsafe field: {field}"
                )

    if lease.get("command", {}).get(
        "registrationMutation"
    ) != "read-only":
        raise CityDispatchPacketError(
            "lease command must be read-only"
        )

    grant_id = grant.get("grantId")
    admission_id = admission.get("admissionId")
    lease_id = lease.get("leaseId")

    if (
        not isinstance(grant_id, str)
        or not grant_id
        or not isinstance(admission_id, str)
        or not admission_id
        or not isinstance(lease_id, str)
        or not lease_id
    ):
        raise CityDispatchPacketError(
            "source identities invalid"
        )

    expected_grant_digest = (
        "sha256:" + _sha256(grant)
    )
    expected_admission_digest = (
        "sha256:" + _sha256(admission)
    )

    admission_evidence = admission.get(
        "evidence"
    )
    lease_source = lease.get("source")

    if not isinstance(admission_evidence, dict):
        raise CityDispatchPacketError(
            "admission evidence invalid"
        )
    if not isinstance(lease_source, dict):
        raise CityDispatchPacketError(
            "lease source invalid"
        )

    if admission_evidence.get("grantId") != grant_id:
        raise CityDispatchPacketError(
            "admission grantId mismatch"
        )
    if admission_evidence.get(
        "grantDigest"
    ) != expected_grant_digest:
        raise CityDispatchPacketError(
            "admission grant digest mismatch"
        )

    if lease_source.get("grantId") != grant_id:
        raise CityDispatchPacketError(
            "lease grantId mismatch"
        )
    if lease_source.get(
        "grantDigest"
    ) != expected_grant_digest:
        raise CityDispatchPacketError(
            "lease grant digest mismatch"
        )
    if lease_source.get("admissionId") != admission_id:
        raise CityDispatchPacketError(
            "lease admissionId mismatch"
        )
    if lease_source.get(
        "admissionDigest"
    ) != expected_admission_digest:
        raise CityDispatchPacketError(
            "lease admission digest mismatch"
        )

    if lease.get("subject") != grant.get("subject"):
        raise CityDispatchPacketError(
            "lease subject mismatch"
        )

    command = lease.get("command")

    if not isinstance(command, dict):
        raise CityDispatchPacketError(
            "lease command missing"
        )

    command_type = command.get("commandType")
    target = command.get("target")
    arguments = command.get("arguments")
    arguments_digest = command.get(
        "argumentsDigest"
    )

    if (
        not isinstance(command_type, str)
        or not command_type
        or not isinstance(target, dict)
        or not isinstance(arguments, dict)
    ):
        raise CityDispatchPacketError(
            "lease command invalid"
        )

    encoded_arguments = _canonical_bytes(
        arguments
    )

    if len(encoded_arguments) > MAX_ARGUMENT_BYTES:
        raise CityDispatchPacketError(
            "arguments exceed size limit"
        )

    expected_arguments_digest = (
        "sha256:" + _sha256(arguments)
    )

    if arguments_digest != expected_arguments_digest:
        raise CityDispatchPacketError(
            "arguments digest mismatch"
        )

    building_id = target.get("buildingId")
    capability_id = target.get("capabilityId")

    if (
        not isinstance(building_id, str)
        or not building_id
        or not isinstance(capability_id, str)
        or not capability_id
    ):
        raise CityDispatchPacketError(
            "lease target invalid"
        )

    directory = (
        directory
        if directory is not None
        else build_directory()
    )
    _resolve_active_target(
        directory,
        building_id=building_id,
        capability_id=capability_id,
    )

    prepared_at = _validate_time(
        prepared_at
    )

    packet_id = (
        "packet-"
        + hashlib.sha256(
            (
                lease_id
                + "|"
                + prepared_at
            ).encode("utf-8")
        ).hexdigest()[:24]
    )

    human_authorization = grant.get(
        "humanAuthorization"
    )

    if not isinstance(
        human_authorization,
        dict,
    ):
        raise CityDispatchPacketError(
            "grant human authorization missing"
        )

    return {
        "protocol": PACKET_PROTOCOL,
        "version": VERSION,
        "cityId": contract["cityId"],
        "kind": "authorized-command-packet",
        "packetId": packet_id,
        "state": contract["packetState"],
        "authority": contract["authority"],
        "preparedAt": prepared_at,
        "requester": {
            "kind": "human-confirmed-runtime-grant",
            "subject": copy.deepcopy(
                grant.get("subject")
            ),
            "grantId": grant_id,
            "leaseId": lease_id,
            "confirmerId": (
                human_authorization.get(
                    "confirmerId"
                )
            ),
        },
        "command": {
            "commandType": command_type,
            "target": copy.deepcopy(target),
            "arguments": copy.deepcopy(
                arguments
            ),
            "argumentsDigest": (
                expected_arguments_digest
            ),
            "mutation": "read-only",
            "transport": "local-in-process",
        },
        "evidence": {
            "grantId": grant_id,
            "grantDigest": (
                expected_grant_digest
            ),
            "admissionId": admission_id,
            "admissionDigest": (
                expected_admission_digest
            ),
            "leaseId": lease_id,
            "leaseDigest": (
                "sha256:" + _sha256(lease)
            ),
        },
        "sourceGrantPermission": True,
        "sourceGrantRuntimeAuthority": True,
        "grantsPermission": False,
        "runtimeAuthority": False,
        "grantConsumed": False,
        "consumerConnected": False,
        "dispatchesCommand": False,
        "executesAction": False,
        "mutatesPolicy": False,
        "exposure": copy.deepcopy(
            contract["exposure"]
        ),
    }


def _dispatcher() -> LocalCommandDispatcher:
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
    return dispatcher


def main() -> int:
    argparse.ArgumentParser(
        description=(
            "Prepare a fully bound Bondik City "
            "authorized command packet without "
            "dispatching or consuming it."
        )
    ).parse_args()

    try:
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
            dispatcher=_dispatcher(),
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
        CityCommandError,
        CityCommandLeaseError,
        CityDirectoryError,
        CityDispatchPacketError,
    ) as error:
        print(
            "Bondik City Switchboard ERROR: "
            f"{error}"
        )
        return 1

    print(
        "Bondik City Switchboard OK: "
        f"{packet['state']} / "
        "command=city.status.read / "
        "consumed=false / dispatched=false / "
        f"{PACKET_PROTOCOL}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
