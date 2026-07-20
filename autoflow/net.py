"""Shared HTTP helper: one place for timeouts, user-agent, and retry policy.

Sources fetch over flaky public endpoints (hnrss, reddit). A single 503 used to
kill an entire scheduled run, so every request goes through :func:`get`, which
retries transport errors and retryable status codes with exponential backoff
and jitter. Fully offline-safe: nothing here runs unless a source makes a call.
"""
from __future__ import annotations

import random
import time

import httpx

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
    merged = {"User-Agent": USER_AGENT, **(headers or {})}
    attempts = max(1, retries + 1)
    last_error: Exception | None = None
    resp: httpx.Response | None = None

    for attempt in range(attempts):
        try:
            resp = httpx.get(
                url, params=params, headers=merged, timeout=timeout, follow_redirects=True
            )
        except httpx.TransportError as exc:  # connect / read / timeout
            last_error, resp = exc, None
        else:
            if getattr(resp, "status_code", None) not in RETRY_STATUS:
                return resp

        if attempt == attempts - 1:
            break

        wait = _retry_after(resp) if resp is not None else None
        time.sleep(wait if wait is not None else _sleep_for(attempt, backoff))

    if resp is not None:
        # Retries exhausted on a retryable status — hand it back so the caller's
        # raise_for_status() produces the real error with the real status code.
        return resp

    assert last_error is not None
    raise last_error
