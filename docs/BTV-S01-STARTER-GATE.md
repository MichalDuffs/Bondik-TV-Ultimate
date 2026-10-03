# BTV-S01 — Starter Gate v1

This is the twenty-ninth concrete Bondík City block.

The Starter Gate validates a permission-bearing runtime grant against the live
descriptive city directory and admits it only to the location that owns the
exact capability named by the grant.

It still does not connect a consumer, consume the grant, or execute anything.

## Protocols

Admission contract:

    bondik-city-grant-admission/1

Admission record:

    bondik-city-grant-admission-record/1

Contract:

    config/city-grant-admission-contract.json

Implementation:

    tools/city/grant_admission.py

## Required grant state

The source must remain:

    protocol = bondik-city-runtime-grant-token/1
    state = issued-unconsumed
    grantsPermission = true
    runtimeAuthority = true
    consumed = false
    executesAction = false
    activatesPolicy = false
    mutatesPolicy = false
    consumerConnected = false

Its constraints must still be:

    singleUse = true
    localOnly = true
    consumerConnected = false

## Capability ownership check

The grant's exact capability is resolved through:

    bondik-city-service-directory/1

The requested consumer id must match the unique active location that owns that
capability. A mismatch or missing/duplicate capability fails closed.

For the current demo grant:

    city.command-boundary.local -> dispatch-office

## Admission state

Every v1 admission remains:

    state = admitted-not-consumed
    authority = admission-only
    grantsPermission = false
    runtimeAuthority = false
    grantConsumed = false
    consumerConnected = false
    dispatchesCommand = false
    executesAction = false

The admission record preserves the source grant id and a SHA-256 digest of the
full grant.

## Non-goals

Starter Gate v1 does not:

- connect the Dispatch Office as an executor,
- consume the grant,
- dispatch a command,
- mutate Gatehouse policy,
- publish an event,
- perform a handoff,
- contact a device,
- use the network.

## Verification

From repository root:

    py tools/city/grant_admission.py
    py tools/city/service_directory.py
    py tools/city/visitor_guide.py
    py -m pytest tools/checker/tests/test_city_grant_admission.py -q
    py -m pytest tools/checker/tests/test_city_service_directory.py -q
    py -m pytest tools/checker/tests/test_city_visitor_guide.py -q
    py -m pytest tools/checker/tests -q

Architecture rule:

**the key can pass the starter gate only when its exact capability owner is
known, while the starter circuit remains open.**
