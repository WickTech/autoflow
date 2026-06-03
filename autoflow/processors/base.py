from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Item


class Processor(ABC):
    """Transforms or filters the item stream. Configured from YAML."""

    def __init__(self, **config) -> None:
        self.config = config

    @abstractmethod
    def process(self, items: list[Item]) -> list[Item]:
        ...
