# 🗺️ Bondik TV Ultimate Roadmap

Last refreshed: **2026-08-23**

> **Quality over quantity.**

Bondik TV Ultimate focuses on verified public streams, transparent review,
simple operation and automation that never bypasses human quality control.

---

## 🐾 Current Quality Pipeline

```text
Public M3U sources
        ↓
M3U Hunter v0.9
        ↓
Candidate Gate v0.5.1
        ↓
Manual provenance review
        ↓
AUTO-PROMOTION v1.1
        ↓
status=testing
        ↓
Testing Promotion Gate v0.7.1
        ↓
3 counted passes / minimum 24h gap
        ↓
Manual stable approval
        ↓
STABLE PROMOTION v1.0
        ↓
status=stable
        ↓
Playlist Generator
        ↓
Public Bondik TV playlists
```

No candidate can move directly from discovery into the stable public playlist.

---

## ✅ Foundation

- [x] Repository structure
- [x] MIT license
- [x] Central `channels/channels.yaml` database
- [x] Configuration system
- [x] Country, category and provider playlists
- [x] Ultimate playlist
- [x] Stable-only public generation
- [x] Bondík mascot logo and banner

---

## 🚜 Discovery

### M3U Hunter v0.9

- [x] Bulk M3U discovery
- [x] Country filtering
- [x] Known-source comparison
- [x] New-only discovery
- [x] Stream deduplication
- [x] Deep HLS verification
- [x] Persistent history and stability tracking
- [x] Candidate export and manual decisions

### Candidate Gate v0.5.1

- [x] Existing-stream rejection
- [x] Country/category inference
- [x] Priority / review / parking buckets
- [x] Candidate scoring
- [x] Raw-IP, suspicious-restream and test-feed detection
- [x] Reviewable JSON / CSV / M3U outputs

---

## 🛡️ Promotion

### AUTO-PROMOTION v1.1

- [x] DRY-RUN by default
- [x] Explicit `--apply`
- [x] Duplicate protection
- [x] Country/category validation
- [x] HTTPS, raw-IP, test-feed and parking Risk Gates
- [x] Verified provenance required
- [x] Official website and evidence URLs
- [x] Manual QC note
- [x] Never promotes directly to stable

### Testing Promotion Gate v0.7.1

- [x] Three counted passes by default
- [x] Minimum 24-hour gap
- [x] Failure resets progress
- [x] Stream URL change resets progress
- [x] Persistent state
- [x] CSV / JSON / Markdown reports
- [x] Advisory only

### STABLE PROMOTION v1.0

- [x] Manual approval required
- [x] Promotion Gate eligibility required
- [x] Required pass count enforced
- [x] Last result must be pass
- [x] Decision/report URL must match current URL
- [x] Fresh report required
- [x] Manual review note required
- [x] DRY-RUN by default
- [x] Explicit `--apply`

---

## 📡 Stream Health & EPG

- [x] Stream checker and retry protection
- [x] Scheduled health monitoring
- [x] Cross-run history and failure streaks
- [x] Recovery and repeated-outage detection
- [x] Automatic GitHub Issue workflow
- [x] EPG source registry and validation
- [x] Scheduled EPG monitoring
- [x] EPG maintenance tooling
- [ ] Improve CZ/SK EPG coverage and mappings
- [ ] Add more verified EPG sources

---

## 🇨🇿 🇸🇰 Curated Content

Current priority is **quality CZ/SK coverage**, not maximum channel count.

- [x] CZ/SK discovery pipeline
- [x] Manual provenance workflow
- [x] Testing lifecycle
- [x] Stable promotion lifecycle
- [ ] First production 3/3 → stable promotion
- [ ] Expand verified Czech channels
- [ ] Expand verified Slovak channels
- [ ] Improve channel logos and EPG metadata
- [ ] Remove obsolete sources

---

## 🧪 Quality

- [x] Hunter tests
- [x] Candidate Gate tests
- [x] AUTO-PROMOTION and provenance tests
- [x] Testing Promotion Gate tests
- [x] STABLE PROMOTION tests
- [x] Stream and EPG automation tests
- [x] **289 automated tests passing**

A working stream is not automatically trusted.

A trusted testing stream is not automatically stable.

---

## 🚀 Release Readiness

- [x] Central channel database
- [x] Stable-only playlist generation
- [x] Discovery and candidate-review pipeline
- [x] Provenance-aware testing promotion
- [x] Long-term testing gate
- [x] Controlled stable promotion
- [x] Automated test suite
- [ ] First production 3/3 → stable promotion
- [ ] Improve CZ/SK curated set
- [ ] Improve logo and EPG coverage
- [ ] Final documentation review
- [ ] Stable public release

---

## 🌍 Future

- [ ] Community contribution workflow
- [ ] Statistics dashboard
- [ ] Android / Android TV application
- [ ] Windows / Linux application
- [ ] Web interface

Applications come after the core playlist and QC pipeline is mature.

---

🐾 **Bondik TV Ultimate**

**Open • Free • Community**

> **When Bondík can play it, everyone can play it.**
