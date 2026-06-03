"""Build and run a pipeline from a declarative config.

A pipeline is: one source → an ordered list of processors → one or more sinks.
Everything is referenced by registry name, so the YAML fully describes the run.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import yaml

# Importing these packages registers all built-in plugins.
from . import processors as _processors  # noqa: F401
from . import sinks as _sinks  # noqa: F401
from . import sources as _sources  # noqa: F401
from .models import Item
from .registry import PROCESSORS, SINKS, SOURCES


@dataclass
class PipelineConfig:
    name: str
    source: dict
    processors: list[dict] = field(default_factory=list)
    sinks: list[dict] = field(default_factory=list)

    @classmethod
    def from_yaml(cls, path: str) -> "PipelineConfig":
        data = yaml.safe_load(open(path, encoding="utf-8"))
        return cls(
            name=data.get("name", "pipeline"),
            source=data["source"],
            processors=data.get("processors", []),
            sinks=data.get("sinks", []),
        )


def _build(table: dict, spec: dict):
    spec = dict(spec)
    kind = spec.pop("type")
    if kind not in table:
        raise KeyError(f"unknown component '{kind}'. Available: {sorted(table)}")
    return table[kind](**spec)


@dataclass
class RunResult:
    fetched: int
    emitted: int
    items: list[Item]


def run_pipeline(config: PipelineConfig, *, verbose: bool = True) -> RunResult:
    source = _build(SOURCES, config.source)
    items = source.fetch()
    fetched = len(items)
    if verbose:
        print(f"[{config.name}] fetched {fetched} item(s)")

    for spec in config.processors:
        proc = _build(PROCESSORS, spec)
        before = len(items)
        items = proc.process(items)
        if verbose:
            print(f"[{config.name}] {spec['type']}: {before} → {len(items)}")

    for spec in config.sinks:
        _build(SINKS, spec).emit(items)

    return RunResult(fetched=fetched, emitted=len(items), items=items)
