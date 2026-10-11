"""RSS / Atom source. ElementTree-based parsing — no feedparser dependency.

Accepts http(s) URLs or local file paths (handy for tests and offline runs).
Remote fetches go through :mod:`autoflow.net` so transient failures are retried.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

try:
    # Feeds are untrusted remote input; defusedxml blocks entity-expansion
    # ("billion laughs") and external-entity attacks. Falls back to the stdlib
    # parser so an older install keeps working.
    from defusedxml.ElementTree import fromstring as _fromstring
except ImportError:  # pragma: no cover
    from xml.etree.ElementTree import fromstring as _fromstring

from .. import net
from ..models import Item
from ..registry import source
from .base import Source

_ATOM = "{http://www.w3.org/2005/Atom}"

# Tags that end a line of text when HTML is flattened.
_BLOCK_TAGS = frozenset({"p", "br", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"})

# hnrss.org puts only link metadata in <description> ("Points: 22", ...). It is
# not prose, so it goes to Item.metadata instead of being "summarized".
_HNRSS_LINE = re.compile(r"^(Article URL|Comments URL|Points|# Comments):\s*(.*)$")
_HNRSS_KEYS = {"Comments URL": "comments_url", "Points": "points", "# Comments": "comments"}


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip = max(0, self._skip - 1)
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            # Source newlines are just whitespace in HTML; only block tags break lines.
            self.parts.append(data.replace("\r", " ").replace("\n", " "))


def html_to_text(markup: str) -> str:
    """Flatten feed HTML to plain text: tags dropped, entities decoded,
    one line per block element, whitespace collapsed."""
    if "<" not in markup and "&" not in markup:
        return markup.strip()
    parser = _TextExtractor()
    parser.feed(markup)
    parser.close()
    lines = (" ".join(line.split()) for line in "".join(parser.parts).splitlines())
    return "\n".join(line for line in lines if line)


def _split_hnrss(text: str) -> tuple[str, dict]:
    """Pull hnrss metadata lines out of a description; return (prose, metadata)."""
    prose, meta = [], {}
    for line in text.splitlines():
        match = _HNRSS_LINE.match(line)
        if not match:
            prose.append(line)
            continue
        key = _HNRSS_KEYS.get(match.group(1))
        if key:
            meta[key] = match.group(2).strip()
    return "\n".join(prose), meta


def _content(raw: str) -> tuple[str, dict]:
    return _split_hnrss(html_to_text(raw))


def _text(el, *tags: str) -> str:
    for tag in tags:
        found = el.find(tag)
        if found is not None and found.text:
            return found.text.strip()
    return ""


@source("rss")
class RssSource(Source):
    config_keys = ("url", "urls", "limit", "timeout", "retries")

    def fetch(self) -> list[Item]:
        urls = self.config.get("urls") or ([self.config["url"]] if "url" in self.config else [])
        limit = int(self.config.get("limit", 20))
        items: list[Item] = []
        for url in urls:
            items.extend(self._parse(self._load(url), url))
        return items[:limit] if limit else items

    def _load(self, url: str) -> str:
        if url.startswith(("http://", "https://")):
            resp = net.get(
                url,
                timeout=float(self.config.get("timeout", net.DEFAULT_TIMEOUT)),
                retries=int(self.config.get("retries", net.DEFAULT_RETRIES)),
            )
            resp.raise_for_status()
            return resp.text
        return Path(url).read_text(encoding="utf-8")

    @staticmethod
    def _parse(xml: str, origin: str) -> list[Item]:
        root = _fromstring(xml)
        items: list[Item] = []

        # RSS 2.0
        for it in root.iter("item"):
            link = _text(it, "link")
            content, meta = _content(
                _text(it, "description", "{http://purl.org/rss/1.0/modules/content/}encoded")
            )
            items.append(
                Item(
                    title=html_to_text(_text(it, "title")) or "(untitled)",
                    url=link,
                    content=content,
                    source=origin,
                    metadata=meta,
                )
            )

        # Atom
        for it in root.iter(f"{_ATOM}entry"):
            link_el = it.find(f"{_ATOM}link")
            link = link_el.get("href") if link_el is not None else ""
            content, meta = _content(_text(it, f"{_ATOM}summary", f"{_ATOM}content"))
            items.append(
                Item(
                    title=html_to_text(_text(it, f"{_ATOM}title")) or "(untitled)",
                    url=link or "",
                    content=content,
                    source=origin,
                    metadata=meta,
                )
            )
        return items
