import copy
from pathlib import Path
import subprocess
import sys

import pytest

from tools.city.event_bus import (
    EVENT_PROTOCOL,
    CityEventError,
    LocalEventBus,
    validate_event,
)


ROOT = Path(__file__).resolve().parents[3]


def event():
    return {
        "protocol": EVENT_PROTOCOL,
        "version": 1,
        "kind": "event",
        "eventId": "evt-001",
        "eventType": "city.health.changed",
        "occurredAt": (
            "2026-10-03T17:00:00+02:00"
        ),
        "source": {
            "buildingId": "control-tower",
            "capabilityId": (
                "city.control-tower."
                "health-snapshot"
            ),
        },
        "payload": {
            "status": "degraded",
        },
        "safety": {
            "execution": "not-exposed",
            "delivery": "local-in-process",
        },
    }


def test_exact_subscriber_receives_event():
    bus = LocalEventBus()
    received = []

    bus.subscribe(
        "city.health.changed",
        received.append,
    )
    report = bus.publish(event())

    assert report.delivered == 1
    assert received == [event()]


def test_unrelated_subscriber_is_not_called():
    bus = LocalEventBus()
    received = []

    bus.subscribe(
        "city.github.changed",
        received.append,
    )
    report = bus.publish(event())

    assert report.delivered == 0
    assert received == []


def test_wildcard_subscriber_observes_event():
    bus = LocalEventBus()
    received = []

    bus.subscribe("*", received.append)
    report = bus.publish(event())

    assert report.delivered == 1
    assert received[0]["eventId"] == "evt-001"


def test_unsubscribe_stops_delivery():
    bus = LocalEventBus()
    received = []

    bus.subscribe(
        "city.health.changed",
        received.append,
    )
    assert bus.unsubscribe(
        "city.health.changed",
        received.append,
    ) is True

    report = bus.publish(event())

    assert report.delivered == 0
    assert received == []


def test_duplicate_subscription_is_rejected():
    bus = LocalEventBus()

    def handler(_event):
        pass

    bus.subscribe(
        "city.health.changed",
        handler,
    )

    with pytest.raises(
        CityEventError,
        match="already subscribed",
    ):
        bus.subscribe(
            "city.health.changed",
            handler,
        )


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (
            ("protocol",),
            "other/1",
            "unsupported event protocol",
        ),
        (
            ("eventType",),
            "bad type",
            "eventType is invalid",
        ),
        (
            ("occurredAt",),
            "2026-10-03T17:00:00",
            "include timezone",
        ),
        (
            ("payload",),
            [],
            "payload must be an object",
        ),
        (
            ("safety", "execution"),
            "allowed",
            "safety contract",
        ),
    ],
)
def test_invalid_event_is_rejected(
    path,
    value,
    message,
):
    payload = copy.deepcopy(event())
    target = payload

    for key in path[:-1]:
        target = target[key]

    target[path[-1]] = value

    with pytest.raises(
        CityEventError,
        match=message,
    ):
        validate_event(payload)


def test_handler_failure_is_not_hidden():
    bus = LocalEventBus()

    def broken(_event):
        raise RuntimeError("boom")

    bus.subscribe(
        "city.health.changed",
        broken,
    )

    with pytest.raises(
        RuntimeError,
        match="boom",
    ):
        bus.publish(event())


def test_direct_cli_runs_self_test():
    result = subprocess.run(
        [
            sys.executable,
            str(
                ROOT
                / "tools"
                / "city"
                / "event_bus.py"
            ),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout
    assert (
        "Bondik City Event Bus OK: "
        "delivered 1 / "
        "bondik-city-event/1"
        in result.stdout
    )
