# BTV-S01 — City Foundation

Status: **working foundation / no merge**

## Mission

Bondík-TV is the first flagship building of a larger virtual city.

The goal is not to replace the current project. The goal is to **preserve what works,
add clean extension points, and make future modules easier to build**.

Core rule:

> **Do not delete working foundations. Extend them.**

## Product direction

Bondík-TV remains the first complete product building.

The shared foundation should later support other buildings and services without
copying the same logic again. The first planned neighbour is **Radio Station**.

The virtual city is not only decoration. Its objects should correspond to real
project capabilities, state and services.

## Two views of the same city

The foundation must be useful to both humans and AI agents.

### Human-readable layer

Humans should be able to understand:

- what buildings/modules exist,
- what state each module is in,
- which features are available,
- what is running, failing or waiting for review,
- which PACK is currently being prepared.

### Agent-readable layer

AI agents should be able to discover:

- capabilities,
- services,
- tasks,
- events,
- state,
- permissions,
- artifacts,
- quality gates.

Human and agent views describe the same underlying project state.

## Architecture principles

1. **Preserve current code and behaviour.**
   Existing Web, Android, channel data, validation and automation remain the
   starting point.

2. **Extend through boundaries, not rewrites.**
   New shared services are introduced behind explicit contracts/adapters.

3. **UI is not the core.**
   Actions such as Play, Favorite, Search, ShareToTV or Translate should be
   represented as capabilities/commands that different clients can invoke.

4. **Session is versioned state.**
   Session should grow without forcing destructive migrations.

5. **Shared media capabilities belong below individual buildings.**
   Playback, search, favorites, history, metadata, device sharing and later
   translation should be reusable where practical.

6. **Buildings own product-specific behaviour.**
   Bondík-TV and Radio Station may share infrastructure without becoming one
   giant application.

7. **No installer-first development.**
   Windows setup/packaging is a release concern after the product surface is
   stable.

8. **No VIP core split.**
   Core functionality remains Open / Free; legal and provenance constraints
   still apply to content and sources.

## First city model

### Bondík-TV HQ — active flagship

Current foundation already includes:

- Web application,
- Android / Android TV application,
- channel catalog,
- playlists,
- EPG navigation,
- Favorites surface,
- Search,
- playback,
- quality/discovery pipeline.

BTV-S01 will make these foundations easier to extend instead of replacing them.

### Radio Station — planned second building

Radio Station is the first architecture proof that the city foundation is not
hard-coded to television.

It should be able to reuse compatible media/session/device capabilities while
keeping radio-specific product behaviour separate.

### Shared infrastructure

Initial shared concepts:

- session/state contract,
- capability registry,
- media source contract,
- command/action boundary,
- event boundary,
- storage adapter,
- device/share adapter,
- observability/health surface,
- permissions/safety envelope for agents.

These are contracts first. Implementations remain incremental.

## Virtual campus areas

The visual city may later expose real technical surfaces through familiar places:

- **Bondík-TV HQ** — TV product and operations
- **Radio Station** — radio product
- **Nikča Lab** — AI-assisted work and approved agent capabilities
- **Control Tower** — CI, QC, health and technical review
- **Archive** — persistent artifacts/history/backups
- **Garden** — low-pressure overview / calm dashboard surface
- **Pool** — live data-flow / runtime visualization
- **Party Zone** — demo/showcase/event surface

The labels are optional presentation. The underlying data and services remain
real project objects.

## BTV-S01 first implementation slice

The first implementation slice should be deliberately small:

1. Inventory existing Web/Android state and storage.
2. Define a versioned session contract.
3. Introduce the contract without deleting existing behaviour.
4. Map existing Web state into the session contract first.
5. Add tests for migration/defaults/version handling.
6. Only after that connect Android and additional capabilities.

## Definition of done for S01 foundation

The foundation is ready when:

- Bondík-TV survives restart with defined session state,
- existing playlist behaviour is preserved,
- session format is versioned,
- new fields can be added without breaking old state,
- Web and Android have a clear path to the same logical contract,
- capability boundaries exist for future ShareToTV / Translator / Radio,
- no working feature was deleted merely to achieve the refactor,
- tests and review evidence accompany the PACK.

## PACK mode

Technical work may progress in reviewable steps.

- Nikča: BUILD / analysis / bounded implementation
- Kolega: TECH review, architecture, regression and extensibility gate
- Michal: PACK approval for the completed logical package
- Bondík: mascot + acceptance sniff test

Irreversible actions such as public release or main-branch merge remain separate
PACK decisions.

---

**Foundation rule:** preserve, isolate, extend.

🐾 Bondík-TV first. City-ready from the foundation.
