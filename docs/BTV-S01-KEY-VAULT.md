# BTV-S01 — Key Vault v1

This is the twenty-fifth concrete Bondík City block.

The Key Vault registers already-issued inactive approval certificates as
create-once evidence.

It does not activate them.

## Protocols

Vault contract:

    bondik-city-key-vault/1

Registry entry:

    bondik-city-key-vault-entry/1

Contract:

    config/city-key-vault-contract.json

Implementation:

    tools/city/key_vault.py

## Accepted certificate

Only:

    bondik-city-approval-certificate/1

with:

    state = issued-inactive
    runtimeAuthority = false
    grantsPermission = false
    activatesPolicy = false
    executesAction = false

can be registered.

## Create-once registry

The Key Vault uses the existing Storage Adapter through a restricted wrapper.

Each certificate id is written with:

    expected_revision = 0

A second write for the same certificate id therefore fails instead of silently
overwriting the original registry entry.

The wrapper exposes register, read, and list operations. It exposes no update
or delete method.

## Evidence

Each registry entry contains:

- the full certificate snapshot,
- SHA-256 digest of that certificate,
- the certificate id,
- explicit inactive/non-authoritative flags.

## Verification

From repository root:

    py tools/city/key_vault.py
    py tools/city/service_directory.py
    py tools/city/visitor_guide.py
    py -m pytest tools/checker/tests/test_city_key_vault.py -q
    py -m pytest tools/checker/tests/test_city_service_directory.py -q
    py -m pytest tools/checker/tests/test_city_visitor_guide.py -q
    py -m pytest tools/checker/tests -q

Architecture rule:

**a sealed key can be stored and verified before any mechanism exists to turn
it in the lock.**
