# BTV-S01 — Ignition Office v1

This is the twenty-sixth concrete Bondík City block.

The Ignition Office takes a registered inactive certificate from the Key Vault
and prepares an exact-scope **activation intent** for a named human actor.

It still does not activate anything.

## Protocols

Ignition contract:

    bondik-city-ignition/1

Activation intent:

    bondik-city-activation-intent/1

Contract:

    config/city-ignition-contract.json

Implementation:

    tools/city/ignition_office.py

## Input requirements

The source must be a valid:

    bondik-city-key-vault-entry/1

with:

    state = registered-inactive

The embedded certificate must still be:

    state = issued-inactive
    runtimeAuthority = false
    grantsPermission = false
    activatesPolicy = false
    executesAction = false

The certificate SHA-256 digest stored by Key Vault is recalculated and must
match before an activation intent can be prepared.

## Human intent

Every activation intent records:

- a named human actor,
- timezone-aware preparedAt,
- a human-readable reason,
- exact subject,
- exact operation + capability scope,
- vault-entry SHA-256 digest,
- certificate id + digest.

Every v1 intent remains:

    state = prepared-not-active
    authority = intent-only
    runtimeAuthority = false
    grantsPermission = false
    activatesPolicy = false
    executesAction = false

## Non-goals

Ignition Office v1 does not:

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

    py tools/city/ignition_office.py
    py tools/city/service_directory.py
    py tools/city/visitor_guide.py
    py -m pytest tools/checker/tests/test_city_ignition_office.py -q
    py -m pytest tools/checker/tests/test_city_service_directory.py -q
    py -m pytest tools/checker/tests/test_city_visitor_guide.py -q
    py -m pytest tools/checker/tests -q

Architecture rule:

**putting the key beside the ignition is still not turning it.**
