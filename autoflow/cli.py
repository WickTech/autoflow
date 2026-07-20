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

# Imported after the reconfigure() above so plugin import side effects can't
# print before stdout is UTF-8. E402 is deliberate here.
from .log import configure as configure_logging  # noqa: E402
from .pipeline import PipelineConfig, run_pipeline, validate_config  # noqa: E402
from .registry import PROCESSORS, SINKS, SOURCES  # noqa: E402

app = typer.Typer(help="autoflow — pluggable content automation (sources → processors → sinks).")


@app.command()
def run(
    config: str = typer.Argument(..., help="Path to a pipeline YAML file."),
    quiet: bool = typer.Option(False, "--quiet", "-q"),
    log_level: str = typer.Option("INFO", "--log-level", help="DEBUG, INFO, WARNING, ERROR."),
    log_format: str = typer.Option("text", "--log-format", help="text or json."),
) -> None:
    """Run a pipeline defined in a YAML config."""
    configure_logging(level="WARNING" if quiet else log_level, fmt=log_format)
    cfg = PipelineConfig.from_yaml(config)
    result = run_pipeline(cfg, verbose=not quiet)
    if not quiet:
        typer.echo(f"\nDone: fetched {result.fetched}, delivered {result.emitted}.")


@app.command()
def validate(
    configs: list[str] = typer.Argument(..., help="One or more pipeline YAML files."),
    strict: bool = typer.Option(False, "--strict", help="Treat warnings as errors."),
) -> None:
    """Check pipeline configs without running them. Exits 1 if any are invalid."""
    failed = False

    for path in configs:
        try:
            issues = validate_config(PipelineConfig.from_yaml(path))
        except (OSError, KeyError, ValueError) as exc:
            typer.secho(f"✗ {path}: could not be parsed — {exc}", fg="red")
            failed = True
            continue

        errors = [i for i in issues if i.level == "error"]
        warnings = [i for i in issues if i.level == "warning"]

        if not issues:
            typer.secho(f"✓ {path}: ok", fg="green")
            continue

        colour = "red" if errors else "yellow"
        typer.secho(f"{'✗' if errors else '!'} {path}", fg=colour)
        for issue in issues:
            typer.secho(f"    {issue}", fg="red" if issue.level == "error" else "yellow")

        if errors or (strict and warnings):
            failed = True

    if failed:
        raise typer.Exit(code=1)


@app.command()
def plugins() -> None:
    """List all registered sources, processors, and sinks."""
    typer.echo("Sources:    " + ", ".join(sorted(SOURCES)))
    typer.echo("Processors: " + ", ".join(sorted(PROCESSORS)))
    typer.echo("Sinks:      " + ", ".join(sorted(SINKS)))


if __name__ == "__main__":
    app()
