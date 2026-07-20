"""Shared HTTP helper: one place for timeouts, user-agent, and retry policy.

Sources fetch over flaky public endpoints (hnrss, reddit) and sinks deliver to
equally flaky ones (Slack, Discord). A single 503 used to kill an entire
scheduled run, so every request goes through :func:`get` or :func:`post`, which
retry transport errors and retryable status codes with exponential backoff and
jitter. Fully offline-safe: nothing here runs unless a plugin makes a call.

Delivery retries matter especially now that dedup state is committed only after
sinks succeed — without them a transient webhook blip defers a whole digest.
"""
from __future__ import annotations

import random
import time

import httpx

from .log import log

USER_AGENT = "autoflow/0.1 (+https://github.com/WickTech/autoflow)"

# Transient by definition — anything else is a real error and fails fast.
RETRY_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})

DEFAULT_RETRIES = 3
DEFAULT_BACKOFF = 0.5
DEFAULT_TIMEOUT = 20.0
_MAX_SLEEP = 30.0


def _retry_after(resp: httpx.Response) -> float | None:
    """Honour a server-provided Retry-After (seconds form only)."""
    raw = resp.headers.get("retry-after")
    if not raw:
        return None
    try:
        return min(float(raw), _MAX_SLEEP)
    except ValueError:
        return None


def _sleep_for(attempt: int, backoff: float) -> float:
    """Exponential backoff with full jitter, so parallel sources don't sync up."""
    return min(backoff * (2**attempt) * (0.5 + random.random()), _MAX_SLEEP)


def _request(
    method: str,
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    json: dict | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
    backoff: float = DEFAULT_BACKOFF,
) -> httpx.Response:
    merged = {"User-Agent": USER_AGENT, **(headers or {})}
    attempts = max(1, retries + 1)
    last_error: Exception | None = None
    resp: httpx.Response | None = None

    for attempt in range(attempts):
        try:
            if method == "GET":
                resp = httpx.get(
                    url, params=params, headers=merged, timeout=timeout, follow_redirects=True
                )
            else:
                resp = httpx.post(
                    url,
                    params=params,
                    headers=merged,
                    json=json,
                    timeout=timeout,
                    follow_redirects=True,
                )
        except httpx.TransportError as exc:  # connect / read / timeout
            last_error, resp = exc, None
        else:
            if getattr(resp, "status_code", None) not in RETRY_STATUS:
                return resp

        if attempt == attempts - 1:
            break

        wait = _retry_after(resp) if resp is not None else None
        wait = wait if wait is not None else _sleep_for(attempt, backoff)
        log.warning(
            "%s %s failed (%s), retrying in %.1fs",
            method,
            url,
            f"HTTP {resp.status_code}" if resp is not None else type(last_error).__name__,
            wait,
            extra={"attempt": attempt + 1, "of": attempts, "url": url},
        )
        time.sleep(wait)

    if resp is not None:
        # Retries exhausted on a retryable status — hand it back so the caller's
        # raise_for_status() produces the real error with the real status code.
        return resp

    assert last_error is not None
    raise last_error


def get(
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
    backoff: float = DEFAULT_BACKOFF,
) -> httpx.Response:
    """GET ``url``, retrying transient failures.

    Returns the final response without raising for status — callers decide, so a
    404 still surfaces as a normal ``raise_for_status()`` error at the call site.
    """
    return _request(
        "GET", url, params=params, headers=headers,
        timeout=timeout, retries=retries, backoff=backoff,
    )


def post(
    url: str,
    *,
    json: dict | None = None,
    headers: dict | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
    backoff: float = DEFAULT_BACKOFF,
) -> httpx.Response:
    """POST ``url``, retrying transient failures.

    Safe to retry: every sink that uses this posts an idempotent digest payload,
    and the alternative (one 503 defers the whole run) is strictly worse.
    """
    return _request(
        "POST", url, json=json, headers=headers,
        timeout=timeout, retries=retries, backoff=backoff,
    )
