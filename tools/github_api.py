#!/usr/bin/env python3
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request


def _url_origin(
    url: str,
):
    parsed = urllib.parse.urlparse(
        url
    )

    scheme = parsed.scheme.lower()
    hostname = (
        parsed.hostname or ""
    ).lower()

    port = parsed.port

    if port is None:
        if scheme == "https":
            port = 443
        elif scheme == "http":
            port = 80

    return (
        scheme,
        hostname,
        port,
    )


class SafeRedirectHandler(
    urllib.request.HTTPRedirectHandler
):
    def redirect_request(
        self,
        req,
        fp,
        code,
        msg,
        headers,
        newurl,
    ):
        parsed_new_url = urllib.parse.urlparse(
            newurl
        )

        if (
            parsed_new_url.username is not None
            or parsed_new_url.password is not None
        ):
            return None

        if not parsed_new_url.hostname:
            return None

        parsed_old_url = urllib.parse.urlparse(
            req.full_url
        )

        if (
            parsed_old_url.scheme.lower() == "https"
            and parsed_new_url.scheme.lower() != "https"
        ):
            return None

        redirected = (
            super().redirect_request(
                req,
                fp,
                code,
                msg,
                headers,
                newurl,
            )
        )

        if redirected is None:
            return None

        old_origin = _url_origin(
            req.full_url
        )

        new_origin = _url_origin(
            newurl
        )

        if old_origin != new_origin:
            redirected.remove_header(
                "Authorization"
            )

        return redirected


def github_request(
    url: str,
    token: str,
    *,
    method: str = "GET",
    payload=None,
    opener,
    sleep,
    now,
) -> bytes:
    parsed_url = urllib.parse.urlparse(
        url
    )

    if parsed_url.scheme.lower() != "https":
        raise RuntimeError(
            "GitHub API requests require HTTPS"
        )

    if not parsed_url.hostname:
        raise RuntimeError(
            "GitHub API URL requires hostname"
        )

    try:
        parsed_url.port
    except ValueError as exc:
        raise RuntimeError(
            "GitHub API URL has invalid port"
        ) from exc

    if (
        parsed_url.username is not None
        or parsed_url.password is not None
    ):
        raise RuntimeError(
            "GitHub API URL must not contain credentials"
        )

    data = None

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    if payload is not None:
        data = json.dumps(
            payload,
            ensure_ascii=False,
        ).encode("utf-8")

        headers["Content-Type"] = (
            "application/json"
        )

    request = urllib.request.Request(
        url,
        data=data,
        headers=headers,
        method=method,
    )

    retryable_statuses = {
        408,
        429,
        500,
        502,
        503,
        504,
    }

    max_attempts = 3
    max_retry_delay = 300
    max_total_retry_delay = 300
    total_retry_delay = 0

    retry_safe_method = (
        method.upper() in {"GET", "HEAD"}
    )

    for attempt in range(
        1,
        max_attempts + 1,
    ):
        try:
            with opener.open(
                request,
                timeout=30,
            ) as response:
                return response.read()

        except urllib.error.HTTPError as exc:
            response_headers = (
                exc.headers or {}
            )

            remaining = response_headers.get(
                "X-RateLimit-Remaining"
            )

            retry_after = (
                response_headers.get(
                    "Retry-After"
                )
            )

            try:
                details = exc.read().decode(
                    "utf-8",
                    errors="replace",
                ).strip()

            except (
                OSError,
                ValueError,
            ):
                details = (
                    "<response body unavailable>"
                )

            details_lower = details.lower()

            primary_rate_limit = (
                exc.code in {403, 429}
                and remaining == "0"
            )

            secondary_rate_limit = (
                exc.code == 403
                and (
                    retry_after is not None
                    or (
                        "secondary rate limit"
                        in details_lower
                    )
                )
            )

            rate_limit_retry = (
                exc.code == 429
                or primary_rate_limit
                or secondary_rate_limit
            )

            retryable = (
                rate_limit_retry
                or (
                    retry_safe_method
                    and exc.code
                    in retryable_statuses
                )
            )

            if (
                retryable
                and attempt < max_attempts
            ):
                delay = None

                if retry_after is not None:
                    try:
                        delay = max(
                            0,
                            int(retry_after),
                        )
                    except ValueError:
                        pass

                if (
                    delay is None
                    and primary_rate_limit
                ):
                    reset = (
                        response_headers.get(
                            "X-RateLimit-Reset"
                        )
                    )

                    try:
                        delay = max(
                            0,
                            int(reset)
                            - int(now()),
                        )
                    except (
                        TypeError,
                        ValueError,
                    ):
                        pass

                if delay is None:
                    if rate_limit_retry:
                        delay = (
                            60
                            * (
                                2
                                ** (attempt - 1)
                            )
                        )
                    else:
                        delay = attempt

                if delay > max_retry_delay:
                    exc.close()

                    raise RuntimeError(
                        "GitHub API retry delay "
                        f"{delay}s exceeds safety "
                        f"limit {max_retry_delay}s"
                    ) from exc

                next_total_retry_delay = (
                    total_retry_delay
                    + delay
                )

                if (
                    next_total_retry_delay
                    > max_total_retry_delay
                ):
                    exc.close()

                    raise RuntimeError(
                        "GitHub API retry delay budget "
                        f"{next_total_retry_delay}s "
                        "exceeds safety limit "
                        f"{max_total_retry_delay}s"
                    ) from exc

                total_retry_delay = (
                    next_total_retry_delay
                )

                exc.close()

                sleep(
                    delay
                )

                continue

            exc.close()

            raise RuntimeError(
                "GitHub API returned "
                f"HTTP {exc.code}: {details}"
            ) from exc

        except urllib.error.URLError as exc:
            if (
                retry_safe_method
                and attempt < max_attempts
            ):
                delay = attempt

                next_total_retry_delay = (
                    total_retry_delay
                    + delay
                )

                if (
                    next_total_retry_delay
                    > max_total_retry_delay
                ):
                    raise RuntimeError(
                        "GitHub API retry delay budget "
                        f"{next_total_retry_delay}s "
                        "exceeds safety limit "
                        f"{max_total_retry_delay}s"
                    ) from exc

                total_retry_delay = (
                    next_total_retry_delay
                )

                sleep(
                    delay
                )

                continue

            raise RuntimeError(
                "GitHub API request failed: "
                f"{exc.reason}"
            ) from exc

    raise RuntimeError(
        "GitHub API request failed "
        "after retries"
    )
