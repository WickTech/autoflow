"""Keep only items matching (or excluding) given keywords."""
from __future__ import annotations

from ..models import Item
from ..registry import processor
from .base import Processor


@processor("keyword_filter")
class KeywordFilter(Processor):
    def process(self, items: list[Item]) -> list[Item]:
        include = [k.lower() for k in self.config.get("include", [])]
        exclude = [k.lower() for k in self.config.get("exclude", [])]

        def haystack(item: Item) -> str:
            return f"{item.title} {item.content}".lower()

        result = []
        for item in items:
            text = haystack(item)
            if include and not any(k in text for k in include):
                continue
            if exclude and any(k in text for k in exclude):
                continue
            result.append(item)
        return result
