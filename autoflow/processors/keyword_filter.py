"""Keep only items matching (or excluding) given keywords.

Matching is word-boundary based by default: ``ai`` matches "AI model" but not
"chair", "said", or "Ukraine". Multi-word keywords ("machine learning") match as
a phrase. Set ``substring: true`` for the old naive behaviour.
"""
from __future__ import annotations

import re
from functools import lru_cache

from ..models import Item
from ..registry import processor
from .base import Processor


@lru_cache(maxsize=256)
def _pattern(keyword: str) -> re.Pattern[str]:
    """Word-boundary matcher for a keyword or phrase (whitespace-tolerant)."""
    parts = [re.escape(word) for word in keyword.split()]
    return re.compile(r"\b" + r"\s+".join(parts) + r"\b", re.IGNORECASE)


@processor("keyword_filter")
class KeywordFilter(Processor):
    config_keys = ("include", "exclude", "substring")

    def process(self, items: list[Item]) -> list[Item]:
        include = [k.lower() for k in self.config.get("include", []) if k.strip()]
        exclude = [k.lower() for k in self.config.get("exclude", []) if k.strip()]
        substring = bool(self.config.get("substring", False))

        def matches(keyword: str, text: str) -> bool:
            return keyword in text if substring else bool(_pattern(keyword).search(text))

        result = []
        for item in items:
            text = f"{item.title} {item.content}".lower()
            if include and not any(matches(k, text) for k in include):
                continue
            if exclude and any(matches(k, text) for k in exclude):
                continue
            result.append(item)
        return result
