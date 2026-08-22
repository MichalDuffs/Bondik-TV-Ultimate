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

#### Channels and branding

- Added Plzeň TV as a testing candidate
- Added TV Panorama as a testing candidate
- Updated Bondík TV mascot logo
- Added Bondik TV banner

#### Testing

- Added discovery and promotion regression tests
- Added provenance validation tests
- Added STABLE PROMOTION tests
- Full automated suite reached **289 passing tests**

---

### Changed

- `channels/channels.yaml` remains the single source of truth
- Public playlist generation remains stable-only
- Candidate approval no longer means automatic publication
- Manual provenance review is part of the promotion pipeline
- Testing promotion requires spaced successful checks
- Stable promotion requires automated evidence and human approval

---

### Safety

- Raw-IP and non-HTTPS candidates are blocked from AUTO-PROMOTION
- Test-feed paths are blocked
- Parking candidates cannot bypass review
- Missing provenance blocks AUTO-PROMOTION v1.1
- Manual stable approval cannot bypass Promotion Gate eligibility
- Stream URL changes invalidate previous promotion confidence
- Failed testing checks reset counted promotion passes

---

### Current development pipeline

```text
Hunter
→ Candidate Gate
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

### Next

- Exercise the first real production `3/3 → stable` promotion
- Expand verified CZ/SK coverage
- Improve channel logos
- Improve EPG coverage and mappings
- Complete final documentation review
- Prepare the next stable public release

---

🐾 **Bondik TV Ultimate**

> Quality before quantity.
