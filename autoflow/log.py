"""Structured logging for autoflow.

Two audiences, two streams:

* **Diagnostics** (what the pipeline did, what retried, what fell back) go to
  this logger on **stderr**.
* **Deliverables** (the console sink's digest) stay on ``print`` / **stdout**,
  so ``autoflow run ... > digest.txt`` still does the obvious thing.

``--log-format json`` emits one JSON object per line, which is what you want
when piping GitHub Actions logs into anything that parses them.
"""
from __future__ import annotations

import json
import logging
import os
import sys

LOGGER_NAME = "autoflow"
log = logging.getLogger(LOGGER_NAME)

# Fields the stdlib puts on every record; anything else was added by us via
# `extra=` and belongs in the structured payload.
_STANDARD = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {
    "asctime",
    "message",
    "taskName",
}


class JsonFormatter(logging.Formatter):
    """One JSON object per line, with any ``extra=`` fields merged in."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure(level: str = "INFO", fmt: str = "text", *, stream=None) -> None:
    """Point the autoflow logger at ``stream`` (default stderr).

    Safe to call more than once — handlers are replaced, not stacked, so
    repeated CLI invocations in one process don't duplicate every line.
    """
    level = (os.getenv("AUTOFLOW_LOG_LEVEL") or level).upper()
    fmt = (os.getenv("AUTOFLOW_LOG_FORMAT") or fmt).lower()

    handler = logging.StreamHandler(stream if stream is not None else sys.stderr)
    if fmt == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(levelname)-7s %(message)s"))

    for existing in list(log.handlers):
        log.removeHandler(existing)
    log.addHandler(handler)
    log.setLevel(getattr(logging, level, logging.INFO))
    log.propagate = False  # don't double-print through the root logger
