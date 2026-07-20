from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Item
from ..registry import ConfigSpec


class Processor(ConfigSpec, ABC):
    """Transforms or filters the item stream. Configured from YAML."""

    def __init__(self, **config) -> None:
        self.config = config

    @abstractmethod
    def process(self, items: list[Item]) -> list[Item]:
        ...

    def commit(self) -> None:
        """Persist side effects (e.g. dedup state).

        Called by the runner only after every sink has succeeded, so a failed
        delivery never silently marks items as 'already seen'. No-op by default.
        """
