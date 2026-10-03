# BTV-S01 — Archive Evidence Index v1

This is the tenth concrete Bondík City block.

The Archive does not copy project evidence. It creates a compact read-only catalog of known city evidence surfaces so humans and future agents can answer: what evidence exists here, which protocol does it use, and is it the same file I saw before?

## Protocol

    bondik-city-archive-index/1

Builder:

    tools/city/build_archive_index.py

Default output:

    city-archive-index.json

## Indexed evidence

v1 knows these surfaces:

- config/city-capabilities.json
- config/city-signal.json
- city-health-snapshot.json
- city-github-snapshot.json
- city-status.md

For each available file the Archive records path, evidence kind, byte size, SHA-256 digest, and detected Bondík City protocol when present.

Missing generated artifacts are recorded as unavailable rather than treated as an error or as healthy/current evidence.

## Privacy and duplication boundary

    content = not-copied
    mutation = not-allowed
    execution = not-exposed

The digest is provenance metadata, not an authenticity guarantee by itself.

## Generated local outputs

The city runtime outputs are local evidence products and are ignored by Git:

- city-health-snapshot.json
- city-github-snapshot.json
- city-status.md
- city-archive-index.json

This keeps local inspection artifacts from accidentally entering commits.

## Verification

From repository root:

    py tools/city/build_archive_index.py
    Get-Content -Encoding utf8 .\city-archive-index.json
    py -m pytest tools/checker/tests/test_city_archive_index.py -q
    py -m pytest tools/checker/tests -q

Architecture rule:

**archive provenance, not duplicate truth.**
