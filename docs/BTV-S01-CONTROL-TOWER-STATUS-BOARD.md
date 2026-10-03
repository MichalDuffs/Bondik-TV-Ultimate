# BTV-S01 — Control Tower Status Board v1

This is the seventh concrete Bondík City block.

The previous blocks established machine-readable city capabilities, a static AI
discovery signal, and a read-only health snapshot. This slice adds the matching
**human-readable view of the same project reality**.

## Protocol

```text
bondik-city-status-board/1
```

Renderer:

```text
tools/city/render_status_board.py
```

Default output:

```text
city-status.md
```

## Inputs

The board reads:

- `config/city-capabilities.json`
- `config/city-signal.json`
- optional `city-health-snapshot.json`

The capability registry and AI signal are validated before rendering.

If the health snapshot is absent, the board reports:

```text
UNKNOWN
```

It never converts missing evidence into a GREEN state.

## Human / agent symmetry

The machine-readable sources remain authoritative data surfaces.

The Markdown board is a projection for humans. It shows:

- Control Tower health,
- stream and EPG source states,
- known failure streaks when present,
- active/planned capability counts,
- capability IDs and surfaces,
- AI signal mode and safety envelope.

No state is duplicated as a second source of truth.

## Safety boundary

The renderer is read-only.

It does not:

- execute a capability,
- mutate stream or EPG health,
- edit the capability registry,
- open a command endpoint,
- enable agent handoff,
- merge or publish the project.

## Verification

From repository root:

```powershell
py tools/city/render_status_board.py
Get-Content .\city-status.md
py -m pytest tools/checker/tests/test_city_status_board.py -q
py -m pytest tools/checker/tests -q
```

If `city-health-snapshot.json` exists from the previous Control Tower block,
the board renders it. Otherwise it intentionally renders health as UNKNOWN.

Architecture rule:

**one city reality → machine-readable evidence + human-readable projection**.
