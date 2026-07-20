"""Tests for the Reddit source — mocked HTTP, no network required."""
from unittest.mock import MagicMock, patch

import pytest

from autoflow.sources.reddit import RedditSource


def _make_response(posts: list[dict]) -> MagicMock:
    mock = MagicMock()
    mock.raise_for_status = MagicMock()
    mock.json.return_value = {"data": {"children": [{"data": p} for p in posts]}}
    return mock


SAMPLE_POST = {
    "title": "New LLM beats GPT-4 on coding benchmarks",
    "url": "https://example.com/llm-news",
    "selftext": "",
    "is_self": False,
    "created_utc": 1700000000.0,
    "score": 1234,
    "num_comments": 87,
    "permalink": "/r/MachineLearning/comments/abc123/",
    "author": "user42",
    "link_flair_text": "Research",
}


@patch("autoflow.sources.reddit.net.get")
def test_returns_items(mock_get):
    mock_get.return_value = _make_response([SAMPLE_POST])
    items = RedditSource(subreddits=["MachineLearning"]).fetch()
    assert len(items) == 1
    assert items[0].title == "New LLM beats GPT-4 on coding benchmarks"
    assert items[0].source == "r/MachineLearning"
    assert items[0].metadata["score"] == 1234


@patch("autoflow.sources.reddit.net.get")
def test_limit_respected(mock_get):
    posts = [dict(SAMPLE_POST, title=f"Post {i}", url=f"https://x.com/{i}") for i in range(10)]
    mock_get.return_value = _make_response(posts)
    items = RedditSource(subreddits=["python"], limit=3).fetch()
    assert len(items) == 3


@patch("autoflow.sources.reddit.net.get")
def test_skips_empty_self_posts(mock_get):
    empty_self = dict(SAMPLE_POST, is_self=True, selftext="")
    real_post = dict(SAMPLE_POST, title="Real post", url="https://x.com/real")
    mock_get.return_value = _make_response([empty_self, real_post])
    items = RedditSource(subreddits=["python"]).fetch()
    assert len(items) == 1
    assert items[0].title == "Real post"


@patch("autoflow.sources.reddit.net.get")
def test_multiple_subreddits(mock_get):
    mock_get.return_value = _make_response([SAMPLE_POST])
    items = RedditSource(subreddits=["python", "MachineLearning"], limit=4).fetch()
    # 2 subreddits × 1 post each = 2 items (under limit of 4)
    assert len(items) == 2
    assert mock_get.call_count == 2


def test_missing_subreddits_raises():
    with pytest.raises(ValueError, match="subreddits"):
        RedditSource().fetch()
