# BTV-S01 — Permit Office v1

This is the twenty-first concrete Bondík City block.

The Permit Office creates a review ticket when a future high-impact action needs
human attention.

It does not approve the action.

## Protocol

    bondik-city-permit-request/1

Contract:

    config/city-permit-request-contract.json

Builder:

    tools/city/permit_office.py

## v1 requestable operations

- command
- handoff
- mutate
- publish-event
- execute

These operations remain denied by the current Agent Safety policy.

The Permit Office records that current policy decision instead of bypassing it.

## Ticket state

Every v1 ticket is:

    status = pending-human-review
    authority = request-only
    grantsPermission = false

The ticket includes:

- principal,
- requested operation,
- target capability,
- human-readable reason,
- requested timestamp,
- current Gatehouse decision,
- resolved city location when known,
- empty human review decision.

## Not included

v1 does not:

- approve tickets,
- change Agent Safety policy,
- grant permissions,
- execute commands,
- publish events,
- mutate storage,
- perform handoffs,
- contact devices,
- use the network.

## Verification

From repository root:

    py tools/city/permit_office.py
    py tools/city/service_directory.py
    py tools/city/visitor_guide.py
    py -m pytest tools/checker/tests/test_city_permit_office.py -q
    py -m pytest tools/checker/tests/test_city_service_directory.py -q
    py -m pytest tools/checker/tests/test_city_visitor_guide.py -q
    py -m pytest tools/checker/tests -q

Architecture rule:

**a request for permission is not permission.**
