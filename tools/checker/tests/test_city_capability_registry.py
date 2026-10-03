import json
from pathlib import Path

import pytest

from tools.city.validate_capability_registry import (
    CapabilityRegistryError,
    REGISTRY_PROTOCOL,
    REGISTRY_VERSION,
    load_capability_registry,
    validate_capability_registry,
)


ROOT = Path(__file__).resolve().parents[3]
REGISTRY_PATH = (
    ROOT
    / "config"
    / "city-capabilities.json"
)


def load_payload():
    return json.loads(
        REGISTRY_PATH.read_text(
            encoding="utf-8",
        )
    )


def test_checked_in_registry_is_valid():
    payload = load_capability_registry(
        REGISTRY_PATH
    )

    assert (
        payload["protocol"]
        == REGISTRY_PROTOCOL
    )
    assert (
        payload["version"]
        == REGISTRY_VERSION
    )


def test_capability_ids_are_unique():
    payload = load_payload()
    ids = [
        capability["id"]
        for capability
        in payload["capabilities"]
    ]

    assert len(ids) == len(set(ids))


def test_active_capabilities_have_surfaces():
    payload = load_payload()

    for capability in (
        payload["capabilities"]
    ):
        if (
            capability["status"]
            == "active"
        ):
            assert capability["surfaces"]


def test_v1_never_exposes_agent_execution():
    payload = load_payload()

    assert all(
        capability["agent"]["execution"]
        == "not-exposed"
        for capability
        in payload["capabilities"]
    )


def test_duplicate_capability_is_rejected():
    payload = load_payload()
    payload["capabilities"].append(
        dict(payload["capabilities"][0])
    )

    with pytest.raises(
        CapabilityRegistryError,
        match="duplicate capability id",
    ):
        validate_capability_registry(
            payload
        )


def test_unknown_protocol_is_rejected():
    payload = load_payload()
    payload["protocol"] = (
        "bondik-city-capability-registry/99"
    )

    with pytest.raises(
        CapabilityRegistryError,
        match="unsupported registry protocol",
    ):
        validate_capability_registry(
            payload
        )


def test_active_capability_without_surface_is_rejected():
    payload = load_payload()
    capability = next(
        item
        for item
        in payload["capabilities"]
        if item["status"] == "active"
    )
    capability["surfaces"] = []

    with pytest.raises(
        CapabilityRegistryError,
        match="must expose at least one surface",
    ):
        validate_capability_registry(
            payload
        )


def test_agent_execution_cannot_be_enabled_in_v1():
    payload = load_payload()
    payload["capabilities"][0][
        "agent"
    ]["execution"] = "allowed"

    with pytest.raises(
        CapabilityRegistryError,
        match="must remain not-exposed",
    ):
        validate_capability_registry(
            payload
        )
