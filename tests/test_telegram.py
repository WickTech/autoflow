"""Telegram sink — offline, the Bot API call is stubbed."""
from __future__ import annotations

import httpx
import pytest

from autoflow.models import Item
from autoflow.sinks import telegram as telegram_mod
from autoflow.sinks.telegram import TelegramSink

ITEMS = [Item(title="AI model shipped", url="https://x.test/1", summary="It shipped.")]
CONFIG = {"token": "123:ABC", "chat_id": "-100"}


def _stub_post(monkeypatch, status=200):
    calls: list[dict] = []

    def _fake_post(url, **kwargs):
        calls.append({"url": url, **kwargs})
        return httpx.Response(status, request=httpx.Request("POST", url))

    monkeypatch.setattr(telegram_mod.net, "post", _fake_post)
    return calls


def test_sends_to_the_bot_api(monkeypatch):
    calls = _stub_post(monkeypatch)
    TelegramSink(**CONFIG).emit(ITEMS)

    assert len(calls) == 1
    assert calls[0]["url"] == "https://api.telegram.org/bot123:ABC/sendMessage"
    payload = calls[0]["json"]
    assert payload["chat_id"] == "-100"
    assert payload["parse_mode"] == "HTML"
    assert "AI model shipped" in payload["text"]


def test_plain_format_sends_no_parse_mode(monkeypatch):
    calls = _stub_post(monkeypatch)
    TelegramSink(**CONFIG, format="plain").emit(ITEMS)
    assert "parse_mode" not in calls[0]["json"]


def test_markdown_format_is_supported(monkeypatch):
    calls = _stub_post(monkeypatch)
    TelegramSink(**CONFIG, format="markdown").emit(ITEMS)
    assert calls[0]["json"]["parse_mode"] == "Markdown"
    assert "[AI model shipped](https://x.test/1)" in calls[0]["json"]["text"]


def test_unknown_format_raises(monkeypatch):
    _stub_post(monkeypatch)
    with pytest.raises(ValueError, match="telegram format"):
        TelegramSink(**CONFIG, format="semaphore").emit(ITEMS)


def test_long_digests_are_split_across_messages(monkeypatch):
    calls = _stub_post(monkeypatch)
    many = [Item(title=f"Item {i}", url=f"https://x.test/{i}") for i in range(400)]
    TelegramSink(**CONFIG, format="plain").emit(many)

    assert len(calls) > 1, "a digest over 4096 chars must not be sent as one message"
    for call in calls:
        assert len(call["json"]["text"]) <= telegram_mod.MAX_MESSAGE_CHARS


def test_env_references_are_resolved(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "999:ZZZ")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "-42")
    calls = _stub_post(monkeypatch)
    TelegramSink().emit(ITEMS)
    assert calls[0]["url"].endswith("/bot999:ZZZ/sendMessage")
    assert calls[0]["json"]["chat_id"] == "-42"


def test_missing_credentials_is_skipped_not_fatal(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    calls = _stub_post(monkeypatch)
    TelegramSink().emit(ITEMS)
    assert calls == []


def test_no_items_means_no_call(monkeypatch):
    calls = _stub_post(monkeypatch)
    TelegramSink(**CONFIG).emit([])
    assert calls == []


def test_dry_run_does_not_send(monkeypatch):
    calls = _stub_post(monkeypatch)
    TelegramSink(**CONFIG, dry_run=True).emit(ITEMS)
    assert calls == []


def test_api_errors_propagate(monkeypatch):
    _stub_post(monkeypatch, status=500)
    with pytest.raises(httpx.HTTPStatusError):
        TelegramSink(**CONFIG).emit(ITEMS)
