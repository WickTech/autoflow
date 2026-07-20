"""Retry/backoff policy for source fetches. No real network, no real sleeping."""
from __future__ import annotations

import httpx
import pytest

from autoflow import net

URL = "https://example.com/feed"


def _response(status: int, **headers) -> httpx.Response:
    return httpx.Response(status, request=httpx.Request("GET", URL), headers=headers)


def _sequence(monkeypatch, *results, method="get"):
    """Stub httpx.get/post to yield each result in turn; exceptions are raised."""
    calls: list[dict] = []
    remaining = list(results)

    def _fake(url, **kwargs):
        calls.append({"url": url, **kwargs})
        outcome = remaining.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(net.httpx, method, _fake)
    return calls


def test_success_on_first_try_makes_one_call(monkeypatch):
    calls = _sequence(monkeypatch, _response(200))
    assert net.get(URL).status_code == 200
    assert len(calls) == 1


def test_retries_a_503_then_succeeds(monkeypatch):
    calls = _sequence(monkeypatch, _response(503), _response(503), _response(200))
    assert net.get(URL, retries=3).status_code == 200
    assert len(calls) == 3


def test_gives_up_and_returns_last_response(monkeypatch):
    """Caller's raise_for_status() should still see the real status code."""
    calls = _sequence(monkeypatch, _response(503), _response(503))
    resp = net.get(URL, retries=1)
    assert resp.status_code == 503
    assert len(calls) == 2
    with pytest.raises(httpx.HTTPStatusError):
        resp.raise_for_status()


def test_client_errors_are_not_retried(monkeypatch):
    calls = _sequence(monkeypatch, _response(404))
    assert net.get(URL, retries=3).status_code == 404
    assert len(calls) == 1, "a 404 will not fix itself"


def test_transport_errors_are_retried(monkeypatch):
    calls = _sequence(monkeypatch, httpx.ConnectTimeout("boom"), _response(200))
    assert net.get(URL, retries=2).status_code == 200
    assert len(calls) == 2


def test_transport_error_raises_after_exhausting_retries(monkeypatch):
    _sequence(monkeypatch, httpx.ConnectError("down"), httpx.ConnectError("down"))
    with pytest.raises(httpx.ConnectError):
        net.get(URL, retries=1)


def test_retries_zero_means_a_single_attempt(monkeypatch):
    calls = _sequence(monkeypatch, _response(503))
    assert net.get(URL, retries=0).status_code == 503
    assert len(calls) == 1


def test_retry_after_header_is_honoured(monkeypatch):
    slept: list[float] = []
    monkeypatch.setattr(net.time, "sleep", slept.append)
    _sequence(monkeypatch, _response(429, **{"retry-after": "2"}), _response(200))
    assert net.get(URL, retries=2).status_code == 200
    assert slept == [2.0]


def test_user_agent_is_sent_and_overridable(monkeypatch):
    calls = _sequence(monkeypatch, _response(200), _response(200))
    net.get(URL)
    assert calls[0]["headers"]["User-Agent"] == net.USER_AGENT
    net.get(URL, headers={"User-Agent": "custom/1.0"})
    assert calls[1]["headers"]["User-Agent"] == "custom/1.0"


# --- POST: same policy, because delivery is as flaky as fetching ------------


def test_post_sends_the_json_payload(monkeypatch):
    calls = _sequence(monkeypatch, _response(200), method="post")
    net.post(URL, json={"text": "hello"})
    assert calls[0]["json"] == {"text": "hello"}
    assert calls[0]["headers"]["User-Agent"] == net.USER_AGENT


def test_post_retries_transient_failures(monkeypatch):
    calls = _sequence(monkeypatch, _response(503), _response(200), method="post")
    assert net.post(URL, json={}).status_code == 200
    assert len(calls) == 2


def test_post_does_not_retry_client_errors(monkeypatch):
    calls = _sequence(monkeypatch, _response(400), method="post")
    assert net.post(URL, json={}).status_code == 400
    assert len(calls) == 1, "a malformed payload will not fix itself"
