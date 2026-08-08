# ⚙️ Configuration

This directory contains the central configuration for **Bondik TV Ultimate**.

## Files

### `settings.yaml`
Global project, playlist and generator settings.

### `countries.yaml`
Supported countries, ISO country codes, flags and primary languages.

### `categories.yaml`
Official content categories and their target playlist files.

### `groups.yaml`
Rules used to generate IPTV `group-title` values.

### `quality.yaml`
Validation rules for channels, metadata and playlist inclusion.

## Architecture

```text
channels/channels.yaml
        ↓
config/*.yaml
        ↓
tools/checker
        ↓
tools/generator
        ↓
playlists/