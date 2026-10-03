from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.city.validate_capability_registry import (
    REGISTRY_PROTOCOL,
    load_capability_registry,
)

SIGNAL_PROTOCOL = "bondik-city-agent-signal/1"
SIGNAL_VERSION = 1

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SIGNAL_PATH = (
    ROOT / "config" / "city-signal.json"
)


class CitySignalError(ValueError):
    pass


def validate_city_signal(
    payload: Any,
    registry: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise CitySignalError(
            "signal root must be an object"
        )

    if payload.get("protocol") != SIGNAL_PROTOCOL:
        raise CitySignalError(
            "unsupported signal protocol"
        )

    if payload.get("version") != SIGNAL_VERSION:
        raise CitySignalError(
            "unsupported signal version"
        )

    city_id = payload.get("cityId")

    if city_id != registry.get("cityId"):
        raise CitySignalError(
            "signal cityId must match registry"
        )

    registry_ref = payload.get(
        "capabilityRegistry"
    )

    if not isinstance(registry_ref, dict):
        raise CitySignalError(
            "capabilityRegistry must be an object"
        )

    if (
        registry_ref.get("protocol")
        != REGISTRY_PROTOCOL
    ):
        raise CitySignalError(
            "signal registry protocol mismatch"
        )

    if (
        registry_ref.get("path")
        != "config/city-capabilities.json"
    ):
        raise CitySignalError(
            "signal registry path mismatch"
        )

    identity = payload.get("identity")

    if not isinstance(identity, dict):
        raise CitySignalError(
            "identity must be an object"
        )

    if identity.get("mode") != (
        "static-discovery-manifest"
    ):
        raise CitySignalError(
            "signal v1 must remain static discovery"
        )

    exposure = payload.get("exposure")

    if not isinstance(exposure, dict):
        raise CitySignalError(
            "exposure must be an object"
        )

    if exposure.get("discoverable") is not True:
        raise CitySignalError(
            "signal must be discoverable"
        )

    if (
        exposure.get("sensitiveState")
        != "not-exposed"
    ):
        raise CitySignalError(
            "sensitive state must remain not-exposed"
        )

    if (
        exposure.get("execution")
        != "not-exposed"
    ):
        raise CitySignalError(
            "execution must remain not-exposed"
        )

    if exposure.get("commandEndpoint") is not None:
        raise CitySignalError(
            "command endpoint must remain null"
        )

    handoff = payload.get("handoff")

    if not isinstance(handoff, dict):
        raise CitySignalError(
            "handoff must be an object"
        )

    if handoff.get("status") != "not-enabled":
        raise CitySignalError(
            "handoff must remain disabled in v1"
        )

    if (
        handoff.get("requiresPermission")
        is not True
    ):
        raise CitySignalError(
            "handoff must require permission"
        )

    return payload


def load_city_signal(
    signal_path: Path = DEFAULT_SIGNAL_PATH,
) -> dict[str, Any]:
    try:
        payload = json.loads(
            signal_path.read_text(
                encoding="utf-8",
            )
        )
    except (
        OSError,
        json.JSONDecodeError,
    ) as error:
        raise CitySignalError(
            f"cannot read signal: {error}"
        ) from error

    registry = load_capability_registry()

    return validate_city_signal(
        payload,
        registry,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the Bondik City "
            "static AI discovery signal."
        )
    )
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=DEFAULT_SIGNAL_PATH,
    )
    args = parser.parse_args()

    payload = load_city_signal(args.path)

    print(
        "Bondik City signal OK: "
        f"{payload['protocol']} / "
        f"{payload['identity']['mode']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
