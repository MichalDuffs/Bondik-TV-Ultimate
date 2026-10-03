# BTV-S01 — Control Tower Health Snapshot v1

This is the sixth concrete Bondík City block.

The Control Tower turns existing stream-health and EPG-health state artifacts
into one bounded, machine-readable city health snapshot.

## Protocol

```text
bondik-city-health-snapshot/1
```

Builder:

```text
tools/city/build_health_snapshot.py
```

Default output:

```text
city-health-snapshot.json
```

## Inputs

The builder consumes the existing health-state formats already produced by the
project:

```text
stream-health-state.json
epg-health-state.json
```

Each source state remains the established JSON mapping:

```json
{
  "name": 3
}
```

where the integer is the current consecutive failure streak.

The Control Tower does not replace either existing health workflow.

## Status model

Each source becomes:

- `healthy` — artifact exists and has no failures,
- `degraded` — artifact exists and contains one or more failures,
- `unknown` — artifact is not available to this snapshot run.

Overall status is conservative:

```text
degraded > unknown > healthy
```

A missing artifact is never silently reported as healthy.

## Safety contract

The snapshot is read-only:

```text
sensitiveState = not-exposed
execution = not-exposed
mutation = not-allowed
```

It does not create/close issues, retry streams, edit EPG mappings, or perform
agent actions.

## Verification

From repository root:

```powershell
py tools/city/build_health_snapshot.py
py -m pytest tools/checker/tests/test_city_health_snapshot.py -q
py -m pytest tools/checker/tests -q
```

With no local health artifacts, the first command intentionally produces an
`unknown` snapshot rather than inventing a green state.

To test with real workflow artifacts, place/copy the two health-state JSON files
in the working directory or provide `--stream-state` / `--epg-state`.

## Scope boundary

This slice does not yet:

- download GitHub Actions artifacts,
- query live workflow status,
- expose a network endpoint,
- mutate operational health state,
- make autonomous repair decisions.

Those can be layered later behind separate evidence and permission boundaries.

Architecture rule:

**existing health evidence → Control Tower read model → human/agent views later**.
