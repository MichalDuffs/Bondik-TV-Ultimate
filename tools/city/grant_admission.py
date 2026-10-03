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

ADMISSION_CONTRACT_PROTOCOL = (
    "bondik-city-grant-admission/1"
)
ADMISSION_PROTOCOL = (
    "bondik-city-grant-admission-record/1"
)
VERSION = 1

DEFAULT_CONTRACT_PATH = (
    ROOT
    / "config"
    / "city-grant-admission-contract.json"
)


class CityGrantAdmissionError(ValueError):
    pass


def _load_json(path: Path, *, label: str) -> Any:
    try:
        return json.loads(
            path.read_text(encoding="utf-8-sig")
        )
    except OSError as error:
        raise CityGrantAdmissionError(
            f"cannot read {label}: {error}"
        ) from error
    except json.JSONDecodeError as error:
        raise CityGrantAdmissionError(
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
        raise CityGrantAdmissionError(
            "grant value must be JSON serializable"
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
        label="grant admission contract",
    )

    expected = {
        "protocol": ADMISSION_CONTRACT_PROTOCOL,
        "version": VERSION,
        "cityId": "bondik-city",
        "grantProtocol": GRANT_PROTOCOL,
        "directoryProtocol": DIRECTORY_PROTOCOL,
        "admissionProtocol": ADMISSION_PROTOCOL,
        "authority": "admission-only",
        "admissionState": "admitted-not-consumed",
        "exposure": {
            "execution": "not-exposed",
            "mutation": "not-allowed",
            "network": "not-exposed",
            "permissionGrant": "not-allowed",
            "policyMutation": "not-allowed",
        },
    }

    if not isinstance(payload, dict):
        raise CityGrantAdmissionError(
            "grant admission contract root "
            "must be an object"
        )

    for key, value in expected.items():
        if payload.get(key) != value:
            raise CityGrantAdmissionError(
                f"grant admission contract "
                f"field invalid: {key}"
            )

    return payload


def _resolve_capability_location(
    directory: dict[str, Any],
    capability_id: str,
) -> dict[str, Any]:
    if directory.get("protocol") != DIRECTORY_PROTOCOL:
        raise CityGrantAdmissionError(
            "directory protocol mismatch"
        )

    matches = []

    for location in directory.get(
        "locations",
        [],
    ):
        for capability in location.get(
            "capabilities",
            [],
        ):
            if capability.get("id") == capability_id:
                matches.append(
                    (
                        location,
                        capability,
                    )
                )

    if len(matches) != 1:
        raise CityGrantAdmissionError(
            "grant capability must resolve exactly once"
        )

    location, capability = matches[0]

    if capability.get("status") != "active":
        raise CityGrantAdmissionError(
            "grant capability must be active"
        )

    return {
        "locationId": location.get("id"),
        "locationName": location.get("name"),
        "locationRole": location.get("role"),
        "capabilityStatus": capability.get(
            "status"
        ),
    }


def admit_runtime_grant(
    grant: Any,
    *,
    consumer_id: Any,
    directory: dict[str, Any] | None = None,
    contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    contract = (
        contract
        if contract is not None
        else load_contract()
    )

    if not isinstance(grant, dict):
        raise CityGrantAdmissionError(
            "grant must be an object"
        )

    if grant.get("protocol") != (
        contract["grantProtocol"]
    ):
        raise CityGrantAdmissionError(
            "grant protocol mismatch"
        )

    if grant.get("state") != "issued-unconsumed":
        raise CityGrantAdmissionError(
            "grant must be issued-unconsumed"
        )

    if grant.get("grantsPermission") is not True:
        raise CityGrantAdmissionError(
            "grant must carry permission"
        )

    if grant.get("runtimeAuthority") is not True:
        raise CityGrantAdmissionError(
            "grant must carry runtime authority"
        )

    if grant.get("consumed") is not False:
        raise CityGrantAdmissionError(
            "grant must be unconsumed"
        )

    if grant.get("executesAction") is not False:
        raise CityGrantAdmissionError(
            "grant must not execute action"
        )

    if grant.get("activatesPolicy") is not False:
        raise CityGrantAdmissionError(
            "grant must not activate policy"
        )

    if grant.get("mutatesPolicy") is not False:
        raise CityGrantAdmissionError(
            "grant must not mutate policy"
        )

    if grant.get("consumerConnected") is not False:
        raise CityGrantAdmissionError(
            "grant must not already have a consumer"
        )

    if grant.get("constraints") != {
        "singleUse": True,
        "localOnly": True,
        "consumerConnected": False,
    }:
        raise CityGrantAdmissionError(
            "grant constraints invalid"
        )

    grant_id = grant.get("grantId")
    subject = grant.get("subject")
    scope = grant.get("scope")

    if (
        not isinstance(grant_id, str)
        or not grant_id
        or not isinstance(subject, dict)
        or not isinstance(scope, dict)
    ):
        raise CityGrantAdmissionError(
            "grant identity or scope invalid"
        )

    operation = scope.get("operation")
    capability_id = scope.get("capabilityId")

    if (
        not isinstance(operation, str)
        or not operation
        or not isinstance(
            capability_id,
            str,
        )
        or not capability_id
    ):
        raise CityGrantAdmissionError(
            "grant scope invalid"
        )

    if (
        not isinstance(consumer_id, str)
        or not consumer_id
    ):
        raise CityGrantAdmissionError(
            "consumerId is invalid"
        )

    directory = (
        directory
        if directory is not None
        else build_directory()
    )

    target = _resolve_capability_location(
        directory,
        capability_id,
    )

    if target["locationId"] != consumer_id:
        raise CityGrantAdmissionError(
            "consumer does not own grant capability"
        )

    admission_id = (
        "admit-"
        + hashlib.sha256(
            (
                grant_id
                + "|"
                + consumer_id
            ).encode("utf-8")
        ).hexdigest()[:24]
    )

    return {
        "protocol": ADMISSION_PROTOCOL,
        "version": VERSION,
        "cityId": contract["cityId"],
        "kind": "runtime-grant-admission",
        "admissionId": admission_id,
        "state": contract[
            "admissionState"
        ],
        "authority": contract["authority"],
        "consumer": {
            "id": consumer_id,
            "connected": False,
        },
        "subject": copy.deepcopy(subject),
        "scope": copy.deepcopy(scope),
        "target": copy.deepcopy(target),
        "evidence": {
            "grantId": grant_id,
            "grantDigest": (
                "sha256:" + _sha256(grant)
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


def main() -> int:
    argparse.ArgumentParser(
        description=(
            "Admit an exact-scope Bondik City "
            "runtime grant to its local capability "
            "owner without connecting or consuming it."
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
    except (
        CityPermitError,
        CityReviewError,
        CityAuditError,
        CitySealError,
        CityKeyVaultError,
        CityIgnitionError,
        CityActivationConfirmationError,
        CityRuntimeGrantError,
        CityDirectoryError,
        CityGrantAdmissionError,
    ) as error:
        print(
            "Bondik City Starter Gate ERROR: "
            f"{error}"
        )
        return 1

    print(
        "Bondik City Starter Gate OK: "
        f"{admission['state']} / "
        "consumer=dispatch-office / "
        "consumed=false / executed=false / "
        f"{ADMISSION_PROTOCOL}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
