# Bondík-TV — Finish 01: functional product pages

This slice stops adding city infrastructure and returns to the TV product.

## Goal

Replace the remaining navigation placeholders with useful, bounded product
views while preserving the existing Search, Playlist Library and Live Preview.

## Added

### Favorites

- persistent local favorites under `bondik-tv-favorites-v1`
- star/unstar directly from Search
- Favorites page with live preview
- one-click add to the active playlist
- stale favorite IDs are ignored safely

### EPG

- real EPG metadata coverage from the current catalog
- enabled-channel count and coverage percentage
- visible EPG ID and source per channel
- no invented programme schedule when no verified programme feed is present

### Statistics

- total/stable/testing/EPG counts
- country/category/provider counts
- local favorites and playlist counts
- country and category breakdowns calculated from the shipped catalog

### Tools

- local product readiness view
- active playlist and channel count
- favorites count and active theme
- direct navigation to Search, Playlists, EPG, Statistics and Settings
- no destructive or repository-mutating actions

## Safety / data boundaries

Favorites are additive browser-local state.

This slice does not:
- alter public playlists,
- promote channels,
- change channel metadata,
- execute GitHub writes from the web UI,
- add network diagnostics,
- claim live EPG schedule data that is not bundled.

## Verification

From `web/`:

```powershell
npm test
npm run lint
npm run build
```

Manual smoke test:

1. Open Search and star a channel.
2. Open Favorites and verify it appears.
3. Play the favorite preview.
4. Add it to the active playlist.
5. Reload and verify the favorite persists.
6. Open EPG and verify catalog coverage renders.
7. Open Statistics and verify non-placeholder counts render.
8. Open Tools and verify the local product summary and navigation.

Architecture rule:

**finish visible product gaps first; do not fake data to make a page look done.**
