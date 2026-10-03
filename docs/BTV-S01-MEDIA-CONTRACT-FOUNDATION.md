# BTV-S01 — Media Contract Foundation v1

This is the fifteenth concrete Bondík City block.

The Media Gateway defines one reusable media-source shape between catalog
selection and platform playback without moving player control into the contract.

## Protocols

Contract:

    bondik-city-media-contract/1

Resolved media source:

    bondik-city-media-source/1

Declarative contract:

    config/city-media-contract.json

Reference resolver:

    tools/city/media_contract.py

## Current source of truth

v1 reads the existing channel catalog:

    channels/channels.yaml

The current catalog contains 39 channels and uses HLS streams.

The contract preserves existing stream URLs and optional string headers. It does
not rewrite, probe, repair, or replace stream sources.

## Resolved source shape

Each resolved source contains:

- sourceId,
- kind = live-tv-channel,
- displayName,
- media URI,
- media format,
- request headers,
- channel identity/metadata,
- catalog provenance,
- non-execution exposure contract.

## Deliberate v1 limits

v1 supports the media reality already present in the catalog:

    supportedFormats = hls
    urlSchemes = http, https

DASH and other formats can be added through an explicit protocol evolution or
reviewed contract change rather than being implied before the catalog uses them.

## Existing Web and Android playback

This slice does not migrate Web hls.js or Android Media3/ExoPlayer onto the new
contract yet.

The Android ChannelSelector remains separate from player control. The Media
Contract creates the reusable source shape that a later adapter can consume.

No existing playback behavior is deleted.

## Safety

The contract does not expose playback execution to agents:

    playbackExecution = not-exposed
    agentExecution = not-exposed
    networkMutation = not-exposed

## Verification

From repository root:

    py tools/city/media_contract.py
    py -m pytest tools/checker/tests/test_city_media_contract.py -q
    py -m pytest tools/checker/tests -q

Architecture rule:

**selection chooses a source; the media contract describes it; the player decides
how to play it.**
