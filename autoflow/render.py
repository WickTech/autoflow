"""Turn items into the text a sink delivers.

Every chat-style sink wants the same digest in a slightly different dialect, so
the formatting lives here rather than being copy-pasted per sink:

* ``slack``    — ``<url|title>``, Slack's mrkdwn (the historical default)
* ``markdown`` — ``[title](url)``, for Discord, Telegram and anything sane
* ``html``     — for Telegram's HTML parse mode and email bodies
* ``plain``    — no markup at all
"""
from __future__ import annotations

from html import escape

from .models import Item

STYLES = ("slack", "markdown", "html", "plain")


def _link(item: Item, style: str) -> str:
    if not item.url:
        return escape(item.title) if style == "html" else item.title
    if style == "slack":
        return f"<{item.url}|{item.title}>"
    if style == "markdown":
        return f"[{item.title}]({item.url})"
    if style == "html":
        return f'<a href="{escape(item.url, quote=True)}">{escape(item.title)}</a>'
    return f"{item.title} — {item.url}"


def render_text(items: list[Item], *, header: str = "", style: str = "slack") -> str:
    """One bullet per item, in the given dialect."""
    if style not in STYLES:
        raise ValueError(f"unknown format '{style}'. Available: {list(STYLES)}")

    lines = [header] if header else []
    for item in items:
        bullet = f"• {_link(item, style)}"
        if item.summary:
            summary = escape(item.summary) if style == "html" else item.summary
            bullet += f" — {summary}"
        lines.append(bullet)
    return "\n".join(lines)


def render_html_document(items: list[Item], *, title: str) -> str:
    """A minimal, client-safe HTML digest — no CSS frameworks, no images."""
    parts = [
        "<html><body style=\"font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif\">",
        f"<h2>{escape(title)}</h2>",
    ]
    if not items:
        parts.append("<p><em>No new items.</em></p>")
    for item in items:
        parts.append(f"<p><strong>{_link(item, 'html')}</strong>")
        if item.summary:
            parts.append(f"<br>{escape(item.summary)}")
        if item.source:
            parts.append(f'<br><small style="color:#666">source: {escape(item.source)}</small>')
        parts.append("</p>")
    parts.append("</body></html>")
    return "\n".join(parts)


def chunk(text: str, limit: int) -> list[str]:
    """Split ``text`` into <= ``limit`` character pieces, preferring line breaks.

    Chat APIs reject oversized payloads outright (Telegram caps a message at
    4096 characters), so a long digest has to arrive as several messages rather
    than as a 400.
    """
    if limit <= 0 or len(text) <= limit:
        return [text] if text else []

    pieces: list[str] = []
    current: list[str] = []
    length = 0

    for line in text.split("\n"):
        # A single line longer than the limit has to be hard-split.
        while len(line) > limit:
            if current:
                pieces.append("\n".join(current))
                current, length = [], 0
            pieces.append(line[:limit])
            line = line[limit:]

        extra = len(line) + (1 if current else 0)
        if length + extra > limit:
            pieces.append("\n".join(current))
            current, length = [line], len(line)
        else:
            current.append(line)
            length += extra

    if current:
        pieces.append("\n".join(current))
    return pieces
