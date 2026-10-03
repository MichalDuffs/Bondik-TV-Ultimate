from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.city.media_contract import (
    MEDIA_SOURCE_PROTOCOL,
    CityMediaError,
    load_catalog,
    load_contract as load_media_contract,
    resolve_media_source,
)

ADAPTER_PROTOCOL = (
    "bondik-city-device-share-adapter/1"
)
HANDOFF_PROTOCOL = (
    "bondik-city-device-handoff/1"
)
VERSION = 1

DEFAULT_CONTRACT_PATH = (
    ROOT
    / "config"
    / "city-device-share-contract.json"
)

TARGET_ID_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"
)


class CityDeviceShareError(ValueError):
    pass


def _load_json(
    path: Path,
    *,
    label: str,
) -> Any:
    try:
        return json.loads(
            path.read_text(
                encoding="utf-8-sig"
            )
        )
    except OSError as error:
        raise CityDeviceShareError(
            f"cannot read {label}: {error}"
        ) from error
    except json.JSONDecodeError as error:
        raise CityDeviceShareError(
            f"{label} must be valid JSON"
        ) from error


def load_contract(
    path: Path = DEFAULT_CONTRACT_PATH,
) -> dict[str, Any]:
    payload = _load_json(
        path,
        label="device share contract",
    )

    if not isinstance(payload, dict):
        raise CityDeviceShareError(
            "device share contract root "
            "must be an object"
        )

    if payload.get("protocol") != (
        ADAPTER_PROTOCOL
    ):
        raise CityDeviceShareError(
            "unsupported device share protocol"
        )

    if payload.get("version") != VERSION:
        raise CityDeviceShareError(
            "unsupported device share version"
        )

    if payload.get("cityId") != "bondik-city":
        raise CityDeviceShareError(
            "device share cityId mismatch"
        )

    if payload.get("handoffProtocol") != (
        HANDOFF_PROTOCOL
    ):
        raise CityDeviceShareError(
            "handoff protocol mismatch"
        )

    if payload.get("sourceProtocol") != (
        MEDIA_SOURCE_PROTOCOL
    ):
        raise CityDeviceShareError(
            "source protocol mismatch"
        )

    if payload.get("supportedTargetKinds") != [
        "android-tv"
    ]:
        raise CityDeviceShareError(
            "device share v1 supports "
            "android-tv only"
        )

    if payload.get("deliveryState") != (
        "prepared"
    ):
        raise CityDeviceShareError(
            "delivery state must be prepared"
        )

    if payload.get("transport") != (
        "not-selected"
    ):
        raise CityDeviceShareError(
            "transport must remain not-selected"
        )

    if payload.get("endpoint") != (
        "not-exposed"
    ):
        raise CityDeviceShareError(
            "endpoint must remain not-exposed"
        )

    if payload.get("exposure") != {
        "network": "not-exposed",
        "execution": "not-exposed",
        "agentExecution": "not-exposed",
        "mutation": "not-allowed",
    }:
        raise CityDeviceShareError(
            "device share exposure contract "
            "invalid"
        )

    return payload


def _validate_timestamp(
    value: Any,
) -> str:
    if not isinstance(value, str):
        raise CityDeviceShareError(
            "requestedAt must be a string"
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
        raise CityDeviceShareError(
            "requestedAt must be ISO-8601"
        ) from error

    if parsed.tzinfo is None:
        raise CityDeviceShareError(
            "requestedAt must include timezone"
        )

    return value


def _validate_target(
    target: Any,
    *,
    contract: dict[str, Any],
) -> dict[str, str]:
    if not isinstance(target, dict):
        raise CityDeviceShareError(
            "target must be an object"
        )

    allowed_keys = {
        "targetId",
        "kind",
        "displayName",
    }

    if set(target) - allowed_keys:
        raise CityDeviceShareError(
            "target contains unsupported fields"
        )

    target_id = target.get("targetId")

    if (
        not isinstance(target_id, str)
        or not TARGET_ID_RE.fullmatch(
            target_id
        )
    ):
        raise CityDeviceShareError(
            "targetId is invalid"
        )

    kind = target.get("kind")

    if kind not in contract[
        "supportedTargetKinds"
    ]:
        raise CityDeviceShareError(
            "target kind is not supported"
        )

    display_name = target.get(
        "displayName"
    )

    if (
        not isinstance(
            display_name,
            str,
        )
        or not display_name.strip()
    ):
        raise CityDeviceShareError(
            "target displayName must be "
            "a non-empty string"
        )

    return {
        "targetId": target_id,
        "kind": kind,
        "displayName": display_name,
    }


def prepare_handoff(
    channel_id: str,
    *,
    target: dict[str, Any],
    requested_at: str,
    contract: dict[str, Any] | None = None,
    media_contract: dict[str, Any] | None = None,
    catalog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    contract = (
        contract
        if contract is not None
        else load_contract()
    )
    target = _validate_target(
        target,
        contract=contract,
    )
    requested_at = _validate_timestamp(
        requested_at
    )

    if media_contract is None:
        media_contract = (
            load_media_contract()
        )

    if catalog is None:
        catalog = load_catalog()

    try:
        source = resolve_media_source(
            channel_id,
            catalog=catalog,
            contract=media_contract,
        )
    except CityMediaError as error:
        raise CityDeviceShareError(
            str(error)
        ) from error

    return {
        "protocol": HANDOFF_PROTOCOL,
        "version": VERSION,
        "kind": "device-handoff",
        "handoffId": (
            f"{channel_id}:{target['targetId']}"
        ),
        "requestedAt": requested_at,
        "source": copy.deepcopy(source),
        "target": target,
        "delivery": {
            "state": contract[
                "deliveryState"
            ],
            "transport": contract[
                "transport"
            ],
            "endpoint": None,
        },
        "exposure": copy.deepcopy(
            contract["exposure"]
        ),
    }


def parse_arguments():
    parser = argparse.ArgumentParser(
        description=(
            "Prepare a non-delivered Bondik "
            "City device handoff envelope."
        )
    )
    parser.add_argument(
        "--channel-id",
        default="polar-tv-cz",
    )
    parser.add_argument(
        "--target-id",
        default="demo-tv",
    )
    parser.add_argument(
        "--target-name",
        default="Demo Android TV",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()

    try:
        handoff = prepare_handoff(
            args.channel_id,
            target={
                "targetId": args.target_id,
                "kind": "android-tv",
                "displayName": (
                    args.target_name
                ),
            },
            requested_at=(
                "2026-01-01T00:00:00Z"
            ),
        )
    except CityDeviceShareError as error:
        print(
            "❌ Bondik City Device Share: "
            f"{error}"
        )
        return 1

    print(
        "Bondik City Device Share OK: "
        f"{handoff['source']['sourceId']} -> "
        f"{handoff['target']['targetId']} / "
        f"{handoff['delivery']['state']} / "
        f"{HANDOFF_PROTOCOL}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
