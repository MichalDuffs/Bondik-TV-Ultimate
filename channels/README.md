# 📺 Channel Database

The `channels/` directory contains the central channel database for
**Bondik TV Ultimate**.

`channels.yaml` is the single source of truth for all supported channels.

---

## 📂 Structure

channels/
├── README.md
└── channels.yaml

---

🧩 Channel Schema

Each channel may contain:

Unique ID
Channel name
Country
Language
Category
Provider
Stream URL
Stream format
Quality
EPG ID
Logo
Website
Status
Notes

---

🟢 Status
stable

Verified channel suitable for the main playlist.

testing

New or changed channel waiting for verification.

archived

Inactive or removed channel.

Archived channels are not included in generated playlists.

---

📺 Stream Formats

Supported values:

hls
dash
http
other

HLS (.m3u8) is preferred when available.

---

🎥 Quality

Typical values:

SD
HD
FHD
4K
unknown

Do not guess stream quality.

---

📅 EPG

EPG mapping uses the channel epg.id.

The value should match the XMLTV channel identifier whenever
possible.

---

🖼️ Logos

A channel may use:

an official remote logo URL
a local project asset
no logo if one is not available

Do not use unofficial or misleading branding.

---

🐾 Quality Rules

Before a channel receives stable status:

Stream must work
Country must be correct
Category must exist in config/categories.yaml
Country must exist in config/countries.yaml
Duplicate streams should be avoided
EPG should be tested when available
Official/public sources are preferred


---


⚙️ Data Flow
channels/channels.yaml
        ↓
config/*.yaml
        ↓
tools/checker
        ↓
tools/generator
        ↓
playlists/
├── countries/
├── categories/
├── providers/
└── ultimate.m3u

---

🐾 Quality checked by Bondík
channels.yaml = DATA 📋
README.md     = DOKUMENTACE 📖
config/       = PRAVIDLA ⚙️
playlists/    = VÝSTUP 📺