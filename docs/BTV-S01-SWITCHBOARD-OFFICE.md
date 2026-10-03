# BTV-S01 — Switchboard Office v1

This is the thirty-first concrete Bondík City block.

The Switchboard Office takes the already-narrowed command lease and prepares a
fully bound authorized command packet.

It still does not call the Command Boundary dispatcher.

## Protocols

Switchboard contract:

    bondik-city-dispatch-packet/1

Authorized command packet:

    bondik-city-authorized-command-packet/1

Contract:

    config/city-dispatch-packet-contract.json

Implementation:

    tools/city/dispatch_packet.py

## Evidence chain

The packet is accepted only when all three source artifacts still agree:

- Runtime Grant,
- Starter Gate admission,
- Relay Office command lease.

Switchboard rechecks:

- grant id and SHA-256,
- admission id and SHA-256,
- lease id and SHA-256,
- lease subject against the grant subject,
- command arguments SHA-256,
- read-only registration mode,
- current active target capability in Service Directory.

## Request provenance

The packet explicitly records:

    requester.kind = human-confirmed-runtime-grant

plus:

- original grant subject,
- grant id,
- lease id,
- human confirmer id.

This avoids pretending that the packet came from the existing
`local-ui` Command Boundary requester shape.

## Packet state

Every v1 packet remains:

    state = ready-not-dispatched
    authority = dispatch-preparation-only
    grantConsumed = false
    consumerConnected = false
    dispatchesCommand = false
    executesAction = false

The packet itself grants no new permission or runtime authority.

## Non-goals

Switchboard Office v1 does not:

- call `LocalCommandDispatcher.dispatch()`,
- call a command handler,
- consume the runtime grant,
- connect the Dispatch Office as a consumer,
- mutate Gatehouse policy,
- publish an event,
- perform a handoff,
- contact a device,
- use the network.

## Verification

From repository root:

    py tools/city/dispatch_packet.py
    py tools/city/service_directory.py
    py tools/city/visitor_guide.py
    py -m pytest tools/checker/tests/test_city_dispatch_packet.py -q
    py -m pytest tools/checker/tests/test_city_command_lease.py -q
    py -m pytest tools/checker/tests/test_city_service_directory.py -q
    py -m pytest tools/checker/tests/test_city_visitor_guide.py -q
    py -m pytest tools/checker/tests -q

Architecture rule:

**the command may be fully prepared and cryptographically bound before any
dispatcher is allowed to touch it.**
