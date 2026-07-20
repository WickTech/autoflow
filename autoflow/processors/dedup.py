"""Drop items already seen in previous runs (persistent) or within this batch."""
from __future__ import annotations

from ..models import Item
from ..registry import processor
from ..state import SeenStore
from .base import Processor


@processor("dedup")
class DedupProcessor(Processor):
    config_keys = ("state_path", "persist")

    _pending: SeenStore | None = None

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

        # Deferred: the runner calls commit() only after all sinks succeed, so a
        # failed delivery does not permanently mark unsent items as seen.
        self._pending = store if self.config.get("persist", True) else None
        return fresh

    def commit(self) -> None:
        if self._pending is not None:
            self._pending.save()
            self._pending = None
