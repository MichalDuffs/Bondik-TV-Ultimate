# BTV-S01 — Review Board v1

This is the twenty-second concrete Bondík City block.

The Review Board records a human decision on a Permit Office ticket.

It does not apply that decision to the Agent Safety policy and it does not
execute the requested action.

## Protocol

    bondik-city-human-review/1

Contract:

    config/city-human-review-contract.json

Recorder:

    tools/city/review_board.py

## Supported human decisions

- approve
- deny
- needs-info

Every v1 decision has:

    authority = record-only
    effect = recorded-only
    grantsPermission = false
    changesPolicy = false
    executesAction = false

This is deliberate.

A human can record "approve" without silently converting that review into
runtime authority.

## Input boundary

The Review Board accepts only:

- bondik-city-permit-request/1 tickets,
- status = pending-human-review,
- tickets that already state grantsPermission = false.

The original Permit Office ticket is not mutated.

## Preserved evidence

The review record carries forward:

- ticket id,
- original request,
- current Gatehouse policy decision,
- resolved city route,
- reviewer id,
- decision,
- timestamp,
- optional note.

## Not included

v1 does not:

- grant permission,
- alter Gatehouse policy,
- execute a command,
- publish an event,
- mutate storage,
- perform a handoff,
- contact a device,
- use the network.

## Verification

From repository root:

    py tools/city/review_board.py
    py tools/city/service_directory.py
    py tools/city/visitor_guide.py
    py -m pytest tools/checker/tests/test_city_review_board.py -q
    py -m pytest tools/checker/tests/test_city_service_directory.py -q
    py -m pytest tools/checker/tests/test_city_visitor_guide.py -q
    py -m pytest tools/checker/tests -q

Architecture rule:

**human approval may be recorded before it is ever allowed to become runtime
authority.**
