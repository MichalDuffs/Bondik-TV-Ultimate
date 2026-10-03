# BTV-S01 — City Capability Registry v1

This is the fourth concrete Bondík City product block.

The registry introduces one shared, versioned description of capabilities that
can be read by humans and future AI agents without giving agents an execution
channel.

## Protocol

```text
bondik-city-capability-registry/1
```

Registry:

```text
config/city-capabilities.json
```

Each capability declares:

- stable capability ID,
- owning building ID,
- status,
- current client surfaces,
- human-readable name and description,
- agent discovery visibility,
- agent execution exposure.

## v1 safety boundary

For registry v1 every capability must use:

```text
agent.execution = not-exposed
```

The registry is therefore a **discovery surface, not a command bus**.

This is intentional groundwork for the future Radio Station / AI city beacon.
A future execution protocol must be introduced separately behind explicit
permissions and a safety envelope.

## Current evidence-backed capabilities

Active entries are limited to capabilities already represented by the current
stack:

- Bondík-TV playback on Web and Android,
- Web search,
- Web playlist library,
- Web session restoration,
- Android session restoration.

The future Radio Station agent signal is present only as `planned`, never as
an active executable capability.

## Validation

Run:

```powershell
py tools/city/validate_capability_registry.py
py -m pytest tools/checker/tests/test_city_capability_registry.py -q
```

The normal Python CI also compiles the validator, runs the checker test suite,
and validates the checked-in registry.

## Scope boundary

This slice does not:

- execute agent commands,
- publish sensitive project state,
- create a network discovery endpoint,
- change playback or session behavior,
- merge or publish the project.

Architecture rule: **same city reality → human-readable + agent-readable views**.
