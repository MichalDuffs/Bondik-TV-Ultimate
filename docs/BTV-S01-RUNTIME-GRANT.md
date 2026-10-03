# BTV-S01 — Grant Office v1

This is the twenty-eighth concrete Bondík City block.

For the first time in the chain, a fully human-confirmed activation can produce
an exact-scope **runtime grant token**.

The token is still not connected to any executor.

## Protocols

Grant contract:

    bondik-city-runtime-grant/1

Grant token:

    bondik-city-runtime-grant-token/1

Contract:

    config/city-runtime-grant-contract.json

Implementation:

    tools/city/runtime_grant.py

## Required evidence

Grant Office requires both:

- the original `bondik-city-activation-intent/1`,
- the matching `bondik-city-activation-confirmation/1`.

It verifies:

- exact intent id linkage,
- SHA-256 digest of the full intent,
- exact subject match,
- exact operation + capability scope match,
- human confirmer identity,
- both source records still state no runtime authority and no execution.

## Grant state

Every v1 token is:

    state = issued-unconsumed
    authority = grant-issuer
    grantsPermission = true
    runtimeAuthority = true
    consumed = false
    executesAction = false
    activatesPolicy = false
    mutatesPolicy = false
    consumerConnected = false

The grant is exact-scope, local-only, and marked single-use.

This is the first permission-bearing artifact, but there is deliberately no
consumer wired to it yet.

## Non-goals

Grant Office v1 does not:

- execute the requested command,
- mutate Gatehouse policy,
- publish an event,
- consume the token,
- perform a handoff,
- contact a device,
- use the network.

## Verification

From repository root:

    py tools/city/runtime_grant.py
    py tools/city/service_directory.py
    py tools/city/visitor_guide.py
    py -m pytest tools/checker/tests/test_city_runtime_grant.py -q
    py -m pytest tools/checker/tests/test_city_service_directory.py -q
    py -m pytest tools/checker/tests/test_city_visitor_guide.py -q
    py -m pytest tools/checker/tests -q

Architecture rule:

**a human-confirmed grant may carry authority before any executor is allowed to
consume it.**
