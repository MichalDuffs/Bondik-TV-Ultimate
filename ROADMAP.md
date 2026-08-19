# 🗺️ Bondik TV Ultimate Roadmap

This roadmap reflects the current state and long-term direction of Bondik TV Ultimate.

Our priority is quality over quantity: a clean, transparent and maintainable IPTV project built around verified public streams and simple automation.

---

# 🐾 M3U Hunter v0.4

M3U Hunter hromadně prohledává a ověřuje streamy z veřejných M3U zdrojů a GitHub repozitářů.

Aktuální funkce:

- 🌍 filtrování podle země (`--country CZ`, `--country SK`)
- 🔎 hromadné ověřování stream profilů
- 📺 hluboká HLS kontrola až na dostupný media segment
- 🧹 deduplikace stream profilů
- 🦴 porovnání s již známými streamy (`--known-source`)
- 🆕 hledání pouze nových kandidátů (`--new-only`)
- 🧠 persistentní historie mezi běhy (`--history-file`)
- ✅ počítání úspěšných a neúspěšných kontrol
- 🔁 sledování série úspěšných kontrol (`success_streak`)
- 🏷️ hodnocení stability: `observing` → `promising` → `stable-candidate`

`stable-candidate` znamená technicky stabilního kandidáta podle opakovaných kontrol.
Neznamená automatické zařazení do stabilního playlistu — finální výběr stále podléhá Bondík QC.

## 🇨🇿 Příklad CZ lovu s historií

```powershell
python tools/checker/hunt_m3u.py https://github.com/iptv-org/iptv `
    --country CZ `
    --history-file hunt-history.json `
    --out-dir hunt-results
---

# Version 1.x - Foundation

## Repository

- [x] Repository structure
- [x] Documentation baseline
- [x] Assets structure
- [x] Playlist structure
- [x] Central channel database
- [x] Configuration system
- [ ] Complete graphics package
- [ ] Complete documentation
- [ ] Stable public release

---

# Version 2.x - Automation & Quality

## Playlist Automation

- [x] Playlist generator
- [x] Country playlists
- [x] Category playlists
- [x] Provider playlists
- [x] Ultimate playlist
- [x] Generated playlist cleanup
- [x] Metadata validation

## Stream Health

- [x] Stream checker
- [x] Dead link detection
- [x] Temporary failure retries
- [x] Scheduled stream health checks
- [x] Stream health reports
- [x] Archived GitHub Actions reports
- [x] Cross-run failure history
- [x] Recovery detection
- [x] Repeated outage detection
- [x] Automatic GitHub Issue management
- [x] Stream health automation refactor
- [x] Automated monitoring test suite
- [x] Persistent failure streak tracking
- [x] Outage escalation comments
- [x] Escalation comment throttling

## EPG

- [ ] Improve EPG coverage
- [ ] Automatic EPG updates
- [x] Validate EPG identifiers
- [x] Automated EPG source health checks
- [x] EPG source registry validation

---

# Version 3.x - Content & Community

## Content

- [ ] Expand curated CZ/SK channel set
- [ ] Expand country coverage
- [ ] Expand category coverage
- [ ] Improve channel logos
- [ ] Improve EPG metadata
- [ ] Continue quality-first stream verification

## Community

- [ ] Community contribution workflow
- [ ] Contributor documentation
- [ ] Translation support
- [ ] Community playlists
- [ ] Statistics dashboard

---

# Version 4.x - Applications

## Applications

- [ ] Android application
- [ ] Android TV application
- [ ] Windows application
- [ ] Linux support
- [ ] Web application
- [ ] Remote management

---

# 🐾 Project Milestones

## Phase 1 - Foundation

- [x] Repository structure
- [x] Documentation baseline
- [x] Basic playlists
- [x] Branding preparation
- [x] Configuration architecture

## Phase 2 - Content

- [x] CZ/SK foundation
- [x] Channel metadata structure
- [ ] More verified channels
- [ ] Better logo coverage
- [ ] Better EPG coverage
- [ ] Broader international coverage

## Phase 3 - Automation

- [x] Playlist generation
- [x] Stream checker
- [x] Scheduled health monitoring
- [x] Retry protection
- [x] Historical failure tracking
- [x] Recovery detection
- [x] Automated outage Issues
- [x] Health reports and artifacts
- [x] Maintainable stream health automation
- [x] Automated monitoring test suite
- [x] Persistent outage tracking and escalation
- [x] Scheduled EPG health monitoring
- [x] Automatic EPG maintenance

## Phase 4 - Applications

- [ ] Android app
- [ ] Android TV app
- [ ] Windows app
- [ ] Linux support
- [ ] Web interface
- [ ] Remote management

---

# 🚀 Long-Term Vision

Bondik TV Ultimate aims to become a highly organized, transparent and community-friendly IPTV project.

The project will remain focused on:

- Quality over quantity
- Publicly available streams
- Simple installation and use
- Reliable automated validation
- Clean repository architecture
- Open-source development
- Free access without unnecessary complexity

---

🐾 **Bondik TV Ultimate**

**Open • Free • Community**

> When Bondík can play it, everyone can play it.