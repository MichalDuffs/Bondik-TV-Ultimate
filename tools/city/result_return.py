from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.city.authorized_dispatch import (
    RECEIPT_PROTOCOL,
    CityAuthorizedDispatchError,
)
from tools.city.command_boundary import MAX_RESULT_BYTES
from tools.city.execution_evidence import (
    EVIDENCE_PROTOCOL,
    CityExecutionEvidenceError,
    _demo as evidence_demo,
    build_execution_evidence,
)

RESULT_RETURN_CONTRACT_PROTOCOL = "bondik-city-result-return/1"
RESULT_PROTOCOL = "bondik-city-verified-result-envelope/1"
VERSION = 1

DEFAULT_CONTRACT_PATH = (
    ROOT / "config" / "city-result-return-contract.json"
)

VIEWER_ID_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"
)


class CityResultReturnError(ValueError):
    pass


def _load_json(path: Path, *, label: str) -> Any:
    try:
        return json.loads(
            path.read_text(encoding="utf-8-sig")
        )
    except OSError as error:
        raise CityResultReturnError(
            f"cannot read {label}: {error}"
        ) from error
    except json.JSONDecodeError as error:
        raise CityResultReturnError(
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
        raise CityResultReturnError(
            "result value must be JSON serializable"
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
        label="result return contract",
    )

    expected = {
        "protocol": RESULT_RETURN_CONTRACT_PROTOCOL,
        "version": VERSION,
        "cityId": "bondik-city",
        "receiptProtocol": RECEIPT_PROTOCOL,
        "evidenceProtocol": EVIDENCE_PROTOCOL,
        "resultProtocol": RESULT_PROTOCOL,
        "authority": "human-local-result-return-only",
        "resultState": "verified-result-ready",
        "audience": {
            "kind": "human-local",
            "agentReadable": False,
        },
        "exposure": {
            "execution": "not-exposed",
            "mutation": "not-allowed",
            "network": "not-exposed",
            "permissionGrant": "not-allowed",
            "agentResult": "not-exposed",
        },
    }

    if not isinstance(payload, dict):
        raise CityResultReturnError(
            "result return contract root must be an object"
        )

    for key, value in expected.items():
        if payload.get(key) != value:
            raise CityResultReturnError(
                f"result return contract field invalid: {key}"
            )

    return payload


def prepare_verified_result(
    receipt: Any,
    evidence: Any,
    *,
    viewer_id: Any,
    contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    contract = (
        contract
        if contract is not None
        else load_contract()
    )

    if not isinstance(receipt, dict):
        raise CityResultReturnError(
            "receipt must be an object"
        )
    if not isinstance(evidence, dict):
        raise CityResultReturnError(
            "evidence must be an object"
        )

    if (
        not isinstance(viewer_id, str)
        or not VIEWER_ID_RE.fullmatch(viewer_id)
    ):
        raise CityResultReturnError(
            "viewerId is invalid"
        )

    if receipt.get("protocol") != contract["receiptProtocol"]:
        raise CityResultReturnError(
            "receipt protocol mismatch"
        )
    if evidence.get("protocol") != contract["evidenceProtocol"]:
        raise CityResultReturnError(
            "evidence protocol mismatch"
        )

    if receipt.get("state") != "dispatched-consumed":
        raise CityResultReturnError(
            "receipt must be dispatched-consumed"
        )
    if evidence.get("state") != "verified-completed":
        raise CityResultReturnError(
            "evidence must be verified-completed"
        )
    if evidence.get("authority") != "evidence-only":
        raise CityResultReturnError(
            "evidence authority mismatch"
        )

    for field in (
        "grantConsumed",
        "consumerConnected",
        "dispatchesCommand",
        "executesAction",
    ):
        if receipt.get(field) is not True:
            raise CityResultReturnError(
                f"receipt completion field invalid: {field}"
            )

    for field in (
        "mutatesPolicy",
        "publishesEvent",
        "performsHandoff",
        "usesNetwork",
    ):
        if receipt.get(field) is not False:
            raise CityResultReturnError(
                f"receipt safety field invalid: {field}"
            )

    for field in (
        "grantsPermission",
        "runtimeAuthority",
        "dispatchesCommand",
        "executesAction",
        "mutatesPolicy",
        "publishesEvent",
        "performsHandoff",
        "usesNetwork",
    ):
        if evidence.get(field) is not False:
            raise CityResultReturnError(
                f"evidence safety field invalid: {field}"
            )

    receipt_ref = evidence.get("receipt")
    evidence_command = evidence.get("command")
    receipt_command = receipt.get("command")

    if not isinstance(receipt_ref, dict):
        raise CityResultReturnError(
            "evidence receipt reference invalid"
        )
    if not isinstance(evidence_command, dict):
        raise CityResultReturnError(
            "evidence command reference invalid"
        )
    if not isinstance(receipt_command, dict):
        raise CityResultReturnError(
            "receipt command invalid"
        )

    receipt_id = receipt.get("receiptId")
    evidence_id = evidence.get("evidenceId")

    if (
        not isinstance(receipt_id, str)
        or not receipt_id
        or not isinstance(evidence_id, str)
        or not evidence_id
    ):
        raise CityResultReturnError(
            "result source identities invalid"
        )

    expected_receipt_digest = "sha256:" + _sha256(receipt)

    if receipt_ref.get("receiptId") != receipt_id:
        raise CityResultReturnError(
            "evidence receiptId mismatch"
        )
    if receipt_ref.get("receiptDigest") != expected_receipt_digest:
        raise CityResultReturnError(
            "evidence receipt digest mismatch"
        )

    if evidence_command.get("resultContent") != "not-copied":
        raise CityResultReturnError(
            "evidence result content marker invalid"
        )

    result = receipt_command.get("result")

    if not isinstance(result, dict):
        raise CityResultReturnError(
            "receipt result must be an object"
        )

    encoded_result = _canonical_bytes(result)

    if len(encoded_result) > MAX_RESULT_BYTES:
        raise CityResultReturnError(
            "receipt result exceeds size limit"
        )

    expected_result_digest = "sha256:" + _sha256(result)

    if receipt_command.get("resultDigest") != expected_result_digest:
        raise CityResultReturnError(
            "receipt result digest mismatch"
        )
    if evidence_command.get("resultDigest") != expected_result_digest:
        raise CityResultReturnError(
            "evidence result digest mismatch"
        )

    exact_fields = (
        "commandId",
        "commandType",
        "targetBuildingId",
        "targetCapabilityId",
        "mutation",
        "transport",
    )

    for field in exact_fields:
        if evidence_command.get(field) != receipt_command.get(field):
            raise CityResultReturnError(
                f"command evidence mismatch: {field}"
            )

    if receipt_command.get("mutation") != "read-only":
        raise CityResultReturnError(
            "result source must be read-only"
        )
    if receipt_command.get("transport") != "local-in-process":
        raise CityResultReturnError(
            "result source must be local-in-process"
        )

    verification = evidence.get("verification")

    if verification != {
        "receiptMatchesStorage": True,
        "resultDigestVerified": True,
        "singleUseConsumptionVerified": True,
    }:
        raise CityResultReturnError(
            "execution evidence verification invalid"
        )

    result_id = (
        "result-"
        + hashlib.sha256(
            (
                evidence_id
                + "|"
                + receipt_id
                + "|"
                + viewer_id
                + "|"
                + expected_result_digest
            ).encode("utf-8")
        ).hexdigest()[:24]
    )

    return {
        "protocol": RESULT_PROTOCOL,
        "version": VERSION,
        "cityId": contract["cityId"],
        "kind": "verified-result-envelope",
        "resultId": result_id,
        "state": contract["resultState"],
        "authority": contract["authority"],
        "audience": {
            "kind": "human-local",
            "viewerId": viewer_id,
            "agentReadable": False,
        },
        "source": {
            "receiptId": receipt_id,
            "receiptDigest": expected_receipt_digest,
            "evidenceId": evidence_id,
            "evidenceDigest": "sha256:" + _sha256(evidence),
        },
        "command": {
            "commandId": receipt_command.get("commandId"),
            "commandType": receipt_command.get("commandType"),
            "targetBuildingId": receipt_command.get(
                "targetBuildingId"
            ),
            "targetCapabilityId": receipt_command.get(
                "targetCapabilityId"
            ),
            "mutation": "read-only",
            "transport": "local-in-process",
        },
        "result": copy.deepcopy(result),
        "resultDigest": expected_result_digest,
        "verified": True,
        "grantsPermission": False,
        "runtimeAuthority": False,
        "dispatchesCommand": False,
        "executesAction": False,
        "mutatesPolicy": False,
        "publishesEvent": False,
        "performsHandoff": False,
        "usesNetwork": False,
        "exposure": copy.deepcopy(contract["exposure"]),
    }


def _demo() -> dict[str, Any]:
    receipt, storage = evidence_demo()
    evidence = build_execution_evidence(
        receipt,
        storage=storage,
    )

    return prepare_verified_result(
        receipt,
        evidence,
        viewer_id="demo-human",
    )


def main() -> int:
    argparse.ArgumentParser(
        description=(
            "Prepare a verified local human result envelope "
            "from completed Bondik City execution evidence."
        )
    ).parse_args()

    try:
        result = _demo()
    except (
        CityAuthorizedDispatchError,
        CityExecutionEvidenceError,
        CityResultReturnError,
    ) as error:
        print(
            "Bondik City Result Office ERROR: "
            f"{error}"
        )
        return 1

    print(
        "Bondik City Result Office OK: "
        f"{result['state']} / "
        "command=city.status.read / "
        "viewer=demo-human / "
        "result=available / "
        f"{RESULT_PROTOCOL}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
