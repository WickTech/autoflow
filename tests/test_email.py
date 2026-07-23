"""SMTP sink — offline, smtplib is stubbed. No sockets are opened."""
from __future__ import annotations

import pytest

from autoflow.models import Item
from autoflow.sinks import email as email_mod
from autoflow.sinks.email import EmailSink

ITEMS = [Item(title="AI model shipped", url="https://x.test/1", summary="It shipped.")]
CONFIG = {
    "to": ["someone@example.com"],
    "host": "smtp.example.com",
    "username": "bot@example.com",
    "password": "hunter2",
}


class _FakeServer:
    def __init__(self, host, port, timeout=None):
        self.host, self.port, self.timeout = host, port, timeout
        self.started_tls = False
        self.login_args = None
        self.sent = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        self.started_tls = True

    def login(self, username, password):
        self.login_args = (username, password)

    def send_message(self, message):
        self.sent.append(message)


@pytest.fixture
def servers(monkeypatch):
    """Capture every SMTP/SMTP_SSL connection the sink opens."""
    made: list[_FakeServer] = []

    def _factory(ssl: bool):
        def _open(host, port, timeout=None):
            server = _FakeServer(host, port, timeout)
            server.ssl = ssl
            made.append(server)
            return server

        return _open

    monkeypatch.setattr(email_mod.smtplib, "SMTP", _factory(False))
    monkeypatch.setattr(email_mod.smtplib, "SMTP_SSL", _factory(True))
    return made


def test_sends_a_multipart_message(servers):
    EmailSink(**CONFIG, subject="AI Digest").emit(ITEMS)

    assert len(servers) == 1
    message = servers[0].sent[0]
    assert message["To"] == "someone@example.com"
    assert message["From"] == "bot@example.com"
    assert message["Subject"].startswith("AI Digest — ")
    assert message.is_multipart(), "plain text and HTML alternatives expected"

    body = message.get_body(preferencelist=("plain",)).get_content()
    html = message.get_body(preferencelist=("html",)).get_content()
    assert "AI model shipped" in body
    assert "<a href=" in html


def test_starttls_and_login_by_default(servers):
    EmailSink(**CONFIG).emit(ITEMS)
    assert servers[0].started_tls is True
    assert servers[0].login_args == ("bot@example.com", "hunter2")
    assert servers[0].port == email_mod.DEFAULT_PORT


def test_implicit_tls_skips_starttls(servers):
    EmailSink(**CONFIG, ssl=True, port=465).emit(ITEMS)
    assert servers[0].ssl is True
    assert servers[0].started_tls is False
    assert servers[0].port == 465


def test_a_single_string_recipient_is_accepted(servers):
    EmailSink(**{**CONFIG, "to": "solo@example.com"}).emit(ITEMS)
    assert servers[0].sent[0]["To"] == "solo@example.com"


def test_env_references_are_resolved(monkeypatch, servers):
    monkeypatch.setenv("SMTP_HOST", "mail.example.net")
    monkeypatch.setenv("SMTP_USERNAME", "env-user")
    monkeypatch.setenv("SMTP_PASSWORD", "env-pass")
    EmailSink(to=["x@example.com"]).emit(ITEMS)
    assert servers[0].host == "mail.example.net"
    assert servers[0].login_args == ("env-user", "env-pass")


def test_missing_host_is_skipped_not_fatal(monkeypatch, servers):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    EmailSink(to=["x@example.com"]).emit(ITEMS)
    assert servers == []


def test_missing_recipients_is_skipped(servers):
    EmailSink(to=[], host="smtp.example.com").emit(ITEMS)
    assert servers == []


def test_no_sender_is_skipped(monkeypatch, servers):
    monkeypatch.delenv("SMTP_USERNAME", raising=False)
    EmailSink(to=["x@example.com"], host="smtp.example.com").emit(ITEMS)
    assert servers == [], "no from address and no username means nothing to send as"


def test_no_items_means_no_connection(servers):
    EmailSink(**CONFIG).emit([])
    assert servers == []


def test_dry_run_does_not_connect(servers):
    EmailSink(**CONFIG, dry_run=True).emit(ITEMS)
    assert servers == []
