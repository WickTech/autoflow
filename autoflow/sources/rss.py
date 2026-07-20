"""RSS / Atom source. ElementTree-based parsing — no feedparser dependency.

Accepts http(s) URLs or local file paths (handy for tests and offline runs).
Remote fetches go through :mod:`autoflow.net` so transient failures are retried.
"""
from __future__ import annotations

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
            items.append(
                Item(
                    title=_text(it, "title") or "(untitled)",
                    url=link,
                    content=_text(it, "description", "{http://purl.org/rss/1.0/modules/content/}encoded"),
                    source=origin,
                )
            )

        # Atom
        for it in root.iter(f"{_ATOM}entry"):
            link_el = it.find(f"{_ATOM}link")
            link = link_el.get("href") if link_el is not None else ""
            items.append(
                Item(
                    title=_text(it, f"{_ATOM}title") or "(untitled)",
                    url=link or "",
                    content=_text(it, f"{_ATOM}summary", f"{_ATOM}content"),
                    source=origin,
                )
            )
        return items
