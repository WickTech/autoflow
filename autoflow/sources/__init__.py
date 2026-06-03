"""Source plugins. Importing this package registers the built-ins."""
from . import rss  # noqa: F401  (registers "rss")

__all__ = ["rss"]
