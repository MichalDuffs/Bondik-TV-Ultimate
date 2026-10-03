# BTV-S01 — Control Tower GitHub Panel v1

This is the ninth concrete Bondík City block.

The GitHub Service from block #8 already creates a machine-readable repository
snapshot. This slice wires that evidence into the human Control Tower status
board.

## Relationship

Machine-readable evidence:

    city-github-snapshot.json
    bondik-city-github-service/1

Human-readable projection:

    city-status.md
    bondik-city-status-board/1

The status board does not query GitHub directly. It reads the snapshot produced
by the GitHub Service, so collection and presentation remain separate.

## What the panel shows

- repository name,
- exact default-branch HEAD,
- open PR count,
- open issue count,
- workflow source window and truncation flag,
- latest observed default-branch run for each workflow,
- whether that workflow run matches the current default-branch HEAD.

Workflow freshness labels:

    current-main
    stale-vs-main

A successful workflow whose head SHA differs from the current main HEAD is not
silently presented as current-main evidence.

## Missing evidence

If the GitHub snapshot is absent, the panel reports UNKNOWN.

The board never converts missing GitHub evidence into a GREEN state.

## Safety boundary

The panel is a read-only projection.

It cannot:

- merge a PR,
- edit an issue,
- rerun a workflow,
- change repository files,
- expose a GitHub token,
- execute a city capability.

## Verification

From repository root, after block #8 has produced the GitHub snapshot:

    py tools/city/build_github_service_snapshot.py
    py tools/city/render_status_board.py
    Get-Content -Encoding utf8 .\city-status.md
    py -m pytest tools/checker/tests/test_city_status_board.py -q
    py -m pytest tools/checker/tests -q

Architecture rule:

**GitHub Service collects evidence; Control Tower projects evidence.**
