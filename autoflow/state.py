"""Persistent set of already-seen item fingerprints for cross-run dedup."""
from __future__ import annotations

import json
from pathlib import Path


class SeenStore:
    def __init__(self, path: str | Path = ".autoflow_state.json") -> None:
        self.path = Path(path)
        self._seen: set[str] = set()
        if self.path.exists():
            try:
                self._seen = set(json.loads(self.path.read_text()))
            except (json.JSONDecodeError, ValueError):
                self._seen = set()

    def __contains__(self, fingerprint: str) -> bool:
        return fingerprint in self._seen

    def add(self, fingerprint: str) -> None:
        self._seen.add(fingerprint)

    def save(self) -> None:
        self.path.write_text(json.dumps(sorted(self._seen)))
