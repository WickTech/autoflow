"""Processor plugins. Importing this package registers the built-ins."""
from . import dedup, keyword_filter, summarize  # noqa: F401

__all__ = ["dedup", "keyword_filter", "summarize"]
