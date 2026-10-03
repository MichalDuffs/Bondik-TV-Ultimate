# BTV-S01 — Dispatch Gate v1

This is the thirty-second concrete Bondík City block.

Dispatch Gate performs the final just-in-time preflight for an already prepared
authorized command packet.

It still does not dispatch the command.

## Protocols

Preflight contract:

    bondik-city-dispatch-preflight/1

Preflight record:

    bondik-city-dispatch-preflight-record/1

Contract:

    config/city-dispatch-preflight-contract.json

Implementation:

    tools/city/dispatch_preflight.py

## Final revalidation

Dispatch Gate rechecks the packet immediately before any future consumer could
be allowed to dispatch it:

- packet protocol and ready-not-dispatched state,
- packet id integrity,
- human-confirmed requester provenance,
- command arguments SHA-256,
- read-only/local-in-process command shape,
- current LocalCommandDispatcher registration,
- exact registration target,
- current active target in Service Directory.

This closes the registration/topology time-of-check gap between Relay Office,
Switchboard Office, and a future consumer.

## Preflight state

Every v1 preflight remains:

    state = validated-not-dispatched
    authority = final-preflight-only
    preflightPassed = true
    singleUseRequired = true
    grantConsumptionRequired = true
    grantConsumed = false
    consumerConnected = false
    dispatchesCommand = false
    executesAction = false

The preflight record itself grants no new permission or runtime authority.

## Non-goals

Dispatch Gate v1 does not:

- call LocalCommandDispatcher.dispatch(),
- call a command handler,
- consume the Runtime Grant,
- connect the Dispatch Office as a consumer,
- mutate Gatehouse policy,
- publish an event,
- perform a handoff,
- contact a device,
- use the network.

## Verification

From repository root:

    py tools/city/dispatch_preflight.py
    py tools/city/service_directory.py
    py tools/city/visitor_guide.py
    py -m pytest tools/checker/tests/test_city_dispatch_preflight.py -q
    py -m pytest tools/checker/tests/test_city_dispatch_packet.py -q
    py -m pytest tools/checker/tests/test_city_service_directory.py -q
    py -m pytest tools/checker/tests/test_city_visitor_guide.py -q
    py -m pytest tools/checker/tests -q

Architecture rule:

**the last check before dispatch must use the current registration and current
city topology, while the dispatch switch remains open.**
