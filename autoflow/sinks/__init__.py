"""Sink plugins. Importing this package registers the built-ins."""
from . import console, email, markdown, telegram, webhook  # noqa: F401

__all__ = ["console", "email", "markdown", "telegram", "webhook"]
