from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

DIRECTORY_PROTOCOL = "bondik-city-service-directory/1"
VERSION = 1

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "config" / "city-service-directory-contract.json"
FOUNDATION_PATH = ROOT / "config" / "city-foundation.yaml"
REGISTRY_PATH = ROOT / "config" / "city-capabilities.json"


class CityDirectoryError(ValueError):
    pass


def _json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        raise CityDirectoryError(str(error)) from error


def _yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    except (OSError, yaml.YAMLError) as error:
        raise CityDirectoryError(str(error)) from error


def load_contract() -> dict[str, Any]:
    value = _json(CONTRACT_PATH)
    if not isinstance(value, dict):
        raise CityDirectoryError("contract must be an object")
    if value.get("protocol") != DIRECTORY_PROTOCOL:
        raise CityDirectoryError("unsupported directory protocol")
    if value.get("version") != VERSION:
        raise CityDirectoryError("unsupported directory version")
    if value.get("cityId") != "bondik-city":
        raise CityDirectoryError("directory cityId mismatch")
    if value.get("authority") != "descriptive-only":
        raise CityDirectoryError("directory authority must be descriptive-only")
    if value.get("exposure") != {
        "execution": "not-exposed",
        "mutation": "not-allowed",
        "network": "not-exposed",
    }:
        raise CityDirectoryError("directory exposure contract invalid")
    return value


def load_foundation() -> dict[str, Any]:
    value = _yaml(FOUNDATION_PATH)
    if not isinstance(value, dict):
        raise CityDirectoryError("foundation must be an object")
    if value.get("city", {}).get("id") != "bondik-city":
        raise CityDirectoryError("foundation cityId mismatch")
    return value


def load_registry() -> dict[str, Any]:
    value = _json(REGISTRY_PATH)
    if not isinstance(value, dict):
        raise CityDirectoryError("registry must be an object")
    if value.get("cityId") != "bondik-city":
        raise CityDirectoryError("registry cityId mismatch")
    if not isinstance(value.get("capabilities"), list):
        raise CityDirectoryError("capabilities must be a list")
    return value


def build_directory(
    foundation: dict[str, Any] | None = None,
    registry: dict[str, Any] | None = None,
    contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    foundation = foundation or load_foundation()
    registry = registry or load_registry()
    contract = contract or load_contract()

    locations: dict[str, dict[str, Any]] = {}

    for building in foundation.get("buildings", []):
        if not isinstance(building, dict) or not isinstance(building.get("id"), str):
            raise CityDirectoryError("invalid building entry")
        location_id = building["id"]
        if location_id in locations:
            raise CityDirectoryError("duplicate location id")
        locations[location_id] = {
            "id": location_id,
            "name": building.get("name", location_id),
            "status": building.get("status"),
            "role": building.get("role"),
            "sources": ["building"],
            "virtualMapping": None,
            "capabilities": [],
        }

    for area in foundation.get("virtual_areas", []):
        if not isinstance(area, dict) or not isinstance(area.get("id"), str):
            raise CityDirectoryError("invalid virtual area entry")
        location_id = area["id"]
        if location_id not in locations:
            locations[location_id] = {
                "id": location_id,
                "name": location_id,
                "status": area.get("status"),
                "role": None,
                "sources": ["virtual-area"],
                "virtualMapping": area.get("maps_to"),
                "capabilities": [],
            }
        else:
            locations[location_id]["sources"].append("virtual-area")
            locations[location_id]["virtualMapping"] = area.get("maps_to")

    seen: set[str] = set()
    active = 0
    planned = 0

    for capability in registry["capabilities"]:
        capability_id = capability.get("id")
        location_id = capability.get("buildingId")
        status = capability.get("status")

        if not isinstance(capability_id, str):
            raise CityDirectoryError("invalid capability id")
        if capability_id in seen:
            raise CityDirectoryError("duplicate capability id")
        seen.add(capability_id)

        if status not in {"active", "planned"}:
            raise CityDirectoryError("unsupported capability status")
        if location_id not in locations:
            raise CityDirectoryError("capability references unknown location")

        locations[location_id]["capabilities"].append(
            {
                "id": capability_id,
                "status": status,
                "surfaces": capability.get("surfaces", []),
                "discoverable": capability.get("agent", {}).get("discoverable"),
                "execution": capability.get("agent", {}).get("execution"),
            }
        )

        if status == "active":
            active += 1
        else:
            planned += 1

    output = []
    for location_id in sorted(locations):
        item = locations[location_id]
        item["capabilities"].sort(key=lambda entry: entry["id"])
        output.append(item)

    return {
        "protocol": DIRECTORY_PROTOCOL,
        "version": VERSION,
        "cityId": contract["cityId"],
        "kind": "service-directory",
        "authority": contract["authority"],
        "summary": {
            "locations": len(output),
            "activeCapabilities": active,
            "plannedCapabilities": planned,
        },
        "locations": output,
        "exposure": contract["exposure"],
    }


def main() -> int:
    argparse.ArgumentParser(
        description="Build the Bondik City descriptive service directory."
    ).parse_args()

    try:
        directory = build_directory()
    except CityDirectoryError as error:
        print(f"Bondik City Directory ERROR: {error}")
        return 1

    summary = directory["summary"]
    print(
        "Bondik City Directory OK: "
        f"{summary['locations']} locations / "
        f"{summary['activeCapabilities']} active / "
        f"{summary['plannedCapabilities']} planned / "
        f"{DIRECTORY_PROTOCOL}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
