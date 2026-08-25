# 📜 Changelog

All notable changes to **Bondik TV Ultimate** are documented here.

Current development work is collected under **Unreleased** until the next
formal public release.

---

## [Unreleased]

### Added

#### Discovery and candidates

- M3U Hunter v0.9 bulk public-stream discovery
- Country filtering, known-source comparison and new-only discovery
- Deep HLS verification
- Persistent Hunter history and stability tracking
- Second-chance playlist scanner
- Candidate Gate v0.5.1
- Priority / review / parking buckets
- Candidate scoring and provenance-risk flags

#### BAGTOP

- BAGTOP v1.0 production candidate ranking and audit tooling
- Diversity quality floor to prevent weak candidates displacing stronger TOP entries
- Category cap and category-family grouping for balanced TOP selections
- Selection ledger recording TOP rank, reason and category family
- Full `bagtop-selection-audit.csv` for selected and skipped decisions
- `bagtop-manifest.json` run manifest
- Metadata cache validation and automatic repair
- Verified-cache fallback when metadata refresh fails
- Invalid explicit metadata rejection
- Downloaded metadata revalidation

#### AUTO-PROMOTION

- AUTO-PROMOTION v1.0 candidate-to-testing workflow
- DRY-RUN by default and explicit `--apply`
- Duplicate URL, ID and name protection
- HTTPS, raw-IP, test-feed and parking Risk Gates
- AUTO-PROMOTION v1.1 verified provenance requirement
- Official website and evidence URL storage
- Manual provenance/QC note

#### Testing and stable lifecycle

- Testing Promotion Gate v0.7.1
- Three counted successful passes by default
- Minimum 24-hour gap between counted passes
- Failure and stream-URL-change reset protection
- Persistent state and CSV / JSON / Markdown reports
- STABLE PROMOTION v1.0
- Manual stable approval
- Promotion Gate eligibility enforcement
- Stream URL binding between decision, report and channel
- Fresh-report and manual-review-note requirements
- First production testing → stable batch completed

#### Channels and branding

- Added and promoted verified CZ/SK regional candidates through the testing lifecycle
- Production stable batch included MTR, TVT, Televizia Mocenok, Plzeň TV, Elektrika TV, TV DK and TV Ružinov
- Updated Bondík TV team logo
- Refreshed README with larger branding, Quick Start, quality pipeline and tooling overview
- Added Bondik TV banner

#### Testing

- Added discovery and promotion regression tests
- Added provenance validation tests
- Added STABLE PROMOTION tests
- Expanded BAGTOP regression coverage through v1.0
- CI now reports **359 passing tests + 22 passing subtests**

---

### Changed

- `channels/channels.yaml` remains the single source of truth
- Public playlist generation remains stable-only
- Candidate approval no longer means automatic publication
- Manual provenance review remains part of the promotion pipeline
- Testing promotion requires spaced successful checks
- Stable promotion requires automated evidence and human approval
- Candidate ranking now includes auditable selection reasons and skipped decisions
- GitHub Actions CI uses `pytest` for the checker test suite
- CI compiles BAGTOP alongside production checker/generator tooling
- README now reflects the actual discovery → ranking → testing → stable architecture

---

### Safety

- Raw-IP and non-HTTPS candidates are blocked from AUTO-PROMOTION
- Test-feed paths are blocked
- Parking candidates cannot bypass review
- Missing provenance blocks AUTO-PROMOTION v1.1
- Manual stable approval cannot bypass Promotion Gate eligibility
- Stream URL changes invalidate previous promotion confidence
- Failed testing checks reset counted promotion passes
- BAGTOP diversity cannot silently bypass the configured quality floor
- Invalid metadata caches are not trusted as refresh fallbacks
- Explicit invalid metadata is rejected instead of silently accepted

---

### Current development pipeline

```text
Hunter
→ Candidate Gate
→ BAGTOP ranking / diversity / audit
→ manual provenance review
→ AUTO-PROMOTION
→ testing
→ Testing Promotion Gate
→ 3/3 eligible
→ manual stable review
→ STABLE PROMOTION
→ stable
→ public playlists
```

---

### Current CI snapshot

- **359 tests passed**
- **22 subtests passed**
- **39 validated channels**
- **29 Ultimate stable channels**
- **16 country playlists**
- **14 category playlists**
- **22 provider playlists**
- Generated playlists synchronized with `channels/channels.yaml`
- CI result: **Bondík approved**

---

### Next

- Expand verified CZ/SK coverage
- Improve CZ/SK EPG coverage and mappings
- Improve channel logos and provenance metadata
- Continue using BAGTOP v1.0 audit outputs for candidate review
- Complete final documentation review
- Prepare the next stable public release

---

🐾 **Bondik TV Ultimate**

> Quality before quantity.
