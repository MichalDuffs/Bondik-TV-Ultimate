#!/usr/bin/env python3
"""
Bondik TV Ultimate - Stream Hunter v0.3 "Second Chance Sniff"

Downloads public M3U playlists, extracts stream candidates, removes duplicates,
tests streams concurrently and writes review files.

v0.3 improvements:
- retries temporary failures (timeouts, 429, 5xx and similar)
- browser User-Agent fallback for HTTP 403
- no forced Range header (some IPTV/CDN servers reject it)
- supports common M3U headers (#EXTVLCOPT, #EXTHTTP, Kodi URL pipe headers)
- normalizes non-ASCII URLs safely
- keeps TLS certificate verification enabled
- reports second-chance recoveries
- never modifies approved Bondik TV channels or production playlists
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse


VERSION = "0.3"
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_SOURCES = SCRIPT_DIR / "sources.txt"
DEFAULT_OUTPUT = SCRIPT_DIR / "results"

HUNTER_USER_AGENT = (
    f"Bondik-TV-Ultimate-Stream-Hunter/{VERSION} "
    "(+https://github.com/MichalDuffs/Bondik-TV-Ultimate)"
)

BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/151.0.0.0 Safari/537.36"
)

PLAYLIST_READ_LIMIT = 8 * 1024 * 1024
STREAM_READ_LIMIT = 64 * 1024

EXTINF_ATTR_RE = re.compile(r'([\w-]+)="([^"]*)"')

TRANSIENT_HTTP_CODES = {
    408, 425, 429,
    500, 502, 503, 504,
    520, 521, 522, 523, 524, 525, 526,
    530, 567,
}

UNCERTAIN_HTTP_CODES = {
    401, 403, 408, 425, 429, 451,
    500, 502, 503, 504,
    520, 521, 522, 523, 524, 525, 526,
    530, 567,
}


@dataclass
class Source:
    label: str
    url: str


@dataclass
class Candidate:
    source: str
    name: str
    url: str
    extinf: str
    attributes: dict[str, str] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)


@dataclass
class Result:
    candidate: Candidate
    status: str
    detail: str
    attempts: int = 1
    recovered: bool = False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="🐾 Bondik TV Ultimate - bulk public IPTV stream hunter"
    )
    parser.add_argument(
        "--sources",
        type=Path,
        default=DEFAULT_SOURCES,
        help="text file with playlist URLs (label|url or plain url)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="directory for generated review files",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=40,
        help="parallel stream checks (default: 40)",
    )
    parser.add_argument(
        "--download-workers",
        type=int,
        default=8,
        help="parallel playlist downloads (default: 8)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="timeout per request in seconds (default: 10)",
    )
    parser.add_argument(
        "--attempts",
        type=int,
        default=2,
        help="maximum attempts for temporary failures (default: 2)",
    )
    parser.add_argument(
        "--retry-delay",
        type=float,
        default=0.75,
        help="seconds between retries (default: 0.75)",
    )
    parser.add_argument(
        "--no-test",
        action="store_true",
        help="only collect and deduplicate candidates; skip stream checks",
    )

    args = parser.parse_args()

    if args.workers < 1 or args.download_workers < 1:
        parser.error("worker counts must be at least 1")
    if args.timeout <= 0:
        parser.error("--timeout must be greater than 0")
    if args.attempts < 1:
        parser.error("--attempts must be at least 1")
    if args.retry_delay < 0:
        parser.error("--retry-delay cannot be negative")

    return args


def normalize_url(url: str) -> str:
    """Encode Unicode URL parts without double-encoding existing % escapes."""
    split = urllib.parse.urlsplit(url)

    if split.scheme not in {"http", "https"}:
        return url

    hostname = split.hostname
    if not hostname:
        return url

    try:
        host_ascii = hostname.encode("idna").decode("ascii")
    except UnicodeError:
        host_ascii = hostname

    netloc = host_ascii
    if split.port:
        netloc += f":{split.port}"

    if split.username:
        userinfo = urllib.parse.quote(split.username, safe="")
        if split.password:
            userinfo += ":" + urllib.parse.quote(split.password, safe="")
        netloc = f"{userinfo}@{netloc}"

    path = urllib.parse.quote(split.path, safe="/:@%+~!$&'()*,-.;=_")
    query = urllib.parse.quote(split.query, safe="=&;%+,:/@?~!$'()*-._")
    fragment = urllib.parse.quote(split.fragment, safe="%+,:/@?~!$&'()*-._")

    return urllib.parse.urlunsplit(
        (split.scheme, netloc, path, query, fragment)
    )


def sanitize_headers(headers: dict[str, str]) -> dict[str, str]:
    """Keep valid HTTP header values and avoid urllib encoding crashes."""
    clean: dict[str, str] = {}

    for key, value in headers.items():
        key = str(key).strip()
        value = str(value).strip()

        if not key or not value:
            continue

        if "\r" in key or "\n" in key or "\r" in value or "\n" in value:
            continue

        try:
            key.encode("ascii")
            value.encode("latin-1")
        except UnicodeEncodeError:
            continue

        clean[key] = value

    return clean


def load_sources(path: Path) -> list[Source]:
    if not path.exists():
        raise FileNotFoundError(f"Missing sources file: {path}")

    sources: list[Source] = []

    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8-sig").splitlines(),
        start=1,
    ):
        line = raw_line.strip()

        if not line or line.startswith("#"):
            continue

        if "|" in line:
            label, url = (part.strip() for part in line.split("|", 1))
        else:
            label, url = "", line

        parsed = urlparse(url)

        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            print(f"⚠️ Ignoring invalid source on line {line_number}: {line}")
            continue

        if not label:
            label = parsed.netloc

        sources.append(Source(label=label, url=url))

    return sources


def request_bytes(
    url: str,
    timeout: float,
    *,
    headers: dict[str, str] | None = None,
    limit: int,
    browser_fallback: bool = False,
) -> tuple[bytes, str, str]:
    request_headers = {
        "User-Agent": BROWSER_USER_AGENT if browser_fallback else HUNTER_USER_AGENT,
        "Accept": (
            "application/vnd.apple.mpegurl,"
            "application/x-mpegURL,"
            "application/octet-stream,"
            "video/*,"
            "text/plain,*/*"
        ),
        "Accept-Encoding": "identity",
        "Connection": "close",
    }

    if headers:
        request_headers.update(sanitize_headers(headers))

    request = urllib.request.Request(
        normalize_url(url),
        headers=request_headers,
        method="GET",
    )

    with urllib.request.urlopen(
        request,
        timeout=timeout,
        context=ssl.create_default_context(),
    ) as response:
        data = response.read(limit)
        final_url = response.geturl()
        content_type = response.headers.get("Content-Type", "")
        return data, final_url, content_type


def download_source(
    source: Source,
    timeout: float,
) -> tuple[Source, str | None, str]:
    try:
        payload, final_url, _ = request_bytes(
            source.url,
            timeout,
            limit=PLAYLIST_READ_LIMIT,
        )
        text = payload.decode("utf-8-sig", errors="replace")

        if "#EXTM3U" not in text[:2048]:
            return source, None, "response is not an M3U playlist"

        detail = "OK" if final_url == source.url else f"OK -> {final_url}"
        return source, text, detail

    except urllib.error.HTTPError as error:
        return source, None, f"HTTP {error.code}"
    except urllib.error.URLError as error:
        return source, None, f"connection error: {error.reason}"
    except (socket.timeout, TimeoutError):
        return source, None, "timeout"
    except Exception as error:
        return source, None, f"{type(error).__name__}: {error}"


def parse_attributes(extinf: str) -> dict[str, str]:
    return {
        key.lower(): value
        for key, value in EXTINF_ATTR_RE.findall(extinf)
    }


def parse_name(extinf: str) -> str:
    in_quotes = False
    escaped = False

    for index, character in enumerate(extinf):
        if escaped:
            escaped = False
            continue

        if character == "\\":
            escaped = True
            continue

        if character == '"':
            in_quotes = not in_quotes
            continue

        if character == "," and not in_quotes:
            name = extinf[index + 1:].strip()
            if name:
                return name
            break

    return "<unnamed>"


def normalize_header_name(key: str) -> str:
    mapping = {
        "user-agent": "User-Agent",
        "useragent": "User-Agent",
        "referer": "Referer",
        "referrer": "Referer",
        "origin": "Origin",
        "cookie": "Cookie",
        "authorization": "Authorization",
    }
    return mapping.get(key.strip().lower(), key.strip())


def parse_kodi_pipe_url(line: str) -> tuple[str, dict[str, str]]:
    """
    Parse common Kodi form:
    https://example/stream.m3u8|User-Agent=...&Referer=...
    """
    if "|" not in line:
        return line, {}

    url, raw_headers = line.split("|", 1)
    headers: dict[str, str] = {}

    for key, value in urllib.parse.parse_qsl(
        raw_headers,
        keep_blank_values=False,
    ):
        headers[normalize_header_name(key)] = value

    return url.strip(), headers


def parse_exthttp(line: str) -> dict[str, str]:
    """Parse #EXTHTTP:{...} header metadata when present."""
    _, _, raw = line.partition(":")
    raw = raw.strip()

    if not raw:
        return {}

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}

    if not isinstance(data, dict):
        return {}

    return {
        normalize_header_name(str(key)): str(value)
        for key, value in data.items()
        if value is not None
    }


