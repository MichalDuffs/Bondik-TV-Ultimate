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

from tools.city.result_return import (
    RESULT_PROTOCOL,
    CityResultReturnError,
    _demo as result_return_demo,
)

RESULT_VIEW_CONTRACT_PROTOCOL = "bondik-city-result-view/1"
RESULT_CARD_PROTOCOL = "bondik-city-result-card/1"
VERSION = 1

DEFAULT_CONTRACT_PATH = (
    ROOT / "config" / "city-result-view-contract.json"
)

VIEWER_ID_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"
)
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class CityResultViewError(ValueError):
    pass


def _load_json(path: Path, *, label: str) -> Any:
    try:
        return json.loads(
            path.read_text(encoding="utf-8-sig")
        )
    except OSError as error:
        raise CityResultViewError(
            f"cannot read {label}: {error}"
        ) from error
    except json.JSONDecodeError as error:
        raise CityResultViewError(
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
        raise CityResultViewError(
            "result view value must be JSON serializable"
        ) from error


def _sha256(value: Any) -> str:
    return hashlib.sha256(
        _canonical_bytes(value)
    ).hexdigest()


def _validate_digest(value: Any, *, label: str) -> str:
    if (
        not isinstance(value, str)
        or not SHA256_RE.fullmatch(value)
    ):
        raise CityResultViewError(
            f"{label} digest is invalid"
        )
    return value


def load_contract(
    path: Path = DEFAULT_CONTRACT_PATH,
) -> dict[str, Any]:
    payload = _load_json(
        path,
        label="result view contract",
    )

    expected = {
        "protocol": RESULT_VIEW_CONTRACT_PROTOCOL,
        "version": VERSION,
        "cityId": "bondik-city",
        "inputProtocol": RESULT_PROTOCOL,
        "cardProtocol": RESULT_CARD_PROTOCOL,
        "authority": "presentation-only",
        "inputAuthority": "human-local-result-return-only",
        "inputState": "verified-result-ready",
        "cardState": "rendered-local",
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
        raise CityResultViewError(
            "result view contract root must be an object"
        )

    for key, value in expected.items():
        if payload.get(key) != value:
            raise CityResultViewError(
                f"result view contract field invalid: {key}"
            )

    allowed = payload.get("allowedCommands")
    if not isinstance(allowed, dict):
        raise CityResultViewError(
            "result view allowedCommands invalid"
        )

    if set(allowed) != {"city.status.read"}:
        raise CityResultViewError(
            "result view v1 command allowlist invalid"
        )

    command = allowed["city.status.read"]
    expected_command = {
        "targetBuildingId": "control-tower",
        "targetCapabilityId": (
            "city.control-tower.status-board"
        ),
        "mutation": "read-only",
        "transport": "local-in-process",
        "allowedResultKeys": ["status"],
        "allowedStatusValues": ["available"],
    }

    if command != expected_command:
        raise CityResultViewError(
            "result view command contract invalid"
        )

    return payload


def build_result_card(
    envelope: Any,
    *,
    viewer_id: Any,
    contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    contract = (
        contract
        if contract is not None
        else load_contract()
    )

    if not isinstance(envelope, dict):
        raise CityResultViewError(
            "result envelope must be an object"
        )

    if (
        not isinstance(viewer_id, str)
        or not VIEWER_ID_RE.fullmatch(viewer_id)
    ):
        raise CityResultViewError(
            "viewerId is invalid"
        )

    if envelope.get("protocol") != contract["inputProtocol"]:
        raise CityResultViewError(
            "result envelope protocol mismatch"
        )
    if envelope.get("version") != VERSION:
        raise CityResultViewError(
            "result envelope version mismatch"
        )
    if envelope.get("cityId") != contract["cityId"]:
        raise CityResultViewError(
            "result envelope cityId mismatch"
        )
    if envelope.get("state") != contract["inputState"]:
        raise CityResultViewError(
            "result envelope state mismatch"
        )
    if envelope.get("authority") != contract["inputAuthority"]:
        raise CityResultViewError(
            "result envelope authority mismatch"
        )
    if envelope.get("verified") is not True:
        raise CityResultViewError(
            "result envelope must be verified"
        )

    audience = envelope.get("audience")
    if not isinstance(audience, dict):
        raise CityResultViewError(
            "result envelope audience invalid"
        )
    if audience.get("kind") != "human-local":
        raise CityResultViewError(
            "result envelope audience kind mismatch"
        )
    if audience.get("agentReadable") is not False:
        raise CityResultViewError(
            "result envelope must remain non-agent-readable"
        )
    if audience.get("viewerId") != viewer_id:
        raise CityResultViewError(
            "viewerId does not match result envelope"
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
        if envelope.get(field) is not False:
            raise CityResultViewError(
                f"unsafe result envelope field: {field}"
            )

    exposure = envelope.get("exposure")
    if exposure != contract["exposure"]:
        raise CityResultViewError(
            "result envelope exposure mismatch"
        )

    result_id = envelope.get("resultId")
    if (
        not isinstance(result_id, str)
        or not result_id
    ):
        raise CityResultViewError(
            "resultId is invalid"
        )

    source = envelope.get("source")
    if not isinstance(source, dict):
        raise CityResultViewError(
            "result source is invalid"
        )

    for identity_field in (
        "receiptId",
        "evidenceId",
    ):
        value = source.get(identity_field)
        if (
            not isinstance(value, str)
            or not value
        ):
            raise CityResultViewError(
                f"result source {identity_field} invalid"
            )

    _validate_digest(
        source.get("receiptDigest"),
        label="receipt",
    )
    _validate_digest(
        source.get("evidenceDigest"),
        label="evidence",
    )

    command = envelope.get("command")
    if not isinstance(command, dict):
        raise CityResultViewError(
            "result command is invalid"
        )

    command_type = command.get("commandType")
    allowed = contract["allowedCommands"].get(
        command_type
    )
    if allowed is None:
        raise CityResultViewError(
            "result command is not presentation-allowed"
        )

    expected_command = {
        "targetBuildingId": allowed["targetBuildingId"],
        "targetCapabilityId": allowed[
            "targetCapabilityId"
        ],
        "mutation": allowed["mutation"],
        "transport": allowed["transport"],
    }

    for field, expected_value in expected_command.items():
        if command.get(field) != expected_value:
            raise CityResultViewError(
                f"result command {field} mismatch"
            )

    command_id = command.get("commandId")
    if (
        not isinstance(command_id, str)
        or not command_id
    ):
        raise CityResultViewError(
            "result commandId is invalid"
        )

    result = envelope.get("result")
    if not isinstance(result, dict):
        raise CityResultViewError(
            "result content must be an object"
        )

    if list(result.keys()) != allowed["allowedResultKeys"]:
        raise CityResultViewError(
            "result content keys are not presentation-allowed"
        )

    status = result.get("status")
    if status not in allowed["allowedStatusValues"]:
        raise CityResultViewError(
            "result status is not presentation-allowed"
        )

    expected_result_digest = (
        "sha256:" + _sha256(result)
    )
    if envelope.get("resultDigest") != expected_result_digest:
        raise CityResultViewError(
            "result digest mismatch"
        )

    card_id = (
        "result-card-"
        + hashlib.sha256(
            (
                result_id
                + "|"
                + viewer_id
                + "|"
                + expected_result_digest
            ).encode("utf-8")
        ).hexdigest()[:24]
    )

    return {
        "protocol": RESULT_CARD_PROTOCOL,
        "version": VERSION,
        "cityId": contract["cityId"],
        "kind": "result-card",
        "cardId": card_id,
        "state": contract["cardState"],
        "authority": contract["authority"],
        "audience": {
            "kind": "human-local",
            "viewerId": viewer_id,
            "agentReadable": False,
        },
        "source": {
            "resultId": result_id,
            "resultDigest": expected_result_digest,
            "receiptId": source["receiptId"],
            "evidenceId": source["evidenceId"],
        },
        "command": {
            "commandId": command_id,
            "commandType": command_type,
            "targetBuildingId": command[
                "targetBuildingId"
            ],
            "targetCapabilityId": command[
                "targetCapabilityId"
            ],
        },
        "display": {
            "label": "Control Tower status",
            "value": status,
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


def _demo() -> dict[str, Any]:
    envelope = result_return_demo()

    return build_result_card(
        envelope,
        viewer_id="demo-human",
    )


def main() -> int:
    argparse.ArgumentParser(
        description=(
            "Render one verified Bondik City result "
            "as a bounded local human result card."
        )
    ).parse_args()

    try:
        card = _demo()
    except (
        CityResultReturnError,
        CityResultViewError,
    ) as error:
        print(
            "Bondik City Result Window ERROR: "
            f"{error}"
        )
        return 1

    print(
        "Bondik City Result Window OK: "
        f"{card['state']} / "
        "viewer=demo-human / "
        "city.status.read=available / "
        f"{RESULT_CARD_PROTOCOL}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
