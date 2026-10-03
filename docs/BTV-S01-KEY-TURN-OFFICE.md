# BTV-S01 — Key Turn Office v1

This is the twenty-seventh concrete Bondík City block.

The Key Turn Office records an explicit human confirmation of one already
prepared activation intent.

It still does not activate anything.

## Protocol

    bondik-city-activation-confirmation/1

Contract:

    config/city-activation-confirmation-contract.json

Implementation:

    tools/city/activation_confirmation.py

## Input requirements

The source must be a valid:

    bondik-city-activation-intent/1

with:

    state = prepared-not-active
    runtimeAuthority = false
    grantsPermission = false
    activatesPolicy = false
    executesAction = false

The human confirmer must echo the exact `intentId` being confirmed. A mismatch
fails closed.

## Confirmation record

Every confirmation records:

- named human confirmer,
- timezone-aware confirmedAt,
- human-readable reason,
- exact subject,
- exact operation + capability scope,
- source intent id,
- SHA-256 digest of the full source intent,
- original intent actor and preparedAt.

Every v1 confirmation remains:

    state = confirmed-not-active
    authority = confirmation-only
    runtimeAuthority = false
    grantsPermission = false
    activatesPolicy = false
    executesAction = false

## Non-goals

Key Turn Office v1 does not:

- activate Gatehouse policy,
- grant runtime permission,
- execute a command,
- publish an event,
- mutate the Key Vault,
- perform a handoff,
- contact a device,
- use the network.

## Verification

From repository root:

    py tools/city/activation_confirmation.py
    py tools/city/service_directory.py
    py tools/city/visitor_guide.py
    py -m pytest tools/checker/tests/test_city_activation_confirmation.py -q
    py -m pytest tools/checker/tests/test_city_service_directory.py -q
    py -m pytest tools/checker/tests/test_city_visitor_guide.py -q
    py -m pytest tools/checker/tests -q

Architecture rule:

**confirming the exact key-turn intent is still not turning the key.**