def parse_playlist(source: Source, text: str) -> list[Candidate]:
    candidates: list[Candidate] = []
    current_extinf = ""
    current_headers: dict[str, str] = {}

    for raw_line in text.splitlines():
        line = raw_line.strip()

        if not line:
            continue

        if line.startswith("#EXTINF:"):
            current_extinf = line
            current_headers = {}
            continue

        lower = line.lower()

        if lower.startswith("#extvlcopt:http-user-agent="):
            current_headers["User-Agent"] = line.split("=", 1)[1].strip()
            continue

        if (
            lower.startswith("#extvlcopt:http-referrer=")
            or lower.startswith("#extvlcopt:http-referer=")
        ):
            current_headers["Referer"] = line.split("=", 1)[1].strip()
            continue

        if lower.startswith("#exthttp:"):
            current_headers.update(parse_exthttp(line))
            continue

        if line.startswith("#"):
            continue

        stream_url, pipe_headers = parse_kodi_pipe_url(line)
        parsed = urlparse(stream_url)

        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            current_extinf = ""
            current_headers = {}
            continue

        headers = current_headers.copy()
        headers.update(pipe_headers)

        extinf = current_extinf or f"#EXTINF:-1,{stream_url}"

        candidates.append(
            Candidate(
                source=source.label,
                name=parse_name(extinf),
                url=stream_url,
                extinf=extinf,
                attributes=parse_attributes(extinf),
                headers=headers,
            )
        )

        current_extinf = ""
        current_headers = {}

    return candidates


