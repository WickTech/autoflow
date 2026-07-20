from pathlib import Path

import pytest

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


def test_entity_expansion_is_rejected(tmp_path):
    """Feeds are untrusted input — a 'billion laughs' bomb must not be expanded."""
    pytest.importorskip("defusedxml", reason="hardened parsing requires defusedxml")
    from defusedxml.common import EntitiesForbidden

    bomb = tmp_path / "bomb.xml"
    bomb.write_text(
        '<?xml version="1.0"?>\n'
        "<!DOCTYPE rss [\n"
        '  <!ENTITY a "aaaaaaaaaa">\n'
        '  <!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">\n'
        "]>\n"
        '<rss version="2.0"><channel><item>'
        "<title>&b;</title><link>http://x</link>"
        "</item></channel></rss>",
        encoding="utf-8",
    )
    with pytest.raises(EntitiesForbidden):
        RssSource(url=str(bomb)).fetch()
