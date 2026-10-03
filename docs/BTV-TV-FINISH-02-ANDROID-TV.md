# Bondík-TV — Finish 02: Android TV remote / focus pass

This slice takes the existing Android MVP and finishes the first real TV-remote
interaction pass.

## Goal

Make the Android app behave like a TV app when used without touch:

- visible D-pad focus,
- predictable channel selection,
- restored selection brought back into view,
- OK/select starts playback,
- the app appears in Android TV launchers,
- touch is not required.

## Implemented

### D-pad focus

Each channel row has a single focus target with:

- visible focused border,
- visible focused background,
- selected-channel marker,
- selected channel restored back into view.

The currently selected row requests focus only after it exists in the lazy
list. The list scrolls to the restored selection first.

### Playback behavior

Restoring a prior session prepares the channel but does not autoplay.

A deliberate user selection through the channel row starts playback
immediately.

Media3 PlayerView remains responsible for playback controls.

### TV launcher support

The manifest now declares:

- `android.software.leanback` support,
- touchscreen not required,
- `LEANBACK_LAUNCHER`,
- a dedicated TV banner drawable.

The normal launcher category is preserved, so the same application remains
usable outside Android TV.

## Verification

From repository root on Windows:

```powershell
cd C:\Git_Repository\Bondik-TV-Ultimate\android
.\gradlew.bat testDebugUnitTest assembleDebug
```

Expected: **BUILD SUCCESSFUL**.

Recommended device smoke:

1. Install the debug APK on Android TV.
2. Launch Bondík TV from the TV launcher.
3. Confirm the previously selected channel scrolls into view.
4. Move through channel rows using D-pad Up/Down.
5. Confirm focus highlight is always visible.
6. Press OK on a different channel.
7. Confirm the selected marker moves and playback starts.
8. Relaunch the app and confirm the last selected channel is restored without
   forced autoplay.

Architecture rule:

**TV input must remain usable with a D-pad only; restoring state must not be
mistaken for a new human playback command.**
