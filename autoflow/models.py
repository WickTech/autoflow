"""Core data types flowing through the pipeline."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Item:
    """A single piece of content moving through the pipeline."""

    title: str
    url: str
    content: str = ""
    summary: str = ""
    source: str = ""
    published: datetime | None = None
    metadata: dict = field(default_factory=dict)

    @property
    def fingerprint(self) -> str:
        """Stable id used for cross-run deduplication (URL first, else title+content)."""
        basis = self.url or f"{self.title}:{self.content[:200]}"
        return hashlib.sha1(basis.encode("utf-8")).hexdigest()