def deduplicate(
    candidates: list[Candidate],
) -> tuple[list[Candidate], int]:
    unique: dict[str, Candidate] = {}

    for candidate in candidates:
        key = normalize_url(candidate.url)
        unique.setdefault(key, candidate)

    removed = len(candidates) - len(unique)
    return list(unique.values()), removed


def classify_http_error(code: int) -> str:
    if code in UNCERTAIN_HTTP_CODES:
        return "uncertain"
    if 400 <= code < 500:
        return "dead"
    return "uncertain"


def is_transient_detail(detail: str) -> bool:
    if detail == "timeout":
        return True

    if detail.startswith("HTTP "):
        try:
            code = int(detail.split()[1])
        except (IndexError, ValueError):
            return False
        return code in TRANSIENT_HTTP_CODES

    return detail.startswith(
        (
            "RemoteDisconnected:",
            "ConnectionResetError:",
        )
    )


def test_once(
    candidate: Candidate,
    timeout: float,
    *,
    browser_fallback: bool = False,
) -> Result:
    headers = candidate.headers.copy()

    try:
        payload, final_url, content_type = request_bytes(
            candidate.url,
            timeout,
            headers=headers,
            limit=STREAM_READ_LIMIT,
            browser_fallback=browser_fallback,
        )

        if not payload:
            return Result(candidate, "uncertain", "empty response")

        url_lower = candidate.url.lower()
        final_lower = final_url.lower()
        type_lower = content_type.lower()

        looks_hls = (
            ".m3u8" in url_lower
            or ".m3u8" in final_lower
            or "mpegurl" in type_lower
        )

        if looks_hls:
            text = payload.decode(
                "utf-8-sig",
                errors="replace",
            ).lstrip()

            if not text.startswith("#EXTM3U"):
                return Result(
                    candidate,
                    "uncertain",
                    "HLS URL returned non-M3U data",
                )

        detail = "OK"

        if browser_fallback:
            detail += " (browser UA fallback)"

        if final_url != normalize_url(candidate.url):
            detail += f" -> {final_url}"

        return Result(candidate, "working", detail)

    except urllib.error.HTTPError as error:
        return Result(
            candidate,
            classify_http_error(error.code),
            f"HTTP {error.code}",
        )

    except urllib.error.URLError as error:
        reason = error.reason

        if isinstance(reason, socket.timeout):
            return Result(candidate, "uncertain", "timeout")

        if isinstance(reason, ssl.SSLCertVerificationError):
            return Result(
                candidate,
                "dead",
                f"TLS certificate error: {reason}",
            )

        return Result(
            candidate,
            "dead",
            f"connection error: {reason}",
        )

    except (socket.timeout, TimeoutError):
        return Result(candidate, "uncertain", "timeout")

    except ssl.SSLCertVerificationError as error:
        return Result(
            candidate,
            "dead",
            f"TLS certificate error: {error}",
        )

    except ssl.SSLError as error:
        return Result(
            candidate,
            "uncertain",
            f"SSL error: {error}",
        )

    except Exception as error:
        return Result(
            candidate,
            "uncertain",
            f"{type(error).__name__}: {error}",
        )


