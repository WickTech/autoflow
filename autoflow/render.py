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

# Feed titles and summaries are untrusted text. Unescaped, a title like
# "<!channel>" pings a whole Slack channel, and a stray "_" or "[" makes
# Telegram reject the message outright.
_SLACK_ESCAPES = str.maketrans({"&": "&amp;", "<": "&lt;", ">": "&gt;"})
_SLACK_URL_ESCAPES = str.maketrans({"|": "%7C", "<": "%3C", ">": "%3E"})
_MD_TITLE_ESCAPES = str.maketrans({"\\": "\\\\", "[": "\\[", "]": "\\]"})
_MD_TEXT_ESCAPES = str.maketrans(
    {"\\": "\\\\", "_": "\\_", "*": "\\*", "`": "\\`", "[": "\\[", "]": "\\]"}
)
_MD_URL_ESCAPES = str.maketrans({"(": "%28", ")": "%29", " ": "%20", "<": "%3C", ">": "%3E"})


def _text(value: str, style: str) -> str:
    """Escape free text (titles without a URL, summaries) for ``style``."""
    if style == "html":
        return escape(value)
    if style == "slack":
        return value.translate(_SLACK_ESCAPES)
    if style == "markdown":
        return value.translate(_MD_TEXT_ESCAPES)
    return value


def _link(item: Item, style: str) -> str:
    if not item.url:
        return _text(item.title, style)
    if style == "slack":
        url = item.url.translate(_SLACK_URL_ESCAPES)
        return f"<{url}|{item.title.translate(_SLACK_ESCAPES)}>"
    if style == "markdown":
        url = item.url.translate(_MD_URL_ESCAPES)
        return f"[{item.title.translate(_MD_TITLE_ESCAPES)}]({url})"
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
            bullet += f" — {_text(item.summary, style)}"
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
