# BTV-S01 — Storage Adapter Foundation v1

This is the fourteenth concrete Bondík City block.

The Storage Hub defines one persistence contract for local product and city
state instead of allowing every future module to invent its own semantics.

## Protocols

Adapter contract:

    bondik-city-storage-adapter/1

Record envelope:

    bondik-city-storage-record/1

Reference file format:

    bondik-city-storage-file/1

Declarative contract:

    config/city-storage-contract.json

Reference implementation:

    tools/city/storage_adapter.py

## Semantics

v1 defines four operations:

- read
- write
- delete
- list

Records are namespaced and versioned. Each key has a monotonic revision.

Writes and deletes can supply expected_revision. A stale revision fails instead
of silently overwriting newer state.

JSON values are bounded to 64 KiB.

## Reference adapters

v1 includes:

- MemoryStorageAdapter for deterministic tests and temporary state
- JsonFileStorageAdapter for local durable state

The file adapter writes through a temporary file plus os.replace so a completed
write replaces the prior document atomically on the local filesystem.

## Existing Web and Android session state

This block does not silently rewrite the existing Web localStorage or Android
session persistence seams.

The contract is active; migration of those platform-specific stores onto this
adapter semantics is intentionally tracked as later slices.

That keeps working product behavior intact while establishing the shared
persistence boundary first.

## Agent boundary

Storage mutation is application-local infrastructure.

The capability remains agent execution = not-exposed and the storage contract
does not create network access or AI write authority.

## Verification

From repository root:

    py tools/city/storage_adapter.py
    py -m pytest tools/checker/tests/test_city_storage_adapter.py -q
    py -m pytest tools/checker/tests -q

Architecture rule:

**share persistence semantics first; migrate platform stores without breaking
their existing state.**
