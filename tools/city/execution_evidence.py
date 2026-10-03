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

from tools.city.authorized_dispatch import (
    RECEIPT_PROTOCOL,
    CityAuthorizedDispatchError,
    _build_demo_sources,
    execute_authorized_read_only,
)
from tools.city.storage_adapter import (
    CityStorageError,
    MemoryStorageAdapter,
)

EVIDENCE_CONTRACT_PROTOCOL = (
    "bondik-city-execution-evidence/1"
)
EVIDENCE_PROTOCOL = (
    "bondik-city-execution-evidence-record/1"
)
VERSION = 1

DEFAULT_CONTRACT_PATH = (
    ROOT
    / "config"
    / "city-execution-evidence-contract.json"
)


class CityExecutionEvidenceError(ValueError):
    pass


def _load_json(path: Path, *, label: str) -> Any:
    try:
        return json.loads(
            path.read_text(encoding="utf-8-sig")
        )
    except OSError as error:
        raise CityExecutionEvidenceError(
            f"cannot read {label}: {error}"
        ) from error
    except json.JSONDecodeError as error:
        raise CityExecutionEvidenceError(
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
        raise CityExecutionEvidenceError(
            "evidence value must be JSON serializable"
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
        label="execution evidence contract",
    )

    expected = {
        "protocol": EVIDENCE_CONTRACT_PROTOCOL,
        "version": VERSION,
        "cityId": "bondik-city",
        "receiptProtocol": RECEIPT_PROTOCOL,
        "storageNamespace": (
            "city.dispatch.spent"
        ),
        "evidenceProtocol": EVIDENCE_PROTOCOL,
        "authority": "evidence-only",
        "evidenceState": "verified-completed",
        "exposure": {
            "execution": "not-exposed",
            "mutation": "not-allowed",
            "network": "not-exposed",
            "permissionGrant": "not-allowed",
            "resultContent": "digest-only",
        },
    }

    if not isinstance(payload, dict):
        raise CityExecutionEvidenceError(
            "execution evidence contract root "
            "must be an object"
        )

    for key, value in expected.items():
        if payload.get(key) != value:
            raise CityExecutionEvidenceError(
                f"execution evidence contract "
                f"field invalid: {key}"
            )

    return payload


def _validate_storage(storage: Any) -> None:
    if (
        storage is None
        or not callable(
            getattr(storage, "read", None)
        )
    ):
        raise CityExecutionEvidenceError(
            "storage adapter is invalid"
        )


def build_execution_evidence(
    receipt: Any,
    *,
    storage: Any,
    contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    contract = (
        contract
        if contract is not None
        else load_contract()
    )

    if not isinstance(receipt, dict):
        raise CityExecutionEvidenceError(
            "receipt must be an object"
        )

    _validate_storage(storage)

    if receipt.get("protocol") != (
        contract["receiptProtocol"]
    ):
        raise CityExecutionEvidenceError(
            "receipt protocol mismatch"
        )

    if receipt.get("state") != (
        "dispatched-consumed"
    ):
        raise CityExecutionEvidenceError(
            "receipt must be dispatched-consumed"
        )

    if receipt.get("authority") != (
        "exact-read-only-executor"
    ):
        raise CityExecutionEvidenceError(
            "receipt authority mismatch"
        )

    if receipt.get("singleUse") is not True:
        raise CityExecutionEvidenceError(
            "receipt must be single-use"
        )

    for field in (
        "grantConsumed",
        "consumerConnected",
        "dispatchesCommand",
        "executesAction",
    ):
        if receipt.get(field) is not True:
            raise CityExecutionEvidenceError(
                f"receipt completion field invalid: {field}"
            )

    for field in (
        "mutatesPolicy",
        "publishesEvent",
        "performsHandoff",
        "usesNetwork",
    ):
        if receipt.get(field) is not False:
            raise CityExecutionEvidenceError(
                f"receipt safety field invalid: {field}"
            )

    grant = receipt.get("grant")
    packet = receipt.get("packet")
    preflight = receipt.get("preflight")
    command = receipt.get("command")

    if not isinstance(grant, dict):
        raise CityExecutionEvidenceError(
            "receipt grant evidence invalid"
        )
    if not isinstance(packet, dict):
        raise CityExecutionEvidenceError(
            "receipt packet evidence invalid"
        )
    if not isinstance(preflight, dict):
        raise CityExecutionEvidenceError(
            "receipt preflight evidence invalid"
        )
    if not isinstance(command, dict):
        raise CityExecutionEvidenceError(
            "receipt command evidence invalid"
        )

    if grant.get("sourceArtifactConsumed") is not False:
        raise CityExecutionEvidenceError(
            "source grant artifact must remain immutable"
        )
    if grant.get("consumptionRecorded") is not True:
        raise CityExecutionEvidenceError(
            "receipt consumption must be recorded"
        )
    if grant.get("consumptionNamespace") != (
        contract["storageNamespace"]
    ):
        raise CityExecutionEvidenceError(
            "receipt consumption namespace mismatch"
        )

    revision = grant.get(
        "consumptionRevision"
    )
    grant_id = grant.get("grantId")

    if (
        not isinstance(revision, int)
        or revision < 2
        or not isinstance(grant_id, str)
        or not grant_id
    ):
        raise CityExecutionEvidenceError(
            "receipt consumption identity invalid"
        )

    if command.get("mutation") != "read-only":
        raise CityExecutionEvidenceError(
            "receipt command must be read-only"
        )
    if command.get("transport") != (
        "local-in-process"
    ):
        raise CityExecutionEvidenceError(
            "receipt command must be local-in-process"
        )

    result = command.get("result")
    result_digest = command.get(
        "resultDigest"
    )

    if not isinstance(result, dict):
        raise CityExecutionEvidenceError(
            "receipt result must be an object"
        )

    expected_result_digest = (
        "sha256:" + _sha256(result)
    )

    if result_digest != expected_result_digest:
        raise CityExecutionEvidenceError(
            "receipt result digest mismatch"
        )

    try:
        stored = storage.read(
            contract["storageNamespace"],
            grant_id,
        )
    except CityStorageError as error:
        raise CityExecutionEvidenceError(
            f"cannot read consumption record: {error}"
        ) from error

    if stored is None:
        raise CityExecutionEvidenceError(
            "consumption record is missing"
        )

    if stored.get("revision") != revision:
        raise CityExecutionEvidenceError(
            "consumption revision mismatch"
        )

    value = stored.get("value")

    if not isinstance(value, dict):
        raise CityExecutionEvidenceError(
            "consumption record value invalid"
        )

    expected_pairs = {
        "protocol": RECEIPT_PROTOCOL,
        "kind": "dispatch-consumption-claim",
        "state": "dispatched-consumed",
        "grantId": grant_id,
        "packetId": packet.get("packetId"),
        "packetDigest": packet.get(
            "packetDigest"
        ),
        "preflightId": preflight.get(
            "preflightId"
        ),
        "preflightDigest": preflight.get(
            "preflightDigest"
        ),
        "commandId": command.get(
            "commandId"
        ),
        "executedAt": receipt.get(
            "executedAt"
        ),
        "resultDigest": expected_result_digest,
    }

    for key, expected in expected_pairs.items():
        if value.get(key) != expected:
            raise CityExecutionEvidenceError(
                f"consumption evidence mismatch: {key}"
            )

    receipt_id = receipt.get("receiptId")

    if (
        not isinstance(receipt_id, str)
        or not receipt_id
    ):
        raise CityExecutionEvidenceError(
            "receiptId is invalid"
        )

    evidence_id = (
        "evidence-"
        + hashlib.sha256(
            (
                receipt_id
                + "|"
                + str(revision)
                + "|"
                + expected_result_digest
            ).encode("utf-8")
        ).hexdigest()[:24]
    )

    return {
        "protocol": EVIDENCE_PROTOCOL,
        "version": VERSION,
        "cityId": contract["cityId"],
        "kind": "execution-evidence",
        "evidenceId": evidence_id,
        "state": contract["evidenceState"],
        "authority": contract["authority"],
        "receipt": {
            "receiptId": receipt_id,
            "receiptDigest": (
                "sha256:" + _sha256(receipt)
            ),
            "executedAt": receipt.get(
                "executedAt"
            ),
        },
        "grant": {
            "grantId": grant_id,
            "consumptionNamespace": (
                contract["storageNamespace"]
            ),
            "consumptionRevision": revision,
            "consumptionState": (
                "dispatched-consumed"
            ),
        },
        "command": {
            "commandId": command.get(
                "commandId"
            ),
            "commandType": command.get(
                "commandType"
            ),
            "targetBuildingId": command.get(
                "targetBuildingId"
            ),
            "targetCapabilityId": command.get(
                "targetCapabilityId"
            ),
            "mutation": "read-only",
            "transport": "local-in-process",
            "resultDigest": (
                expected_result_digest
            ),
            "resultContent": "not-copied",
        },
        "verification": {
            "receiptMatchesStorage": True,
            "resultDigestVerified": True,
            "singleUseConsumptionVerified": True,
        },
        "grantsPermission": False,
        "runtimeAuthority": False,
        "dispatchesCommand": False,
        "executesAction": False,
        "mutatesPolicy": False,
        "publishesEvent": False,
        "performsHandoff": False,
        "usesNetwork": False,
        "exposure": copy.deepcopy(
            contract["exposure"]
        ),
    }


def _demo() -> tuple[
    dict[str, Any],
    MemoryStorageAdapter,
]:
    grant, packet, preflight, dispatcher = (
        _build_demo_sources()
    )
    storage = MemoryStorageAdapter()
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
    return receipt, storage


def main() -> int:
    argparse.ArgumentParser(
        description=(
            "Verify one completed Bondik City "
            "read-only dispatch against the "
            "single-use consumption ledger."
        )
    ).parse_args()

    try:
        receipt, storage = _demo()
        evidence = build_execution_evidence(
            receipt,
            storage=storage,
        )
    except (
        CityAuthorizedDispatchError,
        CityStorageError,
        CityExecutionEvidenceError,
    ) as error:
        print(
            "Bondik City Receipt Office ERROR: "
            f"{error}"
        )
        return 1

    print(
        "Bondik City Receipt Office OK: "
        f"{evidence['state']} / "
        "command=city.status.read / "
        "receipt-storage=true / result-digest=true / "
        f"{EVIDENCE_PROTOCOL}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
