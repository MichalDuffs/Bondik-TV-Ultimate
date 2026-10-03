# BTV-S01 — Web Session Seam

This slice implements the first additive Web session contract for Bondík-TV.

## Contract

```text
BondikTvSession v1
- version
- theme
- activePlaylistId
```

Storage key:

```text
bondik-tv-session-v1
```

## Preserve

The existing playlist library remains the source of playlist content.

The current keys and migration path remain unchanged:

- `bondik-tv-playlist-library-v3`
- `bondik-tv-playlist-v2`
- `bondik-tv-playlist-v1`

The session stores only the active playlist ID and theme. It does not copy,
rewrite, or replace playlist content.

## Load behavior

1. Load and normalize the existing playlist library first.
2. Load `BondikTvSession v1`.
3. Invalid/missing theme falls back to `ultimate`.
4. Missing/stale `activePlaylistId` falls back to the normalized library active ID.
5. Unknown session versions fall back safely to current v1 defaults.

## Save behavior

Web state writes an additive session record containing only:

- `version`
- `theme`
- `activePlaylistId`

Restricted/unavailable browser storage remains non-fatal.

## Verification

From `web/`:

```powershell
npm test
npm run lint
npm run build
```

## Scope boundary

This slice does not add:

- Android session persistence
- playback/ExoPlayer state
- cloud sync
- agent command execution

Architecture rule: **preserve → isolate → extend**.
