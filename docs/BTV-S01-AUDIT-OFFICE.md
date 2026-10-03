# BTV-S01 — Audit Office v1

This is the twenty-third concrete Bondík City block.

The Audit Office creates a create-once evidence record that links one Permit
Office ticket to one Review Board decision.

It does not turn human approval into runtime authority.

## Protocols

Ledger contract:

    bondik-city-audit-ledger/1

Stored audit entry:

    bondik-city-audit-entry/1

Contract:

    config/city-audit-ledger-contract.json

Implementation:

    tools/city/audit_office.py

## Evidence chain

Before an entry can be recorded, the Review Board snapshot must match the
original Permit Office ticket for:

- ticket id,
- requested timestamp,
- request,
- current Gatehouse policy decision,
- resolved city route.

The entry carries SHA-256 digests of both full JSON records.

## Create-once storage

Audit Office uses the existing Storage Adapter through a restricted wrapper.

The wrapper records each ticket under a deterministic review entry id with:

    expected_revision = 0

Therefore a second write for the same ticket fails instead of overwriting the
first audit record.

The Audit Office wrapper exposes record, read, and list operations. It exposes
no update or delete method.

This is an application-level create-once boundary; the generic underlying
Storage Adapter itself remains unchanged.

## Authority

Every audit entry states:

    authority = record-only
    grantsPermission = false
    changesPolicy = false
    executesAction = false

The ledger does not approve, execute, or change policy.

## Verification

From repository root:

    py tools/city/audit_office.py
    py tools/city/service_directory.py
    py tools/city/visitor_guide.py
    py -m pytest tools/checker/tests/test_city_audit_office.py -q
    py -m pytest tools/checker/tests/test_city_service_directory.py -q
    py -m pytest tools/checker/tests/test_city_visitor_guide.py -q
    py -m pytest tools/checker/tests -q

Architecture rule:

**an approval record becomes auditable evidence before it can ever become
authority.**
