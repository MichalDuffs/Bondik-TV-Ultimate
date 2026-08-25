# 🗺️ Bondik TV Ultimate Roadmap

Last refreshed: **2026-08-26**

> **Quality before quantity.**

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
BAGTOP v1.0
ranking / diversity / audit
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
Playlist Generator v5
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
- [x] Bondík mascot / team branding
- [x] README refresh with Quick Start and quality pipeline
- [x] CI validation on push and pull request

---

## 🚜 Discovery & Ranking

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

### BAGTOP v1.0

- [x] Score-based TOP selection
- [x] Diversity quality floor
- [x] Maximum per category family
- [x] Category-family grouping
- [x] Selection ledger with rank and reason
- [x] Full selection audit
- [x] Run manifest
- [x] Metadata cache validation
- [x] Automatic repair of corrupt automatic metadata cache
- [x] Verified-cache fallback after metadata refresh failure
- [x] Invalid explicit metadata rejection

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
- [x] First production testing → stable batch completed

The first verified production batch moved channels through the controlled
testing-to-stable lifecycle instead of publishing directly from discovery.

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

Current CI snapshot:

- **39** validated channel records
- **29** channels in the stable Ultimate playlist
- **16** country playlists
- **14** category playlists
- **22** provider playlists

Progress:

- [x] CZ/SK discovery pipeline
- [x] Manual provenance workflow
- [x] Candidate ranking and audit
- [x] Testing lifecycle
- [x] Stable promotion lifecycle
- [x] First production testing → stable promotion
- [ ] Expand verified Czech channels
- [ ] Expand verified Slovak channels
- [ ] Improve channel logos and EPG metadata
- [ ] Remove obsolete sources

---

## 🧪 Quality

- [x] Hunter tests
- [x] Candidate Gate tests
- [x] BAGTOP regression tests
- [x] AUTO-PROMOTION and provenance tests
- [x] Testing Promotion Gate tests
- [x] STABLE PROMOTION tests
- [x] Stream and EPG automation tests
- [x] CI compiles production Python tooling
- [x] CI verifies generated playlists remain synchronized
- [x] **359 tests passing + 22 subtests passing**

A working stream is not automatically trusted.

A trusted testing stream is not automatically stable.

A high-scoring candidate is not automatically published.

---

## 🚀 Release Readiness

- [x] Central channel database
- [x] Stable-only playlist generation
- [x] Discovery and candidate-review pipeline
- [x] Auditable candidate ranking with BAGTOP v1.0
- [x] Provenance-aware testing promotion
- [x] Long-term testing gate
- [x] Controlled stable promotion
- [x] First real production stable batch
- [x] Automated CI test suite
- [x] Team branding and README refresh
- [ ] Expand the verified CZ/SK curated set
- [ ] Improve CZ/SK EPG and channel logos
- [ ] Final documentation review
- [ ] Prepare the next stable public release

---

## 🎯 Next Priorities

1. Expand verified CZ/SK candidates while preserving the quality floor.
2. Improve EPG mappings, channel logos and provenance metadata.
3. Finish documentation/release review and prepare the next stable public release.

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

**Open • Free • Community • Verified IPTV**

> **Když to přehraje Bondík, přehraje to každý.**