def test_candidate(
    candidate: Candidate,
    timeout: float,
    attempts: int,
    retry_delay: float,
) -> Result:
    """
    First try normal Hunter headers.
    HTTP 403 gets an immediate browser-UA second sniff.
    Temporary failures are retried up to --attempts.
    """
    total_network_attempts = 0
    last: Result | None = None

    for attempt_number in range(1, attempts + 1):
        total_network_attempts += 1
        result = test_once(candidate, timeout)
        last = result

        if result.status == "working":
            result.attempts = total_network_attempts
            result.recovered = total_network_attempts > 1
            if result.recovered and "after retry" not in result.detail:
                result.detail += f" (after retry {attempt_number})"
            return result

        if result.detail == "HTTP 403":
            total_network_attempts += 1
            browser_result = test_once(
                candidate,
                timeout,
                browser_fallback=True,
            )

            if browser_result.status == "working":
                browser_result.attempts = total_network_attempts
                browser_result.recovered = True
                return browser_result

            last = browser_result

        if attempt_number >= attempts:
            break

        if last is None or not is_transient_detail(last.detail):
            break

        if retry_delay:
            time.sleep(retry_delay)

    assert last is not None
    last.attempts = total_network_attempts
    last.recovered = False
    return last


def write_m3u(path: Path, results: list[Result]) -> None:
    lines = ["#EXTM3U"]

    for result in results:
        candidate = result.candidate
        lines.append(candidate.extinf)

        user_agent = candidate.headers.get("User-Agent")
        referer = candidate.headers.get("Referer")

        if user_agent:
            lines.append(
                f"#EXTVLCOPT:http-user-agent={user_agent}"
            )

        if referer:
            lines.append(
                f"#EXTVLCOPT:http-referrer={referer}"
            )

        lines.append(candidate.url)

    path.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def write_csv(path: Path, results: list[Result]) -> None:
    with path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        writer = csv.writer(handle)

        writer.writerow(
            [
                "status",
                "source",
                "name",
                "tvg-id",
                "group-title",
                "url",
                "detail",
                "attempts",
                "recovered",
            ]
        )

        for result in results:
            candidate = result.candidate

            writer.writerow(
                [
                    result.status,
                    candidate.source,
                    candidate.name,
                    candidate.attributes.get("tvg-id", ""),
                    candidate.attributes.get("group-title", ""),
                    candidate.url,
                    result.detail,
                    result.attempts,
                    str(result.recovered).lower(),
                ]
            )


def write_dead(path: Path, results: list[Result]) -> None:
    lines = [
        (
            f"{item.candidate.name}\t"
            f"{item.candidate.url}\t"
            f"{item.detail}"
        )
        for item in results
        if item.status == "dead"
    ]

    path.write_text(
        "\n".join(lines) + ("\n" if lines else ""),
        encoding="utf-8",
    )


def write_recovered(path: Path, results: list[Result]) -> None:
    recovered = [
        item
        for item in results
        if item.status == "working" and item.recovered
    ]

    with path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "source",
                "name",
                "url",
                "detail",
                "attempts",
            ]
        )

        for item in recovered:
            writer.writerow(
                [
                    item.candidate.source,
                    item.candidate.name,
                    item.candidate.url,
                    item.detail,
                    item.attempts,
                ]
            )


