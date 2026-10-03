# BTV-S01 — Channel Selection Boundary

Status: **reviewable implementation slice / no merge**

This slice implements the first concrete Bondík City extension seam proposed by
Nikola's V381 live mission, with one TECH refinement:

> channel selection stays separate from player control.

Nikola correctly identified the current `selectChannel(...)` helper in the
Android UI as a useful first extraction point. The proposal originally described
a selector that would also update the player. That would merely move the current
UI/player coupling into a differently named class.

This implementation keeps the slice smaller and cleaner.

## What changed

A new pure boundary was added:

```text
ChannelSelector
    ↓
ChannelSelection
    ├─ channel
    └─ mediaUri
```

`DefaultChannelSelector` currently preserves the exact existing choice:

```text
selected channel = requested channel
media URI        = channel.url
```

The Compose screen remains responsible for applying the result to ExoPlayer.

## Why this boundary exists

Today a user click selects a channel directly.

Later the same selection boundary can be fed by:

- keyboard / remote navigation,
- search results,
- favorites,
- session restore,
- ShareToTV hand-off preparation,
- approved AI-agent proposals,
- Radio Station / city discovery surfaces where media-like targets may need a
  common selection shape.

The boundary is intentionally small. It does not attempt to solve playback,
session persistence, routing or permissions yet.

## Preserved behavior

The slice preserves:

- catalog loading through `BondikCatalogRepository`,
- first-channel fallback selection,
- empty-catalog fallback status,
- selected-channel UI display,
- ExoPlayer media item creation,
- `prepare()`,
- `playWhenReady = false`,
- current click-to-select behavior.

## Tests

Unit tests verify that the default selector:

- preserves the selected `BondikChannel`,
- maps `mediaUri` to the current channel URL,
- does not rewrite channel metadata.

Android build/test and live TV behavior still require CI / Black acceptance.

## Authority / PACK boundary

This branch does not:

- merge to main,
- release,
- delete current behavior,
- change playlist/catalog provenance,
- grant AI agents playback authority,
- expose a command channel.

It is an additive seam only.

**Rule:** preserve → isolate → extend.
