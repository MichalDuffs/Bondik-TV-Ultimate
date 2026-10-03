# BTV-S01 — Agent Safety Envelope v1

This is the thirteenth concrete Bondík City block.

The Gatehouse establishes the permission boundary that must exist before future
AI agents can be given any useful city access.

## Protocol

    bondik-city-agent-safety/1

Policy:

    config/city-agent-policy.json

Evaluator:

    tools/city/agent_safety.py

## v1 model

v1 is default-deny.

Unknown roles, unknown capabilities, and unlisted operations are denied.

Two initial roles exist:

- observer
- builder

In v1 both roles are intentionally limited to the same non-executing access:
city discovery plus inspection of explicitly approved evidence capabilities.

## Explicitly denied operations

The policy must deny:

- execute
- command
- mutate
- handoff
- publish-event

The exposure contract is fixed to:

    sensitiveState = not-exposed
    commandAuthority = none
    mutationAuthority = none
    networkAuthority = none

## Capability checks

A capability referenced by the policy must exist in the current capability
registry and remain:

- active,
- discoverable,
- agent execution = not-exposed.

The evaluator re-checks these properties when deciding access.

## Important boundary

This block does not grant an AI access by itself.

It provides a policy and deterministic decision function that future AI-facing
surfaces can consult.

It does not enable:

- agent commands,
- agent Event Bus publishing,
- network access,
- GitHub mutation,
- handoff,
- autonomous repair,
- Radio Station execution.

## Verification

From repository root:

    py tools/city/agent_safety.py
    py -m pytest tools/checker/tests/test_city_agent_safety.py -q
    py -m pytest tools/checker/tests -q

Architecture rule:

**agents get permissions through policy; buildings expose capabilities, not ownership.**
