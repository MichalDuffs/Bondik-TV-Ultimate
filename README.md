# đź“ş Bondik TV Ultimate

<p align="center">
  <img src="assets/logo/bondik-tv-logo.png" width="500" alt="Bondik TV Ultimate Logo">
</p>

<p align="center">
  <strong>Quality before quantity.</strong><br>
  Open â€˘ Free â€˘ Community â€˘ Verified IPTV
</p>

<p align="center">

![CI](https://github.com/MichalDuffs/Bondik-TV-Ultimate/actions/workflows/playlist-check.yml/badge.svg)
![Version](https://img.shields.io/badge/version-1.0-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![IPTV](https://img.shields.io/badge/IPTV-M3U-orange)
![EPG](https://img.shields.io/badge/EPG-Supported-blueviolet)

</p>

---

## đźŚŤ Welcome

**Bondik TV Ultimate** is a free and open-source IPTV playlist project focused on verified public streams, simple playlists and transparent quality control.

The current priority is **high-quality CZ/SK coverage**, not the highest possible channel count.

A working stream is not automatically trusted.  
A trusted testing stream is not automatically stable.

---

## â–¶ď¸Ź Quick Start

The main public playlist is:

```text
https://raw.githubusercontent.com/MichalDuffs/Bondik-TV-Ultimate/main/playlists/ultimate.m3u
```

Paste the URL into a compatible IPTV player.

Public playlists are generated from channels that have reached **stable** status. Testing candidates stay out of the public playlist until they pass the quality process.

- â­ [Ultimate playlist](playlists/ultimate.m3u)
- đźŚŤ [Country playlists](playlists/countries/)
- đźŽ¬ [Category playlists](playlists/categories/)
- đź“ˇ [Provider playlists](playlists/providers/)

---

## đź›ˇď¸Ź Quality Pipeline

```text
Public M3U sources
        â†“
M3U Hunter v0.9
        â†“
Candidate Gate v0.5.1
        â†“
Candidate ranking / audit
BAGTOP v1.0
        â†“
Manual provenance review
        â†“
AUTO-PROMOTION v1.1
        â†“
status=testing
        â†“
Testing Promotion Gate v0.7.1
        â†“
3 counted passes / minimum 24h gap
        â†“
Manual stable review
        â†“
STABLE PROMOTION v1.0
        â†“
status=stable
        â†“
Playlist Generator
        â†“
Public Bondik TV playlists
```

No candidate moves directly from discovery into the stable public playlist.

Automation helps us find, test and organize channels â€” it does **not** bypass human quality control.

---

## đźšś Tooling

- đź”Ž **M3U Hunter v0.9** â€” bulk discovery, country filtering, deep HLS verification and history
- đźš¦ **Candidate Gate v0.5.1** â€” scoring, deduplication and priority / review / parking buckets
- đźšś **BAGTOP v1.0** â€” quality ranking, diversity controls, category-family caps, full selection audit and run manifest
- đź›ˇď¸Ź **AUTO-PROMOTION v1.1** â€” provenance and risk gates before a candidate can enter testing
- đź§Ş **Testing Promotion Gate v0.7.1** â€” spaced health passes with reset protection
- âś… **STABLE PROMOTION v1.0** â€” controlled human-approved move from testing to stable
- đź“ˇ **Stream health monitoring** â€” scheduled checks, outage streaks, recovery detection and issue automation
- đź“… **EPG tooling** â€” source validation, monitoring and maintenance planning
- đź¤– **GitHub Actions CI** â€” tests, metadata validation and playlist synchronization on every push / PR

The checker suite contains **300+ automated regression tests**, and CI validates the repository before changes are considered healthy.

---

## âś¨ Features

- â­ Stable-only Ultimate playlist
- đźŚŤ Country playlists
- đźŽ¬ Category playlists
- đź“ˇ Provider playlists
- đź“… EPG support
- đź”Ž Automated stream discovery
- đź›ˇď¸Ź Provenance and risk gates
- đź§Ş Testing â†’ stable lifecycle
- đź“Š Auditable candidate ranking
- âť¤ď¸Ź Community driven
- đźš€ Free and open source

---

## đź“‚ Repository Structure

```text
assets/        branding and graphics
channels/      source-of-truth channel metadata
docs/          project documentation
epg/           EPG configuration and data
playlists/     generated public playlists
tools/         discovery, QC, promotion and generator tools
.github/       CI and scheduled automation
```

`channels/channels.yaml` is the central source of truth. Public playlists are generated from it.

---

## đź“… EPG & Stream Health

Supported channels can include Electronic Program Guide metadata.

The project also contains scheduled stream and EPG monitoring, retry protection, failure history and maintenance tooling so temporary outages do not automatically become permanent decisions.

---

## đź“± Supported Platforms

M3U playlists can be used with compatible players on platforms such as:

- Android / Android TV
- Windows
- Linux
- macOS
- iPhone / iPad / Apple TV
- LG webOS
- Samsung Tizen
- Fire TV

Player support depends on the application and stream format.

---

## đź—şď¸Ź Project Status

The core discovery and quality-control pipeline is already in place. Current work focuses on:

- đź‡¨đź‡ż expanding verified Czech coverage
- đź‡¸đź‡° expanding verified Slovak coverage
- đź“… improving CZ/SK EPG mappings
- đź–Ľď¸Ź improving channel logos and metadata
- âś… exercising the full production testing â†’ stable lifecycle
- đź“š keeping documentation aligned with the tooling

For the detailed plan see [ROADMAP.md](ROADMAP.md).  
For recent changes see [CHANGELOG.md](CHANGELOG.md).

---

## đź¦® NaĹˇe filozofie

NevytvĂˇĹ™Ă­me projekt pro zisk.

VytvĂˇĹ™Ă­me projekt, kterĂ˝ bychom sami chtÄ›li pouĹľĂ­vat.

**Open Source. Zdarma. KomunitnĂ­. S respektem k autorĹŻm obsahu.**

> **KdyĹľ to pĹ™ehraje BondĂ­k, pĹ™ehraje to kaĹľdĂ˝.**

---

## đź¤ť Contributing

Contributions are welcome â€” especially verified stream fixes, EPG improvements, documentation and reproducible bug reports.

Please read:

- [CONTRIBUTING.md](.github/CONTRIBUTING.md)
- [CODE_OF_CONDUCT.md](.github/CODE_OF_CONDUCT.md)

---

## â„ąď¸Ź Content Notice

Bondik TV Ultimate does not host television or video content. The project organizes playlist metadata and references publicly reachable stream URLs. Availability, ownership and distribution rights remain with the respective providers and rights holders.

---

## đź“ś License

This project is licensed under the [MIT License](LICENSE).

---

## âť¤ď¸Ź Special Thanks

Thanks to everyone who supports the project and helps improve it.

Special appreciation goes to our four-legged quality inspector:

đźľ **BondĂ­k â€” Chief Quality Officer (CQO)** đź¦®

<p align="center">
  Made with âť¤ď¸Ź by the Open Source community.<br>
  Tested with đźľ by BondĂ­k.
</p>

---

â­ Dej projektu hvÄ›zdiÄŤku.  
đźŤ´ Forkni projekt.  
đź¤ť PĹ™ispÄ›j.  
đź“˘ SdĂ­lej Bondik TV Ultimate.  
đź¦® StaĹ se ÄŤlenem Bondik komunity.

### đź¦® BondĂ­k Ĺ™Ă­kĂˇ:

> â€žNefunguje nÄ›jakĂ˝ kanĂˇl? NevadĂ­. PoĹˇli Pull Request. JĂˇ zatĂ­m pohlĂ­dĂˇm buĹ™ty.â€ś

đź¶đź”ĄđźŚ­

