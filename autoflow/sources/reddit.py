"""Reddit source. Uses the public JSON API — no OAuth needed for public subreddits.

Supports one or more subreddits. The ``sort`` parameter accepts the same values
Reddit exposes: ``hot``, ``top``, ``new``, ``rising``.
"""
from __future__ import annotations

from datetime import datetime, timezone

import httpx

from ..models import Item
from ..registry import source
from .base import Source

_BASE = "https://www.reddit.com"
_HEADERS = {"User-Agent": "autoflow/0.1 (content pipeline; open-source)"}


@source("reddit")
class RedditSource(Source):
    """Fetch posts from one or more subreddits.

    YAML config keys:
      subreddits: list[str]   # e.g. [python, MachineLearning]
      sort: str               # hot | top | new | rising  (default: hot)
      time: str               # hour | day | week | month | year | all (only for top)
      limit: int              # max items to return total (default: 25)
    """

    def fetch(self) -> list[Item]:
        subs = self.config.get("subreddits") or []
        if not subs and "subreddit" in self.config:
            subs = [self.config["subreddit"]]
        if not subs:
            raise ValueError("reddit source requires 'subreddits' list")

        sort = self.config.get("sort", "hot")
        time = self.config.get("time", "day")
        limit = int(self.config.get("limit", 25))

        items: list[Item] = []
        per_sub = max(1, limit // len(subs)) if subs else limit

        for sub in subs:
            items.extend(self._fetch_sub(sub, sort=sort, time=time, limit=per_sub))

        return items[:limit]

    def _fetch_sub(self, subreddit: str, *, sort: str, time: str, limit: int) -> list[Item]:
        params: dict[str, str | int] = {"limit": min(limit, 100), "raw_json": 1}
        if sort == "top":
            params["t"] = time

        url = f"{_BASE}/r/{subreddit}/{sort}.json"
        resp = httpx.get(url, params=params, headers=_HEADERS, timeout=15, follow_redirects=True)
        resp.raise_for_status()

        posts = resp.json().get("data", {}).get("children", [])
        items: list[Item] = []
        for post in posts:
            d = post.get("data", {})
            if d.get("is_self") and not d.get("selftext"):
                continue  # skip empty self-posts
            pub = datetime.fromtimestamp(d.get("created_utc", 0), tz=timezone.utc)
            items.append(
                Item(
                    title=d.get("title", "(untitled)"),
                    url=d.get("url", f"{_BASE}{d.get('permalink', '')}"),
                    content=d.get("selftext", "") or d.get("url", ""),
                    source=f"r/{subreddit}",
                    published=pub,
                    metadata={
                        "score": d.get("score", 0),
                        "comments": d.get("num_comments", 0),
                        "permalink": f"{_BASE}{d.get('permalink', '')}",
                        "author": d.get("author", ""),
                        "flair": d.get("link_flair_text", ""),
                    },
                )
            )
        return items
