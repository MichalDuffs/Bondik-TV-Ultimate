# BTV-S01 — GitHub Service Snapshot v1

This is the eighth concrete Bondík City block.

The GitHub Service is a read-only repository evidence gateway for the city. It
lets Bondík City observe its public GitHub project state without giving the
service mutation authority.

## Protocol

```text
bondik-city-github-service/1
```

Collector:

```text
tools/city/build_github_service_snapshot.py
```

Default output:

```text
city-github-snapshot.json
```

## Live evidence

The collector reads fixed GitHub REST surfaces for the configured repository:

- repository metadata,
- exact default-branch HEAD,
- open pull requests,
- open issues, excluding pull requests,
- recent workflow runs.

For workflows, the snapshot keeps the newest observed run for each workflow on
the default branch. Feature-branch workflow runs do not replace default-branch
operational evidence.

The current request window is bounded to 100 items per collection. The snapshot
marks a collection as `truncated` when that window is full rather than
pretending it is exhaustive.

## Authentication

Public repositories can be read without a token.

If `GITHUB_TOKEN` is present, the collector may use it for authenticated
read-only GitHub API requests. The token is never written to the snapshot.

## Safety boundary

The service is read-only:

```text
mutation = not-allowed
token = not-exported
execution = not-exposed
```

It has no POST/PATCH/PUT/DELETE path and does not merge pull requests, edit
issues, rerun workflows, or write repository files.

## Verification

From repository root:

```powershell
py tools/city/build_github_service_snapshot.py
Get-Content -Encoding utf8 .\city-github-snapshot.json
py -m pytest tools/checker/tests/test_city_github_service.py -q
py -m pytest tools/checker/tests -q
```

The first command is intentionally a live read against GitHub. The focused unit
tests remain offline and deterministic.

## Future layers

This snapshot can later feed the Control Tower status board and the AI city
signal. Any future GitHub write capability must be a separate protocol and
permission boundary.

Architecture rule:

**GitHub is evidence first; mutation authority comes only later and explicitly.**
