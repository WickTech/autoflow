"""Source plugins. Importing this package registers the built-ins."""
from . import reddit, rss  # noqa: F401  (registers "reddit", "rss")

__all__ = ["reddit", "rss"]
