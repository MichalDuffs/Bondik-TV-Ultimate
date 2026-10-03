# BTV-S01 — Event Bus Foundation v1

This is the eleventh concrete Bondík City block.

The Post Office gives city modules a shared event boundary without wiring one
building directly into another.

## Protocol

    bondik-city-event/1

Implementation:

    tools/city/event_bus.py

v1 is deliberately local and in-process. It does not create a socket, server,
queue broker, webhook, background worker, or autonomous command surface.

## Event envelope

Every event is a versioned JSON-compatible object with:

- protocol and version,
- kind = event,
- eventId,
- namespaced eventType,
- occurredAt with timezone,
- source buildingId and optional capabilityId,
- bounded JSON payload,
- fixed safety contract.

The v1 safety contract is:

    execution = not-exposed
    delivery = local-in-process

Payload size is bounded to 64 KiB.

## Delivery

LocalEventBus supports:

- exact event-type subscriptions,
- one wildcard observer subscription namespace using *,
- explicit unsubscribe,
- synchronous deterministic delivery.

Handler failures are not swallowed. A failing consumer remains visible to the
caller instead of creating a false successful delivery report.

## Scope boundary

This block does not yet provide:

- persistent queues,
- retries,
- cross-process delivery,
- network transport,
- commands,
- automatic repair,
- agent execution,
- Radio Station broadcast.

Those require separate protocols and permission boundaries.

## Verification

From repository root:

    py tools/city/event_bus.py
    py -m pytest tools/checker/tests/test_city_event_bus.py -q
    py -m pytest tools/checker/tests -q

Architecture rule:

**buildings publish facts; consumers decide what to do with them later.**
