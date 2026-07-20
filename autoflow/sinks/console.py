from __future__ import annotations

from ..models import Item
from ..registry import sink
from .base import Sink


@sink("console")
class ConsoleSink(Sink):
    """Prints the digest itself, so this deliberately uses ``print`` (stdout)
    rather than the logger (stderr) — ``autoflow run ... > digest.txt`` should
    capture the digest, not the diagnostics."""

    def emit(self, items: list[Item]) -> None:
        if not items:
            print("autoflow: no new items.")
            return
        print(f"autoflow: {len(items)} item(s)\n")
        for i, item in enumerate(items, 1):
            print(f"{i}. {item.title}")
            if item.summary:
                print(f"   {item.summary}")
            if item.url:
                print(f"   {item.url}")
            print()
