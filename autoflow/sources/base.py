from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable
from xml.etree.ElementTree import ParseError

import httpx

from ..log import log
from ..models import Item
from ..registry import ConfigSpec


class Source(ConfigSpec, ABC):
    """Produces items. Configured from a dict in the pipeline YAML."""

    def __init__(self, **config) -> None:
        self.config = config

    @abstractmethod
    def fetch(self) -> list[Item]:
        ...


# What one bad feed/subreddit can raise: HTTP status/transport errors, a missing
# local file, unparseable XML/JSON (defusedxml's errors subclass ValueError).
FETCH_ERRORS: tuple[type[BaseException], ...] = (httpx.HTTPError, OSError, ValueError, ParseError)


def fetch_each(
    keys: Iterable[str],
    fetch_one: Callable[[str], list[Item]],
    *,
    label: Callable[[str], str] = str,
) -> list[Item]:
    """Fetch every key, skipping (and logging) the ones that fail.

    One dead feed shouldn't cost the whole digest. But if *every* key fails the
    last error is re-raised: a total outage must fail the run loudly, not
    deliver an empty digest and report success.
    """
    items: list[Item] = []
    last_error: BaseException | None = None
    succeeded = 0
    for key in keys:
        try:
            items.extend(fetch_one(key))
        except FETCH_ERRORS as exc:
            last_error = exc
            log.warning(
                "skipping %s: %s: %s", label(key), type(exc).__name__, exc,
                extra={"source_key": label(key), "error": type(exc).__name__},
            )
        else:
            succeeded += 1
    if last_error is not None and succeeded == 0:
        raise last_error
    return items
