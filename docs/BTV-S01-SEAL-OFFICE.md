# BTV-S01 — Seal Office v1

This is the twenty-fourth concrete Bondík City block.

The Seal Office turns an already-audited human `approve` decision into an
**inactive approval certificate**.

It does not activate that certificate.

## Protocols

Seal contract:

    bondik-city-approval-seal/1

Certificate:

    bondik-city-approval-certificate/1

Contract:

    config/city-approval-seal-contract.json

Implementation:

    tools/city/seal_office.py

## Source requirement

Seal Office accepts only a valid `bondik-city-audit-entry/1` whose linked
Review Board decision is exactly:

    approve

The audit entry must still state:

    grantsPermission = false
    changesPolicy = false
    executesAction = false

The Permit Office snapshot inside the review must still match the permit stored
in the audit entry.

## Certificate state

Every v1 certificate is:

    state = issued-inactive
    authority = certificate-only
    runtimeAuthority = false
    grantsPermission = false
    activatesPolicy = false
    executesAction = false

The certificate captures the exact principal, requested operation, capability,
human reviewer, current Gatehouse policy state, city route, audit entry id, and
SHA-256 digest of the source audit entry.

This is a seal of human approval evidence, not a runtime credential.

## Non-goals

Seal Office v1 does not:

- activate Gatehouse policy,
- grant an agent permission,
- execute a command,
- publish an event,
- mutate city storage,
- perform a handoff,
- contact a device,
- use the network.

## Verification

From repository root:

    py tools/city/seal_office.py
    py tools/city/service_directory.py
    py tools/city/visitor_guide.py
    py -m pytest tools/checker/tests/test_city_seal_office.py -q
    py -m pytest tools/checker/tests/test_city_service_directory.py -q
    py -m pytest tools/checker/tests/test_city_visitor_guide.py -q
    py -m pytest tools/checker/tests -q

Architecture rule:

**human approval can be sealed into a verifiable artifact without becoming
runtime authority.**
