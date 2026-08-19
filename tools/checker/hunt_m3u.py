#!/usr/bin/env python3
"""Bondik TV bulk M3U hunter v0.4.

v0.2 added robust EXTINF parsing, per-stream User-Agent/Referer support,
and deeper HLS validation down to a reachable media segment/object.

v0.3 adds country-aware candidate filtering while keeping the existing
regex matcher available for additional fine-grained filtering.

v0.4 adds persistent result history for tracking stream stability
across multiple hunter runs.

v0.5 adds stability-based filtering of candidates from persistent history.

v0.6 adds review export for stability-filtered candidates.

v0.7 adds human-readable QC review reporting for filtered candidates.

v0.8 adds machine-readable promotion candidate export for manual QC approval.

v0.9 adds manual QC decision input and approved-candidate proposal export.

The tool checks URLs already present in supplied public/local playlists.
It does not bypass authentication, DRM, geo-blocking, or access controls.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

VERSION = "0.9"
USER_AGENT = f"Bondik-TV-Ultimate-M3U-Hunter/{VERSION}"
DEFAULT_TIMEOUT = 8.0
DEFAULT_WORKERS = 20
MAX_SOURCE_BYTES = 12 * 1024 * 1024
MAX_HLS_BYTES = 256 * 1024
PROBE_BYTES = 8192
SEGMENT_BYTES = 4096
MAX_HLS_DEPTH = 3

ATTR_RE = re.compile(r'([\w-]+)="((?:\\.|[^"])*)"')
GITHUB_REPO_RE = re.compile(
    r"^https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/#?]+?)(?:\.git)?/?(?:[?#].*)?$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Channel:
    name: str
    url: str
    group: str = ""
    tvg_id: str = ""
    tvg_name: str = ""
    source: str = ""
    user_agent: str = ""
    referer: str = ""


@dataclass
class Result:
    name: str
    url: str
    group: str
    tvg_id: str
    tvg_name: str
    source: str
    user_agent: str
    referer: str
    ok: bool
    http_status: int | None
    response_ms: int | None
    content_type: str
    final_url: str
    validation: str
    detail: str

    @property
    def rank_key(self) -> tuple:
        return (
            0 if self.ok else 1,
            self.response_ms if self.response_ms is not None else 10**9,
            self.name.casefold(),
            self.url,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=f"Bondik M3U Hunter v{VERSION}: bulk M3U stream checker."
    )
    parser.add_argument(
        "sources",
        nargs="*",
        help="Local M3U, playlist URL, GitHub blob URL, or GitHub repository URL.",
    )
    parser.add_argument("--source-list", type=Path)
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument("--match")
    parser.add_argument("--country",
        action="append",
        default=[],
        metavar="CODE",
        help="Filter channels by country code (for example CZ or SK). May be repeated.",
    )
    parser.add_argument(
        "--known-source",
        action="append",
        default=[],
        metavar="SOURCE",
        help="Known Bondik playlist/source used to identify already known stream profiles. May be repeated.",
    )
    parser.add_argument(
        "--new-only",
        action="store_true",
        help="Output and report only working stream profiles not present in known sources.",
    )
    parser.add_argument(
        "--history-file",
        type=Path,
        help="Persistent JSON history used to track stream results across hunter runs.",
    )
    parser.add_argument(
        "--stability",
        choices=["observing", "promising", "stable-candidate"],
        help="Filter output by stability label from persistent history.",
    )
    parser.add_argument(
    "--review-out",
        type=Path,
        help="Write stability-filtered candidates to a separate review M3U file.",
    )
    parser.add_argument(
        "--review-report",
        type=Path,
        help="Write a human-readable QC review report for filtered candidates.",
    )
    parser.add_argument(
    "--promotion-out",
    type=Path,
    help="Write machine-readable promotion candidates for manual QC approval.",
    )
    parser.add_argument(
    "--decision-file",
    type=Path,
    help="Read manual QC decisions for promotion candidates.",
    )
    parser.add_argument(
    "--approved-out",
    type=Path,
    help="Write manually approved candidates to an M3U proposal.",
    )
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--out-dir", type=Path, default=Path("hunt-results"))
    return parser.parse_args()


def github_blob_to_raw(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if parsed.netloc.casefold() != "github.com":
        return url
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) >= 5 and parts[2] == "blob":
        owner, repo, _, branch = parts[:4]
        rest = "/".join(parts[4:])
        return f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{rest}"
    return url


def build_headers(
    user_agent: str = "",
    referer: str = "",
    range_bytes: int | None = None,
) -> dict[str, str]:
    headers = {
        "User-Agent": user_agent or USER_AGENT,
        "Accept": "*/*",
        "Accept-Encoding": "identity",
    }
    if referer:
        headers["Referer"] = referer
    if range_bytes:
        headers["Range"] = f"bytes=0-{range_bytes - 1}"
    return headers


def request_bytes(
    url: str,
    timeout: float,
    *,
    max_bytes: int,
    user_agent: str = "",
    referer: str = "",
    range_bytes: int | None = None,
    strict_size: bool = False,
) -> tuple[bytes, int, str, str]:
    req = urllib.request.Request(
        url,
        headers=build_headers(user_agent, referer, range_bytes),
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        data = response.read(max_bytes + (1 if strict_size else 0))
        if strict_size and len(data) > max_bytes:
            raise ValueError(f"response exceeds {max_bytes} bytes")
        data = data[:max_bytes]
        status = int(getattr(response, "status", None) or response.getcode())
        return (
            data,
            status,
            response.headers.get("Content-Type", ""),
            response.geturl(),
        )


def fetch_json(url: str, timeout: float) -> dict:
    payload, _, _, _ = request_bytes(
        url,
        timeout,
        max_bytes=4 * 1024 * 1024,
        strict_size=True,
    )
    return json.loads(payload.decode("utf-8"))


def discover_github_playlists(repo_url: str, timeout: float) -> list[str]:
    match = GITHUB_REPO_RE.match(repo_url)
    if not match:
        return []

    owner = match.group("owner")
    repo = match.group("repo")
    metadata = fetch_json(f"https://api.github.com/repos/{owner}/{repo}", timeout)
    branch = metadata.get("default_branch") or "main"
    tree = fetch_json(
        f"https://api.github.com/repos/{owner}/{repo}/git/trees/"
        f"{urllib.parse.quote(branch, safe='')}?recursive=1",
        timeout,
    )

    urls = []
    for item in tree.get("tree", []):
        if item.get("type") != "blob":
            continue
        path = str(item.get("path", ""))
        if Path(path).suffix.casefold() not in {".m3u", ".m3u8"}:
            continue
        quoted = urllib.parse.quote(path, safe="/")
        urls.append(
            f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{quoted}"
        )

    if tree.get("truncated"):
        print(
            f"WARNING: GitHub tree for {owner}/{repo} was truncated.",
            file=sys.stderr,
        )
    return urls


def read_source_list(path: Path) -> list[str]:
    result = []
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            result.append(line)
    return result


def load_playlist(source: str, timeout: float) -> str:
    candidate = github_blob_to_raw(source)
    parsed = urllib.parse.urlparse(candidate)

    if parsed.scheme in {"http", "https"}:
        body, _, content_type, _ = request_bytes(
            candidate,
            timeout,
            max_bytes=MAX_SOURCE_BYTES,
            strict_size=True,
        )
        try:
            text = body.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = body.decode("latin-1")

        if "#EXTM3U" not in text[:4096] and "mpegurl" not in content_type.casefold():
            raise ValueError("source does not look like an M3U playlist")
        return text

    return Path(candidate).read_text(
        encoding="utf-8-sig",
        errors="replace",
    )


def split_unquoted_comma(value: str) -> tuple[str, str]:
    in_quotes = False
    escaped = False
    for index, char in enumerate(value):
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == '"':
            in_quotes = not in_quotes
            continue
        if char == "," and not in_quotes:
            return value[:index], value[index + 1 :]
    return value, ""


def parse_extinf(line: str) -> dict[str, str]:
    payload = line[len("#EXTINF:") :]
    metadata, name = split_unquoted_comma(payload)
    parts = metadata.strip().split(maxsplit=1)
    attrs_text = parts[1] if len(parts) > 1 else ""

    attrs = {
        key.casefold(): value
        for key, value in ATTR_RE.findall(attrs_text)
    }

    return {
        "name": name.strip(),
        "group": attrs.get("group-title", "").strip(),
        "tvg-id": attrs.get("tvg-id", "").strip(),
        "tvg-name": attrs.get("tvg-name", "").strip(),
        "user-agent": (
            attrs.get("http-user-agent")
            or attrs.get("user-agent")
            or ""
        ).strip(),
        "referer": (
            attrs.get("http-referrer")
            or attrs.get("http-referer")
            or attrs.get("referer")
            or ""
        ).strip(),
    }


def parse_m3u(text: str, source: str) -> list[Channel]:
    channels = []
    pending = None

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue

        if line.startswith("#EXTINF:"):
            pending = parse_extinf(line)
            continue

        if line.startswith("#EXTVLCOPT:") and pending is not None:
            key, sep, value = line[len("#EXTVLCOPT:") :].partition("=")
            if sep:
                key = key.strip().casefold()
                value = value.strip()
                if key == "http-user-agent":
                    pending["user-agent"] = value
                elif key in {"http-referrer", "http-referer"}:
                    pending["referer"] = value
            continue

        if line.startswith("#"):
            continue

        if not line.casefold().startswith(("http://", "https://")):
            pending = None
            continue

        meta = pending or {
            "name": "",
            "group": "",
            "tvg-id": "",
            "tvg-name": "",
            "user-agent": "",
            "referer": "",
        }
        channels.append(
            Channel(
                name=meta["name"] or meta["tvg-name"] or line,
                url=line,
                group=meta["group"],
                tvg_id=meta["tvg-id"],
                tvg_name=meta["tvg-name"],
                source=source,
                user_agent=meta["user-agent"],
                referer=meta["referer"],
            )
        )
        pending = None

    return channels


def dedupe_channels(channels: Iterable[Channel]) -> list[Channel]:
    seen = set()
    unique = []
    for channel in channels:
        key = (
            channel.url.strip(),
            channel.user_agent.strip(),
            channel.referer.strip(),
        )
        if not key[0] or key in seen:
            continue
        seen.add(key)
        unique.append(channel)
    return unique

def channel_profile_key(channel: Channel) -> tuple[str, str, str]:
    return (
        channel.url.strip(),
        channel.user_agent.strip(),
        channel.referer.strip(),
    )

def matches(channel: Channel, pattern: re.Pattern[str] | None) -> bool:
    if pattern is None:
        return True
    return pattern.search(
        " | ".join(
            [channel.name, channel.group, channel.tvg_id, channel.tvg_name]
        )
    ) is not None

def source_country(source: str) -> str:
    parsed = urllib.parse.urlparse(source)
    path = parsed.path.casefold()

    match = re.search(r"/streams/([a-z]{2})\.m3u8?$", path)
    if match:
        return match.group(1).upper()

    match = re.search(r"/countries/([a-z]{2})\.m3u8?$", path)
    if match:
        return match.group(1).upper()

    return ""


def matches_country(channel: Channel, countries: set[str]) -> bool:
    if not countries:
        return True
    return source_country(channel.source) in countries

def load_known_profiles(sources: list[str], timeout: float) -> set[tuple[str, str, str]]:
    known = set()

    for source in sources:
        for expanded_source in expand_sources([source], timeout):
            text = load_playlist(expanded_source, timeout)
            for channel in parse_m3u(text, expanded_source):
                known.add(channel_profile_key(channel))

    return known

def load_history(path: Path | None) -> dict:
    if path is None or not path.exists():
        return {}

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid history file: {exc}") from exc

def save_history(path: Path | None, history: dict) -> None:
    if path is None:
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(history, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

def stability_label(entry: dict) -> str:
    streak = int(entry.get("success_streak", 0))
    failures = int(entry.get("failure_count", 0))

    if streak >= 3 and failures == 0:
        return "stable-candidate"
    if streak >= 2:
        return "promising"
    return "observing"

def matches_stability(
    channel: Channel,
    history: dict,
    wanted: str | None,
) -> bool:
    if not wanted:
        return True

    key = " | ".join(
        [
            channel.url.strip(),
            channel.user_agent.strip(),
            channel.referer.strip(),
        ]
    )

    entry = history.get(key)
    if not entry:
        return False

    return entry.get("stability") == wanted

def update_history(history: dict, results: list[Result]) -> dict:
    now = int(time.time())

    for result in results:
        key = " | ".join(
            [
                result.url.strip(),
                result.user_agent.strip(),
                result.referer.strip(),
            ]
        )

        entry = history.setdefault(
            key,
            {
                "name": result.name,
                "success_count": 0,
                "failure_count": 0,
                "last_ok": None,
                "last_seen": None,
                "success_streak": 0,
            },
        )

        entry["name"] = result.name
        entry["last_seen"] = now
        entry.setdefault("success_streak", 0)

        if result.ok:
            entry["success_count"] += 1
            entry["success_streak"] += 1
            entry["last_ok"] = now
        else:
            entry["failure_count"] += 1
            entry["success_streak"] = 0
        entry["stability"] = stability_label(entry)

    return history

def looks_like_html(content_type: str, body: bytes) -> bool:
    prefix = body.lstrip()[:256].lower()
    return (
        "text/html" in content_type.casefold()
        or prefix.startswith(b"<!doctype html")
        or prefix.startswith(b"<html")
    )


def is_hls(url: str, content_type: str, body: bytes) -> bool:
    return (
        urllib.parse.urlparse(url).path.casefold().endswith(".m3u8")
        or "mpegurl" in content_type.casefold()
        or body.lstrip()[:64].upper().startswith(b"#EXTM3U")
    )


def hls_playlist_kind(text: str) -> str:
    upper = text.upper()
    if "#EXT-X-STREAM-INF" in upper or "#EXT-X-I-FRAME-STREAM-INF" in upper:
        return "master"
    if (
        "#EXTINF:" in upper
        or "#EXT-X-TARGETDURATION" in upper
        or "#EXT-X-MEDIA-SEQUENCE" in upper
        or "#EXT-X-MAP:" in upper
    ):
        return "media"
    return "unknown"


def first_master_variant(text: str) -> str | None:
    waiting = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.upper().startswith("#EXT-X-STREAM-INF:"):
            waiting = True
            continue
        if waiting and not line.startswith("#"):
            return line
    return None


def first_media_uri(text: str) -> str | None:
    for raw in text.splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            return line

    for raw in text.splitlines():
        line = raw.strip()
        if line.upper().startswith("#EXT-X-MAP:"):
            match = re.search(r'URI="([^"]+)"', line, re.IGNORECASE)
            if match:
                return match.group(1)
    return None


def fetch_hls_playlist(
    url: str,
    channel: Channel,
    timeout: float,
) -> tuple[str, str]:
    body, status, content_type, final_url = request_bytes(
        url,
        timeout,
        max_bytes=MAX_HLS_BYTES,
        user_agent=channel.user_agent,
        referer=channel.referer,
    )
    if not (200 <= status < 400):
        raise ValueError(f"HTTP {status}")
    if not body:
        raise ValueError("empty HLS playlist")
    if looks_like_html(content_type, body):
        raise ValueError("HLS playlist returned HTML")

    text = body.decode("utf-8-sig", errors="replace").lstrip()
    if not text.startswith("#EXTM3U"):
        raise ValueError("HLS URL returned non-M3U8 content")
    return text, final_url


def validate_hls(
    initial_body: bytes,
    initial_final_url: str,
    channel: Channel,
    timeout: float,
) -> tuple[bool, str, str, str, int | None]:
    text = initial_body.decode("utf-8-sig", errors="replace").lstrip()
    current_url = initial_final_url

    if not text.startswith("#EXTM3U"):
        return False, "hls", "HLS URL returned non-M3U8 content", current_url, None

    for _ in range(MAX_HLS_DEPTH):
        kind = hls_playlist_kind(text)

        if kind == "master":
            uri = first_master_variant(text)
            if not uri:
                return False, "hls-master", "master has no variant URI", current_url, None
            current_url = urllib.parse.urljoin(current_url, uri)
            try:
                text, current_url = fetch_hls_playlist(
                    current_url,
                    channel,
                    timeout,
                )
            except Exception as exc:
                return (
                    False,
                    "hls-variant",
                    f"variant failed: {type(exc).__name__}: {exc}",
                    current_url,
                    None,
                )
            continue

        if kind == "media":
            uri = first_media_uri(text)
            if not uri:
                return False, "hls-media", "media playlist has no media URI", current_url, None

            media_url = urllib.parse.urljoin(current_url, uri)
            try:
                body, status, content_type, final_url = request_bytes(
                    media_url,
                    timeout,
                    max_bytes=SEGMENT_BYTES,
                    user_agent=channel.user_agent,
                    referer=channel.referer,
                    range_bytes=SEGMENT_BYTES,
                )
            except urllib.error.HTTPError as exc:
                return False, "hls-segment", f"segment HTTP {exc.code}", media_url, exc.code
            except Exception as exc:
                return (
                    False,
                    "hls-segment",
                    f"segment failed: {type(exc).__name__}: {exc}",
                    media_url,
                    None,
                )

            if not (200 <= status < 400):
                return False, "hls-segment", f"segment HTTP {status}", final_url, status
            if not body:
                return False, "hls-segment", "empty media segment", final_url, status
            if looks_like_html(content_type, body):
                return False, "hls-segment", "segment returned HTML", final_url, status

            return True, "hls-segment", "OK: HLS media object reachable", final_url, status

        return (
            False,
            "hls",
            "M3U8 missing recognizable HLS master/media tags",
            current_url,
            None,
        )

    return False, "hls", "HLS nesting too deep", current_url, None


def probe(channel: Channel, timeout: float) -> Result:
    started = time.perf_counter()
    status = None
    content_type = ""
    final_url = channel.url

    try:
        body, status, content_type, final_url = request_bytes(
            channel.url,
            timeout,
            max_bytes=PROBE_BYTES,
            user_agent=channel.user_agent,
            referer=channel.referer,
            range_bytes=PROBE_BYTES,
        )

        if not (200 <= status < 400):
            raise ValueError(f"HTTP {status}")
        if not body:
            raise ValueError("empty response")
        if looks_like_html(content_type, body):
            raise ValueError("HTTP 200 returned HTML instead of media")

        if is_hls(final_url, content_type, body):
            ok, validation, detail, checked_url, checked_status = validate_hls(
                body,
                final_url,
                channel,
                timeout,
            )
            return Result(
                **asdict(channel),
                ok=ok,
                http_status=checked_status or status,
                response_ms=round((time.perf_counter() - started) * 1000),
                content_type=content_type,
                final_url=checked_url,
                validation=validation,
                detail=detail,
            )

        return Result(
            **asdict(channel),
            ok=True,
            http_status=status,
            response_ms=round((time.perf_counter() - started) * 1000),
            content_type=content_type,
            final_url=final_url,
            validation="http-media",
            detail="OK: non-HLS media response reachable",
        )

    except urllib.error.HTTPError as exc:
        return Result(
            **asdict(channel),
            ok=False,
            http_status=exc.code,
            response_ms=round((time.perf_counter() - started) * 1000),
            content_type=exc.headers.get("Content-Type", "") if exc.headers else "",
            final_url=getattr(exc, "url", channel.url),
            validation="http",
            detail=f"HTTP {exc.code}",
        )
    except Exception as exc:
        return Result(
            **asdict(channel),
            ok=False,
            http_status=status,
            response_ms=round((time.perf_counter() - started) * 1000),
            content_type=content_type,
            final_url=final_url,
            validation="http",
            detail=f"{type(exc).__name__}: {exc}",
        )


def write_csv(path: Path, results: list[Result]) -> None:
    fields = [
        "ok", "validation", "response_ms", "http_status", "name", "group",
        "tvg_id", "tvg_name", "url", "final_url", "content_type", "detail",
        "user_agent", "referer", "source",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for result in results:
            row = asdict(result)
            writer.writerow({field: row.get(field) for field in fields})


def write_json(path: Path, results: list[Result]) -> None:
    payload = {
        "hunter_version": VERSION,
        "total": len(results),
        "ok": sum(item.ok for item in results),
        "failed": sum(not item.ok for item in results),
        "deep_hls_ok": sum(
            item.ok and item.validation == "hls-segment"
            for item in results
        ),
        "results": [asdict(item) for item in results],
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def m3u_escape(value: str) -> str:
    return value.replace('"', "'").replace("\r", " ").replace("\n", " ")


def write_working_m3u(path: Path, results: list[Result]) -> None:
    lines = [f'#EXTM3U x-bondik-hunter-version="{VERSION}"']
    for item in results:
        if not item.ok:
            continue

        attrs = []
        if item.tvg_id:
            attrs.append(f'tvg-id="{m3u_escape(item.tvg_id)}"')
        if item.tvg_name:
            attrs.append(f'tvg-name="{m3u_escape(item.tvg_name)}"')
        if item.group:
            attrs.append(f'group-title="{m3u_escape(item.group)}"')
        attr_text = (" " + " ".join(attrs)) if attrs else ""

        lines.append(f'#EXTINF:-1{attr_text},{m3u_escape(item.name)}')
        if item.user_agent:
            lines.append(f"#EXTVLCOPT:http-user-agent={item.user_agent}")
        if item.referer:
            lines.append(f"#EXTVLCOPT:http-referrer={item.referer}")
        lines.append(item.url)

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

def write_review_m3u(path: Path | None, results: list[Result]) -> None:
    if path is None:
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    write_working_m3u(path, results)

def write_review_report(
    path: Path | None,
    results: list[Result],
    history: dict,
) -> None:
    if path is None:
        return

    path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        f"Bondik M3U Hunter v{VERSION} - QC Review Report",
        "=" * 60,
        "",
    ]

    for result in results:
        key = " | ".join(
            [
                result.url.strip(),
                result.user_agent.strip(),
                result.referer.strip(),
            ]
        )
        entry = history.get(key, {})

        lines.extend(
            [
                f"Name: {result.name}",
                f"Stability: {entry.get('stability', 'unknown')}",
                f"Success count: {entry.get('success_count', 0)}",
                f"Failure count: {entry.get('failure_count', 0)}",
                f"Success streak: {entry.get('success_streak', 0)}",
                f"Validation: {result.validation}",
                f"Response: {result.response_ms} ms",
                f"URL: {result.url}",
                "Decision: REVIEW",
                "-" * 60,
            ]
        )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

def write_promotion_candidates(
    path: Path | None,
    results: list[Result],
    history: dict,
) -> None:
    if path is None:
        return

    path.parent.mkdir(parents=True, exist_ok=True)

    candidates = []

    for result in results:
        if not result.ok:
            continue

        key = " | ".join(
            [
                result.url.strip(),
                result.user_agent.strip(),
                result.referer.strip(),
            ]
        )
        entry = history.get(key, {})

        if entry.get("stability") != "stable-candidate":
            continue

        candidates.append(
            {
                "name": result.name,
                "url": result.url,
                "tvg_id": result.tvg_id,
                "tvg_name": result.tvg_name,
                "group": result.group,
                "user_agent": result.user_agent,
                "referer": result.referer,
                "validation": result.validation,
                "response_ms": result.response_ms,
                "success_count": entry.get("success_count", 0),
                "failure_count": entry.get("failure_count", 0),
                "success_streak": entry.get("success_streak", 0),
                "stability": entry.get("stability", "unknown"),
                "decision": "manual-review",
            }
        )

    payload = {
        "hunter_version": VERSION,
        "candidate_count": len(candidates),
        "candidates": candidates,
    }

    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

def load_decisions(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid decision file: {exc}") from exc

    decisions = {}

    for item in payload.get("candidates", []):
        url = str(item.get("url", "")).strip()
        decision = str(item.get("decision", "")).strip().casefold()

        if url and decision in {"approve", "reject"}:
            decisions[url] = decision

    return decisions

def write_approved_m3u(
    path: Path | None,
    results: list[Result],
    decisions: dict[str, str],
) -> None:
    if path is None:
        return

    approved = [
        result
        for result in results
        if result.ok
        and decisions.get(result.url.strip()) == "approve"
    ]

    path.parent.mkdir(parents=True, exist_ok=True)
    write_working_m3u(path, approved)

def expand_sources(sources: list[str], timeout: float) -> list[str]:
    expanded = []
    for source in sources:
        repo_playlists = discover_github_playlists(source, timeout)
        if repo_playlists:
            print(
                f"GitHub repo: {source} -> {len(repo_playlists)} playlist(s)",
                file=sys.stderr,
            )
            expanded.extend(repo_playlists)
        else:
            expanded.append(source)
    return expanded


def main() -> int:
    args = parse_args()

    sources = list(args.sources)
    if args.source_list:
        sources.extend(read_source_list(args.source_list))

    if not sources:
        print("ERROR: provide a source or --source-list.", file=sys.stderr)
        return 2
    if args.workers < 1 or args.timeout <= 0:
        print("ERROR: invalid workers/timeout.", file=sys.stderr)
        return 2

    try:
        pattern = re.compile(args.match, re.IGNORECASE) if args.match else None
    except re.error as exc:
        print(f"ERROR: invalid --match regex: {exc}", file=sys.stderr)
        return 2

    expanded = expand_sources(sources, args.timeout)
    collected = []
    source_failures = 0

    for index, source in enumerate(expanded, 1):
        try:
            channels = parse_m3u(load_playlist(source, args.timeout), source)
            collected.extend(channels)
            print(
                f"[{index}/{len(expanded)}] {source}: {len(channels)} URL(s)",
                file=sys.stderr,
            )
        except Exception as exc:
            source_failures += 1
            print(
                f"[{index}/{len(expanded)}] FAILED {source}: "
                f"{type(exc).__name__}: {exc}",
                file=sys.stderr,
            )

    countries = {
        value.strip().upper()
        for value in args.country
        if value.strip()
    }

    try:
        known_profiles = load_known_profiles(args.known_source, args.timeout)
    except Exception as exc:
        print(
            f"ERROR: failed to load known source: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    try:
        history = load_history(args.history_file)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    channels = [
        channel
        for channel in dedupe_channels(collected)
        if matches(channel, pattern)
        and matches_country(channel, countries)
        and (
            not args.new_only
            or channel_profile_key(channel) not in known_profiles
        and matches_stability(channel, history, args.stability)
        )
    ]
    
    if args.limit > 0:
        channels = channels[: args.limit]

    print(
        f"\nUnique stream profiles to test: {len(channels)}",
        file=sys.stderr,
    )
    if not channels:
        return 1

    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [
            executor.submit(probe, channel, args.timeout)
            for channel in channels
        ]
        for done, future in enumerate(as_completed(futures), 1):
            result = future.result()
            results.append(result)
            print(
                f"[{done:>4}/{len(futures)}] "
                f"{'OK ' if result.ok else 'BAD'} "
                f"{result.response_ms:>5} ms  "
                f"{result.validation:<11}  {result.name}",
                file=sys.stderr,
            )

    results.sort(key=lambda item: item.rank_key)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    try:
        history = load_history(args.history_file)
        history = update_history(history, results)
        save_history(args.history_file, history)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    try:
        decisions = load_decisions(args.decision_file)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2    

    csv_path = args.out_dir / "results.csv"
    json_path = args.out_dir / "results.json"
    m3u_path = args.out_dir / "working.m3u"

    write_csv(csv_path, results)
    write_json(json_path, results)
    write_working_m3u(m3u_path, results)
    write_review_m3u(args.review_out, results)
    write_review_report(args.review_report, results, history)
    write_promotion_candidates(args.promotion_out, results, history)
    write_approved_m3u(args.approved_out, results, decisions)

    ok_count = sum(item.ok for item in results)
    deep_hls = sum(
        item.ok and item.validation == "hls-segment"
        for item in results
    )

    print(f"\n🐾 Bondik M3U Hunter v{VERSION}")
    print(f"Sources loaded: {len(expanded) - source_failures}")
    print(f"Source failures: {source_failures}")
    if args.known_source:
        print(f"Known profiles loaded: {len(known_profiles)}")
    if args.new_only:
        print(f"New profiles tested: {len(results)}")
    print(f"Unique profiles tested: {len(results)}")
    print(f"Working: {ok_count}")
    print(f"  Deep HLS verified: {deep_hls}")
    print(f"Failed: {len(results) - ok_count}")
    print(f"CSV:  {csv_path}")
    print(f"JSON: {json_path}")
    print(f"M3U:  {m3u_path}")
    if args.review_out:
        print(f"Review M3U: {args.review_out}")
    if args.approved_out:
        print(f"Approved M3U: {args.approved_out}")       
    if args.review_report:
        print(f"Review report: {args.review_report}")
    if args.promotion_out:
        print(f"Promotion candidates: {args.promotion_out}")

    return 0 if ok_count else 1


if __name__ == "__main__":
    raise SystemExit(main())
