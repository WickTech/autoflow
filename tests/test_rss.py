from pathlib import Path

from autoflow.sources.rss import RssSource

SAMPLE = str(Path(__file__).parent.parent / "examples" / "sample-feed.xml")


def test_parses_rss_items_from_file():
    items = RssSource(url=SAMPLE).fetch()
    assert len(items) == 3
    first = items[0]
    assert first.title == "New open-source LLM beats benchmarks"
    assert first.url == "https://example.com/llm-news"
    assert "language model" in first.content


def test_limit_respected():
    items = RssSource(url=SAMPLE, limit=2).fetch()
    assert len(items) == 2