def print_summary(
    source_count: int,
    downloaded: int,
    found: int,
    unique: int,
    duplicate_count: int,
    results: list[Result] | None,
    output: Path,
) -> None:
    print()
    print("🐾 Bondik TV Ultimate")
    print(f"📡 Stream Hunter v{VERSION} - Second Chance Sniff")
    print("=" * 60)
    print(f"Playlist sources:      {source_count}")
    print(f"Downloaded:            {downloaded}")
    print(f"Found streams:         {found}")
    print(f"Unique streams:        {unique}")
    print(f"Duplicates removed:    {duplicate_count}")

    if results is not None:
        for status, icon in (
            ("working", "✅"),
            ("uncertain", "⚠️"),
            ("dead", "❌"),
        ):
            count = sum(
                item.status == status
                for item in results
            )
            print(
                f"{icon} {status.capitalize():<19}{count}"
            )

        recovered = sum(
            item.status == "working" and item.recovered
            for item in results
        )
        print(f"🐕 Second-chance saves: {recovered}")

    print(f"Results:               {output}")
    print("=" * 60)
    print(
        "Nothing was added to approved Bondik TV playlists automatically."
    )


def main() -> int:
    args = parse_args()

    try:
        sources = load_sources(args.sources)
    except OSError as error:
        print(f"❌ {error}")
        return 2

    if not sources:
        print("❌ No valid playlist sources found.")
        return 2

    print(
        f"🐾 Bondik Stream Hunter v{VERSION} "
        "is sniffing public playlists..."
    )

    downloaded: list[tuple[Source, str]] = []

    with ThreadPoolExecutor(
        max_workers=args.download_workers
    ) as executor:
        futures = {
            executor.submit(
                download_source,
                source,
                args.timeout,
            ): source
            for source in sources
        }

        for future in as_completed(futures):
            source, text, detail = future.result()

            if text is None:
                print(
                    f"❌ source {source.label}: {detail}"
                )
                continue

            print(
                f"✅ source {source.label}: {detail}"
            )
            downloaded.append((source, text))

    candidates: list[Candidate] = []

    for source, text in downloaded:
        candidates.extend(
            parse_playlist(source, text)
        )

    unique_candidates, duplicate_count = deduplicate(
        candidates
    )

    args.output.mkdir(
        parents=True,
        exist_ok=True,
    )

    if args.no_test:
        results = [
            Result(
                candidate,
                "untested",
                "network test skipped",
            )
            for candidate in unique_candidates
        ]

        write_m3u(
            args.output / "candidates.m3u",
            results,
        )
        write_csv(
            args.output / "candidates.csv",
            results,
        )

        print_summary(
            len(sources),
            len(downloaded),
            len(candidates),
            len(unique_candidates),
            duplicate_count,
            None,
            args.output,
        )
        return 0

    results: list[Result] = []

    print(
        f"\nTesting {len(unique_candidates)} unique streams "
        f"with {args.workers} workers, "
        f"up to {args.attempts} attempts..."
    )

    with ThreadPoolExecutor(
        max_workers=args.workers
    ) as executor:
        futures = {
            executor.submit(
                test_candidate,
                candidate,
                args.timeout,
                args.attempts,
                args.retry_delay,
            ): candidate
            for candidate in unique_candidates
        }

        completed = 0
        total = len(futures)

        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            completed += 1

            if completed % 50 == 0 or completed == total:
                print(
                    f"  checked {completed}/{total}"
                )

    order = {
        "working": 0,
        "uncertain": 1,
        "dead": 2,
    }

    results.sort(
        key=lambda item: (
            order.get(item.status, 9),
            item.candidate.source.lower(),
            item.candidate.name.lower(),
        )
    )

    working = [
        item
        for item in results
        if item.status == "working"
    ]

    uncertain = [
        item
        for item in results
        if item.status == "uncertain"
    ]

    write_m3u(
        args.output / "working.m3u",
        working,
    )
    write_m3u(
        args.output / "uncertain.m3u",
        uncertain,
    )
    write_csv(
        args.output / "candidates.csv",
        results,
    )
    write_dead(
        args.output / "dead.txt",
        results,
    )
    write_recovered(
        args.output / "recovered.csv",
        results,
    )

    print_summary(
        len(sources),
        len(downloaded),
        len(candidates),
        len(unique_candidates),
        duplicate_count,
        results,
        args.output,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
