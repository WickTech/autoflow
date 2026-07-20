"""Persistent set of already-seen item fingerprints for cross-run dedup."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


class SeenStore:
    def __init__(self, path: str | Path = ".autoflow_state.json") -> None:
        self.path = Path(path)
        self._seen: set[str] = set()
        if self.path.exists():
            try:
                self._seen = set(json.loads(self.path.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, ValueError, OSError):
                self._seen = set()

    def __contains__(self, fingerprint: str) -> bool:
        return fingerprint in self._seen

    def add(self, fingerprint: str) -> None:
        self._seen.add(fingerprint)

    def save(self) -> None:
        """Write atomically.

        A truncated state file is worse than no state file: the load path treats
        invalid JSON as an empty seen-set, which silently re-delivers everything.
        Write to a temp file in the same directory, then ``os.replace`` — on both
        POSIX and Windows that swap is atomic, so readers see old or new, never half.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(
            dir=str(self.path.parent or "."), prefix=f".{self.path.name}.", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(sorted(self._seen), handle)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, self.path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
