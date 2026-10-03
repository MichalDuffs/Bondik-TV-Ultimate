# BTV-S01 — Visitor Guide v1

This is the twentieth concrete Bondík City block.

The Visitor Center answers one safe question:

> For this principal, which active discoverable city capabilities are currently
> allowed or denied for evidence inspection, and where do they live?

It composes two existing sources without taking authority from either:

- Gatehouse remains the source of access decisions.
- Directory Office remains the source of city location truth.

## Protocol

    bondik-city-visitor-guide/1

Contract:

    config/city-visitor-guide-contract.json

Builder:

    tools/city/visitor_guide.py

## v1 operation

v1 evaluates only:

    inspect-evidence

It does not generalize into command, mutation, handoff, or event authority.

## Output

The guide returns:

- principal id and role,
- allowed and denied capability lists,
- Gatehouse reason for each decision,
- exact city location when known,
- explicit grantsPermission = false.

Even an allowed guide entry is advisory. It does not grant permission and does
not execute anything.

## Safety boundary

The Visitor Guide does not:

- execute commands,
- publish events,
- mutate storage,
- start playback,
- contact devices,
- use the network,
- change Agent Safety policy.

## Verification

From repository root:

    py tools/city/visitor_guide.py
    py tools/city/service_directory.py
    py -m pytest tools/checker/tests/test_city_visitor_guide.py -q
    py -m pytest tools/checker/tests/test_city_service_directory.py -q
    py -m pytest tools/checker/tests -q

Architecture rule:

**the Visitor Center explains what the Gatehouse allows; it never becomes a
second Gatehouse.**
