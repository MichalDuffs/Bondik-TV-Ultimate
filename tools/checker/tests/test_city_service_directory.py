import copy
import subprocess
import sys
from pathlib import Path

import pytest

from tools.city.service_directory import (
    CityDirectoryError,
    build_directory,
    load_contract,
    load_registry,
)


ROOT = Path(__file__).resolve().parents[3]


def locations_by_id(directory):
    return {
        item["id"]: item
        for item in directory["locations"]
    }


def test_current_directory_summary():
    directory = build_directory()

    assert directory["summary"] == {
        "locations": 33,
        "activeCapabilities": 37,
        "plannedCapabilities": 0,
    }


def test_archive_combines_building_and_virtual_area():
    archive = locations_by_id(
        build_directory()
    )["archive"]

    assert archive["sources"] == [
        "building",
        "virtual-area",
    ]
    assert archive["virtualMapping"] == (
        "artifacts-history-backups"
    )


def test_control_tower_is_virtual_location():
    tower = locations_by_id(
        build_directory()
    )["control-tower"]

    assert tower["sources"] == [
        "virtual-area"
    ]
    assert tower["virtualMapping"] == (
        "ci-qc-health-review"
    )


def test_directory_office_maps_own_capability():
    office = locations_by_id(
        build_directory()
    )["directory-office"]

    assert [
        item["id"]
        for item in office["capabilities"]
    ] == [
        "city.directory.service-map"
    ]


def test_radio_station_maps_both_active_signals():
    station = locations_by_id(
        build_directory()
    )["radio-station"]

    assert {
        item["id"]
        for item in station["capabilities"]
    } == {
        "city.discovery-manifest",
        "radio-station.agent-signal",
    }
    assert all(
        item["status"] == "active"
        for item in station["capabilities"]
    )


def test_every_registry_capability_appears_once():
    directory = build_directory()
    registry = load_registry()

    directory_ids = [
        capability["id"]
        for location in directory["locations"]
        for capability in location["capabilities"]
    ]
    registry_ids = [
        item["id"]
        for item in registry["capabilities"]
    ]

    assert sorted(directory_ids) == sorted(
        registry_ids
    )
    assert len(directory_ids) == len(
        set(directory_ids)
    )


def test_unknown_location_fails_closed():
    registry = load_registry()
    broken = copy.deepcopy(registry)
    broken["capabilities"][0][
        "buildingId"
    ] = "missing-place"

    with pytest.raises(
        CityDirectoryError,
        match="unknown location",
    ):
        build_directory(
            registry=broken
        )


def test_duplicate_capability_fails_closed():
    registry = load_registry()
    broken = copy.deepcopy(registry)
    broken["capabilities"].append(
        copy.deepcopy(
            broken["capabilities"][0]
        )
    )

    with pytest.raises(
        CityDirectoryError,
        match="duplicate capability id",
    ):
        build_directory(
            registry=broken
        )


def test_contract_is_descriptive_only():
    contract = load_contract()

    assert contract["authority"] == (
        "descriptive-only"
    )
    assert contract["exposure"] == {
        "execution": "not-exposed",
        "mutation": "not-allowed",
        "network": "not-exposed",
    }


def test_direct_cli_builds_directory():
    result = subprocess.run(
        [
            sys.executable,
            str(
                ROOT
                / "tools"
                / "city"
                / "service_directory.py"
            ),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout
    assert (
        "Bondik City Directory OK: "
        "33 locations / 37 active / "
        "0 planned / "
        "bondik-city-service-directory/1"
        in result.stdout
    )
