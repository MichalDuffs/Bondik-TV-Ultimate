# BTV-S01 — Android Session Seam

This is the third concrete Bondík City product block.

It adds a deliberately small Android-local restart seam without moving playback
responsibility out of `MainActivity` and without weakening the pure
`ChannelSelector` boundary.

## Contract

```text
BondikTvAndroidSession v1
- version
- selectedChannelUrl
```

SharedPreferences file:

```text
bondik-tv-android-session-v1
```

The Android contract is platform-local for this slice. It does **not** pretend
to be identical to the Web `BondikTvSession v1`, because Android currently has
no Web theme or playlist-library state to restore.

## Restore behavior

1. Load the channel catalog exactly as before.
2. Read Android session v1.
3. If the saved channel URL still exists, restore that channel.
4. If the saved URL is stale, missing, or the stored version is unknown,
   fall back to the first catalog channel.
5. If the catalog is empty, keep the selection empty.

## Save behavior

Every successful channel selection stores only:

- current session version,
- selected channel URL.

ExoPlayer mutation remains in `MainActivity`; the session layer never owns
`MediaItem`, `prepare()`, or playback state.

## Verification

From `android/`:

```powershell
.\gradlew.bat testDebugUnitTest assembleDebug --no-daemon
```

## Scope boundary

This slice does not add:

- playback resume position,
- play/pause persistence,
- Web theme or playlist semantics to Android,
- cloud synchronization,
- agent execution,
- migration or merge authority.

Architecture rule: **preserve → isolate → extend**.
