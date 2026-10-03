# BTV-S01 — Contactor Office v1

This is the thirty-third concrete Bondík City block.

For the first time, the human-confirmed authorization chain can execute one
exact registered **read-only** local command.

K33 is the contactor: it closes the circuit only after the K32 final preflight
still matches the current dispatcher registration and current city topology.

## Protocols

Execution contract:

    bondik-city-authorized-dispatch/1

Execution receipt:

    bondik-city-read-only-dispatch-receipt/1

Contract:

    config/city-authorized-dispatch-contract.json

Implementation:

    tools/city/authorized_dispatch.py

## Single-use consumption

Before the handler is touched, Contactor Office writes a create-once claim to
the Storage Adapter namespace:

    city.dispatch.spent

using:

    expected_revision = 0

The grant id is the storage key.

A second attempt for the same grant therefore fails closed before the handler
can run.

The source Runtime Grant artifact remains immutable. Consumption is represented
by the storage claim/receipt, not by mutating the original grant JSON.

## At-most-once rule

The sequence is deliberately:

    fresh K32 preflight
        -> create consumption claim
        -> invoke exact registered read-only handler
        -> finalize consumption record
        -> return receipt

If the handler fails, the claim is finalized as:

    failed-consumed

and the grant still cannot be replayed.

This favors at-most-once safety over automatic retry.

## Actual execution boundary

A successful v1 receipt records:

    state = dispatched-consumed
    grantConsumed = true
    consumerConnected = true
    dispatchesCommand = true
    executesAction = true

but remains restricted to:

    mutation = read-only
    transport = local-in-process
    usesNetwork = false
    mutatesPolicy = false
    publishesEvent = false
    performsHandoff = false

The demo command is:

    city.status.read
        -> control-tower
        -> city.control-tower.status-board

and returns:

    {"status": "available"}

## Command Boundary

The existing public `dispatch()` behavior remains unchanged and still accepts
only the original local-ui command contract.

Internally, its already-registered read-only handler path is factored into
`_dispatch_registered_read_only()`. The K33 executor reaches that primitive
only after authorization, fresh preflight, and single-use consumption claim
validation.

## Verification

From repository root:

    py tools/city/authorized_dispatch.py
    py tools/city/service_directory.py
    py tools/city/visitor_guide.py
    py -m pytest tools/checker/tests/test_city_authorized_dispatch.py -q
    py -m pytest tools/checker/tests/test_city_dispatch_preflight.py -q
    py -m pytest tools/checker/tests/test_city_command_boundary.py -q
    py -m pytest tools/checker/tests/test_city_service_directory.py -q
    py -m pytest tools/checker/tests/test_city_visitor_guide.py -q
    py -m pytest tools/checker/tests -q

Architecture rule:

**claim the single-use grant before touching the handler, then execute only the
exact current read-only registration that passed the final preflight.**
