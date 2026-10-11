"""Fill each item's `summary` via the LLM (or offline extractive fallback)."""
from __future__ import annotations

from .. import llm
from ..models import Item
from ..registry import processor
from .base import Processor


@processor("summarize")
class SummarizeProcessor(Processor):
    config_keys = ("max_sentences",)

    def process(self, items: list[Item]) -> list[Item]:
        max_sentences = int(self.config.get("max_sentences", 2))
        for item in items:
            # No body means nothing to summarize: restating the title as a
            # "summary" (or paying an LLM to) adds noise, not information.
            if item.content.strip():
                item.summary = llm.summarize(item.content, max_sentences=max_sentences)
        return items
