# Bondik TV Ultimate — Current State

Last synchronized: 2026-10-01

This document describes the verified current project state.
ROADMAP.md describes direction; this file describes what exists now.

## Repository

- Branch baseline: main
- Baseline commit: 718a444668e4f4de05aaa32a477d8998d0727469
- Python verification: 381 tests passed + 270 subtests passed
- Central channel database: channels/channels.yaml
- Current catalog: 39 channel records
  - 29 stable
  - 10 testing

## Playlist generation

Current generator snapshot:

- Validated channels: 39
- Ultimate stable channels: 29
- Country playlists: 16
- Category playlists: 14
- Provider playlists: 22

Public playlists remain stable-only.

## Quality pipeline

The established pipeline is:

Public M3U sources
→ M3U Hunter
→ Candidate Gate
→ BAGTOP
→ provenance/manual review
→ AUTO-PROMOTION
→ testing
→ Testing Promotion Gate
→ manual stable approval
→ STABLE PROMOTION
→ Playlist Generator
→ public playlists

Discovery never promotes directly to stable.

## Android / Android TV

An Android application foundation already exists under `android/`.

Verified implementation includes:

- Kotlin
- Jetpack Compose
- Media3 / ExoPlayer
- HLS playback support
- Bondik catalog loading
- channel selection
- integrated player surface
- Bondik launcher assets
- application version 0.1.0
- minSdk 23

Status: prototype / MVP foundation exists.

This is no longer a future-only roadmap item.

## Web application

A real web application foundation already exists under `web/`.

Verified implementation includes:

- React
- Vite
- hls.js
- Search
- channel filtering
- live preview
- playlist management
- playlist import/export interoperability
- EPG navigation
- Favorites
- Tools
- Statistics
- Settings
- production `dist/` output

Status: working application foundation exists.

This is no longer a future-only roadmap item.

## Windows / Linux application

No standalone Windows/Linux application project was confirmed during the
2026-10-01 repository inventory.

Status: future / not yet confirmed.

Do not infer a standalone desktop application merely from playlist support
in Windows players.

## Stream and EPG health

Health automation is active.

At the 2026-10-01 sync checkpoint:

- TV Ružinov is the known repeated stable-stream failure.
- `epgshare-cz` is the known repeated EPG-source failure.

These are operational health findings, not evidence that the whole project
or catalog is broken.

## NIKOLA-assisted operations

The NIKOLA project already contains a Bondik-TV assistance track.

Existing work includes bounded/read-only support for:

- project evidence collection
- stable-outage review
- quarantine/proposal workflows
- guarded maintenance
- sandboxed playlist regeneration review
- delegated bounded maintenance
- discovery batch preparation
- read-only discovery execution
- source expansion research
- country attribution analysis

The relevant NIKOLA development sequence currently spans V341–V357.

Nikola must operate from current project evidence and must not treat the old
ROADMAP snapshot as authoritative current state.

## Operating principle

Documentation must not claim a feature is absent when verified code already
exists.

Current state should be synchronized before new development begins.

Nikola may research, analyze and prepare reversible proposals autonomously
inside her approved safety envelope.

Publishing, merging, destructive changes and other irreversible project
actions remain separately controlled.

---

🐾 Bondik TV Ultimate

**Když to přehraje Bondík, přehraje to každý.**
