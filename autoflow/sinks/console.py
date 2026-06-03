from __future__ import annotations

from ..models import Item
from ..registry import sink
from .base import Sink


@sink("console")
class ConsoleSink(Sink):
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
