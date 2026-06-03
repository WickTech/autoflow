from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Item


class Source(ABC):
    """Produces items. Configured from a dict in the pipeline YAML."""

    def __init__(self, **config) -> None:
        self.config = config

    @abstractmethod
    def fetch(self) -> list[Item]:
        ...
