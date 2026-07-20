"""A tiny plugin registry so the pipeline is configured by name in YAML.

Sources, processors, and sinks register themselves with a string key; the
config file references those keys. Adding a new component is one decorator and
zero changes to the runner.
"""
from __future__ import annotations

from typing import Callable, TypeVar

T = TypeVar("T")

SOURCES: dict[str, type] = {}
PROCESSORS: dict[str, type] = {}
SINKS: dict[str, type] = {}


class ConfigSpec:
    """Optional declaration of the YAML keys a plugin understands.

    Consumed by ``autoflow validate`` to catch typo'd or missing config before a
    scheduled run. Leaving ``config_keys`` empty disables unknown-key checking,
    so third-party plugins are never forced to opt in.
    """

    config_keys: tuple[str, ...] = ()
    required_keys: tuple[str, ...] = ()


def _register(table: dict[str, type], name: str) -> Callable[[type[T]], type[T]]:
    def deco(cls: type[T]) -> type[T]:
        if name in table:
            raise ValueError(f"duplicate registration for '{name}'")
        table[name] = cls
        return cls

    return deco


def source(name: str):
    return _register(SOURCES, name)


def processor(name: str):
    return _register(PROCESSORS, name)


def sink(name: str):
    return _register(SINKS, name)
