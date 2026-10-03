# BTV-S01 — Receipt Office v1

This is the thirty-fourth concrete Bondík City block.

K33 proved that one exact human-confirmed read-only command can execute.
K34 turns that completed execution into independently verified evidence.

## Protocols

Evidence contract:

    bondik-city-execution-evidence/1

Evidence record:

    bondik-city-execution-evidence-record/1

Contract:

    config/city-execution-evidence-contract.json

Implementation:

    tools/city/execution_evidence.py

## What Receipt Office verifies

Receipt Office does not trust the returned K33 receipt by itself.

It checks the receipt against the actual single-use consumption record stored
under:

    city.dispatch.spent/<grantId>

and requires the stored revision referenced by the receipt to exist.

It verifies agreement on:

- grant id,
- packet id + digest,
- preflight id + digest,
- command id,
- execution timestamp,
- final state `dispatched-consumed`,
- result SHA-256,
- read-only/local execution safety flags.

## Result privacy

K34 deliberately does **not** copy command result content into the evidence
record.

The evidence records only:

    resultDigest = sha256:...
    resultContent = not-copied

That gives the city an auditable fact that a result existed and matched the
consumption ledger without turning the evidence layer into a broad data-return
surface.

A later result-return surface can decide explicitly what content may be shown
to humans or agents.

## Authority

Every K34 record remains:

    state = verified-completed
    authority = evidence-only
    grantsPermission = false
    runtimeAuthority = false
    dispatchesCommand = false
    executesAction = false
    mutatesPolicy = false
    publishesEvent = false
    performsHandoff = false
    usesNetwork = false

## Verification

From repository root:

    py tools/city/execution_evidence.py
    py tools/city/service_directory.py
    py tools/city/visitor_guide.py
    py -m pytest tools/checker/tests/test_city_execution_evidence.py -q
    py -m pytest tools/checker/tests/test_city_authorized_dispatch.py -q
    py -m pytest tools/checker/tests/test_city_service_directory.py -q
    py -m pytest tools/checker/tests/test_city_visitor_guide.py -q
    py -m pytest tools/checker/tests -q

Architecture rule:

**execution is not considered city evidence until the returned receipt and the
single-use consumption ledger agree.**
