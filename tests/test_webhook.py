"""Webhook sink — delivery goes through the retrying HTTP layer."""
from __future__ import annotations

import httpx
import pytest

from autoflow.models import Item
from autoflow.sinks import webhook as webhook_mod
from autoflow.sinks.webhook import WebhookSink

URL = "https://hooks.example.com/abc"
ITEMS = [Item(title="AI model shipped", url="https://x.test/1", summary="It shipped.")]


def _stub_post(monkeypatch, response=None, error=None):
    calls: list[dict] = []

    def _fake_post(url, **kwargs):
        calls.append({"url": url, **kwargs})
        if error is not None:
            raise error
        return response

    monkeypatch.setattr(webhook_mod.net, "post", _fake_post)
    return calls


def _ok(status=200):
    return httpx.Response(status, request=httpx.Request("POST", URL))


def test_posts_items_through_net(monkeypatch):
    calls = _stub_post(monkeypatch, _ok())
    WebhookSink(url=URL, header="*Digest*").emit(ITEMS)

    assert len(calls) == 1
    assert calls[0]["url"] == URL
    text = calls[0]["json"]["text"]
    assert "*Digest*" in text
    assert "AI model shipped" in text
    assert "It shipped." in text


def test_retries_and_timeout_are_configurable(monkeypatch):
    calls = _stub_post(monkeypatch, _ok())
    WebhookSink(url=URL, retries=5, timeout=3).emit(ITEMS)
    assert calls[0]["retries"] == 5
    assert calls[0]["timeout"] == 3.0


def test_failed_delivery_raises_so_dedup_state_is_not_committed(monkeypatch):
    """The whole point of routing through net: a 500 that survives retries must
    still surface, so run_pipeline skips commit() and retries tomorrow."""
    _stub_post(monkeypatch, _ok(500))
    with pytest.raises(httpx.HTTPStatusError):
        WebhookSink(url=URL).emit(ITEMS)


def test_missing_url_is_skipped_not_fatal(monkeypatch):
    calls = _stub_post(monkeypatch, _ok())
    monkeypatch.delenv("AUTOFLOW_WEBHOOK_URL", raising=False)
    WebhookSink().emit(ITEMS)  # resolves ${AUTOFLOW_WEBHOOK_URL} → ""
    assert calls == [], "no URL configured means no call, and no crash"


def test_env_reference_is_resolved(monkeypatch):
    monkeypatch.setenv("AUTOFLOW_WEBHOOK_URL", URL)
    calls = _stub_post(monkeypatch, _ok())
    WebhookSink(url="${AUTOFLOW_WEBHOOK_URL}").emit(ITEMS)
    assert calls[0]["url"] == URL


def test_default_format_is_slack_for_backward_compatibility(monkeypatch):
    calls = _stub_post(monkeypatch, _ok())
    WebhookSink(url=URL).emit(ITEMS)
    assert "<https://x.test/1|AI model shipped>" in calls[0]["json"]["text"]


def test_markdown_format_for_discord_and_teams(monkeypatch):
    """Slack's <url|title> renders literally elsewhere — hence the format key."""
    calls = _stub_post(monkeypatch, _ok())
    WebhookSink(url=URL, format="markdown").emit(ITEMS)
    text = calls[0]["json"]["text"]
    assert "[AI model shipped](https://x.test/1)" in text
    assert "|" not in text


def test_no_items_means_no_post(monkeypatch):
    calls = _stub_post(monkeypatch, _ok())
    WebhookSink(url=URL).emit([])
    assert calls == []


def test_dry_run_does_not_post(monkeypatch):
    calls = _stub_post(monkeypatch, _ok())
    WebhookSink(url=URL, dry_run=True).emit(ITEMS)
    assert calls == []
