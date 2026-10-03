# BTV-S01 — Command Boundary Foundation v1

This is the twelfth concrete Bondík City block.

The Dispatch Office gives local UI code a single explicit command boundary
instead of allowing views to call arbitrary actions directly.

## Protocol

    bondik-city-command/1

Implementation:

    tools/city/command_boundary.py

v1 is deliberately local, in-process, explicitly registered, and read-only.

## Command envelope

Every command carries:

- protocol and version,
- kind = command,
- commandId,
- namespaced commandType,
- timezone-aware requestedAt,
- requester = local-ui,
- explicit target buildingId and capabilityId,
- bounded JSON arguments,
- fixed safety contract.

The v1 safety contract is:

    authorization = explicit-registration
    agentExecution = not-exposed
    mutation = read-only
    transport = local-in-process

Arguments and handler results are each limited to 64 KiB of JSON.

## Dispatcher

LocalCommandDispatcher requires every command type to be registered with an
exact building and capability target before dispatch.

v1 rejects:

- unregistered command types,
- target mismatches,
- duplicate registrations,
- mutating registrations,
- agent-originated commands,
- invalid envelopes,
- non-object command results.

Handler failures are not swallowed.

## Event Bus relationship

The Event Bus carries facts that happened.

The Command Boundary carries explicit requests to a known local capability.

v1 does not automatically turn commands into events and does not let events
execute commands. That bridge can be added later as a separate reviewed slice.

## Scope boundary

This block does not provide:

- network commands,
- GitHub writes,
- merge actions,
- persistent queues,
- retries,
- agent command authority,
- autonomous repair,
- Radio Station command transport.

## Verification

From repository root:

    py tools/city/command_boundary.py
    py -m pytest tools/checker/tests/test_city_command_boundary.py -q
    py -m pytest tools/checker/tests -q

Architecture rule:

**commands are explicit requests; events are observations. Keep them separate.**
