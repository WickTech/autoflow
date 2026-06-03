"""autoflow CLI."""
from __future__ import annotations

import sys

import typer

# Ensure Unicode output (arrows, emoji) doesn't crash on Windows' cp1252 console.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass

from .pipeline import PipelineConfig, run_pipeline
from .registry import PROCESSORS, SINKS, SOURCES

app = typer.Typer(help="autoflow — pluggable content automation (sources → processors → sinks).")


@app.command()
def run(
    config: str = typer.Argument(..., help="Path to a pipeline YAML file."),
    quiet: bool = typer.Option(False, "--quiet", "-q"),
) -> None:
    """Run a pipeline defined in a YAML config."""
    cfg = PipelineConfig.from_yaml(config)
    result = run_pipeline(cfg, verbose=not quiet)
    if not quiet:
        typer.echo(f"\nDone: fetched {result.fetched}, delivered {result.emitted}.")


@app.command()
def plugins() -> None:
    """List all registered sources, processors, and sinks."""
    typer.echo("Sources:    " + ", ".join(sorted(SOURCES)))
    typer.echo("Processors: " + ", ".join(sorted(PROCESSORS)))
    typer.echo("Sinks:      " + ", ".join(sorted(SINKS)))


if __name__ == "__main__":
    app()
