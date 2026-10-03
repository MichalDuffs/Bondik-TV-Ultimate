# BTV-S01 — Result Window v1

This is the thirty-sixth concrete Bondík City block.

K35 can return verified command result content to one named local human.
K36 adds a narrower presentation boundary before that content is shown as a
human-readable result card.

## Protocols

Result view contract:

    bondik-city-result-view/1

Rendered result card:

    bondik-city-result-card/1

Contract:

    config/city-result-view-contract.json

Implementation:

    tools/city/result_view.py

## Narrow v1 display allowlist

K36 does not display arbitrary command results.

Version 1 accepts only:

    city.status.read

with the exact source target:

    control-tower
    city.control-tower.status-board

and the exact result shape:

    {"status": "available"}

Extra result keys, unknown commands, different targets, a different mutation
mode, a different transport, or an unapproved status value fail closed.

## Human-local boundary

The source K35 envelope must still say:

    kind = human-local
    viewerId = the same named viewer
    agentReadable = false

K36 never upgrades that audience. The card remains local-human only and agent
result content remains not-exposed.

## Safety

Every card remains:

    state = rendered-local
    authority = presentation-only
    grantsPermission = false
    runtimeAuthority = false
    dispatchesCommand = false
    executesAction = false
    mutatesPolicy = false
    publishesEvent = false
    performsHandoff = false
    usesNetwork = false

K36 does not execute a command, consume a grant, alter evidence, publish an
event, or persist result content.

## Verification

From repository root:

    py tools/city/result_view.py
    py tools/city/service_directory.py
    py tools/city/visitor_guide.py
    py -m pytest tools/checker/tests/test_city_result_view.py -q
    py -m pytest tools/checker/tests/test_city_result_return.py -q
    py -m pytest tools/checker/tests -q

Architecture rule:

**verified result content crosses into presentation only through an explicit
command-specific allowlist, and v1 remains named-human-local only.**
