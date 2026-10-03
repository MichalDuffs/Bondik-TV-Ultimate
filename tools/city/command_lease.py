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

LEASE_CONTRACT_PROTOCOL = (
    "bondik-city-command-lease/1"
)
LEASE_PROTOCOL = (
    "bondik-city-command-lease-token/1"
)
VERSION = 1

DEFAULT_CONTRACT_PATH = (
    ROOT
    / "config"
    / "city-command-lease-contract.json"
)


class CityCommandLeaseError(ValueError):
    pass


def _load_json(path: Path, *, label: str) -> Any:
    try:
        return json.loads(
            path.read_text(encoding="utf-8-sig")
        )
    except OSError as error:
        raise CityCommandLeaseError(
            f"cannot read {label}: {error}"
        ) from error
    except json.JSONDecodeError as error:
        raise CityCommandLeaseError(
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
        raise CityCommandLeaseError(
            "value must be JSON serializable"
        ) from error


def _sha256(value: Any) -> str:
    return hashlib.sha256(
        _canonical_bytes(value)
    ).hexdigest()


def _clone_arguments(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CityCommandLeaseError(
            "arguments must be an object"
        )

    encoded = _canonical_bytes(value)

    if len(encoded) > MAX_ARGUMENT_BYTES:
        raise CityCommandLeaseError(
            "arguments exceed size limit"
        )

    return json.loads(
        encoded.decode("utf-8")
    )


def load_contract(
    path: Path = DEFAULT_CONTRACT_PATH,
) -> dict[str, Any]:
    payload = _load_json(
        path,
        label="command lease contract",
    )

    expected = {
        "protocol": LEASE_CONTRACT_PROTOCOL,
        "version": VERSION,
        "cityId": "bondik-city",
        "grantProtocol": GRANT_PROTOCOL,
        "admissionProtocol": ADMISSION_PROTOCOL,
        "leaseProtocol": LEASE_PROTOCOL,
        "commandBoundaryCapability": (
            "city.command-boundary.local"
        ),
        "authority": "scope-narrowing-only",
        "leaseState": "prepared-unconsumed",
        "constraints": {
            "readOnly": True,
            "singleUse": True,
            "localOnly": True,
            "consumerConnected": False,
        },
        "exposure": {
            "execution": "not-exposed",
            "mutation": "not-allowed",
            "network": "not-exposed",
            "permissionGrant": "not-allowed",
            "grantConsumption": "not-allowed",
        },
    }

    if not isinstance(payload, dict):
        raise CityCommandLeaseError(
            "command lease contract root "
            "must be an object"
        )

    for key, value in expected.items():
        if payload.get(key) != value:
            raise CityCommandLeaseError(
                f"command lease contract "
                f"field invalid: {key}"
            )

    return payload


def _find_active_capability(
    directory: dict[str, Any],
    *,
    building_id: str,
    capability_id: str,
) -> None:
    if directory.get("protocol") != DIRECTORY_PROTOCOL:
        raise CityCommandLeaseError(
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
        raise CityCommandLeaseError(
            "command target capability "
            "must resolve exactly once"
        )

    if matches[0].get("status") != "active":
        raise CityCommandLeaseError(
            "command target capability "
            "must be active"
        )


def prepare_command_lease(
    grant: Any,
    admission: Any,
    *,
    dispatcher: LocalCommandDispatcher,
    command_type: Any,
    target_building_id: Any,
    target_capability_id: Any,
    arguments: Any,
    directory: dict[str, Any] | None = None,
    contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    contract = (
        contract
        if contract is not None
        else load_contract()
    )

    if not isinstance(grant, dict):
        raise CityCommandLeaseError(
            "grant must be an object"
        )

    if not isinstance(admission, dict):
        raise CityCommandLeaseError(
            "admission must be an object"
        )

    if grant.get("protocol") != (
        contract["grantProtocol"]
    ):
        raise CityCommandLeaseError(
            "grant protocol mismatch"
        )

    if admission.get("protocol") != (
        contract["admissionProtocol"]
    ):
        raise CityCommandLeaseError(
            "admission protocol mismatch"
        )

    if grant.get("state") != "issued-unconsumed":
        raise CityCommandLeaseError(
            "grant must be issued-unconsumed"
        )

    if admission.get("state") != (
        "admitted-not-consumed"
    ):
        raise CityCommandLeaseError(
            "admission must be admitted-not-consumed"
        )

    if grant.get("grantsPermission") is not True:
        raise CityCommandLeaseError(
            "grant must carry permission"
        )

    if grant.get("runtimeAuthority") is not True:
        raise CityCommandLeaseError(
            "grant must carry runtime authority"
        )

    if grant.get("consumed") is not False:
        raise CityCommandLeaseError(
            "grant must be unconsumed"
        )

    if admission.get("grantConsumed") is not False:
        raise CityCommandLeaseError(
            "admission must not consume grant"
        )

    if admission.get("consumerConnected") is not False:
        raise CityCommandLeaseError(
            "admission consumer must remain disconnected"
        )

    if admission.get("dispatchesCommand") is not False:
        raise CityCommandLeaseError(
            "admission must not dispatch command"
        )

    if admission.get("executesAction") is not False:
        raise CityCommandLeaseError(
            "admission must not execute action"
        )

    grant_id = grant.get("grantId")
    admission_evidence = admission.get(
        "evidence"
    )

    if (
        not isinstance(grant_id, str)
        or not grant_id
        or not isinstance(
            admission_evidence,
            dict,
        )
    ):
        raise CityCommandLeaseError(
            "grant admission evidence invalid"
        )

    expected_grant_digest = (
        "sha256:" + _sha256(grant)
    )

    if admission_evidence.get(
        "grantId"
    ) != grant_id:
        raise CityCommandLeaseError(
            "admission grantId mismatch"
        )

    if admission_evidence.get(
        "grantDigest"
    ) != expected_grant_digest:
        raise CityCommandLeaseError(
            "admission grant digest mismatch"
        )

    scope = grant.get("scope")

    if scope != {
        "operation": "command",
        "capabilityId": contract[
            "commandBoundaryCapability"
        ],
    }:
        raise CityCommandLeaseError(
            "grant is not scoped to command boundary"
        )

    consumer = admission.get("consumer")

    if consumer != {
        "id": "dispatch-office",
        "connected": False,
    }:
        raise CityCommandLeaseError(
            "admission consumer must be dispatch-office"
        )

    if (
        not isinstance(dispatcher, LocalCommandDispatcher)
    ):
        raise CityCommandLeaseError(
            "dispatcher must be LocalCommandDispatcher"
        )

    if not isinstance(command_type, str):
        raise CityCommandLeaseError(
            "commandType must be a string"
        )

    if not isinstance(target_building_id, str):
        raise CityCommandLeaseError(
            "target buildingId must be a string"
        )

    if not isinstance(target_capability_id, str):
        raise CityCommandLeaseError(
            "target capabilityId must be a string"
        )

    try:
        registration = (
            dispatcher.describe_registration(
                command_type
            )
        )
    except CityCommandError as error:
        raise CityCommandLeaseError(
            str(error)
        ) from error

    if registration.mutation != "read-only":
        raise CityCommandLeaseError(
            "command registration must be read-only"
        )

    if (
        registration.building_id
        != target_building_id
        or registration.capability_id
        != target_capability_id
    ):
        raise CityCommandLeaseError(
            "command target does not match registration"
        )

    arguments = _clone_arguments(
        arguments
    )

    directory = (
        directory
        if directory is not None
        else build_directory()
    )

    _find_active_capability(
        directory,
        building_id=target_building_id,
        capability_id=target_capability_id,
    )

    lease_id = (
        "lease-"
        + hashlib.sha256(
            (
                grant_id
                + "|"
                + admission.get(
                    "admissionId",
                    "",
                )
                + "|"
                + command_type
                + "|"
                + target_building_id
                + "|"
                + target_capability_id
                + "|"
                + _sha256(arguments)
            ).encode("utf-8")
        ).hexdigest()[:24]
    )

    return {
        "protocol": LEASE_PROTOCOL,
        "version": VERSION,
        "cityId": contract["cityId"],
        "kind": "command-lease-token",
        "leaseId": lease_id,
        "state": contract["leaseState"],
        "authority": contract["authority"],
        "source": {
            "grantId": grant_id,
            "grantDigest": expected_grant_digest,
            "admissionId": admission.get(
                "admissionId"
            ),
            "admissionDigest": (
                "sha256:" + _sha256(admission)
            ),
        },
        "subject": copy.deepcopy(
            grant.get("subject")
        ),
        "command": {
            "commandType": command_type,
            "target": {
                "buildingId": (
                    target_building_id
                ),
                "capabilityId": (
                    target_capability_id
                ),
            },
            "arguments": arguments,
            "argumentsDigest": (
                "sha256:" + _sha256(arguments)
            ),
            "registrationMutation": (
                registration.mutation
            ),
        },
        "constraints": copy.deepcopy(
            contract["constraints"]
        ),
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
            "Prepare an exact read-only Bondik City "
            "command lease without dispatching it."
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
        CityDirectoryError,
        CityCommandLeaseError,
    ) as error:
        print(
            "Bondik City Relay Office ERROR: "
            f"{error}"
        )
        return 1

    print(
        "Bondik City Relay Office OK: "
        f"{lease['state']} / "
        "command=city.status.read / "
        "consumed=false / dispatched=false / "
        f"{LEASE_PROTOCOL}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
