"""Logging configuration and the JSON formatter."""
from __future__ import annotations

import io
import json
import logging

import pytest

from autoflow import log as log_mod
from autoflow.log import log


@pytest.fixture(autouse=True)
def _restore_handlers():
    original = list(log.handlers)
    original_level = log.level
    original_propagate = log.propagate
    yield
    log.handlers[:] = original
    log.setLevel(original_level)
    log.propagate = original_propagate  # configure() disables it; caplog needs it


def _capture(level="INFO", fmt="text"):
    stream = io.StringIO()
    log_mod.configure(level=level, fmt=fmt, stream=stream)
    return stream


def test_text_format_includes_level_and_message():
    stream = _capture()
    log.info("wrote %d item(s)", 3)
    assert "INFO" in stream.getvalue()
    assert "wrote 3 item(s)" in stream.getvalue()


def test_json_format_emits_one_object_per_line():
    stream = _capture(fmt="json")
    log.warning("retrying %s", "soon")

    line = stream.getvalue().strip()
    payload = json.loads(line)
    assert payload["level"] == "WARNING"
    assert payload["message"] == "retrying soon"
    assert payload["logger"] == "autoflow"
    assert "ts" in payload


def test_json_format_merges_extra_fields():
    stream = _capture(fmt="json")
    log.info("fetched", extra={"pipeline": "tech-digest", "count": 30})

    payload = json.loads(stream.getvalue().strip())
    assert payload["pipeline"] == "tech-digest"
    assert payload["count"] == 30


def test_level_filters_lower_severity():
    stream = _capture(level="WARNING")
    log.info("should not appear")
    log.warning("should appear")
    assert "should not appear" not in stream.getvalue()
    assert "should appear" in stream.getvalue()


def test_configure_is_idempotent():
    """Re-configuring must replace handlers, not stack them."""
    stream = _capture()
    log_mod.configure(level="INFO", fmt="text", stream=stream)
    log.info("once")
    assert stream.getvalue().count("once") == 1
    assert len(log.handlers) == 1


def test_env_vars_override_arguments(monkeypatch):
    monkeypatch.setenv("AUTOFLOW_LOG_FORMAT", "json")
    monkeypatch.setenv("AUTOFLOW_LOG_LEVEL", "debug")
    stream = _capture(level="INFO", fmt="text")
    log.debug("debugging")

    payload = json.loads(stream.getvalue().strip())
    assert payload["level"] == "DEBUG"
    assert log.level == logging.DEBUG


def test_exceptions_are_serialised_in_json():
    stream = _capture(fmt="json")
    try:
        raise ValueError("boom")
    except ValueError:
        log.exception("something failed")

    payload = json.loads(stream.getvalue().strip())
    assert "ValueError: boom" in payload["exception"]
