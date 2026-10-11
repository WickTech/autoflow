"""Sink plugins. Importing this package registers the built-ins."""
from . import console, email, markdown, telegram, webhook

__all__ = ["console", "email", "markdown", "telegram", "webhook"]
