# Bondík-TV — Android TV device smoke helper

This helper closes the gap between a successful Gradle build and the final
real-device Android TV acceptance.

Script:

    android/scripts/tv-smoke.ps1

## Prerequisites

- Android platform-tools / `adb` available in `PATH`
- one authorized Android TV device connected through USB or network ADB
- the debug APK already built

Build first:

```powershell
cd C:\Git_Repository\Bondik-TV-Ultimate\android
.\gradlew.bat testDebugUnitTest assembleDebug
```

## Automated smoke

With exactly one connected TV/device:

```powershell
.\scripts\tv-smoke.ps1
```

The helper verifies:

- debug APK exists,
- APK installs,
- package is visible,
- `LEANBACK_LAUNCHER` resolves,
- `MainActivity` launches,
- the application process is running.

When more than one device is connected:

```powershell
.\scripts\tv-smoke.ps1 -Serial "<adb-serial>"
```

## Optional remote probe

To send two D-pad Down presses and one OK press after launch:

```powershell
.\scripts\tv-smoke.ps1 -ProbeRemote
```

This intentionally changes the selected channel and can start playback.

To then force-stop and relaunch the application so session restore can be
checked:

```powershell
.\scripts\tv-smoke.ps1 -ProbeRemote -ProbeRestore
```

## Final human acceptance

Automation cannot prove visual focus styling or that video visibly plays on
the physical TV. The human check remains:

1. exactly one channel row shows a visible focus highlight,
2. D-pad Up/Down moves focus predictably,
3. OK on another channel moves the selected marker and starts playback,
4. relaunch brings the last selected channel back into view,
5. relaunch does not force autoplay.

The helper does not merge branches, publish a release, change public
playlists, or alter project data outside installing the local debug APK on the
selected Android device.
