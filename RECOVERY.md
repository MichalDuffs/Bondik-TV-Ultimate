# Bondik TV disaster recovery

This document protects Bondik TV Ultimate against loss of the development machine.

## Primary copy

The GitHub repository is the authoritative copy of the curated channel metadata, source code, tests, workflows, Android project, generated playlist definitions, and project history.

## Create an independent recovery copy

Use a separate physical or encrypted destination such as a BitLocker-protected USB drive, NAS, or encrypted synced folder.

```powershell
.\tools\backup_bondik_tv.ps1 -DestinationRoot "E:\BONDIK-TV-BACKUPS"
```

The backup contains:

- a complete Git bundle with all refs
- current branch, HEAD SHA, remotes, and working-tree status
- SHA-256 checksum for the Git bundle

Optional local discovery results can be copied too:

```powershell
.\tools\backup_bondik_tv.ps1 `
  -DestinationRoot "E:\BONDIK-TV-BACKUPS" `
  -IncludeLocalResults
```

`hunt-results/` can be large and is not required to rebuild the application or curated playlists, so it is opt-in.

The script does not upload anything and does not copy credentials or environment secrets.

## Restore on a new machine

```powershell
git clone .\Bondik-TV-Ultimate.bundle C:\Git_Repository\Bondik-TV-Ultimate
cd C:\Git_Repository\Bondik-TV-Ultimate
git remote set-url origin https://github.com/MichalDuffs/Bondik-TV-Ultimate.git
py -m pytest tools\checker\tests -q
```

Then regenerate and verify playlists using the normal project workflow.

## Recovery rule

GitHub is the working source of truth. Keep at least one independent bundle backup on storage that will survive a Black Tower hardware failure.
