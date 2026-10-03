from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

EVENT_PROTOCOL = "bondik-city-event/1"
EVENT_VERSION = 1
BUILDING_ID = "post-office"
MAX_PAYLOAD_BYTES = 65536

EVENT_ID_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"
)
EVENT_TYPE_RE = re.compile(
    r"^[a-z0-9]+(?:[.-][a-z0-9]+)+$"
)
BUILDING_ID_RE = re.compile(
    r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
)


class CityEventError(ValueError):
    pass


EventHandler = Callable[
    [dict[str, Any]],
    None,
]


@dataclass(frozen=True)
class DeliveryReport:
    event_id: str
    event_type: str
    delivered: int


def _validate_timestamp(value: Any) -> None:
    if not isinstance(value, str):
        raise CityEventError(
            "occurredAt must be a string"
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
        raise CityEventError(
            "occurredAt must be ISO-8601"
        ) from error

    if parsed.tzinfo is None:
        raise CityEventError(
            "occurredAt must include timezone"
        )


def _validate_payload(
    payload: Any,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise CityEventError(
            "payload must be an object"
        )

    try:
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (
        TypeError,
        ValueError,
    ) as error:
        raise CityEventError(
            "payload must be JSON serializable"
        ) from error

    if len(encoded) > MAX_PAYLOAD_BYTES:
        raise CityEventError(
            "payload exceeds size limit"
        )

    return payload


def validate_event(
    event: Any,
) -> dict[str, Any]:
    if not isinstance(event, dict):
        raise CityEventError(
            "event must be an object"
        )

    if event.get("protocol") != EVENT_PROTOCOL:
        raise CityEventError(
            "unsupported event protocol"
        )

    if event.get("version") != EVENT_VERSION:
        raise CityEventError(
            "unsupported event version"
        )

    if event.get("kind") != "event":
        raise CityEventError(
            "kind must be event"
        )

    event_id = event.get("eventId")

    if (
        not isinstance(event_id, str)
        or not EVENT_ID_RE.fullmatch(
            event_id
        )
    ):
        raise CityEventError(
            "eventId is invalid"
        )

    event_type = event.get("eventType")

    if (
        not isinstance(event_type, str)
        or not EVENT_TYPE_RE.fullmatch(
            event_type
        )
    ):
        raise CityEventError(
            "eventType is invalid"
        )

    source = event.get("source")

    if not isinstance(source, dict):
        raise CityEventError(
            "source must be an object"
        )

    building_id = source.get("buildingId")

    if (
        not isinstance(building_id, str)
        or not BUILDING_ID_RE.fullmatch(
            building_id
        )
    ):
        raise CityEventError(
            "source buildingId is invalid"
        )

    capability_id = source.get(
        "capabilityId"
    )

    if (
        capability_id is not None
        and (
            not isinstance(
                capability_id,
                str,
            )
            or not EVENT_TYPE_RE.fullmatch(
                capability_id
            )
        )
    ):
        raise CityEventError(
            "source capabilityId is invalid"
        )

    _validate_timestamp(
        event.get("occurredAt")
    )
    _validate_payload(
        event.get("payload")
    )

    safety = event.get("safety")

    if safety != {
        "execution": "not-exposed",
        "delivery": "local-in-process",
    }:
        raise CityEventError(
            "event safety contract is invalid"
        )

    return event


class LocalEventBus:
    def __init__(self) -> None:
        self._handlers: dict[
            str,
            list[EventHandler],
        ] = defaultdict(list)

    def subscribe(
        self,
        event_type: str,
        handler: EventHandler,
    ) -> None:
        if (
            event_type != "*"
            and not EVENT_TYPE_RE.fullmatch(
                event_type
            )
        ):
            raise CityEventError(
                "subscription event type "
                "is invalid"
            )

        if not callable(handler):
            raise CityEventError(
                "handler must be callable"
            )

        if handler in self._handlers[
            event_type
        ]:
            raise CityEventError(
                "handler already subscribed"
            )

        self._handlers[
            event_type
        ].append(handler)

    def unsubscribe(
        self,
        event_type: str,
        handler: EventHandler,
    ) -> bool:
        handlers = self._handlers.get(
            event_type
        )

        if (
            not handlers
            or handler not in handlers
        ):
            return False

        handlers.remove(handler)

        if not handlers:
            self._handlers.pop(
                event_type,
                None,
            )

        return True

    def publish(
        self,
        event: dict[str, Any],
    ) -> DeliveryReport:
        validated = validate_event(
            event
        )
        event_type = validated[
            "eventType"
        ]

        handlers = list(
            self._handlers.get(
                event_type,
                (),
            )
        ) + list(
            self._handlers.get(
                "*",
                (),
            )
        )

        for handler in handlers:
            handler(validated)

        return DeliveryReport(
            event_id=validated["eventId"],
            event_type=event_type,
            delivered=len(handlers),
        )


def _demo_event() -> dict[str, Any]:
    return {
        "protocol": EVENT_PROTOCOL,
        "version": EVENT_VERSION,
        "kind": "event",
        "eventId": "city-self-test-1",
        "eventType": "city.system.self-test",
        "occurredAt": (
            "2026-01-01T00:00:00Z"
        ),
        "source": {
            "buildingId": BUILDING_ID,
            "capabilityId": (
                "city.event-bus.local"
            ),
        },
        "payload": {
            "message": (
                "Bondik City event delivery "
                "self-test"
            )
        },
        "safety": {
            "execution": "not-exposed",
            "delivery": (
                "local-in-process"
            ),
        },
    }


def parse_arguments():
    parser = argparse.ArgumentParser(
        description=(
            "Run the Bondik City local "
            "Event Bus self-test."
        )
    )
    return parser.parse_args()


def main() -> int:
    parse_arguments()

    delivered = []
    bus = LocalEventBus()
    bus.subscribe(
        "city.system.self-test",
        delivered.append,
    )
    report = bus.publish(
        _demo_event()
    )

    if (
        report.delivered != 1
        or len(delivered) != 1
    ):
        print(
            "❌ Bondik City Event Bus "
            "self-test failed"
        )
        return 1

    print(
        "Bondik City Event Bus OK: "
        f"delivered {report.delivered} / "
        f"{EVENT_PROTOCOL}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
