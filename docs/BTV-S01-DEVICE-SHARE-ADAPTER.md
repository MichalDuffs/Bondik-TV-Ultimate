# BTV-S01 — Device Share Adapter v1

This is the sixteenth concrete Bondík City block.

The Device Dock prepares a versioned handoff envelope between an approved media
source and a logical target device without performing discovery, networking, or
playback.

## Protocols

Adapter contract:

    bondik-city-device-share-adapter/1

Prepared handoff:

    bondik-city-device-handoff/1

Declarative contract:

    config/city-device-share-contract.json

Reference implementation:

    tools/city/device_share_adapter.py

## v1 target

v1 supports one logical target kind:

    android-tv

The target contains only:

- targetId,
- kind,
- displayName.

Network addresses, URLs, endpoints, tokens, or discovery results are not
accepted into the target descriptor.

## Relationship to Media Gateway

The adapter resolves an approved catalog channel through the Media Contract and
embeds that resolved source into a prepared handoff.

The adapter does not rewrite the source.

It does not call Android Media3/ExoPlayer, Web hls.js, casting APIs, sockets, or
device discovery.

## Delivery state

Every v1 handoff remains:

    state = prepared
    transport = not-selected
    endpoint = null

This means the system can prepare the intent to share without pretending that a
real TV has been found or contacted.

## Safety

The handoff exposure contract remains:

    network = not-exposed
    execution = not-exposed
    agentExecution = not-exposed
    mutation = not-allowed

## Future slices

A later reviewed slice may add:

- device discovery,
- transport selection,
- Android TV receiver integration,
- user-approved delivery,
- delivery receipts.

Those are intentionally separate because they cross the current local-only
boundary.

## Verification

From repository root:

    py tools/city/device_share_adapter.py
    py -m pytest tools/checker/tests/test_city_device_share_adapter.py -q
    py -m pytest tools/checker/tests -q

Architecture rule:

**prepare the handoff first; discover and deliver only through a later explicit
permission boundary.**
