from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Item


class Sink(ABC):
    """Delivers the final items somewhere. Configured from YAML."""

    def __init__(self, **config) -> None:
        self.config = config

    @abstractmethod
    def emit(self, items: list[Item]) -> None:
        ...
