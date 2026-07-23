"""Build and run a pipeline from a declarative config.

A pipeline is: one source → an ordered list of processors → one or more sinks.
Everything is referenced by registry name, so the YAML fully describes the run.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

import yaml

# Importing these packages registers all built-in plugins.
from . import env, llm
from . import processors as _processors  # noqa: F401
from . import sinks as _sinks  # noqa: F401
from . import sources as _sources  # noqa: F401
from .log import log
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
class Issue:
    """A problem found by :func:`validate_config`."""

    level: str  # "error" | "warning"
    where: str  # e.g. "processors[1]"
    message: str

    def __str__(self) -> str:
        return f"{self.level.upper():7} {self.where}: {self.message}"


def _check_spec(table: dict, spec: dict, where: str, kind_label: str) -> list[Issue]:
    issues: list[Issue] = []

    if not isinstance(spec, dict):
        return [Issue("error", where, f"expected a mapping, got {type(spec).__name__}")]
    if "type" not in spec:
        return [Issue("error", where, f"missing required key 'type' ({kind_label})")]

    kind = spec["type"]
    if kind not in table:
        return [
            Issue("error", where, f"unknown {kind_label} '{kind}'. Available: {sorted(table)}")
        ]

    cls = table[kind]
    given = {k for k in spec if k != "type"}

    for required in getattr(cls, "required_keys", ()):
        if required not in given:
            issues.append(Issue("error", where, f"'{kind}' requires key '{required}'"))

    known = set(getattr(cls, "config_keys", ()))
    if known:  # empty means the plugin opted out of unknown-key checking
        for key in sorted(given - known):
            msg = f"'{kind}' does not use key '{key}' (known: {sorted(known)})"
            issues.append(Issue("warning", where, msg))

    # ${VAR} references are resolved at runtime — warn early if unset.
    for key, value in spec.items():
        for candidate in value if isinstance(value, list) else [value]:
            var = env.ref_name(candidate)
            if var and not os.getenv(var):
                issues.append(Issue("warning", where, f"'{key}' references ${var}, which is unset"))

    return issues


def validate_config(config: PipelineConfig) -> list[Issue]:
    """Statically check a pipeline config without running it.

    Catches typo'd keys, unknown component names, missing required options, and
    unresolved ``${ENV_VAR}`` references — before a scheduled run does.
    """
    issues = _check_spec(SOURCES, config.source, "source", "source")

    for i, spec in enumerate(config.processors):
        issues += _check_spec(PROCESSORS, spec, f"processors[{i}]", "processor")

    if not config.sinks:
        issues.append(Issue("warning", "sinks", "no sinks configured — items go nowhere"))
    for i, spec in enumerate(config.sinks):
        issues += _check_spec(SINKS, spec, f"sinks[{i}]", "sink")

    return issues


@dataclass
class RunResult:
    fetched: int
    emitted: int
    items: list[Item]


def run_pipeline(config: PipelineConfig, *, verbose: bool = True) -> RunResult:
    llm.reset_budget()  # token budget is per run, not per process

    source = _build(SOURCES, config.source)
    items = source.fetch()
    fetched = len(items)
    if verbose:
        log.info(
            "[%s] fetched %d item(s)",
            config.name,
            fetched,
            extra={"pipeline": config.name, "stage": "source", "count": fetched},
        )

    built: list = []
    for spec in config.processors:
        proc = _build(PROCESSORS, spec)
        built.append(proc)
        before = len(items)
        items = proc.process(items)
        if verbose:
            log.info(
                "[%s] %s: %d → %d",
                config.name,
                spec["type"],
                before,
                len(items),
                extra={
                    "pipeline": config.name,
                    "stage": spec["type"],
                    "before": before,
                    "after": len(items),
                },
            )

    for spec in config.sinks:
        _build(SINKS, spec).emit(items)

    # Only now are the items definitely delivered — persist processor side
    # effects (dedup state) so a sink failure is retried on the next run.
    for proc in built:
        proc.commit()

    if verbose and llm.tokens_used():
        log.info(
            "[%s] LLM tokens used: %d",
            config.name,
            llm.tokens_used(),
            extra={"pipeline": config.name, "tokens": llm.tokens_used()},
        )

    return RunResult(fetched=fetched, emitted=len(items), items=items)
