"""Fill each item's `summary` via the LLM (or offline extractive fallback)."""
from __future__ import annotations

from .. import llm
from ..models import Item
from ..registry import processor
from .base import Processor


@processor("summarize")
class SummarizeProcessor(Processor):
    def process(self, items: list[Item]) -> list[Item]:
        max_sentences = int(self.config.get("max_sentences", 2))
        for item in items:
            text = item.content or item.title
            item.summary = llm.summarize(text, max_sentences=max_sentences)
        return items
