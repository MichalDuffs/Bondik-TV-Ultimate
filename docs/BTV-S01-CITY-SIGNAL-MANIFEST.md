# BTV-S01 — City Signal Manifest v1

This is the fifth concrete Bondík City block.

The goal is to give future AI agents one bounded, machine-readable answer to:

> **Bondík City is here. What can I safely discover?**

The signal is deliberately static and non-executable.

## Protocol

```text
bondik-city-agent-signal/1
```

Signal manifest:

```text
config/city-signal.json
```

It points to the existing capability registry instead of duplicating capability
state:

```text
config/city-capabilities.json
bondik-city-capability-registry/1
```

## Safety contract

Signal v1 requires:

```text
mode = static-discovery-manifest
sensitiveState = not-exposed
execution = not-exposed
commandEndpoint = null
handoff.status = not-enabled
handoff.requiresPermission = true
```

The validator rejects any v1 manifest that tries to expose a command endpoint,
execution, sensitive state, or enabled handoff.

## Capability registry relationship

The registry now contains an active shared capability:

```text
city.discovery-manifest
```

That means the static discovery manifest exists as real project infrastructure.

The broader Radio Station capability remains separately marked `planned`.
A file on disk is not being misrepresented as a live network broadcaster.

## Verification

Run from the repository root:

```powershell
py tools/city/validate_capability_registry.py
py tools/city/validate_city_signal.py
py -m pytest tools/checker/tests/test_city_signal.py -q
py -m pytest tools/checker/tests -q
```

## Scope boundary

This slice does not:

- open a network port,
- advertise a command endpoint,
- execute agent actions,
- expose private/sensitive runtime state,
- enable autonomous handoff,
- merge or publish the stack.

Architecture rule:

**signal identity → registry discovery → permissioned execution later**.
