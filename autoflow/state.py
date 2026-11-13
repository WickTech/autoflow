"""Persistent set of already-seen item fingerprints for cross-run dedup."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .log import log


class SeenStore:
    def __init__(self, path: str | Path = ".autoflow_state.json") -> None:
        self.path = Path(path)
        self._seen: set[str] = set()
        if self.path.exists():
            try:
                self._seen = set(json.loads(self.path.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, ValueError, TypeError, OSError) as exc:
                self._seen = set()
                self._quarantine(exc)

    def _quarantine(self, exc: BaseException) -> None:
        """Keep an unreadable state file instead of silently overwriting it.

        Starting from an empty seen-set re-delivers everything, so say so loudly
        and move the bad file aside (``<name>.corrupt``) so it can be inspected.
        """
        backup = self.path.with_name(self.path.name + ".corrupt")
        try:
            os.replace(self.path, backup)
            where = f"moved to {backup}"
        except OSError:
            where = "could not be backed up"
        log.warning(
            "state file %s is unreadable (%s: %s); starting with an empty seen-set, "
            "previously seen items may be re-sent. Bad file %s",
            self.path, type(exc).__name__, exc, where,
            extra={"state_path": str(self.path), "error": type(exc).__name__},
        )

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
