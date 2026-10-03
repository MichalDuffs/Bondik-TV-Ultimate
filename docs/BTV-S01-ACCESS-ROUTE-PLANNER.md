# BTV-S01 — Access Route Planner v1

This is the nineteenth concrete Bondík City block.

The Navigator Office combines two already separated concerns without merging
their authority:

- Directory Office says **where a capability lives**.
- Gatehouse says **whether the requested access is allowed**.

The Access Route Planner produces one non-executing plan containing both facts.

## Protocol

    bondik-city-access-route/1

Contract:

    config/city-access-route-contract.json

Planner:

    tools/city/access_route_planner.py

## Output

For a principal, operation, and capability id, the planner returns:

- the Gatehouse allow/deny decision and reason,
- the capability's city location when known,
- the location role and virtual mapping,
- the capability status and surfaces,
- explicit grantsPermission = false.

An allowed plan still does not execute anything.

A denied plan can still say where the requested capability lives. This is useful
for explanation and diagnostics without bypassing policy.

Unknown capabilities remain denied and unresolved.

## Authority boundary

The planner is plan-only.

It does not:

- grant permissions,
- execute commands,
- publish events,
- mutate storage,
- invoke playback,
- perform network access,
- contact a device.

Gatehouse remains the source of access truth.

## Verification

From repository root:

    py tools/city/access_route_planner.py
    py -m pytest tools/checker/tests/test_city_access_route_planner.py -q
    py -m pytest tools/checker/tests -q

Architecture rule:

**map plus permission produces a route plan; a route plan is never execution.**
