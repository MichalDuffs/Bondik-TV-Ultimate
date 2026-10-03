# BTV-S01 — Relay Office v1

This is the thirtieth concrete Bondík City block.

The Relay Office narrows an admitted runtime grant to one exact registered
read-only command without dispatching that command.

The starter circuit remains open.

## Protocols

Lease contract:

    bondik-city-command-lease/1

Lease token:

    bondik-city-command-lease-token/1

Contract:

    config/city-command-lease-contract.json

Implementation:

    tools/city/command_lease.py

## Why this block exists

The Runtime Grant authorizes access to the local command boundary:

    operation = command
    capabilityId = city.command-boundary.local

That is intentionally broader than one specific registered command.

Before any future consumer can spend the grant, Relay Office narrows it to:

- one command type,
- one target building,
- one target capability,
- one JSON arguments object,
- one existing read-only command registration.

The target capability must also resolve as active in the current Service
Directory.

## Current demo lease

    city.status.read
        -> control-tower
        -> city.control-tower.status-board

The existing LocalCommandDispatcher is only inspected for registration
metadata. Relay Office does not call `dispatch()`.

## Lease state

Every v1 lease remains:

    state = prepared-unconsumed
    authority = scope-narrowing-only
    grantConsumed = false
    consumerConnected = false
    dispatchesCommand = false
    executesAction = false

The lease itself grants no new permission or runtime authority. It preserves
the source grant/admission digests and the SHA-256 digest of command arguments.

## Command Boundary extension

LocalCommandDispatcher gains a read-only `describe_registration()` method so
Relay Office can verify command metadata without touching a handler.

No execution behavior is widened.

## Verification

From repository root:

    py tools/city/command_lease.py
    py tools/city/service_directory.py
    py tools/city/visitor_guide.py
    py -m pytest tools/checker/tests/test_city_command_lease.py -q
    py -m pytest tools/checker/tests/test_city_command_boundary.py -q
    py -m pytest tools/checker/tests/test_city_service_directory.py -q
    py -m pytest tools/checker/tests/test_city_visitor_guide.py -q
    py -m pytest tools/checker/tests -q

Architecture rule:

**permission reaches the relay only after being narrowed to one known
read-only command, while dispatch remains physically absent from this layer.**
