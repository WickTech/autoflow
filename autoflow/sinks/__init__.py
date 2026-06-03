"""Sink plugins. Importing this package registers the built-ins."""
from . import console, markdown, webhook  # noqa: F401

__all__ = ["console", "markdown", "webhook"]
