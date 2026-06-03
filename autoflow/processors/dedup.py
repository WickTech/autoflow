"""Drop items already seen in previous runs (persistent) or within this batch."""
from __future__ import annotations

from ..models import Item
from ..registry import processor
from ..state import SeenStore
from .base import Processor


@processor("dedup")
class DedupProcessor(Processor):
    def process(self, items: list[Item]) -> list[Item]:
        state_path = self.config.get("state_path", ".autoflow_state.json")
        store = SeenStore(state_path)

        fresh: list[Item] = []
        batch_seen: set[str] = set()
        for item in items:
            fp = item.fingerprint
            if fp in store or fp in batch_seen:
                continue
            fresh.append(item)
            batch_seen.add(fp)
            store.add(fp)

        if self.config.get("persist", True):
            store.save()
        return fresh
